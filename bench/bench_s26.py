"""
Comprehensive timing benchmark for ElectrodomesticsBot searching "S26".
Times each store individually (sequential) with per-phase breakdown,
then times the full parallel run for wall-clock comparison.
"""
import asyncio
import functools
import sys
import time
import warnings
import os

# Suppress all warnings (SSL, deprecation, etc.)
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

QUERY = "S26"


class PhaseTimer:
    """Tracks call counts and cumulative time for a named phase."""
    def __init__(self, name):
        self.name = name
        self.calls = 0
        self.total_time = 0.0

    def record(self, elapsed):
        self.calls += 1
        self.total_time += elapsed


def wrap_async_method(obj, method_name, timer):
    """Monkey-patch an async method on an object to record timing."""
    original = getattr(obj, method_name)

    @functools.wraps(original)
    async def timed(*args, **kwargs):
        t0 = time.perf_counter()
        result = await original(*args, **kwargs)
        timer.record(time.perf_counter() - t0)
        return result

    setattr(obj, method_name, timed)


def wrap_sync_method(obj, method_name, timer):
    """Monkey-patch a sync method on an object to record timing."""
    original = getattr(obj, method_name)

    @functools.wraps(original)
    def timed(*args, **kwargs):
        t0 = time.perf_counter()
        result = original(*args, **kwargs)
        timer.record(time.perf_counter() - t0)
        return result

    setattr(obj, method_name, timed)


def instrument_adapter(adapter):
    """Attach phase timers to an adapter based on its platform type. Returns dict of timers."""
    from electrodomestics_bot.platforms.vtex import VtexAdapter
    from electrodomestics_bot.platforms.magento import MagentoAdapter
    from electrodomestics_bot.platforms.fravega import FravegaAdapter
    from electrodomestics_bot.platforms.megatone import MegatoneAdapter

    timers = {}

    if isinstance(adapter, FravegaAdapter):
        timers["search"] = PhaseTimer("search (GQL product fetch)")
        timers["shipping"] = PhaseTimer("shipping (GQL per-SKU)")
        timers["gql_total"] = PhaseTimer("_post_gql (all GQL calls)")
        wrap_async_method(adapter, "_fetch_all_products", timers["search"])
        wrap_async_method(adapter, "_fetch_free_shipping", timers["shipping"])
        wrap_async_method(adapter, "_post_gql", timers["gql_total"])

    elif isinstance(adapter, MegatoneAdapter):
        timers["search"] = PhaseTimer("search (Doofinder fetch)")
        timers["plans"] = PhaseTimer("plans (retornarplanes batch)")
        timers["plans_batch"] = PhaseTimer("_fetch_plans_batch (individual)")
        wrap_async_method(adapter, "_fetch_all_products", timers["search"])
        wrap_async_method(adapter, "_fetch_card_counts", timers["plans"])
        wrap_async_method(adapter, "_fetch_plans_batch", timers["plans_batch"])

    elif isinstance(adapter, VtexAdapter):
        # Castillo and OnCity are VtexAdapter subclasses
        timers["search"] = PhaseTimer("search (VTEX product fetch)")
        timers["shipping"] = PhaseTimer("shipping (simulation POST)")
        wrap_async_method(adapter, "_fetch_all_products", timers["search"])
        wrap_async_method(adapter, "_check_free_shipping", timers["shipping"])

    elif isinstance(adapter, MagentoAdapter):
        timers["search"] = PhaseTimer("search (HTML scrape)")
        timers["search_page"] = PhaseTimer("_fetch_search_page (per page)")
        wrap_async_method(adapter, "_fetch_all_search_pages", timers["search"])
        wrap_async_method(adapter, "_fetch_search_page", timers["search_page"])

    return timers


def fmt_time(seconds):
    if seconds < 0.001:
        return "<1ms"
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    return f"{seconds:.2f}s"


def print_separator(char="-", width=70):
    print(char * width)


async def bench_single_store(adapter):
    """Run a single store search with instrumentation. Returns (results, timers, total_time)."""
    timers = instrument_adapter(adapter)
    t0 = time.perf_counter()
    try:
        results = await adapter.search(QUERY)
    except Exception as e:
        results = []
        print(f"  ERROR: {e}")
    total = time.perf_counter() - t0
    return results, timers, total


