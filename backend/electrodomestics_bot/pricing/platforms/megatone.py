"""
Megatone plan extraction — sin-interés plans only (v1).

Reuses the fetching adapter's `_fetch_plans_batch` to issue parallel
`retornarplanes` calls per card network and per bank promo, then emits
one PaymentPlan per (card_system, count) plus issuer-tagged rows for the
bank promos that exceed the base Visa count.

Con-interés plans are not extracted in v1: the spreadsheet's con-interés
rows are already covered by the VTEX-platform stores, and Megatone's
website itself only displays the sin-interés tier per card.
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


def _find_adapter() -> MegatoneAdapter | None:
    for adapter in ADAPTERS:
        if isinstance(adapter, MegatoneAdapter):
            return adapter
    return None


async def fetch_all_plans(sku: str, base_price: float) -> list[PaymentPlan]:
    """
    Fetch sin-interés payment plans for a Megatone SKU.

    Returns one PaymentPlan per (card_system, count) for the standard
    networks (Visa, Mastercard, AmEx, Cabal, NaranjaX) plus issuer-tagged
    Visa rows for bank promos that exceed the base Visa count.
    """
    if base_price <= 0 or not sku:
        return []

    adapter = _find_adapter()
    if adapter is None:
        return []

    skus = [sku]
    bank_ids = list(adapter._BANK_PROMOS.keys())

    card_results, bank_results = await asyncio.gather(
        asyncio.gather(*[
            adapter._fetch_plans_batch(skus, base_price, card_id=cid)
            for cid, _ in adapter._CARD_CALLS
        ]),
        asyncio.gather(*[
            adapter._fetch_plans_batch(skus, base_price, card_id=5, bank_id=bid)
            for bid in bank_ids
        ]),
    )

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, str | None, int]] = set()

    def _emit(card_system: str, issuer: str | None, count: int) -> None:
        if count <= 1:
            return
        key = (card_system, issuer, count)
        if key in seen:
            return
        seen.add(key)
        plans.append(PaymentPlan(
            card_system=card_system,
            card_issuer=issuer,
            installment_count=count,
            has_interest=False,
            interest_rate=0.0,
            amount_per_installment=round(base_price / count, 2),
        ))

    visa_max = 0
    for (_, card_name), raw_plans in zip(adapter._CARD_CALLS, card_results):
        for raw in raw_plans:
            if not adapter._is_sin_interes(raw):
                continue
            try:
                count = int(raw["cuotas"])
            except (KeyError, TypeError, ValueError):
                continue
            _emit(card_name, None, count)
            if card_name == "Visa" and count > visa_max:
                visa_max = count

    # Bank-promo rows are emitted as Visa with issuer, mirroring website logic:
    # only when the bank promo exceeds the base Visa count.
    for bank_id, raw_plans in zip(bank_ids, bank_results):
        bank_name = adapter._BANK_PROMOS.get(bank_id, "")
        issuer = _BANK_TO_ISSUER.get(bank_name)
        if issuer is None:
            continue
        for raw in raw_plans:
            if not adapter._is_sin_interes(raw):
                continue
            try:
                count = int(raw["cuotas"])
            except (KeyError, TypeError, ValueError):
                continue
            if count <= visa_max:
                continue
            _emit("Visa", issuer, count)

    plans.sort(key=lambda p: (p.card_system, p.card_issuer or "", p.installment_count))
    return plans
