"""
Fravega plan extraction — sin-interés plans only (v1).

Reuses the fetching adapter's plans GQL to fetch every (system, issuer, count)
combination, filters to sin-interés, and emits PaymentPlan objects with
interest_rate=0 and amount = price / count (exact for 0% plans).

Con-interés plans are not extracted in v1: the GQL we currently issue does not
include an amount/value field, and the spreadsheet's con-interés rows are
already covered by the VTEX-platform stores. Adding con-interés support means
discovering the missing field on Fravega's plans schema first.
"""

from __future__ import annotations

from ...fetching.adapters import ADAPTERS
from ...fetching.platforms.fravega import FravegaAdapter
from ..models import PaymentPlan


# Fravega issuer-name → canonical issuer key used by card_mapping._LABEL_MAP.
# Lowercased for lookup; entries cover the variants Fravega returns in the
# `issuer.name` field of the plans GQL response.
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
    Fetch sin-interés payment plans for a Fravega SKU.

    Returns one PaymentPlan per (card_system, issuer, installment_count) row
    from the plans GQL. Issuer-tagged rows represent bank-exclusive promos
    (e.g. BNA at 12x on Visa). Generic rows have card_issuer=None.
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
        "  installments { quantity hasInterest }"
        "} }"
    )
    try:
        resp = await adapter._post_gql(gql)
    except Exception:
        return []

    raw_plans = (resp.get("data") or {}).get("plans") or []

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, str | None, int]] = set()

    for plan in raw_plans:
        system_name = (plan.get("system") or {}).get("name", "").strip()
        issuer_raw = (plan.get("issuer") or {}).get("name", "").strip()
        inst = plan.get("installments") or {}
        if inst.get("hasInterest"):
            continue
        try:
            count = int(inst.get("quantity", 0))
        except (TypeError, ValueError):
            continue
        if count <= 1 or not system_name:
            continue

        issuer = _normalize_issuer(issuer_raw) if issuer_raw else None
        # Skip issuer rows we don't recognize — emitting them would produce
        # PaymentPlan objects no template row can match against.
        if issuer_raw and issuer is None:
            continue

        key = (system_name, issuer, count)
        if key in seen:
            continue
        seen.add(key)

        plans.append(PaymentPlan(
            card_system=system_name,
            card_issuer=issuer,
            installment_count=count,
            has_interest=False,
            interest_rate=0.0,
            amount_per_installment=round(base_price / count, 2),
        ))

    plans.sort(key=lambda p: (p.card_system, p.card_issuer or "", p.installment_count))
    return plans
