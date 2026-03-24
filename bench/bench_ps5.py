# -*- coding: utf-8 -*-
"""
bench_ps5.py - Comprehensive performance diagnosis for the "PS5" query.

Measures:
  1. Per-store wall-clock time with phase breakdown (fetch pages, shipping, etc.)
  2. HTTP request count and sizes per store
  3. Sequential vs parallel store execution (the main architectural concern)
  4. VTEX redirect detection and its cost
  5. Concurrency behavior for shipping/plans checks

Run from the project root:
    python bench/bench_ps5.py
"""
import asyncio
import math
import time
from collections import defaultdict
from urllib.parse import quote

import httpx

from electrodomestics_bot.adapters.fravega import FravegaAdapter as _FravegaStoreAdapter
from electrodomestics_bot.platforms.fravega import FravegaAdapter as FravegaPlatform
from electrodomestics_bot.platforms.vtex import VtexAdapter
from electrodomestics_bot.platforms.magento import MagentoAdapter
from electrodomestics_bot.core import matches_query
import electrodomestics_bot.core as _core

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUERY = "PS5"
SEP = "=" * 68


# ------------------------------------------------------------------------------
# HTTP instrumentation -- monkey-patch httpx and curl_cffi to count calls
# ------------------------------------------------------------------------------

class RequestLog:
    """Thread/async-safe accumulator for HTTP request timings."""
    def __init__(self):
        self.calls: list[dict] = []

    def record(self, method: str, url: str, elapsed: float, status: int, size_bytes: int):
        self.calls.append({
            "method": method,
            "url": url[:120],
            "elapsed": elapsed,
            "status": status,
            "bytes": size_bytes,
        })

    def summary(self) -> dict:
        if not self.calls:
            return {"n": 0, "total_s": 0.0, "avg_s": 0.0, "max_s": 0.0,
                    "total_kb": 0.0, "errors": 0}
        elapsed_list = [c["elapsed"] for c in self.calls]
        return {
            "n": len(self.calls),
            "total_s": sum(elapsed_list),
            "avg_s": sum(elapsed_list) / len(elapsed_list),
            "max_s": max(elapsed_list),
            "total_kb": sum(c["bytes"] for c in self.calls) / 1024,
            "errors": sum(1 for c in self.calls if c["status"] >= 400 or c["status"] == 0),
        }

    def slowest(self, n: int = 5) -> list[dict]:
        return sorted(self.calls, key=lambda c: c["elapsed"], reverse=True)[:n]


_request_log = RequestLog()
_original_get = None
_original_post = None


def _install_httpx_spy():
    """Wraps core.http_get / http_post to record timing and counts."""
    global _original_get, _original_post
    import electrodomestics_bot.core as core_mod

    _original_get = core_mod.http_get
    _original_post = core_mod.http_post

    async def _spy_get(url: str, verify_ssl: bool = True) -> httpx.Response:
        t0 = time.perf_counter()
        try:
            resp = await _original_get(url, verify_ssl=verify_ssl)
            _request_log.record("GET", url, time.perf_counter() - t0,
                                resp.status_code, len(resp.content))
            return resp
        except Exception as e:
            _request_log.record("GET", url, time.perf_counter() - t0, 0, 0)
            raise

    async def _spy_post(url: str, verify_ssl: bool = True, **kwargs) -> httpx.Response:
        t0 = time.perf_counter()
        try:
            resp = await _original_post(url, verify_ssl=verify_ssl, **kwargs)
            _request_log.record("POST", url, time.perf_counter() - t0,
                                resp.status_code, len(resp.content))
            return resp
        except Exception as e:
            _request_log.record("POST", url, time.perf_counter() - t0, 0, 0)
            raise

    core_mod.http_get = _spy_get
    core_mod.http_post = _spy_post

    # Patch vtex.py and magento.py module references too
    from electrodomestics_bot.platforms import vtex as vtex_mod
    from electrodomestics_bot.platforms import magento as magento_mod
    vtex_mod.http_get = _spy_get
    vtex_mod.http_post = _spy_post
    magento_mod.http_get = _spy_get


# Separate log for curl_cffi (fravega)
_fravega_log = RequestLog()


# ------------------------------------------------------------------------------
# Instrumented adapters
# ------------------------------------------------------------------------------

