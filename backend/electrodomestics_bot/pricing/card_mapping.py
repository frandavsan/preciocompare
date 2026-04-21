"""
Card mapping — bridges spreadsheet row identifiers and API card names.

Two layers:
  1. Row identity: parses Excel columns (A, B, I) into a TemplateRow with
     normalized card systems, issuer, and interest type.
  2. Plan matching: given a store's list of PaymentPlans, finds the plan
     that matches a TemplateRow's (cards, issuer, count, interest_type).
"""

from __future__ import annotations

from .models import InterestType, PaymentPlan, TemplateRow


# ---------------------------------------------------------------------------
# API name normalization — maps raw API card names to canonical lowercase keys
# ---------------------------------------------------------------------------

_CARD_ALIASES: dict[str, str] = {
    "visa": "visa",
    "mastercard": "mastercard",
    "master": "mastercard",
    "american express": "amex",
    "amex": "amex",
    "naranjax": "naranjax",
    "naranja x": "naranjax",
    "naranja": "naranjax",
    "mercado pago": "mercadopago",
    "mercadopago": "mercadopago",
    "mercadopagopro": "mercadopago",
    "mercado pago pro": "mercadopago",
    "cabal": "cabal",
    "getnet": "getnet",
    "credimas": "credimas",
    "sucredito": "sucredito",
    "su credito": "sucredito",
    "payway": "payway",
}


def normalize_card_name(api_name: str) -> str:
    """Normalize an API card name to its canonical key."""
    return _CARD_ALIASES.get(api_name.strip().lower(), api_name.strip().lower())


# ---------------------------------------------------------------------------
# Spreadsheet label → (card set, issuer) mapping
# ---------------------------------------------------------------------------

# Maps spreadsheet column A labels to (canonical card systems, bank issuer).
# Two entries for SUCREDITO handle the accent variant in the sheet.
_LABEL_MAP: dict[str, tuple[frozenset[str], str | None]] = {
    "VISA/MASTERCARD/AMEX": (frozenset({"visa", "mastercard", "amex"}), None),
    "VISA/MASTER MACRO":    (frozenset({"visa", "mastercard"}), "macro"),
    "VISA/MASTER NACION":   (frozenset({"visa", "mastercard"}), "nacion"),
    "NARANJAX":             (frozenset({"naranjax"}), None),
    "MERCADO PAGO":         (frozenset({"mercadopago"}), None),
    "GETNET SANTANDER":     (frozenset({"getnet"}), "santander"),
    "CREDIMAS":             (frozenset({"credimas"}), None),
    "SUCRÉDITO":            (frozenset({"sucredito"}), None),
    "SUCREDITO":            (frozenset({"sucredito"}), None),
    "PAYWAY":               (frozenset({"payway"}), None),
}


def _parse_interest_type(description: str) -> InterestType:
    """Determine sin/con from column I description text."""
    d = description.lower()
    if "sin int" in d or "s/i" in d:
        return "sin"
    if "con int" in d or "c/i" in d:
        return "con"
    # Marketing names that are known sin-interes plans
    if d in ("plan z", "plan facil 3", "plan facil 6", "plan fácil 3", "plan fácil 6"):
        return "sin"
    # "N Cuotas" without sin/con qualifier — treat as unknown (could be either)
    return "unknown"


_MISSING: tuple[()] = ()  # sentinel to distinguish "not in dict" from "value is None"


def parse_template_row(
    excel_row: int,
    card_label: str,
    installment_count: int,
    description: str,
) -> TemplateRow:
    """Build a TemplateRow from raw Excel cell values."""
    label_upper = card_label.strip().upper()
    # Try uppercase first, then raw label as fallback for accent variants.
    mapping = _LABEL_MAP.get(label_upper, _MISSING)  # type: ignore[arg-type]
    if mapping is _MISSING:
        mapping = _LABEL_MAP.get(card_label.strip(), _MISSING)  # type: ignore[arg-type]

    if mapping is _MISSING:
        cards: frozenset[str] = frozenset()
        issuer: str | None = None
    else:
        cards, issuer = mapping

    return TemplateRow(
        excel_row=excel_row,
        card_label=card_label.strip(),
        installment_count=installment_count,
        description=description.strip() if description else "",
        interest_type=_parse_interest_type(description or ""),
        cards=cards,
        issuer=issuer,
    )


# ---------------------------------------------------------------------------
# Plan matching — find the PaymentPlan that fills a TemplateRow cell
# ---------------------------------------------------------------------------

def find_matching_plan(
    row: TemplateRow,
    plans: list[PaymentPlan],
) -> PaymentPlan | None:
    """
    Find the plan from a store that matches this template row.

    Match criteria:
      - installment_count must match exactly
      - interest_type: "sin" matches has_interest=False, "con" matches has_interest=True
      - card_system (normalized) must be in row.cards
      - issuer (normalized, lowered) must match row.issuer if row has one;
        if row has no issuer, any issuer (or None) matches

    Returns the first match, or None if no plan fits this row.
    """
    if row.interest_type == "unknown":
        # Rows like "Débito/Crédito" (count=1) — skip for now per plan
        return None

    want_interest = row.interest_type == "con"

    for plan in plans:
        if plan.installment_count != row.installment_count:
            continue
        if plan.has_interest != want_interest:
            continue
        if normalize_card_name(plan.card_system) not in row.cards:
            continue
        # Issuer check
        if row.issuer is not None:
            plan_issuer = plan.card_issuer.lower() if plan.card_issuer else None
            if plan_issuer != row.issuer:
                continue
        return plan
    return None