async def bench_parallel(adapters):
    """Run all stores in parallel. Returns (results_dict, total_time)."""
    from electrodomestics_bot.core import search_all_stores
    t0 = time.perf_counter()
    results = await search_all_stores(QUERY, adapters)
    total = time.perf_counter() - t0
    return results, total


async def main():
    # Import adapters fresh for each run
    from electrodomestics_bot.adapters import ADAPTERS

    print("=" * 70)
    print(f"  ElectrodomesticsBot Benchmark -- query: \"{QUERY}\"")
    print(f"  Stores: {', '.join(a.name for a in ADAPTERS)}")
    print("=" * 70)
    print()

    # ---- Phase 1: Sequential per-store benchmarks ----
    print("PHASE 1: Sequential per-store benchmarks")
    print("  (each store runs alone, no parallelism between stores)")
    print_separator()

    store_results = {}  # name -> (results, timers, total_time)

    for adapter in ADAPTERS:
        # Create a fresh adapter instance to avoid state leaking between runs
        fresh = adapter.__class__()
        print(f"\n  [{fresh.name}]")
        results, timers, total = await bench_single_store(fresh)
        store_results[fresh.name] = (results, timers, total)

        print(f"    Total time:    {fmt_time(total)}")
        print(f"    Products found: {len(results)}")

        if timers:
            print(f"    Phase breakdown:")
            for key, timer in timers.items():
                if timer.calls > 0:
                    avg = timer.total_time / timer.calls if timer.calls > 1 else timer.total_time
                    detail = f"  ({timer.calls} calls, avg {fmt_time(avg)})" if timer.calls > 1 else ""
                    print(f"      {timer.name}: {fmt_time(timer.total_time)}{detail}")

    # ---- Phase 2: Parallel wall-clock benchmark ----
    print()
    print_separator("=")
    print()
    print("PHASE 2: Parallel wall-clock benchmark")
    print("  (all stores run concurrently via asyncio.gather)")
    print_separator()

    parallel_results, parallel_time = await bench_parallel(ADAPTERS)

    print(f"\n  Total wall-clock time: {fmt_time(parallel_time)}")
    for name, prods in parallel_results.items():
        print(f"    {name}: {len(prods)} products")

    # ---- Summary ----
    print()
    print_separator("=")
    print()
    print("SUMMARY")
    print_separator()

    # Sort stores by total time descending
    sorted_stores = sorted(store_results.items(), key=lambda x: x[1][2], reverse=True)

    print(f"\n  {'Store':<12} {'Time':>10} {'Products':>10}  Bottleneck Phase")
    print(f"  {'-'*12} {'-'*10} {'-'*10}  {'-'*30}")

    for name, (results, timers, total) in sorted_stores:
        # Find the slowest phase
        bottleneck = ""
        if timers:
            slowest = max(timers.values(), key=lambda t: t.total_time)
            if slowest.calls > 0:
                pct = (slowest.total_time / total * 100) if total > 0 else 0
                bottleneck = f"{slowest.name} ({fmt_time(slowest.total_time)}, {pct:.0f}%)"

        print(f"  {name:<12} {fmt_time(total):>10} {len(results):>10}  {bottleneck}")

    seq_total = sum(t for _, (_, _, t) in store_results.items())
    print()
    print(f"  Sequential total (sum):  {fmt_time(seq_total)}")
    print(f"  Parallel wall-clock:     {fmt_time(parallel_time)}")
    speedup = seq_total / parallel_time if parallel_time > 0 else 0
    print(f"  Speedup from parallel:   {speedup:.1f}x")

    # Identify overall bottleneck
    bottleneck_store = sorted_stores[0][0]
    bottleneck_time = sorted_stores[0][1][2]
    print(f"\n  Bottleneck store: {bottleneck_store} ({fmt_time(bottleneck_time)})")

    # Identify bottleneck phase across all stores
    all_phases = []
    for name, (_, timers, _) in store_results.items():
        for key, timer in timers.items():
            if timer.calls > 0:
                all_phases.append((name, timer))

    if all_phases:
        worst_store, worst_timer = max(all_phases, key=lambda x: x[1].total_time)
        print(f"  Bottleneck phase: {worst_store} -> {worst_timer.name} ({fmt_time(worst_timer.total_time)}, {worst_timer.calls} calls)")

    print()


if __name__ == "__main__":
    asyncio.run(main())