class InstrumentedFravega(_FravegaStoreAdapter):
    """Records per-phase timing for Fravega."""

    _gql_semaphore = asyncio.Semaphore(9999)  # no cap for raw diagnosis

    def _reset(self):
        self._t_fetch_products = None
        self._t_shipping_wall = None
        self._n_products = 0
        self._n_shipping = 0
        self._n_pages = 0
        self._shipping_times: list[float] = []
        self._gql_calls: list[float] = []
        self._gql_log = _fravega_log

    async def _post_gql(self, gql: str) -> dict:
        # Use the module-level shared session (same as production).
        # Mirrors the 2-attempt retry logic from the parent class.
        from electrodomestics_bot.platforms.fravega import _session
        for attempt in range(2):
            t0 = time.perf_counter()
            try:
                resp = await _session.post(
                    self._endpoint, json={"query": gql}, verify=self.verify_ssl
                )
                resp.raise_for_status()
                elapsed = time.perf_counter() - t0
                data = resp.json()
                self._gql_calls.append(elapsed)
                _fravega_log.record("GQL", self._endpoint, elapsed,
                                    resp.status_code, len(resp.content))
                return data
            except Exception:
                elapsed = time.perf_counter() - t0
                if attempt == 0:
                    _fravega_log.record("GQL", self._endpoint, elapsed, 0, 0)
                    await asyncio.sleep(2)
                else:
                    self._gql_calls.append(elapsed)
                    _fravega_log.record("GQL", self._endpoint, elapsed, 0, 0)
                    raise

    async def _fetch_all_products(self, query: str) -> list[dict]:
        t0 = time.perf_counter()
        results = await super()._fetch_all_products(query)
        self._t_fetch_products = time.perf_counter() - t0
        self._n_products = len(results)
        return results

    async def _fetch_free_shipping(self, sku: str, seller_id: str) -> bool:
        t0 = time.perf_counter()
        result = await super()._fetch_free_shipping(sku, seller_id)
        self._shipping_times.append(time.perf_counter() - t0)
        return result


class InstrumentedVtex(VtexAdapter):
    """Records per-phase timing for OnCity (VTEX)."""

    name = "oncity"
    base_url = "https://www.oncity.com"
    verify_ssl = False

    def _reset(self):
        self._t_fetch_products = None
        self._t_shipping_wall = None
        self._n_products = 0
        self._n_shipping = 0
        self._redirect_used = False
        self._shipping_times: list[float] = []

    async def _fetch_all_products(self, quoted_query: str) -> list[dict]:
        t0 = time.perf_counter()
        results = await super()._fetch_all_products(quoted_query)
        self._t_fetch_products = time.perf_counter() - t0
        self._n_products = len(results)
        return results

    async def _fetch_all_products_legacy(self, quoted_query: str) -> list[dict]:
        self._redirect_used = True
        return await super()._fetch_all_products_legacy(quoted_query)

    async def _check_free_shipping(self, product: dict) -> bool:
        t0 = time.perf_counter()
        result = await super()._check_free_shipping(product)
        self._shipping_times.append(time.perf_counter() - t0)
        return result


class InstrumentedMagento(MagentoAdapter):
    """Records per-phase timing for Cetrogar (Magento)."""

    name = "cetrogar"
    base_url = "https://www.cetrogar.com.ar"

    def _reset(self):
        self._t_fetch_products = None
        self._n_products = 0
        self._n_pages = 0
        self._page_times: list[float] = []

    async def _fetch_search_page(self, quoted_query: str, page: int):
        t0 = time.perf_counter()
        result = await super()._fetch_search_page(quoted_query, page)
        self._page_times.append(time.perf_counter() - t0)
        return result

    async def _fetch_all_search_pages(self, quoted_query: str) -> list[dict]:
        t0 = time.perf_counter()
        results = await super()._fetch_all_search_pages(quoted_query)
        self._t_fetch_products = time.perf_counter() - t0
        self._n_products = len(results)
        return results


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _pct(lst: list[float], p: int) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    idx = max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))
    return s[idx]


def _fmt(s: float | None) -> str:
    if s is None:
        return "--"
    return f"{s:.3f}s"


def _print_http_log(log: RequestLog, label: str):
    sm = log.summary()
    print(f"\n  [{label}] HTTP calls: {sm['n']}  "
          f"total serial time: {sm['total_s']:.2f}s  "
          f"avg: {sm['avg_s']:.3f}s  max: {sm['max_s']:.3f}s  "
          f"data: {sm['total_kb']:.0f} KB  errors: {sm['errors']}")
    print(f"  Slowest {min(5, sm['n'])} requests:")
    for c in log.slowest(5):
        tag = "ERR" if c["status"] == 0 else str(c["status"])
        print(f"    [{tag}] {c['elapsed']:.3f}s  {c['method']}  {c['url'][:90]}")


