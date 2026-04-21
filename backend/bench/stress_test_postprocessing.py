"""
Step 2+3+4: Derive queries from Fravega listings, run through the bot's
post-processing layer, and analyze grouping/matching output for bugs.
"""
import asyncio
import sys
import time
import io

sys.path.insert(0, r'C:\Users\Frand\Documents\Bots\ElectrodomesticsBot')

# Force UTF-8 output on Windows to avoid charmap encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from electrodomestics_bot.fetching.service import search_products
from electrodomestics_bot.processing.matching import dedup_results, group_results, extract_keys

# ---------------------------------------------------------------------------
# Queries derived from real Fravega listings — model code style, as a user
# would type. Rules: drop brand/category words, keep model code or SKU.
# ---------------------------------------------------------------------------

QUERIES = [
    # HELADERAS — model codes from Fravega listings
    ("heladeras", "PHCT225B"),           # Philco ciclica 199L
    ("heladeras", "PHSB470XD2"),         # Philco No Frost Side by Side
    ("heladeras", "WRM42HK"),            # Whirlpool Inverter No Frost 386L
    ("heladeras", "HGF388AFB"),          # Gafa con freezer 374L
    ("heladeras", "HGNF333P"),           # Gafa No Frost 356L Inverter

    # LAVARROPAS
    ("lavarropas", "LCFDR0814SB0"),      # Drean 8kg 1400RPM
    ("lavarropas", "WW95AA046BXU"),      # Samsung 9.5Kg
    ("lavarropas", "WW65A4000SU"),       # Samsung 6.5Kg Carga Frontal
    ("lavarropas", "PHLF8014PI2"),       # Philco Predicta Inverter 8Kg
    ("lavarropas", "MF200"),             # Midea Inverter WiFi 8kg

    # TELEVISORES (skip the noisy search results, use safe model codes)
    ("televisores", "43S5K"),            # TCL 43 QLED Google TV
    ("televisores", "32S5K"),            # TCL 32 QLED Google TV
    ("televisores", "QN90D"),            # Samsung 43 Neo QLED 4K

    # CELULARES — Samsung model codes
    ("celulares", "S26 Ultra"),          # Samsung S26 Ultra
    ("celulares", "Galaxy A36"),         # Samsung Galaxy A36 5G
    ("celulares", "Galaxy A56"),         # Samsung Galaxy A56 5G
    ("celulares", "Galaxy A16"),         # Samsung Galaxy A16 (two sub-models)

    # NOTEBOOKS
    ("notebooks", "XR2"),               # Exo Smart XR2
    ("notebooks", "15-fc0235la"),        # HP 15 AMD Ryzen 3
    ("notebooks", "83K100T2AR"),         # Lenovo Ideapad Slim 3
    ("notebooks", "E1504GA-BQ061W"),     # ASUS Vivobook Go 15
    ("notebooks", "UM3406"),             # ASUS Zenbook 14 OLED

    # AIRES ACONDICIONADOS — model codes
    ("aires", "PHIN37HA2AN"),           # Philco Inverter 3200F
    ("aires", "BS26WCDW"),              # BGH 2400F
    ("aires", "BSI55WCNX"),             # BGH Inverter 4730F
    ("aires", "AR40F12C0AM2BG"),        # Samsung Inverter 2500F
    ("aires", "S4-W12JA31A"),           # LG DualCool WiFi 3000F
]

TIMEOUT_SECONDS = 90


def format_price(price):
    if price is None:
        return "?"
    return f"${price / 1000:.0f}k"


async def run_query(category: str, query: str) -> dict:
    """Run one query through the full pipeline with a timeout."""
    start = time.time()
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            raw = await search_products(query, detail=False, use_cache=False, check_shipping=False)
    except TimeoutError:
        elapsed = time.time() - start
        return {"query": query, "category": category, "timed_out": True, "elapsed": elapsed}
    except Exception as e:
        elapsed = time.time() - start
        return {"query": query, "category": category, "error": str(e), "elapsed": elapsed}

    elapsed = time.time() - start
    deduped = dedup_results(raw)
    groups = group_results(deduped)

    # Summarize per-store counts
    store_counts = {
        store: len(ssr.products)
        for store, ssr in deduped.items()
        if ssr.products
    }

    return {
        "query": query,
        "category": category,
        "elapsed": elapsed,
        "timed_out": False,
        "error": None,
        "store_counts": store_counts,
        "groups": groups,
        "raw": deduped,
    }


