from typing import Optional

from .models import ProductResult


def format_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    return f"{round(price):,}".replace(",", ".")


def print_results(
    query: str,
    all_results: dict[str, list[ProductResult]],
    limit: Optional[int] = None,
) -> None:
    width = 68
    line = "-" * width

    print(f"\n  Query: {query}\n")

    for store, products in all_results.items():
        print(line)
        if not products:
            print(f"  {store.upper()}  —  no results found")
            continue

        n = len(products)
        shown = products[:limit] if limit and n > limit else products
        header = f"showing {limit} of {n}" if limit and n > limit else f"{n} result{'s' if n != 1 else ''}"
        print(f"  {store.upper()}  ({header})")
        print(line)

        for i, r in enumerate(shown, 1):
            print(f"  {i}. {r.name}")
            print(f"     SKU      : {r.sku or 'N/A'}")
            print(f"     Price    : {format_price(r.price)}")
            print(f"     Currency : {r.currency}")
            if r.installments:
                for inst in r.installments:
                    cards_str = f" ({', '.join(inst.cards)})" if inst.cards else ""
                    print(f"     Cuotas   : {inst.count}x {format_price(inst.amount)} sin interes{cards_str}")
            else:
                print(f"     Cuotas   : N/A")
            print(f"     Available    : {r.available}")
            print(f"     Free shipping: {r.free_shipping}")
            print(f"     International: {'-' if r.international is None else r.international}")
            print(f"     URL      : {r.url}")
            if i < len(shown):
                print()

        if limit and n > limit:
            print(f"\n  ... and {n - limit} more result{'s' if n - limit != 1 else ''}")

    print(line + "\n")