# ------------------------------------------------------------------------------
# Benchmark: per-store sequential (current service.py behaviour)
# ------------------------------------------------------------------------------

async def run_store_sequential(fravega, vtex, magento):
    """Runs stores one after the other, mirroring how service.py works."""
    print(f"\n{'-'*68}")
    print("SCENARIO A: SEQUENTIAL (current service.py behaviour)")
    print(f"{'-'*68}")

    store_times = {}

    # Cetrogar
    print(f"\n  -> Running Cetrogar (Magento)...")
    magento._reset()
    _request_log.calls.clear()
    t0 = time.perf_counter()
    cetrogar_results = await magento.search(QUERY)
    store_times["cetrogar"] = time.perf_counter() - t0
    cetrogar_http = magento._page_times
    print(f"    Done: {store_times['cetrogar']:.2f}s | "
          f"{len(cetrogar_results)} matching products | "
          f"{magento._n_products} raw | "
          f"{len(cetrogar_http)} pages fetched")
    _print_http_log(_request_log, "Cetrogar")
    cetrogar_log_snap = list(_request_log.calls)

    # Fravega (brief pause to avoid Fravega rate-limiting after prior calls)
    await asyncio.sleep(1)
    print(f"\n  -> Running Fravega (GraphQL)...")
    fravega._reset()
    _fravega_log.calls.clear()
    t0 = time.perf_counter()
    fravega_results = await fravega.search(QUERY)
    store_times["fravega"] = time.perf_counter() - t0
    print(f"    Done: {store_times['fravega']:.2f}s | "
          f"{len(fravega_results)} matching products | "
          f"{fravega._n_products} raw | "
          f"{len(fravega._shipping_times)} shipping checks")
    if fravega._shipping_times:
        st = fravega._shipping_times
        print(f"    Shipping: wall={_fmt(max(st))}  "
              f"p50={_fmt(_pct(st, 50))}  p90={_fmt(_pct(st, 90))}  "
              f"sum={_fmt(sum(st))}")
    _print_http_log(_fravega_log, "Fravega GQL")

    # OnCity
    print(f"\n  -> Running OnCity (VTEX)...")
    vtex._reset()
    _request_log.calls.clear()
    t0 = time.perf_counter()
    vtex_results = await vtex.search(QUERY)
    store_times["oncity"] = time.perf_counter() - t0
    print(f"    Done: {store_times['oncity']:.2f}s | "
          f"{len(vtex_results)} matching products | "
          f"{vtex._n_products} raw")
    if vtex._redirect_used:
        print(f"    [!]  VTEX redirect detected -- legacy API fallback was used!")
    if vtex._shipping_times:
        st = vtex._shipping_times
        print(f"    Shipping: wall={_fmt(max(st))}  "
              f"p50={_fmt(_pct(st, 50))}  p90={_fmt(_pct(st, 90))}  "
              f"sum={_fmt(sum(st))}")
    _print_http_log(_request_log, "OnCity HTTP")

    total_sequential = sum(store_times.values())
    print(f"\n  SEQUENTIAL TOTAL: {total_sequential:.2f}s")
    print(f"    cetrogar: {store_times['cetrogar']:.2f}s")
    print(f"    fravega:  {store_times['fravega']:.2f}s")
    print(f"    oncity:   {store_times['oncity']:.2f}s")

    return store_times


# ------------------------------------------------------------------------------
# Benchmark: all stores in parallel (ideal behaviour)
# ------------------------------------------------------------------------------

async def run_stores_parallel(fravega, vtex, magento):
    """Runs all stores concurrently, like search_all_stores() does."""
    print(f"\n{'-'*68}")
    print("SCENARIO B: PARALLEL (all stores via asyncio.gather)")
    print(f"{'-'*68}")

    fravega._reset()
    vtex._reset()
    magento._reset()
    _request_log.calls.clear()
    _fravega_log.calls.clear()

    t0 = time.perf_counter()
    results = await asyncio.gather(
        magento.search(QUERY),
        fravega.search(QUERY),
        vtex.search(QUERY),
    )
    parallel_total = time.perf_counter() - t0
    cetrogar_results, fravega_results, vtex_results = results

    print(f"\n  PARALLEL TOTAL: {parallel_total:.2f}s")
    print(f"    cetrogar: {len(cetrogar_results)} matching products")
    print(f"    fravega:  {len(fravega_results)} matching products")
    print(f"    oncity:   {len(vtex_results)} matching products")
    if vtex._redirect_used:
        print(f"    [!]  VTEX redirect detected (legacy API fallback)")

    return parallel_total


