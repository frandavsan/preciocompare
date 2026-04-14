"""
Magento plan extraction — ALL installment plans for a product.

Primary path: Summa Solutions' `/installments-plans/ajax/getplanbyproduct`
endpoint returns structured JSON with every plan the PDP modal would display
(sin + con interés, per-card, per-bank). This is far richer than what the PDP
HTML strip exposes, so we prefer it.

Fallback path: scrape `div.payment-info.pdp_logo` from the PDP HTML. Used when
the JSON endpoint is unavailable or the product ID cannot be located.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...fetching.core import http_get
from ...fetching.platforms.magento import DEFAULT_CARD_KEYWORDS
from ..models import PaymentPlan

_PRODUCT_ID_RE = re.compile(r'name="product"\s+value="(\d+)"')
_PLANS_ENDPOINT = "/installments-plans/ajax/getplanbyproduct/productid/{pid}"


async def fetch_all_plans(
    product_url: str,
    base_price: float,
    card_keywords: list[tuple[str, str]] | None = None,
) -> list[PaymentPlan]:
    """
    Fetch ALL installment plans for a Magento+Summa product.

    Tries the JSON plans endpoint first; falls back to HTML scraping.
    """
    if base_price <= 0:
        return []

    try:
        resp = await http_get(product_url)
        html = resp.text
    except Exception:
        return []

    product_id = _extract_product_id(html)
    if product_id:
        base = _origin_from_url(product_url)
        try:
            json_resp = await http_get(f"{base}{_PLANS_ENDPOINT.format(pid=product_id)}")
            data = json_resp.json()
            plans = _plans_from_json(data, base_price)
            if plans:
                return plans
        except Exception:
            pass

    return _plans_from_html(html, base_price, card_keywords or DEFAULT_CARD_KEYWORDS)


def _extract_product_id(html: str) -> str | None:
    m = _PRODUCT_ID_RE.search(html)
    return m.group(1) if m else None


def _origin_from_url(url: str) -> str:
    # https://www.cetrogar.com.ar/foo/bar  ->  https://www.cetrogar.com.ar
    m = re.match(r"(https?://[^/]+)", url)
    return m.group(1) if m else ""


def _plans_from_json(data: dict, base_price: float) -> list[PaymentPlan]:
    """
    Expand the plans/cards/banks JSON into flat PaymentPlan objects.

    Each plan rule has card_id/bank_id CSV strings; cartesian-expand with each
    feesValues entry (one per installment count). Dedup by
    (card, issuer, count, has_interest), keeping the lowest interest rate.
    """
    cards = data.get("cards") or {}
    banks = data.get("banks") or {}
    plans_raw = data.get("plans") or {}

    # Key: (card_system, card_issuer, count, has_interest) -> PaymentPlan
    best: dict[tuple[str, str | None, int, bool], PaymentPlan] = {}

    for plan in plans_raw.values():
        card_ids = _split_ids(plan.get("card_id", ""))
        bank_ids = _split_ids(plan.get("bank_id", ""))
        fees = plan.get("feesValues") or {}
        fee_list = fees.values() if isinstance(fees, dict) else fees

        for fee in fee_list:
            try:
                count = int(fee.get("count", 0))
            except (TypeError, ValueError):
                continue
            if count < 1:
                continue

            try:
                interest = float(fee.get("interest", 0) or 0)
            except (TypeError, ValueError):
                interest = 0.0

            note = (fee.get("note") or "").lower()
            has_interest = interest != 0 or "bonif" in note
            amount = base_price * (1 + interest) / count

            for cid in card_ids:
                card_info = cards.get(cid)
                if not card_info:
                    continue
                card_system = card_info.get("name", "").strip()
                if not card_system:
                    continue

                for bid in (bank_ids or [None]):
                    issuer = _bank_name(banks, bid) if bid else None
                    key = (card_system, issuer, count, has_interest)
                    existing = best.get(key)
                    if existing is None or interest < existing.interest_rate:
                        best[key] = PaymentPlan(
                            card_system=card_system,
                            card_issuer=issuer,
                            installment_count=count,
                            has_interest=has_interest,
                            interest_rate=round(interest, 6),
                            amount_per_installment=round(amount, 2),
                        )

    out = list(best.values())
    out.sort(key=lambda p: (p.card_system, p.card_issuer or "", p.installment_count, p.has_interest))
    return out


def _split_ids(csv: str) -> list[str]:
    return [x.strip() for x in (csv or "").split(",") if x.strip()]


def _bank_name(banks: dict, bank_id: str) -> str | None:
    info = banks.get(bank_id)
    if not info:
        return None
    name = (info.get("name") or "").strip()
    if not name:
        return None
    # Strip "Banco " prefix for consistency with spreadsheet labels.
    if name.lower().startswith("banco "):
        name = name[6:].strip()
    return name or None


# ---------------------------------------------------------------------------
# HTML fallback — used when the JSON endpoint is unavailable.
# ---------------------------------------------------------------------------

def _plans_from_html(
    html: str,
    base_price: float,
    card_keywords: list[tuple[str, str]],
) -> list[PaymentPlan]:
    soup = BeautifulSoup(html, "lxml")
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

        text_lower = text_tag.get_text(strip=True).lower()
        has_interest = "sin inter" not in text_lower

        image_div = container.find(class_="payment-info-image")
        card_names = _cards_from_image_div(image_div, card_keywords) if image_div else []
        if not card_names:
            continue

        if has_interest:
            interest_rate = (amount * count / base_price) - 1.0
        else:
            interest_rate = 0.0

        for card_name in card_names:
            dedup_key = (card_name, count, has_interest)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
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


_BANK_ISSUERS: set[str] = {
    "BNA", "Santander", "Macro", "BBVA", "Galicia", "Hipotecario", "Sol", "Tuya",
}


def _split_card_issuer(card_name: str) -> tuple[str, str | None]:
    if card_name in _BANK_ISSUERS:
        return "Visa", card_name.lower()
    return card_name, None


def _cards_from_image_div(image_div, card_keywords: list[tuple[str, str]]) -> list[str]:
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
