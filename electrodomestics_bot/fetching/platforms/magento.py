# INFRASTRUCTURE LAYER — Magento 2 + Summa Solutions installments platform.
# New features that apply to any Magento/Summa store belong here, not in individual adapters.
# See CLAUDE.md for the full architecture guideline.
import asyncio
import json
import re
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..core import http_get, matches_query
from ...models import Installment, ProductResult
from ..adapters.base import StoreAdapter

# Ordered keyword → card name map for Summa Solutions logo filename parsing.
# naranja_x must appear before naranja to avoid false matches.
DEFAULT_CARD_KEYWORDS: list[tuple[str, str]] = [
    ("naranja_x",   "NaranjaX"),
    ("naranjax",    "NaranjaX"),
    ("naranja",     "Naranja"),
    ("visa",        "Visa"),
    ("master",      "Mastercard"),
    ("cabal",       "Cabal"),
    ("american",    "American Express"),
    ("amex",        "American Express"),
    ("bna",         "BNA"),
    ("santander",   "Santander"),
    ("macro",       "Macro"),
    ("bbva",        "BBVA"),
    ("galicia",     "Galicia"),
    ("sol",         "Sol"),
    ("tuya",        "Tuya"),
]


class MagentoAdapter(StoreAdapter):
    """
    Base adapter for Magento 2 stores using the Summa Solutions installments module.
    Subclasses must set `name` and `base_url`. All platform logic lives here.
    """

    # --- subclasses must override ---
    name: str
    base_url: str

    # --- subclasses may override ---
    card_keywords: list[tuple[str, str]] = DEFAULT_CARD_KEYWORDS

    @property
    def search_result_url(self) -> str:
        return f"{self.base_url}/catalogsearch/result/index/?q={{}}&p={{}}"

    async def search(self, query: str, detail: bool = False, check_shipping: bool = True) -> list[ProductResult]:
        quoted = quote(query)
        all_items = await self._fetch_all_search_pages(quoted)
        items = [i for i in all_items if i.get("name") and matches_query(i["name"], query)]

        if detail:
            # Fetch each product page concurrently to get full card names per installment.
            detail_items = [item for item in items if item.get("url")]
            inst_results = await asyncio.gather(
                *[self._fetch_installments(item["url"]) for item in detail_items]
            )
            url_to_installments = {
                item["url"]: inst
                for item, inst in zip(detail_items, inst_results)
            }
        else:
            url_to_installments = {}

        return [
            ProductResult(
                name=item["name"],
                sku=item.get("sku"),
                price=item.get("price"),
                currency="ARS",
                url=item["url"],
                installments=(
                    url_to_installments.get(item["url"])
                    or item.get("installments", [])
                ) if detail else item.get("installments", []),
            )
            for item in items
        ]

    async def _fetch_all_search_pages(self, quoted_query: str) -> list[dict]:
        """Fetches all search result HTML pages (capped at 10 pages / ~400 results)."""
        items, total_pages = await self._fetch_search_page(quoted_query, 1)
        if not items or total_pages <= 1:
            return items

        total_pages = min(total_pages, 10)
        extra = await asyncio.gather(*[
            self._fetch_search_page(quoted_query, page)
            for page in range(2, total_pages + 1)
        ])
        for more_items, _ in extra:
            items.extend(more_items)

        return items

    async def _fetch_search_page(self, quoted_query: str, page: int) -> tuple[list[dict], int]:
        """Fetches one page of search results. Returns (items, max_page)."""
        url = self.search_result_url.format(quoted_query, page)
        try:
            resp = await http_get(url)
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            return [], 1

        items = []
        for li in soup.find_all("li", class_=lambda c: c and "product-item" in c):
            item = self._parse_search_item(li)
            if item:
                items.append(item)

        max_page = page
        for a in soup.find_all("a", href=lambda h: h and "?p=" in h):
            m = re.search(r"[?&]p=(\d+)", a.get("href", ""))
            if m:
                max_page = max(max_page, int(m.group(1)))

        return items, max_page

    def _parse_search_item(self, li) -> Optional[dict]:
        """Extracts product data from a search result <li> element."""
        url_tag = li.find("a", class_="product-item-info")
        if not url_tag:
            return None
        url = url_tag.get("href", "")
        if not url:
            return None

        # Name and SKU from ajaxWishlist mage-init data attribute
        name = sku = None
        for tag in li.find_all(attrs={"data-mage-init": True}):
            try:
                d = json.loads(tag["data-mage-init"])
                if "ajaxWishlist" in d:
                    name = d["ajaxWishlist"].get("name")
                    sku = d["ajaxWishlist"].get("sku")
                    break
            except Exception:
                pass

        if not name:
            img = li.find("img", class_="product-image-photo")
            name = img.get("alt") if img else None

        if not name:
            return None

        price = None
        price_tag = li.find(attrs={"data-price-type": "finalPrice"})
        if price_tag and price_tag.get("data-price-amount"):
            try:
                price = float(price_tag["data-price-amount"])
            except ValueError:
                pass

        installments = self._parse_search_installments(li)
        return {"name": name, "sku": sku, "price": price, "url": url, "installments": installments}

    def _parse_search_installments(self, li) -> list[Installment]:
        """Extracts interest-free installments from a search result <li> element.
        The search page shows one installment-info per product (best option, no card names).
        """
        installments = []
        for container in li.find_all(class_="installment-info"):
            count_tag = container.find(class_="installment-count")
            amount_tag = container.find(class_="installment-amount")
            text_tag = container.find(class_="installment-text")
            if not count_tag or not amount_tag or not text_tag:
                continue
            if "sin inter" not in text_tag.get_text(strip=True).lower():
                continue
            count_m = re.match(r"(\d+)", count_tag.get_text(strip=True))
            if not count_m:
                continue
            count = int(count_m.group(1))
            if count <= 1:
                continue
            amount_clean = (
                amount_tag.get_text(strip=True)
                .replace("$", "").replace(".", "").replace(",", ".").strip()
            )
            try:
                amount = float(amount_clean)
            except ValueError:
                continue
            installments.append(Installment(count=count, amount=amount, cards=[]))
        return installments

    async def _fetch_installments(self, product_url: str) -> list[Installment]:
        """Fetches the product page and scrapes interest-free installment options."""
        try:
            resp = await http_get(product_url)
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            return []

        installments = []
        for container in soup.find_all("div", class_=lambda c: c and "payment-info" in c and "pdp_logo" in c):
            count_tag = container.find(class_="installment-count")
            amount_tag = container.find(class_="installment-amount")
            text_tag = container.find(class_="installment-text")
            if not count_tag or not amount_tag or not text_tag:
                continue

            if "sin inter" not in text_tag.get_text(strip=True).lower():
                continue

            count_m = re.match(r"(\d+)", count_tag.get_text(strip=True))
            if not count_m:
                continue
            count = int(count_m.group(1))

            amount_clean = (
                amount_tag.get_text(strip=True)
                .replace("$", "").replace(".", "").replace(",", ".").strip()
            )
            try:
                amount = float(amount_clean)
            except ValueError:
                continue

            image_div = container.find(class_="payment-info-image")
            cards = self._cards_from_image_div(image_div) if image_div else []

            if count <= 1:
                continue
            installments.append(Installment(count=count, amount=amount, cards=cards))

        return installments

    def _cards_from_image_div(self, image_div) -> list[str]:
        """Parses card names from logo <img> srcs inside a payment-info-image div."""
        seen: set[str] = set()
        cards: list[str] = []
        for img in image_div.find_all("img"):
            fname = img.get("src", "").split("/")[-1].lower()
            for keyword, card_name in self.card_keywords:
                if keyword in fname and card_name not in seen:
                    seen.add(card_name)
                    cards.append(card_name)
                    break
        return cards