# ------------------------------------------------------------------------------
# Diagnosis: VTEX redirect cost
# ------------------------------------------------------------------------------

async def diagnose_vtex_redirect(vtex):
    print(f"\n{'-'*68}")
    print("VTEX REDIRECT DIAGNOSIS")
    print(f"{'-'*68}")

    quoted = quote(QUERY)
    base = vtex.search_url.format(quoted)

    # Time the intelligent search first hit
    print(f"\n  Testing intelligent search for '{QUERY}'...")
    _request_log.calls.clear()
    t0 = time.perf_counter()
    from electrodomestics_bot.core import http_get
    try:
        resp = await http_get(base, verify_ssl=vtex.verify_ssl)
        data = resp.json()
        t_intel = time.perf_counter() - t0
        products = data.get("products", [])
        redirect = data.get("redirect", "")
        print(f"    Intelligent search: {t_intel:.3f}s | "
              f"{len(products)} products | "
              f"redirect={repr(redirect[:80]) if redirect else 'none'}")

        if not products and redirect:
            print(f"    -> Redirect confirmed. Timing legacy fallback...")
            t1 = time.perf_counter()
            legacy_products = await vtex._fetch_all_products_legacy(quoted)
            t_legacy = time.perf_counter() - t1
            print(f"    Legacy API: {t_legacy:.3f}s | {len(legacy_products)} products")
            print(f"    Wasted on redirect: {t_intel:.3f}s ({t_intel/(t_intel+t_legacy)*100:.0f}% overhead)")
        elif products:
            total_pages = min(data.get("pagination", {}).get("count", 1), 10)
            print(f"    No redirect. Pages: {total_pages}")
    except Exception as e:
        print(f"    ERROR: {e}")


# ------------------------------------------------------------------------------
# Diagnosis: shipping concurrency cap comparison (VTEX)
# ------------------------------------------------------------------------------

async def diagnose_vtex_shipping_concurrency(vtex):
    """
    Simulates the shipping check for all PS5 products with unlimited concurrency
    (current state after revert), to show whether a semaphore would help.
    """
    print(f"\n{'-'*68}")
    print("VTEX SHIPPING CONCURRENCY DIAGNOSIS")
    print(f"{'-'*68}")

    vtex._reset()
    quoted = quote(QUERY)
    all_products = await vtex._fetch_all_products(quoted)
    products = [p for p in all_products
                if p.get("productName") and matches_query(p["productName"], QUERY)]
    available = [p for p in products if vtex._is_available(p)]

    print(f"\n  Products after filter: {len(products)} | available: {len(available)}")
    if not available:
        print("  No available products -- skipping shipping test.")
        return

    # Unlimited
    print(f"\n  Testing UNLIMITED concurrency ({len(available)} simultaneous POSTs)...")
    _request_log.calls.clear()
    t0 = time.perf_counter()
    await asyncio.gather(*[vtex._check_free_shipping(p) for p in available])
    t_unlimited = time.perf_counter() - t0
    sm = _request_log.summary()
    print(f"    Wall: {t_unlimited:.2f}s | "
          f"calls: {sm['n']} | avg: {sm['avg_s']:.3f}s | "
          f"max: {sm['max_s']:.3f}s | errors: {sm['errors']}")

    # Capped at 10
    cap = 10
    print(f"\n  Testing CAPPED concurrency (Semaphore({cap}))...")

    semaphore = asyncio.Semaphore(cap)
    _request_log.calls.clear()

    async def _capped_check(p):
        async with semaphore:
            return await vtex._check_free_shipping(p)

    t0 = time.perf_counter()
    await asyncio.gather(*[_capped_check(p) for p in available])
    t_capped = time.perf_counter() - t0
    sm2 = _request_log.summary()
    print(f"    Wall: {t_capped:.2f}s | "
          f"calls: {sm2['n']} | avg: {sm2['avg_s']:.3f}s | "
          f"max: {sm2['max_s']:.3f}s | errors: {sm2['errors']}")

    if t_unlimited > 0:
        ratio = t_capped / t_unlimited
        better = "FASTER" if ratio < 1 else "SLOWER"
        print(f"\n  Result: Semaphore({cap}) is {abs(1-ratio)*100:.0f}% {better} than unlimited")


# ------------------------------------------------------------------------------
# Diagnosis: matches_query filter rate
# ------------------------------------------------------------------------------

