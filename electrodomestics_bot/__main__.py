import asyncio
import logging
import sys
import time

from .display import print_results
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

    query = input("Model name or SKU: ").strip()
    if not query:
        print("No input provided.")
        sys.exit(1)
    if len(query) < 3:
        print("Query too short — please enter at least 3 characters.")
        sys.exit(1)

    detail_input = input("Include card details per installment? (slower) [y/N]: ").strip().lower()
    detail = detail_input in ("y", "yes")

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
            results = await search_products(query, detail, use_cache=use_cache)
        finally:
            task.cancel()
        return results, time.perf_counter() - start

    try:
        all_results, elapsed = asyncio.run(_fetch_with_progress())
        print_results(query, all_results, limit=_PREVIEW_LIMIT)
        print(f"  Completed in {elapsed:.1f}s\n")

        stores_with_more = [name for name, products in all_results.items() if len(products) > _PREVIEW_LIMIT]
        if stores_with_more:
            options = " / ".join(stores_with_more) + " / all / n"
            choice = input(f"  Show more? [{options}]: ").strip().lower()
            if choice == "all":
                print_results(query, all_results)
            elif choice in all_results and len(all_results[choice]) > _PREVIEW_LIMIT:
                print_results(query, {choice: all_results[choice]})
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
