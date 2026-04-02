"""
Service layer — core search logic used by both CLI and API.
"""
import asyncio
import logging
from collections import defaultdict
from contextlib import contextmanager

from . import cache
from .adapters import ADAPTERS
from .core import search_all_stores
from dataclasses import replace

from ..models import ProductResult, StoreSearchResult
from ..monitoring import anomaly as _anomaly
from ..monitoring.alerts import alert_anomalies as _alert_anomalies
from ..monitoring.collector import make_run_callback

logger = logging.getLogger(__name__)

# Per-(store, query) locks to prevent duplicate concurrent scrapes.
_query_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _lock_key(store: str, query: str) -> str:
    return f"{store}:{query.strip().lower()}"


@contextmanager
def _db():
    conn = cache.open_db()
    try:
        yield conn
    finally:
        conn.close()


async def search_products(
    query: str, detail: bool = False, use_cache: bool = True, check_shipping: bool = True
) -> dict[str, StoreSearchResult]:
    """
    Returns a StoreSearchResult for every store, carrying both products and status.

    use_cache=True (default for API): serve from DB for known queries; live fetch + insert for new ones.
    use_cache=False (default for CLI): always fetch live, upsert fresh data to DB.

    Concurrent requests for the same (store, query) are serialized via per-key
    asyncio locks — the second waiter re-checks cache inside the lock and skips
    the live fetch if the first request already populated it.
    """
    with _db() as conn:
        if use_cache:
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
                key = _lock_key(adapter.name, query)
                async with _query_locks[key]:
                    # Re-check cache inside the lock — another request may have filled it.
                    if use_cache and cache.has_query(conn, adapter.name, query):
                        products = cache.get_query_products(conn, adapter.name, query)
                        return adapter.name, StoreSearchResult(products=products, status="ok")

                    live = await search_all_stores(
                        query, [adapter], detail=detail, check_shipping=check_shipping,
                        on_run=make_run_callback(query),
                    )
                    ssr = live.get(adapter.name, StoreSearchResult())
                    live_results = ssr.products

                    found = _anomaly.check(query, {adapter.name: live_results})
                    if found:
                        asyncio.create_task(_alert_anomalies(found))

                    if use_cache:
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

                    if final:
                        cache.record_query(conn, adapter.name, query, [r.url for r in final])

                    return adapter.name, replace(ssr, products=final)

            for name, ssr in await asyncio.gather(*[_fetch_one(a) for a in new_stores]):
                all_results[name] = ssr

        return {a.name: all_results.get(a.name, StoreSearchResult()) for a in ADAPTERS}
