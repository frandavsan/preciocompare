"""
Refresh module — re-fetches every previously searched query and updates all
cached products with fresh data (prices, availability, installments).

New products discovered during a refresh are added to the DB automatically.
Products that no longer appear in a query's results are left in the DB as-is
(their data simply won't be refreshed until they resurface in a query).

Run directly:
    python refresh.py
    python refresh.py --detail      # also fetches card names per installment (slower)

Schedule on Windows (run once at setup, fires daily at 11:00 UTC):
    schtasks /create ^
        /tn "ElectrodomesticsBot Refresh" ^
        /tr "python C:\\full\\path\\to\\ElectrodomesticsBot\\refresh.py" ^
        /sc daily /st 11:00 /f
"""
import asyncio
import logging
import sys
import time
from collections import defaultdict

from .fetching import cache
from .fetching.adapters import ADAPTERS

logger = logging.getLogger(__name__)


async def refresh_all(detail: bool = False, conn=None) -> dict[str, int]:
    """
    Re-runs every known (store, query) pair and upserts all results.
    Returns {store_name: number_of_products_updated}.

    If conn is None a new DB connection is opened and closed automatically.
    Pass an existing conn to reuse a connection (caller is responsible for closing).
    """
    close_after = conn is None
    if conn is None:
        conn = cache.open_db()

    known = cache.all_known_queries(conn)
    if not known:
        if close_after:
            conn.close()
        return {}

    adapter_map = {a.name: a for a in ADAPTERS}
    counts: dict[str, int] = {}

    # Group queries by store so we can report per-store totals.
    by_store: dict[str, list[str]] = defaultdict(list)
    for store, query_text in known:
        by_store[store].append(query_text)

    for store, queries in by_store.items():
        adapter = adapter_map.get(store)
        if adapter is None:
            continue  # store was removed from ADAPTERS — skip silently

        updated_urls: set[str] = set()
        for query in queries:
            try:
                results = await adapter.search(query, detail=detail)
                # Full upsert: refresh always overwrites with latest live data.
                cache.upsert_products(conn, store, results)
                # Rebuild query-product links in case the result set changed.
                cache.record_query(conn, store, query, [r.url for r in results])
                updated_urls.update(r.url for r in results)
            except Exception as e:
                logger.warning("[%s] query '%s' failed: %s", store, query, e)

        counts[store] = len(updated_urls)

    if close_after:
        conn.close()

    return counts


def main() -> None:
    detail = "--detail" in sys.argv

    conn = cache.open_db()
    known = cache.all_known_queries(conn)

    if not known:
        print("Nothing to refresh — no queries have been searched yet.")
        print("Run the program and search for something first.")
        conn.close()
        return

    stores = sorted({store for store, _ in known})
    print(
        f"Refreshing {len(known)} known quer{'y' if len(known) == 1 else 'ies'} "
        f"across {len(stores)} store(s)"
        f"{' (detail mode)' if detail else ''}..."
    )

    start = time.monotonic()
    counts = asyncio.run(refresh_all(detail=detail, conn=conn))
    elapsed = time.monotonic() - start

    for store, n in counts.items():
        print(f"  {store}: {n} products refreshed")
    print(f"Done in {elapsed:.1f}s")
    conn.close()
