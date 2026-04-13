"""
Pricing service — orchestrates search, plan extraction, and Excel output.

Workflow:
1. Search all pricing stores in parallel (reuses fetching adapters)
2. Pick best match per store
3. Fetch all payment plans per platform (VTEX: re-fetch raw API, Magento: scrape product page)
4. Return PricingResult per store, ready for Excel writing
"""

from __future__ import annotations

from urllib.parse import quote

from ..fetching.core import http_get, search_all_stores
from ..fetching.adapters import ADAPTERS
from ..models import ProductResult
from .adapters import PRICING_STORES, PricingStore
from .models import PaymentPlan, PricingResult
from .platforms.vtex import extract_all_plans as vtex_extract_all_plans
from .platforms.magento import fetch_all_plans as magento_fetch_all_plans
from .platforms.monteshermanos import fetch_all_plans as montes_fetch_all_plans


def _find_adapter(store_name: str):
    """Find the fetching adapter matching a pricing store by name."""
    for adapter in ADAPTERS:
        if adapter.name == store_name:
            return adapter
    return None


async def search_pricing_stores(
    query: str,
) -> dict[str, tuple[PricingStore, list[ProductResult]]]:
    """
    Search all pricing stores and return (store_config, matched_products) per store.

    Reuses the existing search pipeline — no shipping simulation, no detail mode.
    """
    adapters_to_search = []
    store_map: dict[str, PricingStore] = {}
    for ps in PRICING_STORES:
        adapter = _find_adapter(ps.name)
        if adapter:
            adapters_to_search.append(adapter)
            store_map[ps.name] = ps

    if not adapters_to_search:
        return {}

    results = await search_all_stores(
        query, adapters_to_search, detail=False, check_shipping=False,
    )

    out: dict[str, tuple[PricingStore, list[ProductResult]]] = {}
    for name, ssr in results.items():
        if name in store_map:
            out[name] = (store_map[name], ssr.products)
    return out


async def fetch_plans_for_product(
    store: PricingStore,
    product: ProductResult,
) -> PricingResult:
    """Fetch all payment plans for a single matched product from a store."""
    if not product.price or product.price <= 0:
        return PricingResult(
            store_name=store.name,
            product_name=product.name,
            product_url=product.url,
            base_price=0,
            status="error",
            error_detail="No price available",
        )

    try:
        if store.platform == "vtex":
            plans = await _fetch_vtex_plans(store, product)
        elif store.platform == "magento":
            plans = await magento_fetch_all_plans(product.url, product.price)
        elif store.platform == "monteshermanos":
            plans = await montes_fetch_all_plans(product.url, product.price)
        else:
            plans = []

        return PricingResult(
            store_name=store.name,
            product_name=product.name,
            product_url=product.url,
            base_price=product.price,
            plans=plans,
            status="ok" if plans else "no_plans",
        )
    except Exception as e:
        return PricingResult(
            store_name=store.name,
            product_name=product.name,
            product_url=product.url,
            base_price=product.price or 0,
            status="error",
            error_detail=f"{type(e).__name__}: {e}",
        )


async def _fetch_vtex_plans(
    store: PricingStore,
    product: ProductResult,
) -> list[PaymentPlan]:
    """
    Re-fetch a VTEX product's raw API data to extract all installment plans.

    The search pipeline converts raw VTEX dicts to ProductResult, losing the
    commertialOffer.Installments[] data. We search again by SKU (narrow query)
    and match by URL to recover the raw dict for plan extraction.
    """
    sku_query = product.sku or product.name
    url = (
        f"{store.base_url}/_v/api/intelligent-search/product_search/"
        f"?query={quote(sku_query)}&count=10"
    )
    resp = await http_get(url, verify_ssl=store.verify_ssl)
    data = resp.json()

    # Match by link path — product.url = base_url + link
    product_link = product.url.removeprefix(store.base_url)
    products = data.get("products", [])

    for raw_product in products:
        if raw_product.get("link") == product_link:
            return vtex_extract_all_plans(raw_product, product.price)

    return []
