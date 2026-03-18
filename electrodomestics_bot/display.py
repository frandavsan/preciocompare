from typing import Optional

from .models import ProductResult


def format_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    return f"{round(price):,}".replace(",", ".")


def print_results(query: str, all_results: dict[str, list[ProductResult]]) -> None:
    width = 68
    line = "-" * width

    print(f"\n  Query: {query}\n")

    for store, products in all_results.items():
        print(line)
        if not products:
            print(f"  {store.upper()}  —  no results found")
            continue

        print(f"  {store.upper()}  ({len(products)} result{'s' if len(products) != 1 else ''})")
        print(line)

        for i, r in enumerate(products, 1):
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
            print(f"     International: {r.international}")
            print(f"     URL      : {r.url}")
            if i < len(products):
                print()

    print(line + "\n")
