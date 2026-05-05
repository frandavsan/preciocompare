"""
Compare detail=False vs detail=True across 3 representative queries.

Captures wall time, per-store fetch duration, product count, and best sin-interés
count per store. The interesting columns are wall_s (overall latency) and Fravega's
best — that's the data point driving the option A/B/C decision.

Run sequentially per (query, detail) combo to avoid skewing each other.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import warnings
from typing import Any

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from electrodomestics_bot.fetching.service import search_products
from electrodomestics_bot.models import ProductResult, StoreSearchResult

QUERIES = ["S26", "55pud7309", "QN75QN70FAGCZB"]


def best_sin_interes_count(products: list[ProductResult]) -> int:
    best = 0
    for p in products:
        for inst in p.installments:
            if inst.count > best:
                best = inst.count
    return best


def fmt_ms(ms: int | None) -> str:
    if ms is None:
        return "  -  "
    return f"{ms / 1000:5.1f}s"


async def run_one(query: str, detail: bool) -> dict[str, Any]:
    t0 = time.perf_counter()
    results: dict[str, StoreSearchResult] = await search_products(
        query, detail=detail, use_cache=False, check_shipping=True,
    )
    wall = time.perf_counter() - t0
    return {"wall": wall, "results": results}


async def main():
    rows = []
    for q in QUERIES:
        for detail in (False, True):
            print(f"\n>>> running query={q!r} detail={detail} ...", flush=True)
            data = await run_one(q, detail)
            rows.append({"query": q, "detail": detail, **data})
            print(f"    done in {data['wall']:.1f}s", flush=True)

    # Summary table
    print("\n\n" + "=" * 110)
    print("SUMMARY")
    print("=" * 110)
    for q in QUERIES:
        print(f"\nquery={q!r}")
        for detail in (False, True):
            row = next(r for r in rows if r["query"] == q and r["detail"] == detail)
            print(f"  detail={str(detail):<5}  wall={row['wall']:5.1f}s")
            results = row["results"]
            for store_name, ssr in results.items():
                best = best_sin_interes_count(ssr.products)
                n = len(ssr.products)
                status = ssr.status if ssr.status != "ok" else ""
                print(
                    f"      {store_name:<16} {fmt_ms(ssr.duration_ms)}  "
                    f"products={n:<3} best_sin_int={best:>2}x  {status}"
                )

    # Delta on Fravega specifically (the case driving this investigation)
    print("\n\n" + "=" * 110)
    print("FRAVEGA — fast vs detail mode delta")
    print("=" * 110)
    for q in QUERIES:
        fast = next(r for r in rows if r["query"] == q and r["detail"] is False)
        det = next(r for r in rows if r["query"] == q and r["detail"] is True)
        f_fr = fast["results"].get("fravega")
        d_fr = det["results"].get("fravega")
        if f_fr is None or d_fr is None:
            continue
        f_best = best_sin_interes_count(f_fr.products)
        d_best = best_sin_interes_count(d_fr.products)
        f_ms = f_fr.duration_ms or 0
        d_ms = d_fr.duration_ms or 0
        print(
            f"  {q!r:<20}  fast: best={f_best:>2}x ({f_ms / 1000:.1f}s, n={len(f_fr.products)})  "
            f"|  detail: best={d_best:>2}x ({d_ms / 1000:.1f}s, n={len(d_fr.products)})  "
            f"|  delta: +{d_best - f_best}x sin-int, +{(d_ms - f_ms) / 1000:.1f}s"
        )


if __name__ == "__main__":
    asyncio.run(main())
