"""
bench_fravega.py — Timing benchmark for FravegaAdapter.

Instruments _fetch_all_products, _fetch_free_shipping, and _fetch_plans
by overriding each method to capture per-phase wall-clock time, then
delegates to the real implementations via super(). search() is NOT
duplicated — super().search() is called directly so the benchmark stays
in sync with any future changes to the platform logic.

Run from the project root:
    python bench/bench_fravega.py
"""

import asyncio
import math
import statistics
import time

from electrodomestics_bot.adapters.fravega import FravegaAdapter
from electrodomestics_bot.platforms.fravega import _MAX_PAGES, _PAGE_SIZE


# ──────────────────────────────────────────────────────────────────────────────
# Instrumented subclass (unlimited concurrency)
# ──────────────────────────────────────────────────────────────────────────────

class InstrumentedFravegaAdapter(FravegaAdapter):
    """
    Wraps _fetch_all_products, _fetch_free_shipping, and _fetch_plans to
    record wall-clock durations. search() is inherited unchanged so the
    benchmark always reflects the real execution path.

    _gql_semaphore is set to a large value so this adapter benchmarks
    unlimited concurrency, even though the production class caps at 40.
    """

    _gql_semaphore = asyncio.Semaphore(9999)

    def _reset_stats(self):
        self._stats = {
            "fetch_all_products_s": None,
            "fetch_all_products_n_products": 0,
            "fetch_all_products_n_pages": 0,
            "shipping_s": 0.0,
            "shipping_n": 0,
            "shipping_p50": None,
            "shipping_p90": None,
            "shipping_p99": None,
            "shipping_max": None,
            "plans_s": None,
            "plans_n": 0,
            "plans_p50": None,
            "plans_p90": None,
            "plans_p99": None,
            "plans_max": None,
        }
        self._shipping_calls: list[float] = []
        self._plans_calls: list[float] = []

    async def _fetch_all_products(self, query: str) -> list[dict]:
        t0 = time.perf_counter()
        results = await super()._fetch_all_products(query)
        elapsed = time.perf_counter() - t0
        n = len(results)
        pages = min(math.ceil(n / _PAGE_SIZE), _MAX_PAGES) if n > 0 else 1
        self._stats["fetch_all_products_s"] = elapsed
        self._stats["fetch_all_products_n_products"] = n
        self._stats["fetch_all_products_n_pages"] = pages
        return results

    async def _fetch_free_shipping(self, sku: str, seller_id: str) -> bool:
        t0 = time.perf_counter()
        result = await super()._fetch_free_shipping(sku, seller_id)
        self._shipping_calls.append(time.perf_counter() - t0)
        return result

    async def _fetch_plans(self, sku: str):
        t0 = time.perf_counter()
        result = await super()._fetch_plans(sku)
        self._plans_calls.append(time.perf_counter() - t0)
        return result

    def _finalize_stats(self):
        """
        Called after search() completes. Derives aggregate shipping/plans
        timing from the per-call records. Wall time for a fully concurrent
        gather equals the slowest individual call, not the sum.
        Also computes p50/p90/p99/max percentiles from per-call durations.
        """
        if self._shipping_calls:
            calls = sorted(self._shipping_calls)
            n = len(calls)
            self._stats["shipping_n"] = n
            self._stats["shipping_s"] = calls[-1]
            self._stats["shipping_max"] = calls[-1]
            self._stats["shipping_p50"] = _percentile(calls, 50)
            self._stats["shipping_p90"] = _percentile(calls, 90)
            self._stats["shipping_p99"] = _percentile(calls, 99)
        if self._plans_calls:
            calls = sorted(self._plans_calls)
            n = len(calls)
            self._stats["plans_n"] = n
            self._stats["plans_s"] = calls[-1]
            self._stats["plans_max"] = calls[-1]
            self._stats["plans_p50"] = _percentile(calls, 50)
            self._stats["plans_p90"] = _percentile(calls, 90)
            self._stats["plans_p99"] = _percentile(calls, 99)


# ──────────────────────────────────────────────────────────────────────────────
# Semaphore-capped subclass
# ──────────────────────────────────────────────────────────────────────────────

class SemaphoredFravegaAdapter(InstrumentedFravegaAdapter):
    """
    Same as InstrumentedFravegaAdapter but uses the production Semaphore(40)
    cap on _post_gql — matching real FravegaAdapter behavior.
    The semaphore is reset per run so it doesn't leak state between benchmark runs.
    """

    def _reset_stats(self):
        super()._reset_stats()
        self._gql_semaphore = asyncio.Semaphore(40)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _percentile(sorted_data: list[float], pct: int) -> float:
    """
    Returns the p-th percentile of a pre-sorted list using nearest-rank method.
    """
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    # nearest rank: ceil(pct/100 * n) - 1, clamped
    idx = max(0, min(n - 1, math.ceil(pct / 100 * n) - 1))
    return sorted_data[idx]


