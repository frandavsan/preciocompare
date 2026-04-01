import asyncio
import logging
import sys
import time

from .display import print_comparison, print_results
from .matching import dedup_results, group_results
from .service import search_products

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s — %(message)s")

_PREVIEW_LIMIT = 3


def main() -> None:
    # Allow `python -m electrodomestics_bot refresh` as a shorthand.
    if sys.argv[1:] == ["refresh"]:
        from .refresh import main as refresh_main
        refresh_main()
        return

    use_cache = "--cache" in sys.argv
    raw_mode = "--raw" in sys.argv

    query = input("Model name or SKU: ").strip()
    if not query:
        print("No input provided.")
        sys.exit(1)
    if len(query) < 3:
        print("Query too short — please enter at least 3 characters.")
        sys.exit(1)

    detail_input = input("Include card details per installment? (slower) [y/N]: ").strip().lower()
    detail = detail_input in ("y", "yes")

    shipping_input = input("Shipping to CABA? [Y/n]: ").strip().lower()
    check_shipping = shipping_input not in ("n", "no")

    if use_cache:
        print("  [cache mode — reading from DB]\n")

    async def _fetch_with_progress():
        async def _ticker():
            while True:
                print("  Fetching...")
                await asyncio.sleep(5)

        task = asyncio.create_task(_ticker())
        start = time.perf_counter()
        try:
            results = await search_products(query, detail, use_cache=use_cache, check_shipping=check_shipping)
        finally:
            task.cancel()
        return results, time.perf_counter() - start

    try:
        all_results, elapsed = asyncio.run(_fetch_with_progress())
        all_results = dedup_results(all_results)
        print_results(query, all_results, limit=_PREVIEW_LIMIT)
        print(f"  Completed in {elapsed:.1f}s\n")

        stores_with_results = [name for name, products in all_results.items() if products]
        if stores_with_results:
            options = " / ".join(stores_with_results) + " / all / n"
            choice = input(f"  Show more? [{options}]: ").strip().lower()
            if choice == "all":
                print_results(query, all_results)
            elif choice in all_results and all_results[choice]:
                print_results(query, {choice: all_results[choice]})

        if not raw_mode and stores_with_results:
            groups = group_results(all_results)
            cross_store = [g for g in groups if len(g.products) >= 2]
            if cross_store:
                print(f"  Found {len(cross_store)} product{'s' if len(cross_store) != 1 else ''} available in multiple stores:\n")
                for idx, g in enumerate(cross_store, 1):
                    stores_list = ", ".join(sorted(g.products.keys()))
                    print(f"    [{idx}] {g.canonical_name}  ({stores_list})")
                print(f"    [n] Skip\n")
                sel = input(f"  Compare [1-{len(cross_store)}/n]: ").strip().lower()
                if sel.isdigit() and 1 <= int(sel) <= len(cross_store):
                    print_comparison(cross_store[int(sel) - 1])
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
