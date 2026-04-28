"""
Service layer — core search logic used by both CLI and API.
"""
import asyncio
import logging
from collections import defaultdict
from contextlib import contextmanager
from typing import Optional

from . import cache
from .adapters import ADAPTERS
from .core import search_all_stores
from dataclasses import replace

from ..models import ProductResult, StoreSearchResult
from ..monitoring import anomaly as _anomaly
from ..monitoring.alerts import alert_anomalies as _alert_anomalies
from ..monitoring.collector import make_run_callback

logger = logging.getLogger(__name__)

# Per-(store, query, postal_code) locks to prevent duplicate concurrent scrapes.
# Postal is part of the key because different postal codes produce different
# shipping results; without it, concurrent requests for the same query but
# different postals would serialize behind one another.
_query_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _lock_key(store: str, query: str, postal_code: Optional[str]) -> str:
    return f"{store}:{query.strip().lower()}:{postal_code or ''}"


@contextmanager
def _db():
    if cache.CACHE_DISABLED:
        # No connection is opened or migrated; consumers must guard cache calls
        # behind effective_use_cache / bypass_cache_for_custom_postal so they
        # never dereference this None.
        yield None
        return
    conn = cache.open_db()
    try:
        yield conn
    finally:
        conn.close()


async def search_products(
    query: str,
    detail: bool = False,
    use_cache: bool = True,
    check_shipping: bool = True,
    postal_code: Optional[str] = None,
) -> dict[str, StoreSearchResult]:
    """
    Returns a StoreSearchResult for every store, carrying both products and status.

    use_cache=True (default for API): serve from DB for known queries; live fetch + insert for new ones.
    use_cache=False (default for CLI): always fetch live, upsert fresh data to DB.

    When postal_code is provided (any value, including one that matches an adapter
    default), the cache is bypassed and results are not written to DB — shipping data
    is postal-specific and caching custom codes would either pollute the CABA-default
    cache or require a separate cache layer. Callers that want cached CABA behavior
    must omit postal_code entirely.

    Note: while cache.CACHE_DISABLED is True, every call behaves as a cache-bypass
    request regardless of use_cache or postal_code — see cache.py for the rationale.

    Concurrent requests for the same (store, query, postal_code) are serialized via
    per-key asyncio locks — the second waiter re-checks cache inside the lock and
    skips the live fetch if the first request already populated it. Different postal
    codes for the same query do not block each other.
    """
    # Custom postal codes bypass the cache entirely: the cache stores free_shipping
    # per product, computed with each adapter's default postal. Serving a non-default
    # postal from cache would return stale CABA shipping data; writing a non-default
    # postal to cache would pollute future default-postal queries.
    # cache.CACHE_DISABLED forces the same bypass for *every* request — see cache.py.
    bypass_cache_for_custom_postal = postal_code is not None or cache.CACHE_DISABLED
    effective_use_cache = use_cache and not bypass_cache_for_custom_postal

    with _db() as conn:
        if effective_use_cache:
            cached_stores = [a for a in ADAPTERS if cache.has_query(conn, a.name, query)]
            new_stores    = [a for a in ADAPTERS if a not in cached_stores]
        else:
            cached_stores = []
            new_stores = list(ADAPTERS)

        all_results: dict[str, StoreSearchResult] = {}

        for adapter in cached_stores:
            products = cache.get_query_products(conn, adapter.name, query)
            all_results[adapter.name] = StoreSearchResult(products=products, status="ok")

        if new_stores:
            async def _fetch_one(adapter) -> tuple[str, StoreSearchResult]:
                key = _lock_key(adapter.name, query, postal_code)
                async with _query_locks[key]:
                    # Re-check cache inside the lock — another request may have filled it.
                    if effective_use_cache and cache.has_query(conn, adapter.name, query):
                        products = cache.get_query_products(conn, adapter.name, query)
                        return adapter.name, StoreSearchResult(products=products, status="ok")

                    live = await search_all_stores(
                        query, [adapter], detail=detail, check_shipping=check_shipping,
                        postal_code=postal_code,
                        on_run=make_run_callback(query),
                    )
                    ssr = live.get(adapter.name, StoreSearchResult())
                    live_results = ssr.products

                    found = _anomaly.check(query, {adapter.name: live_results})
                    if found:
                        asyncio.create_task(_alert_anomalies(found))

                    if bypass_cache_for_custom_postal:
                        final = live_results
                    elif use_cache:
                        final: list = []
                        new_products: list = []
                        for r in live_results:
                            existing = cache.get_product_by_url(conn, adapter.name, r.url)
                            if existing is not None:
                                final.append(existing)
                            else:
                                final.append(r)
                                new_products.append(r)
                        if new_products:
                            cache.insert_new_products(conn, adapter.name, new_products)
                    else:
                        final = live_results
                        if final:
                            cache.upsert_products(conn, adapter.name, final)

                    if final and not bypass_cache_for_custom_postal:
                        cache.record_query(conn, adapter.name, query, [r.url for r in final])

                    return adapter.name, replace(ssr, products=final)

            for name, ssr in await asyncio.gather(*[_fetch_one(a) for a in new_stores]):
                all_results[name] = ssr

        return {a.name: all_results.get(a.name, StoreSearchResult()) for a in ADAPTERS}
