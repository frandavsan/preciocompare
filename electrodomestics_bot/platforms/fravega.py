# INFRASTRUCTURE LAYER — Fravega custom Next.js + Apollo GraphQL platform.
# New features that apply to any Fravega-style store belong here, not in individual adapters.
# See CLAUDE.md for the full architecture guideline.
import asyncio
import logging
import math
import re
import time
from typing import Optional

from curl_cffi.requests import AsyncSession

from ..core import matches_query
from ..models import Installment, ProductResult
from ..adapters.base import StoreAdapter

_session = AsyncSession(impersonate="chrome120")

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50
_MAX_PAGES = 10
_INSTALL_RE = re.compile(r"(\d+)\s+cuotas?\s+sin\s+inter", re.IGNORECASE)

# Maximum number of matched products for which shipping GQL checks are fired.
# Broad queries (e.g. "PS5") can return hundreds of matches; even with full concurrency
# the wall time is bounded by the slowest single GQL call (~27s for 365 products).
# Queries that return more than this threshold will show free_shipping=False for all results.
_MAX_SHIPPING_CHECKS = 100

# ---------------------------------------------------------------------------
# Per-SKU shipping result cache
# ---------------------------------------------------------------------------
# V1 LAUNCH INSTRUCTION: set _SHIPPING_CACHE_ENABLED = True before going live.
# This eliminates the ~27s Fravega shipping wall-time on repeated queries by
# returning cached results for SKU+seller+postal combinations seen before.
# Each entry expires after _SHIPPING_CACHE_TTL_SECONDS (default: 24 h).
#
# Left False during development/testing so that live shipping data is always
# fetched and the cache does not mask bugs or stale results.
_SHIPPING_CACHE_ENABLED = False
_SHIPPING_CACHE_TTL_SECONDS = 86_400  # 24 hours
_shipping_cache: dict[tuple[str, str, str], tuple[bool, float]] = {}  # (sku, seller_id, postal_code) -> (result, timestamp)


