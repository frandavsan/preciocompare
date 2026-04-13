"""
Montes Hermanos plan extraction — scrapes installment plans from product page.

Montes is a custom PHP/jQuery site. Installment data lives in
div.opcion_tarjeta containers on each product page:
  - Card name: img.img-tarjeta alt attribute ("Naranja", "Visa", "Mastercard")
  - Count + amount: <b> tags inside div.texto_tarjeta ("9 Cuotas de $105.555")

All observed plans are sin-interes (amount × count ≈ list price). The
"CONTADO ONLINE" price is a cash discount off list price, not the base for
installments.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...fetching.core import http_get
from ..models import PaymentPlan

# Amount pattern: "$105.555" or "$1.234.567"
_AMOUNT_RE = re.compile(r"\$\s*([\d.]+)")


async def fetch_all_plans(
    product_url: str,
    base_price: float,
) -> list[PaymentPlan]:
    """
    Fetch a Montes product page and extract all installment plans.

    Scrapes div.opcion_tarjeta containers. Each has a card logo img with
    alt text for the card name, and bold tags for count and amount.

    Args:
        product_url: full URL to the product page
        base_price: list price (not the cash-discount price)

    Returns:
        List of PaymentPlan objects sorted by (card, count).
    """
    if base_price <= 0:
        return []

    try:
        resp = await http_get(product_url)
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        return []

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, int]] = set()

    for container in soup.select("div.opcion_tarjeta"):
        # Card name from logo alt text
        img = container.select_one("img.img-tarjeta")
        if not img:
            continue
        card_name = (img.get("alt") or "").strip()
        if not card_name:
            continue

        # Count and amount from <b> tags in texto_tarjeta
        text_div = container.select_one("div.texto_tarjeta")
        if not text_div:
            continue
        bolds = text_div.find_all("b")
        if len(bolds) < 2:
            continue

        # First <b>: installment count
        try:
            count = int(bolds[0].get_text(strip=True))
        except (ValueError, TypeError):
            continue
        if count < 1:
            continue

        # Second <b>: amount per installment ("$105.555")
        amount_text = bolds[1].get_text(strip=True)
        amount_match = _AMOUNT_RE.search(amount_text)
        if not amount_match:
            continue
        amount_clean = amount_match.group(1).replace(".", "")
        try:
            amount = float(amount_clean)
        except ValueError:
            continue
        if amount <= 0:
            continue

        # Dedup by (card, count)
        dedup_key = (card_name, count)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # Determine sin/con interes from amounts
        total_cost = amount * count
        tolerance = base_price * 0.02  # 2% tolerance for rounding
        has_interest = total_cost > (base_price + tolerance)

        if has_interest:
            interest_rate = (total_cost / base_price) - 1.0
        else:
            interest_rate = 0.0

        card_system, card_issuer = _normalize_card(card_name)

        plans.append(PaymentPlan(
            card_system=card_system,
            card_issuer=card_issuer,
            installment_count=count,
            has_interest=has_interest,
            interest_rate=round(interest_rate, 6),
            amount_per_installment=round(amount, 2),
        ))

    plans.sort(key=lambda p: (p.card_system, p.installment_count, p.has_interest))
    return plans


# Card alt text normalization
_CARD_MAP: dict[str, str] = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "master": "Mastercard",
    "naranja": "NaranjaX",
    "naranjax": "NaranjaX",
    "cabal": "Cabal",
    "american express": "American Express",
    "amex": "American Express",
}


def _normalize_card(alt_text: str) -> tuple[str, str | None]:
    """Normalize card alt text to (card_system, card_issuer)."""
    key = alt_text.strip().lower()
    card_system = _CARD_MAP.get(key, alt_text)
    return card_system, None
