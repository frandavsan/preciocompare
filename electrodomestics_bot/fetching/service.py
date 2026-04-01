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
from ..models import ProductResult
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
) -> dict[str, list[ProductResult]]:
    """
    Returns results for every store.

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

        all_results: dict[str, list[ProductResult]] = {}

        # Cached stores: instant DB lookup
        for adapter in cached_stores:
            all_results[adapter.name] = cache.get_query_products(conn, adapter.name, query)

        if new_stores:
            # Each store gets its own coroutine; all run concurrently via gather.
            # Per-store-query locks still prevent duplicate scrapes — each coroutine
            # acquires only its own store's lock, so stores never block each other.
            async def _fetch_one(adapter) -> tuple[str, list]:
                key = _lock_key(adapter.name, query)
                async with _query_locks[key]:
                    # Re-check cache inside the lock — another request may have filled it.
                    if use_cache and cache.has_query(conn, adapter.name, query):
                        return adapter.name, cache.get_query_products(conn, adapter.name, query)

                    live = await search_all_stores(
                        query, [adapter], detail=detail, check_shipping=check_shipping,
                        on_run=make_run_callback(query),
                    )
                    live_results = live.get(adapter.name, [])
                    found = _anomaly.check(query, {adapter.name: live_results})
                    if found:
                        asyncio.create_task(_alert_anomalies(found))

                    if use_cache:
                        # Preserve richer cached data: use DB version for existing products,
                        # live version for products not yet in the DB.
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
                        # Live mode: show fresh data, overwrite DB with latest prices.
                        final = live_results
                        if final:
                            cache.upsert_products(conn, adapter.name, final)

                    # Only record the query if it returned results — a live fetch that
                    # returns nothing may indicate a transient error and should not be
                    # cached as "searched" so it can be retried next time.
                    if final:
                        cache.record_query(conn, adapter.name, query, [r.url for r in final])

                    return adapter.name, final

            for name, results in await asyncio.gather(*[_fetch_one(a) for a in new_stores]):
                all_results[name] = results

        return {a.name: all_results.get(a.name, []) for a in ADAPTERS}
