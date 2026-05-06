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
from .card_mapping import normalize_card_name
from .models import PaymentPlan, PricingResult
from .platforms.vtex import extract_all_plans as vtex_extract_all_plans
from .platforms.magento import fetch_all_plans as magento_fetch_all_plans
from .platforms.monteshermanos import fetch_all_plans as montes_fetch_all_plans
from .platforms.fravega import fetch_all_plans as fravega_fetch_all_plans
from .platforms.megatone import fetch_all_plans as megatone_fetch_all_plans


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
        elif store.platform == "fravega":
            plans = await fravega_fetch_all_plans(product.sku or "", product.price)
        elif store.platform == "megatone":
            plans = await megatone_fetch_all_plans(product.sku or "", product.price)
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

    extra_issuers = _STORE_EXTRA_ISSUERS.get(store.name)
    mp_sin_tiers = _STORE_MP_SIN_TIERS.get(store.name)
    for raw_product in products:
        if raw_product.get("link") == product_link:
            plans = vtex_extract_all_plans(raw_product, product.price, extra_issuers)
            if mp_sin_tiers:
                plans = _fill_mp_sin_tiers(plans, product.price, mp_sin_tiers)
            return plans

    return []


def _fill_mp_sin_tiers(
    plans: list[PaymentPlan],
    price: float,
    tiers: list[int],
) -> list[PaymentPlan]:
    """
    Synthesize MercadoPago sin-interés plans for installment counts missing from
    the API response.

    VTEX stores often omit multi-installment MP plans from commertialOffer even
    though the website shows them. We synthesize them as 0% interest plans
    (amount = price / count) for any count in tiers not already present.
    """
    existing = {
        p.installment_count
        for p in plans
        if normalize_card_name(p.card_system) == "mercadopago" and not p.has_interest
    }
    synthetic = [
        PaymentPlan(
            card_system="Mercado Pago",
            card_issuer=None,
            installment_count=count,
            has_interest=False,
            interest_rate=0.0,
            amount_per_installment=round(price / count, 2),
        )
        for count in tiers
        if count not in existing
    ]
    return plans + synthetic


# MercadoPago sin-interés tiers to synthesize when the VTEX API omits them.
# VTEX commertialOffer often doesn't include multi-installment MP plans even
# though the store's checkout shows them. List the counts to fill in per store.
_STORE_MP_SIN_TIERS: dict[str, list[int]] = {
    "oncity": [3, 6, 9, 12],
}

# Store-wide bank eligibility sets for VTEX stores that don't use productClusters
# to signal per-product bank eligibility. Derived from each store's own routing
# JSON (e.g. Castillo's /files/especific-cuotes-plp.json).
_STORE_EXTRA_ISSUERS: dict[str, set[str]] = {
    "castillo": {
        "macro", "nacion", "galicia", "santander", "bbva", "hipotecario",
        "credicoop", "cordoba", "ciudad", "supervielle", "patagonia",
        "icbc", "itau", "hsbc", "comafi",
    },
    "cetrogar": {"nacion", "hipotecario"},
}