class FravegaAdapter(StoreAdapter):
    """
    Base adapter for Fravega's custom Next.js + Apollo GraphQL platform.
    Subclasses must set `name` and `base_url`. All platform logic lives here.

    Search endpoint: POST /api/v1/rest/search (GraphQL, no build hash in URL).
    Pagination: offset-based, 50 results/page, capped at 10 pages (500 results).
    Installments fast: count parsed from label text; amount = price / count.
    Installments detail: plans(sku) query per product; networks shown at their generic base count,
      issuers (e.g. BNA) shown only when they offer a higher count than the generic network.
    Free shipping: calculateDeliveryTermAndCost GQL query per product; cost == 0 means free.
    Availability: always True — the API already filters to listable products.
    International: detected via sellerCondition == ["international_seller"] in the search response.
    """

    name: str
    base_url: str
    verify_ssl: bool = True
    postal_code: str = "1425"

    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}/api/v1/rest/search"

    async def search(self, query: str, detail: bool = False) -> list[ProductResult]:
        raw = await self._fetch_all_products(query)
        results = []
        shipping_tasks = []  # list of (result_index, sku, seller_id)
        detail_tasks = []    # list of (result_index, sku)

        for item in raw:
            name = item.get("title", "")
            if not name or not matches_query(name, query):
                continue

            slug = item.get("slug", "")
            price = self._extract_price(item)
            sku_code = self._extract_sku(item)
            seller_id = self._extract_seller_id(item)
            installments = self._extract_installments_fast(item, price)

            pr = ProductResult(
                name=name,
                sku=sku_code,
                price=price,
                currency="ARS",
                url=f"{self.base_url}/p/{slug}-{sku_code}" if sku_code else f"{self.base_url}/p/{slug}",
                installments=installments,
                free_shipping=False,  # resolved below via shipping API
                international=self._extract_international(item),
                available=True,
            )
            results.append(pr)

            idx = len(results) - 1
            if sku_code and seller_id:
                shipping_tasks.append((idx, sku_code, seller_id))
            if detail and sku_code:
                detail_tasks.append((idx, sku_code))

        if shipping_tasks:
            if len(shipping_tasks) > _MAX_SHIPPING_CHECKS:
                logger.debug(
                    "[fravega] %d shipping tasks exceed threshold (%d); skipping shipping checks",
                    len(shipping_tasks), _MAX_SHIPPING_CHECKS,
                )
            else:
                shipping_results = await asyncio.gather(*[
                    self._fetch_free_shipping(sku, seller_id)
                    for _, sku, seller_id in shipping_tasks
                ])
                for (idx, _, _), is_free in zip(shipping_tasks, shipping_results):
                    results[idx].free_shipping = is_free

        if detail_tasks:
            plans_list = await asyncio.gather(*[
                self._fetch_plans(sku) for _, sku in detail_tasks
            ])
            for (idx, _), plans in zip(detail_tasks, plans_list):
                if plans:
                    price = results[idx].price
                    if price:
                        for inst in plans:
                            inst.amount = round(price / inst.count, 2)
                    results[idx].installments = plans

        return results

    async def _fetch_all_products(self, query: str) -> list[dict]:
        """Fetches all pages of results (capped at _MAX_PAGES * _PAGE_SIZE results)."""
        escaped = query.replace('"', '\\"')
        data = await self._post_search(escaped, offset=0)
        items_data = data.get("data", {}).get("items") or {}
        total = items_data.get("total", 0)
        results = list(items_data.get("results") or [])

        total_pages = min(math.ceil(total / _PAGE_SIZE), _MAX_PAGES) if total > 0 else 1
        if total_pages > 1:
            extra = await asyncio.gather(*[
                self._fetch_page(escaped, page)
                for page in range(1, total_pages)
            ])
            for page_items in extra:
                results.extend(page_items)

        return results

    async def _fetch_page(self, escaped_query: str, page: int) -> list[dict]:
        """Fetches one additional page (page index ≥ 1, offset = page * _PAGE_SIZE)."""
        try:
            data = await self._post_search(escaped_query, offset=page * _PAGE_SIZE)
            return data.get("data", {}).get("items", {}).get("results") or []
        except Exception as e:
            logger.warning("[fravega] page %d failed: %s", page, e)
            return []

    async def _post_gql(self, gql: str) -> dict:
        """Posts a GraphQL query to the Fravega endpoint with one retry on transient failure."""
        for attempt in range(2):
            try:
                resp = await _session.post(self._endpoint, json={"query": gql}, verify=self.verify_ssl)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(2)
                else:
                    raise

    async def _post_search(self, escaped_query: str, offset: int) -> dict:
        gql = (
            "{ items(filtering: {"
            f'  keywords: {{ query: "{escaped_query}" }},'
            "  active: true,"
            '  salesChannels: ["fravega-ecommerce"],'
            "  availableStock: { includeThoseWithNoAvailableStockButListable: true }"
            "}) {"
            "  total"
            "  results("
            f"    buckets: [{{ offset: {offset}, sorting: TOTAL_SALES_IN_LAST_30_DAYS, customSorted: false }}],"
            f"    size: {_PAGE_SIZE}"
            "  ) {"
            "    title slug sellerCondition"
            "    installments { values { name } }"
            '    skus { results { code pricing(channel: "fravega-ecommerce") { salePrice } } }'
            "    sellers { id }"
            "  }"
            "} }"
        )
        return await self._post_gql(gql)

    async def _fetch_free_shipping(self, sku: str, seller_id: str) -> bool:
        """Returns True if home delivery is free for this SKU+seller at the configured postal code."""
        if _SHIPPING_CACHE_ENABLED:
            cache_key = (sku, seller_id, self.postal_code)
            entry = _shipping_cache.get(cache_key)
            if entry is not None:
                result, ts = entry
                if time.time() - ts < _SHIPPING_CACHE_TTL_SECONDS:
                    return result

        gql = (
            f'{{ calculateDeliveryTermAndCost(sku: "{sku}", seller: "{seller_id}", postalCode: "{self.postal_code}") {{'
            "  cost"
            "} }"
        )
        try:
            data = (await self._post_gql(gql)).get("data", {}).get("calculateDeliveryTermAndCost") or {}
            result = data.get("cost") == 0
        except Exception as e:
            logger.warning("[fravega] shipping check failed for sku %s: %s", sku, e)
            result = False

        if _SHIPPING_CACHE_ENABLED:
            _shipping_cache[(sku, seller_id, self.postal_code)] = (result, time.time())

        return result

    async def _fetch_plans(self, sku: str) -> list[Installment]:
        """Fetches all payment plans for a SKU and returns interest-free installments with card names."""
        gql = (
            f'{{ plans(sku: "{sku}") {{'
            "  system { name }"
            "  issuer { name }"
            "  installments { quantity hasInterest }"
            "} }"
        )
        try:
            plans = (await self._post_gql(gql)).get("data", {}).get("plans") or []
            return self._parse_plans(plans)
        except Exception as e:
            logger.warning("[fravega] plans fetch failed for sku %s: %s", sku, e)
            return []

    @staticmethod
    def _parse_plans(plans: list[dict]) -> list[Installment]:
        """
        Mirrors how Fravega's website groups interest-free installment options:

        - Card networks (Visa, Mastercard, etc.) are shown at their "base" count —
          the max sin-interés count from generic no-issuer rows of that network.
        - An issuer (e.g. "Banco Nación") is shown at its own max count only when
          that count *exceeds* the base count of every network it appears under,
          meaning the issuer is the one offering an exclusive better deal.

        Example: Visa generic → 6x (shown as Visa at 6x).
                 Visa + BNA → 12x (shown as BNA at 12x, because 12 > 6).
                 Visa + BBVA → 6x (not shown separately, already covered by Visa at 6x).

        Amount is set to 0.0; caller sets price / count after receiving the list.
        """
        system_base: dict[str, int] = {}  # system → max count for no-issuer rows
        issuer_systems: dict[str, set] = {}  # issuer → set of systems it appears under
        issuer_max: dict[str, int] = {}  # issuer → max sin-interés count

        for plan in plans:
            system_name = (plan.get("system") or {}).get("name", "").strip()
            issuer_name = (plan.get("issuer") or {}).get("name", "").strip()
            inst = plan.get("installments") or {}
            if inst.get("hasInterest") or inst.get("quantity", 1) <= 1:
                continue
            count = inst["quantity"]
            if not system_name:
                continue

            if not issuer_name:
                if count > system_base.get(system_name, 0):
                    system_base[system_name] = count
            else:
                issuer_systems.setdefault(issuer_name, set()).add(system_name)
                if count > issuer_max.get(issuer_name, 0):
                    issuer_max[issuer_name] = count

        groups: dict[int, list[str]] = {}
        for system, count in system_base.items():
            groups.setdefault(count, []).append(system)
        for issuer, count in issuer_max.items():
            max_base = max((system_base.get(s, 0) for s in issuer_systems[issuer]), default=0)
            if count > max_base:
                groups.setdefault(count, []).append(issuer)

        return [
            Installment(count=count, amount=0.0, cards=sorted(cards))
            for count, cards in sorted(groups.items(), reverse=True)
        ]

    @staticmethod
    def _extract_price(item: dict) -> Optional[float]:
        try:
            return float(item["skus"]["results"][0]["pricing"][0]["salePrice"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    @staticmethod
    def _extract_sku(item: dict) -> Optional[str]:
        try:
            return item["skus"]["results"][0]["code"]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _extract_international(item: dict) -> bool:
        return "international_seller" in (item.get("sellerCondition") or [])

    @staticmethod
    def _extract_seller_id(item: dict) -> Optional[str]:
        try:
            return item["sellers"][0]["id"]
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _extract_installments_fast(item: dict, price: Optional[float]) -> list[Installment]:
        """
        Extracts installment count from the search-result label (e.g. '12 cuotas sin interés').
        Amount is computed as price / count. No card names available in fast mode.
        """
        values = (item.get("installments") or {}).get("values") or []
        result = []
        for v in values:
            m = _INSTALL_RE.search(v.get("name", ""))
            if m:
                count = int(m.group(1))
                amount = round(price / count, 2) if price else 0.0
                result.append(Installment(count=count, amount=amount, cards=[]))
        return result
