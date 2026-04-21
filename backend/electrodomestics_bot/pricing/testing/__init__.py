"""
Interactive plan-testing tool — fetches and prints payment plans for one
(product, store) combination so the output sent to Excel can be inspected.

Public API:
    run_plan_test()  — interactive CLI
"""

from __future__ import annotations

import asyncio
import sys

from ..adapters import PRICING_STORES, PricingStore
from ..models import PaymentPlan, PricingResult
from ..service import fetch_plans_for_product, search_pricing_stores


def run_plan_test() -> None:
    query = input("Product name or SKU: ").strip()
    if not query or len(query) < 3:
        print("  Query too short — need at least 3 characters.")
        sys.exit(1)

    print("\n  Stores:")
    for i, ps in enumerate(PRICING_STORES, start=1):
        print(f"    {i}. {ps.name}")

    raw = input("\n  Select store [1-{}]: ".format(len(PRICING_STORES))).strip()
    try:
        idx = int(raw) - 1
        store = PRICING_STORES[idx]
    except (ValueError, IndexError):
        print("  Invalid selection.")
        sys.exit(1)

    asyncio.run(_run(query, store))


async def _run(query: str, store: PricingStore) -> None:
    print(f"\n  Searching '{store.name}' for '{query}'...")
    results = await search_pricing_stores(query)

    entry = results.get(store.name)
    if not entry or not entry[1]:
        print(f"  {store.name}: no results")
        return

    _ps, products = entry
    best = products[0]
    price_str = f"${best.price:,.0f}" if best.price else "no price"
    print(f"  Match: {best.name} — {price_str}")
    print(f"  URL:   {best.url}\n")

    print("  Fetching payment plans...")
    result = await fetch_plans_for_product(store, best)

    if result.status == "error":
        print(f"  ERROR: {result.error_detail}")
        return

    _print_plans(result)


def _print_plans(result: PricingResult) -> None:
    sin = [p for p in result.plans if not p.has_interest]
    con = [p for p in result.plans if p.has_interest]
    sin.sort(key=lambda p: (-p.installment_count, p.card_system.lower(), p.card_issuer or ""))
    con.sort(key=lambda p: (-p.installment_count, p.card_system.lower(), p.card_issuer or ""))

    print(f"\n  Total plans: {len(result.plans)} "
          f"(sin interés: {len(sin)}, con interés: {len(con)})\n")

    print("  === SIN INTERÉS ===")
    if sin:
        _print_group(sin)
    else:
        print("    (none)")

    print("\n  === CON INTERÉS ===")
    if con:
        _print_group(con)
    else:
        print("    (none)")


def _print_group(plans: list[PaymentPlan]) -> None:
    header = f"    {'Card':<18} {'Issuer':<14} {'Cuotas':>6}  {'Rate':>8}  {'Cuota':>14}"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for p in plans:
        issuer = p.card_issuer or "-"
        rate = f"{p.interest_rate * 100:.2f}%"
        cuota = f"${p.amount_per_installment:,.0f}"
        print(f"    {p.card_system:<18} {issuer:<14} {p.installment_count:>6}  {rate:>8}  {cuota:>14}")
