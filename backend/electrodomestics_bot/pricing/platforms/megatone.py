"""
Megatone plan extraction — sin + con interés plans.

Reuses the fetching adapter's `_fetch_plans_batch` to issue parallel
`retornarplanes` calls per card network, per bank promo, and one
comprehensive call (IdTarjeta=0) used to backfill cards with no dedicated
endpoint (Mercado Pago).

Each plan row in the response carries `cuotas`, `tasaDirecta` (total
markup as a percentage — `10` means 10%, `0` is sin-interés), `valor`
(amount per installment, integer pesos), and `tarjeta` (the API's card
label, used only for the comprehensive call's MP backfill). We convert
tasaDirecta to a decimal rate (/100) and compute the amount from price
+ rate so it stays consistent with the spreadsheet's other columns.
"""

from __future__ import annotations

import asyncio

from ...fetching.adapters import ADAPTERS
from ...fetching.platforms.megatone import MegatoneAdapter
from ..models import PaymentPlan


# Megatone bank promo display name → canonical issuer key used by card_mapping._LABEL_MAP.
_BANK_TO_ISSUER: dict[str, str] = {
    "BNA": "nacion",
    "Banco Galicia": "galicia",
    "BBVA": "bbva",
    "Banco Santander": "santander",
}

# Issuer keys we fan generic Visa/Mastercard/AmEx/Cabal plans out to. Megatone's
# generic-network promos are available to any cardholder regardless of issuer, so
# we emit one copy per template-relevant issuer. Bank-specific calls then override
# via the lowest-rate dedup when they offer a better deal.
_BANK_EXPAND_ISSUERS: frozenset[str] = frozenset({
    "macro", "nacion", "galicia", "bbva", "santander", "hipotecario",
})

# Card systems that banks issue — the only ones we fan out. Cabal is bank-issued
# in Argentina (Cabal is owned by a consortium of Argentine banks).
_BANK_EXPANDABLE_CARDS: frozenset[str] = frozenset({
    "Visa", "Mastercard", "American Express", "Cabal",
})

# Comprehensive-call card name → canonical PaymentPlan card_system.
# Only entries that are NOT covered by a dedicated _CARD_CALLS slot belong here —
# the comprehensive call understates counts for cards that have one.
_COMPREHENSIVE_CARD_MAP: list[tuple[str, str]] = [
    ("MERCADO PAGO", "Mercado Pago"),
]

# Card labels in the API that the website hides (e.g. NATIVA isn't shown anywhere).
_COMPREHENSIVE_BLACKLIST: frozenset[str] = frozenset({"NATIVA"})


def _find_adapter() -> MegatoneAdapter | None:
    for adapter in ADAPTERS:
        if isinstance(adapter, MegatoneAdapter):
            return adapter
    return None


def _comprehensive_card(label: str) -> str | None:
    upper = label.upper()
    if any(bl in upper for bl in _COMPREHENSIVE_BLACKLIST):
        return None
    for keyword, display in _COMPREHENSIVE_CARD_MAP:
        if keyword in upper:
            return display
    return None


async def fetch_all_plans(sku: str, base_price: float) -> list[PaymentPlan]:
    """
    Fetch sin- and con-interés payment plans for a Megatone SKU.

    Returns one PaymentPlan per (card_system, issuer, count, has_interest)
    across the standard networks plus issuer-tagged Visa rows for bank
    promos that exceed the base Visa sin-interés count, plus Mercado Pago
    plans recovered from the comprehensive-call response.
    """
    if base_price <= 0 or not sku:
        return []

    adapter = _find_adapter()
    if adapter is None:
        return []

    skus = [sku]
    bank_ids = list(adapter._BANK_PROMOS.keys())

    card_results, comprehensive, bank_results = await asyncio.gather(
        asyncio.gather(*[
            adapter._fetch_plans_batch(skus, base_price, card_id=cid)
            for cid, _ in adapter._CARD_CALLS
        ]),
        adapter._fetch_plans_batch(skus, base_price, card_id=0),
        asyncio.gather(*[
            adapter._fetch_plans_batch(skus, base_price, card_id=5, bank_id=bid)
            for bid in bank_ids
        ]),
    )

    # Keyed by (card_system, issuer, count, has_interest); duplicates resolve
    # to the *lowest* interest_rate so an inferior late row can't shadow a
    # better earlier one (same pattern as pricing/platforms/magento.py).
    best: dict[tuple[str, str | None, int, bool], PaymentPlan] = {}

    def _emit(card_system: str, issuer: str | None, count: int, rate: float) -> None:
        if count <= 1:
            return
        has_interest = rate != 0
        normalized_rate = round(rate, 6) if has_interest else 0.0
        key = (card_system, issuer, count, has_interest)
        existing = best.get(key)
        if existing is not None and normalized_rate >= existing.interest_rate:
            return
        best[key] = PaymentPlan(
            card_system=card_system,
            card_issuer=issuer,
            installment_count=count,
            has_interest=has_interest,
            interest_rate=normalized_rate,
            amount_per_installment=round(base_price * (1 + rate) / count, 2),
        )

    for (_, card_name), raw_plans in zip(adapter._CARD_CALLS, card_results):
        for raw in raw_plans:
            try:
                count = int(raw["cuotas"])
                rate = float(raw.get("tasaDirecta", 0) or 0) / 100  # API returns percent, not decimal
            except (KeyError, TypeError, ValueError):
                continue
            # Generic plan (no issuer) goes in for the issuer-agnostic template
            # rows; for bank-issued networks we also emit an issuer-tagged copy
            # per expandable issuer so MACRO/NACION/GALICIA/etc. rows can match
            # generic Visa/MC promos. The bank-specific calls below will
            # overwrite with a lower rate when the bank actually beats generic.
            _emit(card_name, None, count, rate)
            if card_name in _BANK_EXPANDABLE_CARDS:
                for issuer in _BANK_EXPAND_ISSUERS:
                    _emit(card_name, issuer, count, rate)

    # Bank-promo rows from dedicated retornarplanes calls (IdTarjeta=5 + bank).
    # Lowest-rate dedup ensures these only stick when they beat the fanned-out
    # generic Visa copy — no need for a separate count-vs-base filter.
    for bank_id, raw_plans in zip(bank_ids, bank_results):
        bank_name = adapter._BANK_PROMOS.get(bank_id, "")
        issuer = _BANK_TO_ISSUER.get(bank_name)
        if issuer is None:
            continue
        for raw in raw_plans:
            try:
                count = int(raw["cuotas"])
                rate = float(raw.get("tasaDirecta", 0) or 0) / 100  # API returns percent, not decimal
            except (KeyError, TypeError, ValueError):
                continue
            _emit("Visa", issuer, count, rate)

    # Comprehensive (IdTarjeta=0) backfills cards without a dedicated call.
    # Only used for Mercado Pago today — counts for cards with dedicated calls
    # are understated here, so we ignore those entries.
    for raw in comprehensive:
        try:
            count = int(raw["cuotas"])
            rate = float(raw.get("tasaDirecta", 0) or 0) / 100  # API returns percent, not decimal
        except (KeyError, TypeError, ValueError):
            continue
        card_label = raw.get("tarjeta", "")
        card_system = _comprehensive_card(card_label)
        if card_system is None:
            continue
        _emit(card_system, None, count, rate)

    plans = list(best.values())
    plans.sort(key=lambda p: (
        p.card_system, p.card_issuer or "", p.installment_count, p.has_interest
    ))
    return plans
