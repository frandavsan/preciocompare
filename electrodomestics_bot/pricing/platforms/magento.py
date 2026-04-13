"""
Magento plan extraction — scrapes ALL installment plans from product page HTML.

Unlike the search pipeline's _fetch_installments (which filters to sin-interes
only), this extracts every credit card plan including con-interes, and computes
interest rates from the installment amounts.

Requires fetching the individual product page — the search results page only
shows one featured installment option without card names.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...fetching.core import http_get
from ...fetching.platforms.magento import DEFAULT_CARD_KEYWORDS
from ..models import PaymentPlan


async def fetch_all_plans(
    product_url: str,
    base_price: float,
    card_keywords: list[tuple[str, str]] | None = None,
) -> list[PaymentPlan]:
    """
    Fetch a Magento product page and extract ALL installment plans.

    Scrapes div.payment-info.pdp_logo containers on the product page.
    Unlike the search pipeline version, does NOT filter by "sin inter" —
    extracts both sin and con interes plans.

    Args:
        product_url: full URL to the product page
        base_price: the product's cash price, used to compute interest rates
        card_keywords: ordered (keyword, card_name) pairs for logo parsing;
                       defaults to Summa Solutions standard filenames

    Returns:
        List of PaymentPlan objects, one per (card, count, has_interest).
    """
    if base_price <= 0:
        return []

    if card_keywords is None:
        card_keywords = DEFAULT_CARD_KEYWORDS

    try:
        resp = await http_get(product_url)
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception:
        return []

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, int, bool]] = set()

    for container in soup.find_all(
        "div",
        class_=lambda c: c and "payment-info" in c and "pdp_logo" in c,
    ):
        count_tag = container.find(class_="installment-count")
        amount_tag = container.find(class_="installment-amount")
        text_tag = container.find(class_="installment-text")
        if not count_tag or not amount_tag or not text_tag:
            continue

        count_m = re.match(r"(\d+)", count_tag.get_text(strip=True))
        if not count_m:
            continue
        count = int(count_m.group(1))
        if count < 1:
            continue

        amount_clean = (
            amount_tag.get_text(strip=True)
            .replace("$", "").replace(".", "").replace(",", ".").strip()
        )
        try:
            amount = float(amount_clean)
        except ValueError:
            continue
        if amount <= 0:
            continue

        # Determine sin/con interes from text
        text_lower = text_tag.get_text(strip=True).lower()
        has_interest = "sin inter" not in text_lower

        # Extract card names from logo images
        image_div = container.find(class_="payment-info-image")
        card_names = _cards_from_image_div(image_div, card_keywords) if image_div else []
        if not card_names:
            continue  # No recognizable cards — skip this installment block

        # Compute interest rate
        if has_interest:
            total_cost = amount * count
            interest_rate = (total_cost / base_price) - 1.0
        else:
            interest_rate = 0.0

        # Create a plan per card system (each logo = separate card)
        for card_name in card_names:
            dedup_key = (card_name, count, has_interest)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Determine issuer — bank names from logo are issuers, not card systems
            card_system, card_issuer = _split_card_issuer(card_name)

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


# Bank names that appear as logo images but are issuers, not card systems.
# When these appear, the card system is typically Visa (bank promo via Visa).
_BANK_ISSUERS: set[str] = {
    "BNA", "Santander", "Macro", "BBVA", "Galicia", "Sol", "Tuya",
}


def _split_card_issuer(card_name: str) -> tuple[str, str | None]:
    """
    Split a card name into (card_system, card_issuer).

    Bank names (BNA, Macro, etc.) are issuers offering promos via Visa.
    Card networks (Visa, Mastercard, etc.) are card systems with no issuer.

    Assumption: all Argentine bank promos observed so far are Visa-based
    (banks issue Visa co-branded cards). If a Mastercard bank promo appears,
    add it to a separate _BANK_ISSUER_CARD_SYSTEM map.
    """
    if card_name in _BANK_ISSUERS:
        return "Visa", card_name.lower()
    return card_name, None


def _cards_from_image_div(
    image_div,
    card_keywords: list[tuple[str, str]],
) -> list[str]:
    """Parse card names from logo <img> srcs inside a payment-info-image div."""
    seen: set[str] = set()
    cards: list[str] = []
    for img in image_div.find_all("img"):
        fname = img.get("src", "").split("/")[-1].lower()
        for keyword, card_name in card_keywords:
            if keyword in fname and card_name not in seen:
                seen.add(card_name)
                cards.append(card_name)
                break
    return cards
