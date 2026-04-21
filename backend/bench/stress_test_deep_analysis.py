"""
Deep-dive analysis of specific edge cases found in the stress test.
Focuses on: missed matches, dedup behavior, and query noise contamination.
"""
import asyncio
import sys
import io

sys.path.insert(0, r'C:\Users\Frand\Documents\Bots\ElectrodomesticsBot')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from electrodomestics_bot.fetching.service import search_products
from electrodomestics_bot.processing.matching import (
    dedup_results, group_results, extract_keys, _keys_match
)


def format_price(price):
    if price is None:
        return "?"
    return f"${price / 1000:.0f}k"


async def investigate(label: str, query: str):
    print(f"\n{'='*60}")
    print(f"INVESTIGATION: {label}")
    print(f"Query: '{query}'")
    print('='*60)

    raw = await search_products(query, detail=False, use_cache=False, check_shipping=False)
    deduped = dedup_results(raw)

    # Show extract_keys for each product
    print("\n--- extract_keys per product ---")
    for store, ssr in deduped.items():
        for prod in ssr.products:
            keys = extract_keys(prod.name)
            print(f"  [{store}] {prod.name[:60]}")
            print(f"    keys: {sorted(keys)}")

    # Show pairwise key matching
    print("\n--- pairwise _keys_match() results ---")
    all_prods = []
    for store, ssr in deduped.items():
        for prod in ssr.products:
            all_prods.append((store, prod, extract_keys(prod.name)))

    for i, (si, pi, ki) in enumerate(all_prods):
        for j, (sj, pj, kj) in enumerate(all_prods):
            if j <= i or si == sj:
                continue
            match = _keys_match(ki, kj)
            if match:
                print(f"  MATCH: [{si}] {pi.name[:40]} <-> [{sj}] {pj.name[:40]}")
                print(f"    overlap: {sorted(ki & kj)}")
            else:
                overlap = ki & kj
                ratio = len(overlap) / min(len(ki), len(kj)) if min(len(ki), len(kj)) > 0 else 0
                print(f"  NO MATCH (ratio={ratio:.2f}): [{si}] {pi.name[:35]} <-> [{sj}] {pj.name[:35]}")
                print(f"    overlap: {sorted(overlap)}")
                print(f"    keys_i: {sorted(ki)}")
                print(f"    keys_j: {sorted(kj)}")

    groups = group_results(deduped)
    print(f"\n--- Groups formed: {len(groups)} ---")
    for g in groups:
        print(f"  [{len(g.products)} stores] {g.canonical_name[:60]}")
        for store, prod in g.products.items():
            print(f"    {store}: {prod.name[:55]} {format_price(prod.price)}")


async def investigate_dedup(label: str, query: str):
    """Investigate dedup behavior specifically."""
    print(f"\n{'='*60}")
    print(f"DEDUP INVESTIGATION: {label}")
    print(f"Query: '{query}'")
    print('='*60)

    raw = await search_products(query, detail=False, use_cache=False, check_shipping=False)

    for store, ssr in raw.items():
        if not ssr.products:
            continue
        print(f"\n  [{store}] raw: {len(ssr.products)} products")
        for p in ssr.products:
            print(f"    {p.name[:60]} {format_price(p.price)}")
            print(f"      keys: {sorted(extract_keys(p.name))}")

    deduped = dedup_results(raw)
    print("\n  After dedup:")
    for store, ssr in deduped.items():
        if not ssr.products:
            continue
        print(f"  [{store}]: {len(ssr.products)} products")


async def main():
    # 1. WRM42HK: Fravega not grouped with Castillo+Oncity
    await investigate(
        "WRM42HK — Fravega missed from multi-store group",
        "WRM42HK"
    )

    # 2. S4-W12JA31A: Castillo not grouped with Fravega+Megatone
    await investigate(
        "S4-W12JA31A — Castillo missed from multi-store group",
        "S4-W12JA31A"
    )

    # 3. WW95AA046BXU: Two Fravega products for same Samsung washer
    await investigate_dedup(
        "WW95AA046BXU — duplicate Fravega listing",
        "WW95AA046BXU"
    )

    # 4. MF200: "MF200" brand family matching — 6 groups, 3 cross-store
    await investigate(
        "MF200 — broad brand-family query matching",
        "MF200"
    )

    # 5. Galaxy A16 — same query returns 4G and 5G variants; check grouping
    await investigate(
        "Galaxy A16 — two sub-models (4G + 5G) should form separate groups",
        "Galaxy A16"
    )

    # 6. S26 Ultra — noise products (accessories) mixed in
    await investigate_dedup(
        "S26 Ultra — accessories mixed in, dedup for noise items",
        "S26 Ultra"
    )


if __name__ == "__main__":
    asyncio.run(main())
