# STORE LAYER — Montes Hermanos (monteshermanos.com.ar)
# Bespoke PHP/jQuery site; no platform counterpart. All logic lives here.
# See CLAUDE.md for the full architecture guideline.
import re
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..core import http_get, matches_query
from ...models import Installment, ProductResult
from .base import StoreAdapter

_SKU_RE = re.compile(r"f-(\d+)-")
_PRICE_RE = re.compile(r"[\d.,]+")

# Fixed sin-interés tiers shown site-wide (search bot only — pricing tool fetches real plans).
_FIXED_CARDS_3X = ["Mastercard", "Visa"]
_FIXED_CARDS_6X = ["Naranja"]


class MontesHermanosAdapter(StoreAdapter):
    """
    Adapter for Montes Hermanos — a regional electronics store in Tartagal, Salta.
    Custom PHP/jQuery site; no pagination; pure HTML scraping.

    Search: GET /busqueda/?keyword={query}
    Price: actual selling price from <p class="item-price-destacado">…</p>.
           The <p class="item-price"><strike>…</strike></p> is the before/list price
           (higher, struck-through) and must NOT be used — it inflates monto_ingresado
           sent to the installment endpoint.
    Installments: fixed site-wide tiers hardcoded here (not fetched from any API):
      - 1x at price * 0.8 (contado/cash, always 20% off selling price)
      - 3x sin interés: Visa, Mastercard  (amount = price / 3)
      - 6x sin interés: Naranja           (amount = price / 6)
    Free shipping: not offered — always False.
    International: concept doesn't apply — always None.
    Availability: always True (site only surfaces in-stock products).
    """

    name = "monteshermanos"
    base_url = "https://www.monteshermanos.com.ar"

    async def search(self, query: str, detail: bool = False, check_shipping: bool = True) -> list[ProductResult]:
        url = f"{self.base_url}/busqueda/?keyword={quote(query)}"
        resp = await http_get(url)
        soup = BeautifulSoup(resp.text, "lxml")

        results = []
        for anchor in soup.select("a[href*='/producto/']"):
            product = self._parse_item(anchor, query)
            if product:
                results.append(product)

        return results

    def _parse_item(self, anchor, query: str) -> Optional[ProductResult]:
        name_tag = anchor.select_one("h4.nombre")
        if not name_tag:
            return None
        name = name_tag.get_text(strip=True)
        if not name or not matches_query(name, query):
            return None

        href = anchor.get("href", "")
        url = href if href.startswith("http") else self.base_url + href

        price = self._extract_price(anchor)
        sku = self._extract_sku(anchor)

        return ProductResult(
            name=name,
            sku=sku,
            price=price,
            currency="ARS",
            url=url,
            installments=self._build_installments(price),
            free_shipping=False,
            international=None,
            available=True,
        )

    @staticmethod
    def _extract_price(anchor) -> Optional[float]:
        # item-price-destacado = actual selling price (what customers pay)
        # item-price strike    = before/reference price (struck-through, higher) — do not use
        tag = anchor.select_one("p.item-price-destacado")
        if not tag:
            return None
        raw = tag.get_text(strip=True)
        m = _PRICE_RE.search(raw.replace(".", "").replace(",", "."))
        return float(m.group()) if m else None

    @staticmethod
    def _extract_sku(anchor) -> Optional[str]:
        img = anchor.select_one("img")
        if not img:
            return None
        src = img.get("src", "")
        m = _SKU_RE.search(src)
        return m.group(1) if m else None

    @staticmethod
    def _build_installments(price: Optional[float]) -> list[Installment]:
        if not price:
            return []
        return [
            Installment(count=1, amount=round(price * 0.8, 2), cards=[]),
            Installment(count=3, amount=round(price / 3, 2), cards=list(_FIXED_CARDS_3X)),
            Installment(count=6, amount=round(price / 6, 2), cards=list(_FIXED_CARDS_6X)),
        ]
