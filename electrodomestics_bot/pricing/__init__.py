"""
Pricing spreadsheet automation — fetches ALL payment plans (sin + con interes)
from competitor stores and writes interest rates to an Excel template.

Public API:
    run_pricing()  — interactive CLI workflow
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import date
from pathlib import Path

from .adapters import PRICING_STORES
from .excel_io import read_template, write_results
from .models import PricingResult
from .service import fetch_plans_for_product, search_pricing_stores


def run_pricing() -> None:
    """Interactive CLI workflow for pricing spreadsheet automation."""
    # 1. Template path
    template_path = input("Excel template path: ").strip().strip('"')
    if not template_path or not Path(template_path).exists():
        print(f"  Template not found: {template_path}")
        sys.exit(1)

    # 2. Parse template
    template_rows = read_template(template_path)
    print(f"  Parsed {len(template_rows)} data rows from template\n")

    # 3. Product query
    query = input("Product name or SKU for pricing analysis: ").strip()
    if not query or len(query) < 3:
        print("  Query too short — need at least 3 characters.")
        sys.exit(1)

    # 4. Search, confirm, fetch plans, write
    asyncio.run(_run_pipeline(query, template_path, template_rows))


async def _run_pipeline(
    query: str,
    template_path: str,
    template_rows: list,
) -> None:
    """Async pipeline: search → confirm → fetch plans → write Excel."""
    # --- Search ---
    print("  Searching pricing stores...")
    t0 = time.perf_counter()
    store_results = await search_pricing_stores(query)
    elapsed = time.perf_counter() - t0
    print(f"  Search completed in {elapsed:.1f}s\n")

    # --- Show best match per store ---
    confirmed: dict[str, tuple] = {}
    for name, (store, products) in store_results.items():
        if not products:
            print(f"  {name}: no results")
            continue
        best = products[0]
        price_str = f"${best.price:,.0f}" if best.price else "no price"
        print(f"  {name}: {best.name} — {price_str}")
        confirmed[name] = (store, best)

    if not confirmed:
        print("\n  No products found in any pricing store.")
        return

    choice = input("\n  Proceed with these products? [Y/n]: ").strip().lower()
    if choice in ("n", "no"):
        print("  Aborted.")
        return

    # --- Fetch plans in parallel ---
    print("\n  Fetching payment plans...")
    t0 = time.perf_counter()
    tasks = [
        fetch_plans_for_product(store, product)
        for _name, (store, product) in confirmed.items()
    ]
    pricing_results: dict[str, PricingResult] = {}
    for result in await asyncio.gather(*tasks):
        pricing_results[result.store_name] = result
        plan_count = len(result.plans)
        status_tag = "" if result.status == "ok" else f" [{result.status}]"
        print(f"    {result.store_name}: {plan_count} plans{status_tag}")

    elapsed = time.perf_counter() - t0
    print(f"  Plans fetched in {elapsed:.1f}s\n")

    # --- Write Excel ---
    stem = Path(template_path).stem
    output_path = Path(template_path).parent / f"{stem}_{date.today().isoformat()}.xlsx"
    cells = write_results(template_path, output_path, template_rows, pricing_results)

    # --- Summary ---
    total_plans = sum(len(r.plans) for r in pricing_results.values())
    stores_ok = sum(1 for r in pricing_results.values() if r.status == "ok")
    print(f"  {stores_ok}/{len(pricing_results)} stores OK, {total_plans} total plans")
    print(f"  Wrote {cells} cells to {output_path}")
