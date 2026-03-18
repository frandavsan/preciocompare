import asyncio
import sys

from .display import print_results
from .service import search_products


def main() -> None:
    # Allow `python -m electrodomestics_bot refresh` as a shorthand.
    if sys.argv[1:] == ["refresh"]:
        from .refresh import main as refresh_main
        refresh_main()
        return

    query = input("Model name or SKU: ").strip()
    if not query:
        print("No input provided.")
        sys.exit(1)
    if len(query) < 3:
        print("Query too short — please enter at least 3 characters.")
        sys.exit(1)

    detail_input = input("Include card details per installment? (slower) [y/N]: ").strip().lower()
    detail = detail_input in ("y", "yes")

    try:
        all_results = asyncio.run(search_products(query, detail))
        print_results(query, all_results)
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
