"""
Fravega plan extraction — sin + con interés plans.

Schema discovered via GraphQL introspection:
    Installments { quantity hasInterest factor cft tea }

`factor` is the per-installment fraction of principal: amount_per_installment
= price * factor. For sin-interés rows factor == 1/quantity (so the total
markup is 0); for con-interés rows factor > 1/quantity, and the total markup
the spreadsheet wants is `factor * quantity - 1`. cft and tea are not needed
for the spreadsheet (it stores total markups, not annual rates).
"""

from __future__ import annotations

from ...fetching.adapters import ADAPTERS
from ...fetching.platforms.fravega import FravegaAdapter
from ..models import PaymentPlan


# Fravega issuer-name → canonical issuer key used by card_mapping._LABEL_MAP.
# Lowercased on lookup; covers the variants the plans GQL returns under
# `issuer.name`. Issuers not in this map produce no PaymentPlan because no
# template row would match them anyway.
_ISSUER_ALIASES: dict[str, str] = {
    "bna": "nacion",
    "banco nación": "nacion",
    "banco nacion": "nacion",
    "banco galicia": "galicia",
    "galicia": "galicia",
    "bbva": "bbva",
    "banco bbva": "bbva",
    "banco francés": "bbva",
    "banco frances": "bbva",
    "santander": "santander",
    "banco santander": "santander",
    "banco santander río": "santander",
    "banco santander rio": "santander",
    "macro": "macro",
    "banco macro": "macro",
    "hipotecario": "hipotecario",
    "banco hipotecario": "hipotecario",
    "credicoop": "credicoop",
    "banco credicoop": "credicoop",
}


def _normalize_issuer(name: str | None) -> str | None:
    if not name:
        return None
    return _ISSUER_ALIASES.get(name.strip().lower())


def _find_adapter() -> FravegaAdapter | None:
    for adapter in ADAPTERS:
        if isinstance(adapter, FravegaAdapter):
            return adapter
    return None


async def fetch_all_plans(sku: str, base_price: float) -> list[PaymentPlan]:
    """
    Fetch sin- and con-interés payment plans for a Fravega SKU.

    Returns one PaymentPlan per (system, issuer, count, has_interest) row
    in the plans GQL response. Issuer-tagged rows represent bank-exclusive
    promos (BNA at 12x on Visa, etc.); generic rows have card_issuer=None.
    """
    if base_price <= 0 or not sku:
        return []

    adapter = _find_adapter()
    if adapter is None:
        return []

    gql = (
        f'{{ plans(sku: "{sku}") {{'
        "  system { name }"
        "  issuer { name }"
        "  installments { quantity hasInterest factor }"
        "} }"
    )
    try:
        resp = await adapter._post_gql(gql)
    except Exception:
        return []

    raw_plans = (resp.get("data") or {}).get("plans") or []

    # Keyed by (card_system, issuer, count, has_interest); duplicates resolve
    # to the lowest interest_rate (same pattern as pricing/platforms/magento.py).
    best: dict[tuple[str, str | None, int, bool], PaymentPlan] = {}

    for plan in raw_plans:
        system_name = (plan.get("system") or {}).get("name", "").strip()
        issuer_raw = (plan.get("issuer") or {}).get("name", "").strip()
        inst = plan.get("installments") or {}
        try:
            count = int(inst.get("quantity", 0))
        except (TypeError, ValueError):
            continue
        if count <= 1 or not system_name:
            continue

        has_interest = bool(inst.get("hasInterest"))
        try:
            factor = float(inst.get("factor", 0) or 0)
        except (TypeError, ValueError):
            continue
        if factor <= 0:
            continue

        issuer = _normalize_issuer(issuer_raw) if issuer_raw else None
        if issuer_raw and issuer is None:
            # Issuer named in the response but not in our canonical map —
            # no template row would match it, so skip rather than emit a
            # PaymentPlan that goes nowhere.
            continue

        if has_interest:
            # Total markup the spreadsheet stores: total_paid / price - 1.
            interest_rate = round(factor * count - 1, 6)
            if interest_rate <= 0:
                # Floating-point noise on a sin-interés-equivalent row.
                interest_rate = 0.0
                has_interest = False
        else:
            interest_rate = 0.0

        key = (system_name, issuer, count, has_interest)
        existing = best.get(key)
        if existing is not None and interest_rate >= existing.interest_rate:
            continue

        best[key] = PaymentPlan(
            card_system=system_name,
            card_issuer=issuer,
            installment_count=count,
            has_interest=has_interest,
            interest_rate=interest_rate,
            amount_per_installment=round(base_price * factor, 2),
        )

    plans = list(best.values())
    plans.sort(key=lambda p: (
        p.card_system, p.card_issuer or "", p.installment_count, p.has_interest
    ))
    return plans
