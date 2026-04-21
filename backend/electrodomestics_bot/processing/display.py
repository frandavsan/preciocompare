from typing import Optional

from ..models import ProductResult, StoreSearchResult
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
    all_results: dict[str, StoreSearchResult],
    limit: Optional[int] = None,
) -> None:
    print(f"\n  Query: {_B}{query}{_R}\n")

    for store, ssr in all_results.items():
        products = ssr.products
        print(f"{_DIM}{_LINE}{_R}")
        if not products:
            if ssr.status == "error":
                print(f"  {_CYAN}{_B}{store.upper()}{_R}  {_RED}—  error (store unreachable){_R}")
            elif ssr.status == "timeout":
                print(f"  {_CYAN}{_B}{store.upper()}{_R}  {_RED}—  timed out{_R}")
            else:
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
    print(f"  {_DIM}{'Store':<12}{'Price':>12}    {'Best installment':<20}{'Shipping':<12}Link{_R}")
    print(f"{_DIM}{_LINE}{_R}")

    for store, prod in sorted(group.products.items()):
        is_cheapest = store == cheapest_store[0]
        price_str = format_price(prod.price)

        if prod.installments:
            best = max(prod.installments, key=lambda i: i.count)
            inst_plain = f"{best.count}x {format_price(best.amount)}"
            inst_col   = f"{_YLW}{inst_plain}{_R}"
        else:
            inst_plain = "—"
            inst_col   = f"{_DIM}—{_R}"

        shipping_col = f"{_GREEN}FREE{_R}        " if prod.free_shipping else f"{_DIM}—{_R}           "

        store_col = (f"{_CYAN}{_B}{store}{_R}" if is_cheapest else store)
        price_col = (f"{_BGRN}{price_str}{_R}"  if is_cheapest else f"{_GREEN}{price_str}{_R}")

        store_pad = " " * max(0, 12 - len(store))
        price_pad = " " * max(0, 12 - len(price_str))
        inst_pad  = " " * max(0, 20 - len(inst_plain))

        print(f"  {store_col}{store_pad}{price_pad}{price_col}    {inst_col}{inst_pad}{shipping_col}{_DIM}{prod.url}{_R}")

    print(f"{_DIM}{_LINE}{_R}")
    cheapest_price = format_price(cheapest_store[1].price)
    print(f"  Cheapest: {_CYAN}{_B}{cheapest_store[0]}{_R}  {_BGRN}${cheapest_price}{_R}")

    prices = [p.price for p in group.products.values() if p.price is not None]
    if len(prices) > 1:
        avg = sum(prices) / len(prices)
        cheapest_val = cheapest_store[1].price
        most_expensive_val = max(prices)
        cheap_pct  = (cheapest_val - avg) / avg * 100
        exp_pct    = (most_expensive_val - avg) / avg * 100
        spread_pct = (cheapest_val - most_expensive_val) / most_expensive_val * 100
        _W = 30  # label column width
        avg_str    = format_price(avg)
        cheap_str  = f"{cheap_pct:+.1f}%"
        exp_str    = f"{exp_pct:+.1f}%"
        spread_str = f"{spread_pct:+.1f}%"
        print(f"  {_DIM}{'Average price:':<{_W}}{_R}{_GREEN}{avg_str:>10}{_R}")
        print(f"  {_DIM}{'Cheapest vs average:':<{_W}}{_R}{_BGRN}{cheap_str:>10}{_R}")
        print(f"  {_DIM}{'Most expensive vs average:':<{_W}}{_R}{_YLW}{exp_str:>10}{_R}")
        print(f"  {_DIM}{'Cheapest vs most expensive:':<{_W}}{_R}{_BGRN}{spread_str:>10}{_R}")
    print()
