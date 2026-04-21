"""
VTEX plan extraction — reads ALL installment plans from commertialOffer.

Unlike the search pipeline's _extract_installments (which filters to sin-interes
only), this extracts every credit card plan including con-interes, and computes
interest rates from the installment amounts.

Bank-specific promos: VTEX exposes per-plan bank data only indirectly, via
productClusters tags like "Banco Macro" that mark products eligible for a bank's
promo. The site itself applies the generic Visa/Mastercard plans when the user
selects that bank. We mirror this by emitting issuer-tagged copies of generic
Visa/Mastercard/Amex/Cabal plans for each eligible issuer cluster.
"""

from __future__ import annotations

from ..models import PaymentPlan


# productCluster name (lowercased) -> canonical issuer key used in TemplateRow.issuer
_CLUSTER_TO_ISSUER: dict[str, str] = {
    "banco macro": "macro",
    "banco nación": "nacion",
    "banco nacion": "nacion",
    "banco galicia": "galicia",
    "banco santander": "santander",
    "banco santander río": "santander",
    "banco santander rio": "santander",
    "banco bbva": "bbva",
    "banco francés": "bbva",
    "banco frances": "bbva",
    "banco hipotecario": "hipotecario",
    "banco credicoop": "credicoop",
    "banco columbia": "columbia",
    "banco del sol": "sol",
    "banco córdoba": "cordoba",
    "banco cordoba": "cordoba",
    "banco municipal de rosario": "municipal_rosario",
}

# Card systems eligible for bank-promo expansion (generic networks that banks issue)
_BANK_ELIGIBLE_CARDS: set[str] = {"visa", "mastercard", "amex", "american express", "cabal"}


def _extract_eligible_issuers(product: dict) -> set[str]:
    """Parse productClusters into a set of canonical issuer keys."""
    issuers: set[str] = set()
    clusters = product.get("productClusters", [])
    # Intelligent Search: list of dicts with "name"; legacy: already normalized to this shape
    for cluster in clusters:
        if isinstance(cluster, dict):
            name = (cluster.get("name") or "").strip().lower()
        elif isinstance(cluster, str):
            name = cluster.strip().lower()
        else:
            continue
        issuer = _CLUSTER_TO_ISSUER.get(name)
        if issuer:
            issuers.add(issuer)
    return issuers


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


def extract_all_plans(
    product: dict,
    base_price: float,
    extra_issuers: set[str] | None = None,
) -> list[PaymentPlan]:
    """
    Extract ALL installment plans from a VTEX product dict.

    Uses the real seller (same selection as the search pipeline) to avoid
    mixing plans from different sellers. Iterates commertialOffer.Installments[]
    for credit card payment groups, including both sin and con interes plans.

    Args:
        product: raw VTEX product dict (from search or legacy API)
        base_price: the product's cash price, used to compute interest rates
        extra_issuers: additional canonical issuer keys to treat as eligible for
            bank-promo expansion, beyond what productClusters carries. Use this
            for stores where bank eligibility is store-wide (e.g. Castillo's
            especific-cuotes-plp.json) rather than per-product.

    Returns:
        List of PaymentPlan objects, one per (card_system, count) combination.
    """
    if base_price <= 0:
        return []

    eligible_issuers = _extract_eligible_issuers(product)
    if extra_issuers:
        eligible_issuers |= extra_issuers

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, str | None, int, bool]] = set()  # (card_system, issuer, count, has_interest)

    for item in product.get("items", []):
        seller = _get_real_seller(item)
        offer = seller.get("commertialOffer", {})
        if offer.get("Price", 0) <= 0:
            continue
        for inst in offer.get("Installments", []):
                group = inst.get("PaymentSystemGroupName", "")
                # Allow credit cards plus first-party wallets that behave like
                # credit plans (MercadoPagoPro). Exclude debit, boleto, and
                # store-custom payment groups that pollute with 1x-only rows.
                if group and group not in ("creditCardPaymentGroup", "MercadoPagoProPaymentGroup"):
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

                # Compute rate from amounts (more reliable than API's InterestRate)
                total_cost = amount * count
                interest_rate = (total_cost / base_price) - 1.0
                # Clamp tiny floating-point noise to 0 for sin-interes plans
                if not has_interest:
                    interest_rate = 0.0

                # Emit the generic plan plus an issuer-tagged copy per eligible
                # bank cluster (for Visa/Mastercard/Amex/Cabal). This mirrors the
                # site: selecting "Banco Macro" on a Macro-tagged product shows
                # the same generic Visa plans.
                card_issuers: list[str | None] = [None]
                if card_system.lower() in _BANK_ELIGIBLE_CARDS:
                    card_issuers.extend(sorted(eligible_issuers))

                for issuer in card_issuers:
                    dedup_key = (card_system, issuer, count, has_interest)
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    plans.append(PaymentPlan(
                        card_system=card_system,
                        card_issuer=issuer,
                        installment_count=count,
                        has_interest=has_interest,
                        interest_rate=round(interest_rate, 6),
                        amount_per_installment=round(amount, 2),
                    ))

    plans.sort(key=lambda p: (p.card_system, p.installment_count, p.has_interest))
    return plans
