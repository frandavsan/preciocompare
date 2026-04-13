"""
VTEX plan extraction — reads ALL installment plans from commertialOffer.

Unlike the search pipeline's _extract_installments (which filters to sin-interes
only), this extracts every credit card plan including con-interes, and computes
interest rates from the installment amounts.

Limitation: VTEX does not expose bank-specific promos (Macro, Nacion, etc.).
Only generic card system names (Visa, Mastercard, NaranjaX) are available.
"""

from __future__ import annotations

from ..models import PaymentPlan


def _get_real_seller(item: dict) -> dict:
    """Select the real seller, matching fetching/platforms/vtex.py logic."""
    sellers = item.get("sellers", [])
    for seller in sellers:
        offer = seller.get("commertialOffer", {})
        if seller.get("sellerDefault") and offer.get("AvailableQuantity", 0) > 0:
            return seller
    for seller in sellers:
        if seller.get("commertialOffer", {}).get("Price", 0) > 0:
            return seller
    return sellers[0] if sellers else {}


def extract_all_plans(product: dict, base_price: float) -> list[PaymentPlan]:
    """
    Extract ALL installment plans from a VTEX product dict.

    Uses the real seller (same selection as the search pipeline) to avoid
    mixing plans from different sellers. Iterates commertialOffer.Installments[]
    for credit card payment groups, including both sin and con interes plans.

    Args:
        product: raw VTEX product dict (from search or legacy API)
        base_price: the product's cash price, used to compute interest rates

    Returns:
        List of PaymentPlan objects, one per (card_system, count) combination.
    """
    if base_price <= 0:
        return []

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, int, bool]] = set()  # (card_system, count, has_interest)

    for item in product.get("items", []):
        seller = _get_real_seller(item)
        offer = seller.get("commertialOffer", {})
        if offer.get("AvailableQuantity", 0) <= 0:
            continue
        for inst in offer.get("Installments", []):
                group = inst.get("PaymentSystemGroupName", "")
                if group and group != "creditCardPaymentGroup":
                    continue

                count = inst.get("NumberOfInstallments", 1)
                if count < 1:
                    continue

                amount = float(inst.get("Value", 0))
                if amount <= 0:
                    continue

                card_system = inst.get("PaymentSystemName", "")
                if not card_system:
                    continue

                api_rate = inst.get("InterestRate", 0)
                has_interest = api_rate != 0

                # Deduplicate: same card + count + interest type
                dedup_key = (card_system, count, has_interest)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Compute rate from amounts (more reliable than API's InterestRate)
                total_cost = amount * count
                interest_rate = (total_cost / base_price) - 1.0
                # Clamp tiny floating-point noise to 0 for sin-interes plans
                if not has_interest:
                    interest_rate = 0.0

                plans.append(PaymentPlan(
                    card_system=card_system,
                    card_issuer=None,  # VTEX doesn't expose bank-specific promos
                    installment_count=count,
                    has_interest=has_interest,
                    interest_rate=round(interest_rate, 6),
                    amount_per_installment=round(amount, 2),
                ))

    plans.sort(key=lambda p: (p.card_system, p.installment_count, p.has_interest))
    return plans
