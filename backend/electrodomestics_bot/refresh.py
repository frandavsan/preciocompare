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
from datetime import datetime, timezone

from .fetching import cache
from .fetching.adapters import ADAPTERS
from .monitoring import storage as _storage
from .monitoring.canary import run_all as _run_canaries
from .monitoring.alerts import alert_canary_failures as _alert_canary

logger = logging.getLogger(__name__)


async def refresh_all(detail: bool = False, conn=None) -> dict[str, int]:
    """
    Re-runs every known (store, query) pair and upserts all results.
    Returns {store_name: number_of_products_updated}.

    If conn is None a new DB connection is opened and closed automatically.
    Pass an existing conn to reuse a connection (caller is responsible for closing).
    """
    if cache.CACHE_DISABLED:
        logger.info("refresh_all() skipped (cache.CACHE_DISABLED=True)")
        return {}

    started_at = datetime.now(timezone.utc).isoformat()

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
    queries_attempted = 0
    queries_failed = 0
    stores_succeeded = 0

    # Group queries by store so we can report per-store totals.
    by_store: dict[str, list[str]] = defaultdict(list)
    for store, query_text in known:
        by_store[store].append(query_text)

    for store, queries in by_store.items():
        adapter = adapter_map.get(store)
        if adapter is None:
            continue  # store was removed from ADAPTERS — skip silently

        updated_urls: set[str] = set()
        store_ok = True
        for query in queries:
            queries_attempted += 1
            try:
                results = await adapter.search(query, detail=detail)
                # Full upsert: refresh always overwrites with latest live data.
                cache.upsert_products(conn, store, results)
                # Rebuild query-product links in case the result set changed.
                cache.record_query(conn, store, query, [r.url for r in results])
                updated_urls.update(r.url for r in results)
            except Exception as e:
                logger.warning("[%s] query '%s' failed: %s", store, query, e)
                queries_failed += 1
                store_ok = False

        counts[store] = len(updated_urls)
        if store_ok:
            stores_succeeded += 1

    if close_after:
        conn.close()

    try:
        _storage.record_refresh_run(
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            stores_attempted=len(by_store),
            stores_succeeded=stores_succeeded,
            total_products_updated=sum(counts.values()),
            total_queries_attempted=queries_attempted,
            total_queries_failed=queries_failed,
            details=counts,
        )
    except Exception as e:
        logger.warning("Failed to record refresh run: %s", e)

    try:
        _storage.prune_old_runs()
    except Exception as e:
        logger.warning("Failed to prune monitoring DB: %s", e)

    return counts


def main() -> None:
    if cache.CACHE_DISABLED:
        print("Cache is disabled (cache.CACHE_DISABLED=True) — nothing to refresh.")
        print("Re-enable in electrodomestics_bot/fetching/cache.py to use the daily refresh.")
        return

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

    async def _post_refresh():
        failures = await _run_canaries()
        if failures:
            print(f"{len(failures)} canary failure(s):")
            for f in failures:
                print(f"  [{f['store']}] {f['query']!r}: {f['failure_reason']} ({f['duration_ms']} ms)")
            await _alert_canary(failures)
        else:
            print("All canaries passed.")

    print("\nRunning canary checks...")
    asyncio.run(_post_refresh())
