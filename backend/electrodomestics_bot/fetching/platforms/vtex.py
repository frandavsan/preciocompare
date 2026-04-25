# INFRASTRUCTURE LAYER — VTEX Intelligent Search platform.
# New features that apply to any VTEX store belong here, not in individual adapters.
# See CLAUDE.md for the full architecture guideline.
import asyncio
from typing import Optional
from urllib.parse import quote

from ..core import http_get, http_post, matches_query
from ...models import Installment, ProductResult
from ..adapters.base import StoreAdapter


# In-process cache of (base_url, quoted_query) pairs known to trigger a VTEX redirect.
# Populated lazily on first detection; on subsequent calls the ~1.5s wasted intelligent-search
# round-trip is skipped and the legacy API is called directly.
_redirect_queries: set[tuple[str, str]] = set()


class VtexAdapter(StoreAdapter):
    """
    Base adapter for VTEX Intelligent Search stores.
    Subclasses must set `name` and `base_url`. All platform logic lives here.
    """

    # --- subclasses must override ---
    name: str
    base_url: str

    # --- subclasses may override ---
    # Any CABA (Ciudad Autónoma de Buenos Aires) postal code works — shipping APIs
    # return identical results for all CABA codes. Non-CABA codes may return zero SLAs.
    # Override in adapters for stores in other regions (e.g. Castillo uses "4000" for Tucumán).
    postal_code: str = "1425"
    verify_ssl: bool = True
    _free_shipping_override: Optional[bool] = None  # set to skip shipping simulation entirely

    @property
    def search_url(self) -> str:
        return f"{self.base_url}/_v/api/intelligent-search/product_search/?query={{}}&count=50"

    @property
    def simulation_url(self) -> str:
        return f"{self.base_url}/api/checkout/pub/orderForms/simulation"

    async def search(
        self,
        query: str,
        detail: bool = False,
        check_shipping: bool = True,
        postal_code: Optional[str] = None,
    ) -> list[ProductResult]:
        all_products = await self._fetch_all_products(quote(query))

        # Pre-filter before shipping simulations — avoids POSTing for products
        # that will be filtered out by matches_query anyway.
        products = [
            p for p in all_products
            if p.get("productName") and matches_query(p["productName"], query)
        ]

        effective_postal = postal_code or self.postal_code
        effective_override = self._free_shipping_override if check_shipping else False
        available_indices = [i for i, p in enumerate(products) if self._is_available(p)]
        if available_indices and effective_override is None:
            shipping_results = await asyncio.gather(
                *[self._check_free_shipping(products[i], effective_postal) for i in available_indices]
            )
            shipping_map = dict(zip(available_indices, shipping_results))
        elif available_indices:
            shipping_map = {i: effective_override for i in available_indices}
        else:
            shipping_map = {}

        results = []
        for i, p in enumerate(products):
            results.append(ProductResult(
                name=p.get("productName"),
                sku=p.get("productReference") or self._extract_ref(p),
                price=self._extract_price(p),
                currency="ARS",
                url=self.base_url + p.get("link", ""),
                installments=self._extract_installments(p),
                free_shipping=shipping_map.get(i, False),
                international=self._is_international(p),
                available=self._is_available(p),
            ))

        return results

    async def _fetch_all_products(self, quoted_query: str) -> list[dict]:
        """Fetches all pages of VTEX product search results (capped at 10 pages / 500 results).
        Falls back to the legacy catalog API when the intelligent search returns a redirect."""
        # Skip the intelligent search entirely for queries we already know redirect.
        if (self.base_url, quoted_query) in _redirect_queries:
            return await self._fetch_all_products_legacy(quoted_query)

        base = self.search_url.format(quoted_query)
        data = (await http_get(base, verify_ssl=self.verify_ssl)).json()
        products = data.get("products", [])

        # Intelligent search may redirect brand/model queries to category pages.
        # Cache the redirect so future calls skip the wasted round-trip.
        if not products and data.get("redirect"):
            _redirect_queries.add((self.base_url, quoted_query))
            return await self._fetch_all_products_legacy(quoted_query)

        total_pages = min(data.get("pagination", {}).get("count", 1), 10)

        if total_pages <= 1:
            return products

        extra = await asyncio.gather(*[
            self._fetch_product_page(base, page)
            for page in range(2, total_pages + 1)
        ])
        for page_products in extra:
            products.extend(page_products)

        return products

    async def _fetch_product_page(self, base_url: str, page: int) -> list[dict]:
        """Fetches one page of VTEX intelligent search results."""
        try:
            return (
                await http_get(f"{base_url}&page={page}", verify_ssl=self.verify_ssl)
            ).json().get("products", [])
        except Exception:
            return []

    async def _fetch_all_products_legacy(self, quoted_query: str) -> list[dict]:
        """Fetches all products from the VTEX legacy catalog search API (capped at 500 results).
        Used as a fallback when the intelligent search returns a redirect."""
        page_size = 50
        url_base = f"{self.base_url}/api/catalog_system/pub/products/search?ft={quoted_query}"
        first_resp = await http_get(
            f"{url_base}&_from=0&_to={page_size - 1}", verify_ssl=self.verify_ssl
        )
        products = first_resp.json()

        # Response header "resources: 0-49/100" gives the total product count.
        try:
            total = int(first_resp.headers.get("resources", "").split("/")[-1])
        except (ValueError, IndexError):
            total = len(products)
        total = min(total, 500)

        if total > page_size:
            extra = await asyncio.gather(*[
                self._fetch_legacy_page(url_base, start, start + page_size - 1)
                for start in range(page_size, total, page_size)
            ])
            for page_products in extra:
                products.extend(page_products)

        return [self._normalize_legacy_product(p) for p in products]

    async def _fetch_legacy_page(self, url_base: str, start: int, end: int) -> list[dict]:
        """Fetches one page of VTEX legacy catalog search results."""
        try:
            return (
                await http_get(f"{url_base}&_from={start}&_to={end}", verify_ssl=self.verify_ssl)
            ).json()
        except Exception:
            return []

    def _normalize_legacy_product(self, p: dict) -> dict:
        """Normalizes a legacy catalog API product to match the intelligent search format.

        Differences handled:
          - link: legacy returns a full URL; intelligent search returns a relative path.
          - productClusters: legacy is {id: name}; intelligent search is [{id, name}].
        """
        link = p.get("link", "")
        if link.startswith(self.base_url):
            link = link[len(self.base_url):]

        clusters = p.get("productClusters", {})
        if isinstance(clusters, dict):
            clusters = [{"id": k, "name": v} for k, v in clusters.items()]

        return {**p, "link": link, "productClusters": clusters}

    def _get_real_seller(self, item: dict) -> dict:
        """Returns the seller with real data, preferring sellerDefault=True with available stock."""
        sellers = item.get("sellers", [])
        for seller in sellers:
            offer = seller.get("commertialOffer", {})
            if seller.get("sellerDefault") and offer.get("AvailableQuantity", 0) > 0:
                return seller
        for seller in sellers:
            if seller.get("commertialOffer", {}).get("Price", 0) > 0:
                return seller
        return sellers[0] if sellers else {}

    def _is_international(self, product: dict) -> Optional[bool]:
        for cat in product.get("categories", []):
            if "/Compra Internacional/" in cat:
                return True
        for cluster in product.get("productClusters", []):
            if "compra internacional" in cluster.get("name", "").lower():
                return True
        return False

    def _is_available(self, product: dict) -> bool:
        """Returns True if any seller across all items has stock available."""
        for item in product.get("items", []):
            for seller in item.get("sellers", []):
                if seller.get("commertialOffer", {}).get("AvailableQuantity", 0) > 0:
                    return True
        return False

    async def _check_free_shipping(self, product: dict, postal_code: Optional[str] = None) -> bool:
        """Returns True if any home-delivery SLA has price 0 for the given postal code.
        Falls back to self.postal_code when postal_code is None."""
        try:
            items = product.get("items", [])
            if not items:
                return False
            item = items[0]
            sku_id = item.get("itemId")
            if not sku_id:
                return False
            seller_id = self._get_real_seller(item).get("sellerId", "1")
            payload = {
                "items": [{"id": sku_id, "quantity": 1, "seller": seller_id}],
                "postalCode": postal_code or self.postal_code,
                "country": "ARG",
            }
            resp = await http_post(
                self.simulation_url,
                verify_ssl=self.verify_ssl,
                json=payload,
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code != 200:
                return False
            for entry in resp.json().get("logisticsInfo", []):
                for sla in entry.get("slas", []):
                    if sla.get("deliveryChannel") == "delivery" and sla.get("price", -1) == 0:
                        return True
        except Exception:
            pass
        return False

    def _extract_price(self, product: dict) -> Optional[float]:
        """Gets the price from the real seller in the first item."""
        for item in product.get("items", []):
            seller = self._get_real_seller(item)
            price = seller.get("commertialOffer", {}).get("Price")
            if price is not None and price > 0:
                return float(price)
        return None

    def _extract_ref(self, product: dict) -> Optional[str]:
        """Fallback: extracts reference ID from items[0].referenceId."""
        for item in product.get("items", []):
            for ref in item.get("referenceId", []):
                if ref.get("Key") == "RefId":
                    return ref.get("Value")
        return None

    def _extract_installments(self, product: dict) -> list[Installment]:
        """Extracts interest-free installment options from the VTEX commertialOffer."""
        groups: dict[tuple[int, float], list[str]] = {}
        for item in product.get("items", []):
            seller = self._get_real_seller(item)
            for inst in seller.get("commertialOffer", {}).get("Installments", []):
                count = inst.get("NumberOfInstallments", 1)
                if count <= 1 or inst.get("InterestRate", 1) != 0:
                    continue
                group = inst.get("PaymentSystemGroupName", "")
                if group and group != "creditCardPaymentGroup":
                    continue
                key = (count, float(inst["Value"]))
                card = inst.get("PaymentSystemName", "")
                if key not in groups:
                    groups[key] = []
                if card and card not in groups[key]:
                    groups[key].append(card)
        return [
            Installment(count=count, amount=amount, cards=cards)
            for (count, amount), cards in sorted(groups.items())
        ]