QUERY = "Samsung Galaxy S25"


def _fmt(s: float | None) -> str:
    return f"{s:.3f}s" if s is not None else "skipped"


def _req_note(n: int) -> str:
    return f"{n} concurrent requests" if n else "0 requests"


def _print_stats(label: str, n_results: int, stats: dict, total: float) -> None:
    print()
    print("=" * 60)
    print(f"=== {label} — {n_results} matching products ===")
    print("=" * 60)
    print(
        f"  _fetch_all_products: {_fmt(stats['fetch_all_products_s'])}"
        f"  ({stats['fetch_all_products_n_products']} raw products,"
        f" ~{stats['fetch_all_products_n_pages']} page(s))"
    )

    n_ship = stats["shipping_n"]
    if n_ship:
        print(f"  shipping tasks:      {_req_note(n_ship)}")
        print(f"    wall (max):        {_fmt(stats['shipping_max'])}")
        print(f"    p50 (median):      {_fmt(stats['shipping_p50'])}")
        print(f"    p90:               {_fmt(stats['shipping_p90'])}")
        print(f"    p99:               {_fmt(stats['shipping_p99'])}")
    else:
        print(f"  shipping tasks:      0 requests")

    n_plans = stats["plans_n"]
    if stats["plans_s"] is not None:
        print(f"  plans tasks:         {_req_note(n_plans)}")
        print(f"    wall (max):        {_fmt(stats['plans_max'])}")
        print(f"    p50 (median):      {_fmt(stats['plans_p50'])}")
        print(f"    p90:               {_fmt(stats['plans_p90'])}")
        print(f"    p99:               {_fmt(stats['plans_p99'])}")

    print(f"  TOTAL:               {total:.3f}s")


# ──────────────────────────────────────────────────────────────────────────────
# Benchmark runner
# ──────────────────────────────────────────────────────────────────────────────

async def _run_adapter(adapter: InstrumentedFravegaAdapter, detail: bool):
    """Runs a single benchmark pass and returns (n_results, stats, total_s)."""
    adapter._reset_stats()
    t0 = time.perf_counter()
    results = await adapter.search(QUERY, detail=detail)
    total = time.perf_counter() - t0
    adapter._finalize_stats()
    return len(results), dict(adapter._stats), total


async def run_benchmark():
    unlimited = InstrumentedFravegaAdapter()
    semaphored = SemaphoredFravegaAdapter()

    # -- Unlimited concurrency -------------------------------------------------
    print("\n" + "-"*60)
    print("RUN 1: UNLIMITED CONCURRENCY")
    print("-"*60)

    print(f"Running fast mode (detail=False) for query: '{QUERY}' ...")
    n_fast_u, stats_fast_u, total_fast_u = await _run_adapter(unlimited, detail=False)

    print(f"Running detail mode (detail=True) for query: '{QUERY}' ...")
    n_detail_u, stats_detail_u, total_detail_u = await _run_adapter(unlimited, detail=True)

    # -- Semaphore(40) ---------------------------------------------------------
    print("\n" + "-"*60)
    print("RUN 2: SEMAPHORE(40) CONCURRENCY")
    print("-"*60)

    print(f"Running fast mode (detail=False) for query: '{QUERY}' ...")
    n_fast_s, stats_fast_s, total_fast_s = await _run_adapter(semaphored, detail=False)

    print(f"Running detail mode (detail=True) for query: '{QUERY}' ...")
    n_detail_s, stats_detail_s, total_detail_s = await _run_adapter(semaphored, detail=True)

    # -- Report ----------------------------------------------------------------
    print("\n\n" + "-"*60)
    print("RESULTS -- UNLIMITED CONCURRENCY")
    print("-"*60)
    _print_stats("Fast mode (detail=False)", n_fast_u, stats_fast_u, total_fast_u)
    _print_stats("Detail mode (detail=True)", n_detail_u, stats_detail_u, total_detail_u)

    print("\n\n" + "-"*60)
    print("RESULTS -- SEMAPHORE(40) CONCURRENCY")
    print("-"*60)
    _print_stats("Fast mode (detail=False)", n_fast_s, stats_fast_s, total_fast_s)
    _print_stats("Detail mode (detail=True)", n_detail_s, stats_detail_s, total_detail_s)

    print()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
