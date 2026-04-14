"""
Compare the main-tool and pricing-tool Cetrogar installment extractors.

Runs both against the same PDP URL and diffs their sin-interés output.
Purpose: decide whether the main tool can safely migrate onto fetch_all_plans.

We compare against the main tool's DETAIL mode (_fetch_installments), since
that's the apples-to-apples path: same source (PDP HTML) vs. fetch_all_plans'
JSON endpoint. Both return card-level data; the fast path (search page) does
not have card names, so it can't be compared directly.

--- VERDICT (2026-04-15 run on Philips 65PUD8100, base_price=1,319,999) ---
Amounts:   perfect match on all common count-tiers (6x, 9x, 12x).
Counts:    JSON is a strict superset — 5 tiers (1x, 3x, 6x, 9x, 12x) vs.
           main tool's 3 tiers. PDP HTML doesn't display 1x/3x rows.
Cards:     JSON has vastly richer issuer coverage on every tier (30+ banks
           per tier vs. 2-8 from PDP logos). Name variants differ
           (e.g. "Santander Rio" vs "Santander", "Tarjeta Naranja" vs
           "NaranjaX", "Nación" vs "BNA") — normalization layer needed
           for UI parity.
Oddity:    Main tool shows Cabal on 9x; JSON does not. Likely the PDP logo
           is aspirational (Cabal participates in some tier, not 9x
           specifically on this product). Low-impact.

Conclusion: JSON is strictly richer data-wise. Migration is SAFE from a
data-completeness standpoint. The real tradeoff is performance — main tool
currently reads installments from the search-results page with ZERO extra
requests. Migrating means per-product PDP + JSON fetches, which would slow
broad queries noticeably. Recommendation: keep extractors separate for now;
revisit unification if a plans cache lands or the main tool moves to
detail=True anyway.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from electrodomestics_bot.fetching.adapters.cetrogar import CetrogarAdapter
from electrodomestics_bot.pricing.platforms.magento import fetch_all_plans


async def main(product_url: str, base_price: float) -> None:
    print(f"\nPDP: {product_url}")
    print(f"Base price: ${base_price:,.0f}\n")

    # --- Main tool (detail mode — PDP HTML scrape) ---
    main_installments = await CetrogarAdapter()._fetch_installments(product_url)
    main_norm: set[tuple[int, int, tuple[str, ...]]] = set()
    for ins in main_installments:
        # Round amount to handle minor float jitter
        main_norm.add((ins.count, round(ins.amount), tuple(sorted(ins.cards))))

    # --- Pricing tool (JSON endpoint) ---
    plans = await fetch_all_plans(product_url, base_price)
    sin_plans = [p for p in plans if not p.has_interest]
    # Collapse issuer-bearing rows into their card system for fair comparison,
    # since main tool's _fetch_installments groups by card logo, not by issuer.
    pricing_groups: dict[tuple[int, int], set[str]] = {}
    for p in sin_plans:
        key = (p.installment_count, round(p.amount_per_installment))
        # Include issuer name to match main tool's "logo names" model
        label = p.card_issuer if p.card_issuer else p.card_system
        pricing_groups.setdefault(key, set()).add(label)

    pricing_norm: set[tuple[int, int, tuple[str, ...]]] = {
        (count, amount, tuple(sorted(cards)))
        for (count, amount), cards in pricing_groups.items()
    }

    print(f"Main tool (_fetch_installments): {len(main_installments)} sin-interés rows")
    for count, amount, cards in sorted(main_norm):
        print(f"  {count}x  ${amount:>10,}  cards={list(cards)}")

    print(f"\nPricing tool (fetch_all_plans -> filter sin): "
          f"{len(sin_plans)} raw plans, {len(pricing_norm)} distinct (count, amount) groups")
    for count, amount, cards in sorted(pricing_norm):
        print(f"  {count}x  ${amount:>10,}  cards={list(cards)}")

    # --- Diff by (count, amount) ---
    main_ca = {(c, a) for c, a, _ in main_norm}
    pricing_ca = {(c, a) for c, a, _ in pricing_norm}

    only_main = main_ca - pricing_ca
    only_pricing = pricing_ca - main_ca
    common = main_ca & pricing_ca

    print(f"\n--- DIFF by (count, amount) ---")
    print(f"Common: {len(common)}")
    print(f"Only in MAIN:    {sorted(only_main)}")
    print(f"Only in PRICING: {sorted(only_pricing)}")

    # --- Card coverage diff on common (count, amount) ---
    print(f"\n--- Card coverage on common rows ---")
    main_by_ca = {(c, a): set(cards) for c, a, cards in main_norm}
    pricing_by_ca = {(c, a): set(cards) for c, a, cards in pricing_norm}
    for key in sorted(common):
        m_cards = main_by_ca[key]
        p_cards = pricing_by_ca[key]
        if m_cards == p_cards:
            status = "SAME"
        else:
            status = f"DIFF — only_main={m_cards - p_cards}  only_pricing={p_cards - m_cards}"
        print(f"  {key[0]}x ${key[1]:,}:  {status}")


if __name__ == "__main__":
    # Philips 65PUD8100 — used as the reference in prior verification
    URL = "https://www.cetrogar.com.ar/smart-tv-65-philips-4k-65pud8100-77-titan-os.html"
    PRICE = 1319999.0
    asyncio.run(main(URL, PRICE))
