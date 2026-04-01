from typing import Optional

from ..models import ProductResult
from .matching import ProductGroup


_WIDTH = 68
_LINE = "-" * _WIDTH

# ANSI color codes
_R     = "\033[0m"    # reset
_B     = "\033[1m"    # bold
_DIM   = "\033[2m"    # dim
_CYAN  = "\033[36m"   # store names / headers
_GREEN = "\033[32m"   # prices, free shipping, available
_BGRN  = "\033[92m"   # bright green — cheapest highlight
_YLW   = "\033[33m"   # cuotas
_RED   = "\033[31m"   # unavailable


def format_price(price: Optional[float]) -> str:
    if price is None:
        return "N/A"
    return f"{round(price):,}".replace(",", ".")


def print_results(
    query: str,
    all_results: dict[str, list[ProductResult]],
    limit: Optional[int] = None,
) -> None:
    print(f"\n  Query: {_B}{query}{_R}\n")

    for store, products in all_results.items():
        print(f"{_DIM}{_LINE}{_R}")
        if not products:
            print(f"  {_CYAN}{_B}{store.upper()}{_R}  {_DIM}—  no results found{_R}")
            continue

        n = len(products)
        shown = products[:limit] if limit and n > limit else products
        header = f"showing {limit} of {n}" if limit and n > limit else f"{n} result{'s' if n != 1 else ''}"
        print(f"  {_CYAN}{_B}{store.upper()}{_R}  {_DIM}({header}){_R}")
        print(f"{_DIM}{_LINE}{_R}")

        for i, r in enumerate(shown, 1):
            print(f"  {i}. {_B}{r.name}{_R}")
            print(f"  {_DIM}   SKU      : {r.sku or 'N/A'}{_R}")
            print(f"  {_DIM}   Price    : {_R}{_GREEN}{format_price(r.price)}{_R}")
            print(f"  {_DIM}   Currency : {r.currency}{_R}")
            if r.installments:
                for inst in r.installments:
                    cards_str = f" {_DIM}({', '.join(inst.cards)}){_R}" if inst.cards else ""
                    print(f"  {_DIM}   Cuotas   : {_R}{_YLW}{inst.count}x {format_price(inst.amount)}{_R}{_DIM} sin interes{_R}{cards_str}")
            else:
                print(f"  {_DIM}   Cuotas   : N/A{_R}")
            avail_str = f"{_GREEN}True{_R}"  if r.available      else f"{_RED}False{_R}"
            ship_str  = f"{_GREEN}True{_R}"  if r.free_shipping  else f"{_DIM}False{_R}"
            intl_str  = (f"{_DIM}-{_R}"      if r.international is None
                         else (f"{_YLW}True{_R}" if r.international else f"{_DIM}False{_R}"))
            print(f"  {_DIM}   Available    : {_R}{avail_str}")
            print(f"  {_DIM}   Free shipping: {_R}{ship_str}")
            print(f"  {_DIM}   International: {_R}{intl_str}")
            print(f"  {_DIM}   URL      : {r.url}{_R}")
            if i < len(shown):
                print()

        if limit and n > limit:
            print(f"\n  {_DIM}... and {n - limit} more result{'s' if n - limit != 1 else ''}{_R}")

    print(f"{_DIM}{_LINE}{_R}\n")


def print_comparison(group: ProductGroup) -> None:
    cheapest_store = min(
        group.products.items(),
        key=lambda kv: kv[1].price if kv[1].price is not None else float("inf"),
    )

    print(f"\n  {_B}Product:{_R} {group.canonical_name}")
    print(f"{_DIM}{_LINE}{_R}")
    print(f"  {_DIM}{'Store':<12}{'Price':>12}    {'Best installment':<26}Shipping{_R}")
    print(f"{_DIM}{_LINE}{_R}")

    for store, prod in sorted(group.products.items()):
        is_cheapest = store == cheapest_store[0]
        price_str = format_price(prod.price)

        if prod.installments:
            best = max(prod.installments, key=lambda i: i.count)
            cards_plain = f" ({', '.join(best.cards)})" if best.cards else ""
            inst_plain  = f"{best.count}x {format_price(best.amount)}{cards_plain}"
            cards_col   = f" {_DIM}({', '.join(best.cards)}){_R}" if best.cards else ""
            inst_col    = f"{_YLW}{best.count}x {format_price(best.amount)}{_R}{cards_col}"
        else:
            inst_plain = "—"
            inst_col   = f"{_DIM}—{_R}"

        shipping_col = f"{_GREEN}FREE{_R}" if prod.free_shipping else f"{_DIM}—{_R}"

        # Colored variants — padding computed from plain-text lengths
        store_col = (f"{_CYAN}{_B}{store}{_R}" if is_cheapest else store)
        price_col = (f"{_BGRN}{price_str}{_R}"  if is_cheapest else f"{_GREEN}{price_str}{_R}")

        store_pad = " " * max(0, 12 - len(store))
        price_pad = " " * max(0, 12 - len(price_str))
        inst_pad  = " " * max(0, 26 - len(inst_plain))

        print(f"  {store_col}{store_pad}{price_pad}{price_col}    {inst_col}{inst_pad}{shipping_col}")

    print(f"{_DIM}{_LINE}{_R}")
    cheapest_price = format_price(cheapest_store[1].price)
    print(f"  Cheapest: {_CYAN}{_B}{cheapest_store[0]}{_R}  {_BGRN}${cheapest_price}{_R}\n")
