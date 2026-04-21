"""
Canary health checks — runs known-good queries against each store to verify
end-to-end search is working. Results are stored in the canary_runs table
and failures are dispatched via Telegram.

Adapters are shallow-copied before use so canary runs never mutate the shared
adapter state (e.g. postal_code, _free_shipping_override) that normal searches
depend on.

Run standalone:
    python -m electrodomestics_bot.monitoring.canary

Public API:
    CANARY_CHECKS: list[tuple[str, str, int]]
        (store_name, query, expected_min_results) — what to check.

    async run_all(adapters=None) -> list[dict]
        Runs all canary checks concurrently.
        Returns a list of failure dicts; empty list means all checks passed.
        Each failure dict: {store, query, expected_min, actual_count,
                            duration_ms, failure_reason}
"""

import asyncio
import copy
import logging
import sys
import time
from typing import Optional

from ..fetching.core import search_all_stores
from . import storage

logger = logging.getLogger(__name__)

# (store_name, query, expected_min_results)
# Queries are intentionally broad to return stable results regardless of stock.
CANARY_CHECKS: list[tuple[str, str, int]] = [
    ("castillo",        "samsung", 3),
    ("cetrogar",        "samsung", 3),
    ("fravega",         "samsung", 5),
    ("megatone",        "samsung", 3),
    ("monteshermanos",  "samsung", 3),
    ("oncity",          "samsung", 3),
]


async def run_all(adapters: Optional[list] = None) -> list[dict]:
    """
    Runs all configured canary checks concurrently.
    Returns a list of failure dicts; empty list means all checks passed.
    """
    if adapters is None:
        from ..fetching.adapters import ADAPTERS
        adapters = ADAPTERS

    # Shallow-copy so check_shipping=False never sets _free_shipping_override=False
    # on the shared adapter instances used by normal searches.
    _check_stores = {s for s, _, _ in CANARY_CHECKS}
    adapter_map = {a.name: copy.copy(a) for a in adapters if a.name in _check_stores}

    async def _check(store: str, query: str, expected_min: int) -> Optional[dict]:
        adapter = adapter_map.get(store)
        if adapter is None:
            logger.warning("canary: no adapter found for store %r — skipping", store)
            return None

        t0 = time.perf_counter()
        failure_reason: Optional[str] = None
        actual_count = 0
        passed = False

        try:
            raw = await search_all_stores(query, [adapter], check_shipping=False)
            ssr = raw.get(store)
            actual_count = len(ssr.products) if ssr else 0
            passed = actual_count >= expected_min
            if not passed:
                failure_reason = f"got {actual_count}, expected >= {expected_min}"
        except Exception as exc:
            failure_reason = f"{type(exc).__name__}: {exc}"

        duration_ms = int((time.perf_counter() - t0) * 1000)
        storage.record_canary_run(
            store=store,
            query=query,
            expected_min=expected_min,
            actual_count=actual_count,
            passed=passed,
            duration_ms=duration_ms,
            failure_reason=failure_reason,
        )

        if not passed:
            return {
                "store": store,
                "query": query,
                "expected_min": expected_min,
                "actual_count": actual_count,
                "duration_ms": duration_ms,
                "failure_reason": failure_reason,
            }
        return None

    outcomes = await asyncio.gather(*[_check(s, q, n) for s, q, n in CANARY_CHECKS])
    return [r for r in outcomes if r is not None]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async def _main() -> int:
        from .alerts import alert_canary_failures

        print("Running canary checks...")
        failures = await run_all()

        if failures:
            print(f"\n{len(failures)} failure(s):")
            for f in failures:
                print(
                    f"  [{f['store']}] {f['query']!r}: "
                    f"{f['failure_reason']} ({f['duration_ms']} ms)"
                )
            await alert_canary_failures(failures)
            return 1

        print("All checks passed.")
        return 0

    sys.exit(asyncio.run(_main()))