async def diagnose_filter_rates(fravega, vtex, magento):
    """Shows how many raw results are filtered out by matches_query."""
    print(f"\n{'-'*68}")
    print("MATCHES_QUERY FILTER RATES")
    print(f"{'-'*68}")

    # Fravega
    try:
        fravega._reset()
        raw_fravega = await fravega._fetch_all_products(QUERY)
        matched = [r for r in raw_fravega if r.get("title") and matches_query(r.get("title", ""), QUERY)]
        print(f"\n  Fravega:  {len(raw_fravega)} raw -> {len(matched)} matched "
              f"({len(raw_fravega)-len(matched)} filtered out, "
              f"{(len(raw_fravega)-len(matched))/max(len(raw_fravega),1)*100:.0f}%)")
    except Exception as e:
        print(f"\n  Fravega:  ERROR -- {e}")

    # VTEX
    try:
        vtex._reset()
        quoted = quote(QUERY)
        raw_vtex = await vtex._fetch_all_products(quoted)
        matched_vtex = [p for p in raw_vtex
                        if p.get("productName") and matches_query(p["productName"], QUERY)]
        print(f"  OnCity:   {len(raw_vtex)} raw -> {len(matched_vtex)} matched "
              f"({len(raw_vtex)-len(matched_vtex)} filtered out)")
    except Exception as e:
        print(f"  OnCity:   ERROR -- {e}")

    # Magento
    try:
        magento._reset()
        raw_magento = await magento._fetch_all_search_pages(quote(QUERY))
        matched_magento = [i for i in raw_magento
                           if i.get("name") and matches_query(i["name"], QUERY)]
        print(f"  Cetrogar: {len(raw_magento)} raw -> {len(matched_magento)} matched "
              f"({len(raw_magento)-len(matched_magento)} filtered out)")
    except Exception as e:
        print(f"  Cetrogar: ERROR -- {e}")


# ------------------------------------------------------------------------------
# Summary report
# ------------------------------------------------------------------------------

def print_summary(store_times: dict, parallel_total: float):
    print(f"\n\n{SEP}")
    print("PERFORMANCE SUMMARY")
    print(SEP)

    sequential_total = sum(store_times.values())
    theoretical_parallel = max(store_times.values())

    print(f"\n  Measured sequential total:  {sequential_total:.2f}s")
    print(f"  Measured parallel total:    {parallel_total:.2f}s")
    print(f"  Theoretical parallel floor: {theoretical_parallel:.2f}s  (= slowest store)")
    print(f"\n  Parallelism speedup:        {sequential_total/max(parallel_total,0.001):.1f}x")
    print(f"\n  Per-store breakdown:")
    for store, t in sorted(store_times.items(), key=lambda x: -x[1]):
        pct = t / sequential_total * 100
        print(f"    {store:12s}  {t:.2f}s  ({pct:.0f}% of sequential time)")

    print(f"""
  KEY FINDINGS:
  -------------
  1. service.py searches stores SEQUENTIALLY inside a for-loop. Total time is
     the SUM of all store times ({sequential_total:.1f}s) instead of the MAX
     ({theoretical_parallel:.1f}s). Parallelising the loop would save
     ~{sequential_total - parallel_total:.1f}s (~{(1-parallel_total/sequential_total)*100:.0f}% reduction).

  2. VTEX (OnCity) redirect check: 'PS5' triggers an intelligent-search redirect,
     wasting one full round-trip before falling back to the legacy API.

  3. VTEX shipping simulations have NO concurrency cap -- all products fire
     simultaneously. A Semaphore(10) equivalent to Fravega's would help if
     OnCity has many PS5 products.

  4. Fravega GQL semaphore was REVERTED -- all GQL calls are now unlimited.
     This was stable at the time of the revert but may regress on large queries.
""")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

async def main():
    print(SEP)
    print(f"  ElectrodomesticsBot -- PS5 Performance Diagnosis")
    print(f"  Query: '{QUERY}'")
    print(SEP)

    _install_httpx_spy()

    fravega = InstrumentedFravega()
    vtex = InstrumentedVtex()
    magento = InstrumentedMagento()

    # 1. VTEX redirect diagnosis (cheap, run first)
    await diagnose_vtex_redirect(vtex)

    # 2. Filter rate diagnosis
    await diagnose_filter_rates(fravega, vtex, magento)

    # 3. Sequential run (mirrors current service.py)
    store_times = await run_store_sequential(fravega, vtex, magento)

    # 4. Parallel run (ideal)
    parallel_total = await run_stores_parallel(fravega, vtex, magento)

    # 5. VTEX shipping concurrency diagnosis
    await diagnose_vtex_shipping_concurrency(vtex)

    # 6. Summary
    print_summary(store_times, parallel_total)


if __name__ == "__main__":
    asyncio.run(main())
