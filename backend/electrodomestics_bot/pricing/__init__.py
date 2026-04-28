"""
Pricing spreadsheet automation — fetches ALL payment plans (sin + con interes)
from competitor stores and writes interest rates to an Excel template.

Public API:
    run_pricing()             — interactive CLI workflow
    generate_pricing_excel()  — non-interactive pipeline used by the API
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = _PROJECT_ROOT / "Precios E-commerce El Gato (1).xlsx"
EXCELS_DIR = _PROJECT_ROOT / "excels"

from .adapters import PRICING_STORES
from .excel_io import read_template, write_results
from .models import PricingResult
from .service import fetch_plans_for_product, search_pricing_stores


def _slugify(value: str, max_len: int = 30) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())[:max_len].strip("_")
    return cleaned or "query"


async def generate_pricing_excel(query: str) -> Optional[Path]:
    """Non-interactive pipeline used by the API: search → top-match per store →
    fetch all plans → write Excel. Returns the output path on success, or None
    when no pricing store returned any product. Raises FileNotFoundError when
    the template is missing.

    Each call writes to a per-request unique path so concurrent exports
    cannot overwrite each other before their FileResponse drains."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Pricing template not found: {TEMPLATE_PATH}")
    template_path = str(TEMPLATE_PATH)
    # openpyxl is sync I/O — keep it off the event loop so concurrent exports
    # don't stall unrelated requests.
    template_rows = await asyncio.to_thread(read_template, template_path)

    store_results = await search_pricing_stores(query)

    confirmed: dict[str, tuple] = {}
    for name, (store, products) in store_results.items():
        if products:
            confirmed[name] = (store, products[0])

    if not confirmed:
        return None

    tasks = [
        fetch_plans_for_product(store, product)
        for _name, (store, product) in confirmed.items()
    ]
    pricing_results: dict[str, PricingResult] = {}
    for result in await asyncio.gather(*tasks):
        pricing_results[result.store_name] = result

    EXCELS_DIR.mkdir(exist_ok=True)
    output_path = EXCELS_DIR / (
        f"pricing_{date.today().isoformat()}_{_slugify(query)}_{uuid.uuid4().hex[:8]}.xlsx"
    )
    await asyncio.to_thread(
        write_results, template_path, output_path, template_rows, pricing_results
    )

    return output_path


def run_pricing() -> None:
    """Interactive CLI workflow for pricing spreadsheet automation."""
    template_path = str(TEMPLATE_PATH)
    if not TEMPLATE_PATH.exists():
        print(f"  Template not found: {template_path}")
        sys.exit(1)

    # Parse template
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
    EXCELS_DIR.mkdir(exist_ok=True)
    base_name = f"pricing_{date.today().isoformat()}"
    output_path = EXCELS_DIR / f"{base_name}.xlsx"
    # Auto-increment suffix if file is locked (e.g. open in Excel)
    suffix = 1
    while True:
        try:
            cells = write_results(template_path, output_path, template_rows, pricing_results)
            break
        except PermissionError:
            suffix += 1
            output_path = EXCELS_DIR / f"{base_name}_{suffix}.xlsx"

    # --- Summary ---
    total_plans = sum(len(r.plans) for r in pricing_results.values())
    stores_ok = sum(1 for r in pricing_results.values() if r.status == "ok")
    print(f"  {stores_ok}/{len(pricing_results)} stores OK, {total_plans} total plans")
    print(f"  Wrote {cells} cells to {output_path}")