def analyze_groups(result: dict) -> list[str]:
    """Identify potential issues in grouping output."""
    issues = []
    if not result.get("groups"):
        return issues

    groups = result["groups"]
    query = result["query"]

    # 1. Products that appear in only 1 store but should appear in more
    #    (heuristic: if any multi-store group exists, lone-store groups for same product are suspicious)
    multi_store_groups = [g for g in groups if len(g.products) > 1]
    single_store_groups = [g for g in groups if len(g.products) == 1]

    # 2. Groups where the canonical name doesn't seem to match the query
    for g in groups:
        qkeys = extract_keys(query)
        gkeys = g.fingerprint
        overlap = qkeys & gkeys
        if len(qkeys) > 1 and len(overlap) == 0:
            issues.append(f"FALSE MATCH candidate: group '{g.canonical_name[:60]}' shares no keys with query")

    # 3. Check if a store has results but didn't make it into any multi-store group
    stores_in_multi = set()
    for g in multi_store_groups:
        stores_in_multi.update(g.products.keys())

    stores_with_results = set(result.get("store_counts", {}).keys())
    isolated_stores = stores_with_results - stores_in_multi
    if isolated_stores and multi_store_groups:
        for store in isolated_stores:
            # Get the first product name for context
            ssr = result["raw"].get(store)
            if ssr and ssr.products:
                first_prod = ssr.products[0].name[:60]
                issues.append(
                    f"MISSED MATCH: '{store}' has results but not in any multi-store group "
                    f"(e.g. '{first_prod}')"
                )

    # 4. Groups with unusually disparate prices (beyond the 2x guard in the algorithm)
    for g in multi_store_groups:
        prices = [(s, p.price) for s, p in g.products.items() if p.price is not None]
        if len(prices) >= 2:
            prices.sort(key=lambda x: x[1])
            low_s, low_p = prices[0]
            high_s, high_p = prices[-1]
            ratio = high_p / low_p if low_p > 0 else 0
            if ratio > 1.5:
                issues.append(
                    f"PRICE SPREAD in group '{g.canonical_name[:50]}': "
                    f"{low_s}={format_price(low_p)} vs {high_s}={format_price(high_p)} "
                    f"(ratio {ratio:.1f}x)"
                )

    # 5. Groups that contain products from the same store (dedup should have caught this)
    for g in groups:
        store_counts_in_group = {}
        for store in g.products:
            store_counts_in_group[store] = store_counts_in_group.get(store, 0) + 1
        for store, count in store_counts_in_group.items():
            if count > 1:
                issues.append(f"DEDUP FAILURE: store '{store}' appears {count}x in group '{g.canonical_name[:50]}'")

    return issues


def print_result(result: dict) -> list[str]:
    """Print formatted result and return list of issues found."""
    query = result["query"]
    cat = result["category"]
    elapsed = result.get("elapsed", 0)

    print(f'\nQUERY: "{query}" [{cat}] ({elapsed:.1f}s)')

    if result.get("timed_out"):
        print(f"  *** TIMED OUT after {elapsed:.0f}s — skipped")
        return ["TIMEOUT"]

    if result.get("error"):
        print(f"  *** ERROR: {result['error']}")
        return [f"ERROR: {result['error']}"]

    store_counts = result.get("store_counts", {})
    groups = result.get("groups", [])

    if not store_counts:
        print("  No results from any store.")
        return []

    # Format store summary
    stores_str = ", ".join(f"{s}({n})" for s, n in sorted(store_counts.items()))
    print(f"  Stores with results: {stores_str}")
    print(f"  Groups formed: {len(groups)}")

    for i, g in enumerate(groups, 1):
        store_count = len(g.products)
        parts = []
        for store, prod in sorted(g.products.items()):
            parts.append(f'{store}="{prod.name[:45]}" {format_price(prod.price)}')
        stores_label = f"{store_count} store{'s' if store_count > 1 else ''}"
        print(f"    Group {i} [{stores_label}]: {' | '.join(parts)}")
        if store_count == 1:
            print(f"      ^ single-store only")

    issues = analyze_groups(result)
    if issues:
        print(f"  Issues:")
        for issue in issues:
            print(f"    - {issue}")

    return issues


async def main():
    print("=" * 70)
    print("POST-PROCESSING STRESS TEST")
    print("Running queries through full pipeline (no cache, no shipping)")
    print("=" * 70)

    all_issues: list[tuple[str, str, list[str]]] = []

    for category, query in QUERIES:
        result = await run_query(category, query)
        issues = print_result(result)
        if issues:
            all_issues.append((category, query, issues))

    # -----------------------------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL ISSUES")
    print("=" * 70)

    if not all_issues:
        print("No issues found across all queries.")
    else:
        for cat, query, issues in all_issues:
            print(f'\n[{cat}] "{query}":')
            for issue in issues:
                print(f"  - {issue}")

    # Count by type
    all_flat = [i for _, _, issues in all_issues for i in issues]
    timeout_count = sum(1 for i in all_flat if "TIMEOUT" in i)
    missed_count = sum(1 for i in all_flat if "MISSED" in i)
    false_count = sum(1 for i in all_flat if "FALSE" in i)
    price_count = sum(1 for i in all_flat if "PRICE" in i)
    dedup_count = sum(1 for i in all_flat if "DEDUP" in i)

    print(f"\nTotals: {len(QUERIES)} queries, {len(all_issues)} with issues")
    print(f"  Timeouts: {timeout_count}")
    print(f"  Missed matches: {missed_count}")
    print(f"  False matches: {false_count}")
    print(f"  Price spread anomalies: {price_count}")
    print(f"  Dedup failures: {dedup_count}")


if __name__ == "__main__":
    asyncio.run(main())
