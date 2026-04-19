"""
Montes Hermanos plan extraction — fetches all payment plans via the store's
installment query endpoint.

Flow:
1. Fetch product page → extract product ID from abrirTarjetas(id, price) JS call
2. POST to resultado_consultar_cuotas.php?movil=1 for each credit card in parallel
3. Parse each result page for installment rows (count, amount, interest)

Fallback: if the product ID can't be extracted from the page, scrape the
featured div.opcion_tarjeta blocks visible on the product page sidebar (3 cards,
best option only per card — no con-interés data).

Amount format: Montes uses '.' as thousands separator and ',' as decimal
(e.g. "$272.999,63"). Both _AMOUNT_RE and _parse_amount handle this.
"""

from __future__ import annotations

import asyncio
import re

from bs4 import BeautifulSoup

from ...fetching.core import http_get, http_post
from ..models import PaymentPlan


_RESULT_URL = (
    "https://www.monteshermanos.com.ar"
    "/subsitios/producto/consulta_cuotas/resultado_consultar_cuotas.php"
)

# Matches "abrirTarjetas(1692, 727999)" → group 1 = product ID
_PRODUCT_ID_RE = re.compile(r'abrirTarjetas\((\d+),')

# Matches "3 cuotas" or "1 cuota" → group 1 = count
_COUNT_RE = re.compile(r'(\d+)\s+cuotas?', re.IGNORECASE)

# Matches "$727.999,00" → group 1 = "727.999,00"
_AMOUNT_RE = re.compile(r'\$\s*([\d.,]+)')


# (card_id, card_system, card_issuer)
# Debit cards (2=Visa Débito, 4=Maestro, 5=MC Débito, 7=Cabal Débito) excluded.
_CARD_DEFS: list[tuple[int, str, str | None]] = [
    (1,  "Visa",             None),
    (3,  "Mastercard",       None),
    (6,  "Naranja",          None),
    (8,  "Cabal",            None),
    (13, "American Express", None),
    (9,  "American Express", "galicia"),
    (10, "American Express", "macro"),
    (11, "American Express", "santander"),
    (12, "American Express", "hsbc"),
    (16, "Visa",             "naranja"),
    (18, "Mastercard",       "naranja"),
    (23, "American Express", "naranja"),
]


async def fetch_all_plans(
    product_url: str,
    base_price: float,
) -> list[PaymentPlan]:
    """
    Fetch all payment plans for a Montes Hermanos product.

    Extracts the product ID from the product page, then fires parallel POST
    requests to resultado_consultar_cuotas.php for each credit card. Falls back
    to the 3 featured plans visible on the product page if the ID is missing.
    """
    if base_price <= 0:
        return []

    try:
        resp = await http_get(product_url)
        html = resp.text
    except Exception:
        return []

    m = _PRODUCT_ID_RE.search(html)
    if not m:
        return []

    product_id = m.group(1)
    price_str = str(round(base_price))

    tasks = [
        _fetch_card_plans(product_id, price_str, base_price, card_id, card_system, card_issuer)
        for card_id, card_system, card_issuer in _CARD_DEFS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    plans: list[PaymentPlan] = []
    seen: set[tuple[str, str | None, int]] = set()
    for r in results:
        if not isinstance(r, list):
            continue
        for p in r:
            key = (p.card_system, p.card_issuer, p.installment_count)
            if key not in seen:
                seen.add(key)
                plans.append(p)

    plans.sort(key=lambda p: (p.card_system, p.card_issuer or "", p.installment_count, p.has_interest))
    return plans


async def _fetch_card_plans(
    product_id: str,
    price_str: str,
    base_price: float,
    card_id: int,
    card_system: str,
    card_issuer: str | None,
) -> list[PaymentPlan]:
    try:
        resp = await http_post(
            _RESULT_URL + "?movil=1",
            data={
                "tarjeta_elegida": str(card_id),
                "monto_ingresado": price_str,
                "id_producto": product_id,
            },
        )
        return _parse_result_page(resp.text, base_price, card_system, card_issuer)
    except Exception:
        return []


def _parse_result_page(
    html: str,
    base_price: float,
    card_system: str,
    card_issuer: str | None,
) -> list[PaymentPlan]:
    """
    Parse a resultado_consultar_cuotas.php page.

    Each div.datos_cuotas_tarjeta has 4 desktop cells (hidden-xs col-sm-3):
    count text, amount per installment, interest amount, total.
    """
    soup = BeautifulSoup(html, "lxml")
    plans: list[PaymentPlan] = []

    for row in soup.select("div.datos_cuotas_tarjeta"):
        cells = row.select("div.hidden-xs.col-sm-3")
        if len(cells) < 3:
            continue

        count_text = cells[0].get_text(strip=True)
        amount_text = cells[1].get_text(strip=True)
        interest_text = cells[2].get_text(strip=True)

        cm = _COUNT_RE.search(count_text)
        if not cm:
            continue
        count = int(cm.group(1))

        am = _AMOUNT_RE.search(amount_text)
        if not am:
            continue
        amount = _parse_amount(am.group(1))
        if amount <= 0:
            continue

        # has_interest: interest column is non-zero
        im = _AMOUNT_RE.search(interest_text)
        has_interest = im is not None and _parse_amount(im.group(1)) > 0

        if has_interest:
            interest_rate = round((amount * count / base_price) - 1.0, 6)
        else:
            interest_rate = 0.0

        plans.append(PaymentPlan(
            card_system=card_system,
            card_issuer=card_issuer,
            installment_count=count,
            has_interest=has_interest,
            interest_rate=interest_rate,
            amount_per_installment=round(amount, 2),
        ))

    return plans


def _parse_amount(raw: str) -> float:
    """
    Parse Montes amount strings to float.

    Montes uses '.' as thousands separator and ',' as decimal:
      "727.999,00" → 727999.0
      "272.999,63" → 272999.63
    """
    clean = raw.replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Fallback: featured plans from product page sidebar
# ---------------------------------------------------------------------------

_FEATURED_AMOUNT_RE = re.compile(r"\$\s*([\d.]+)")

_CARD_MAP: dict[str, str] = {
    "visa": "Visa",
    "mastercard": "Mastercard",
    "master": "Mastercard",
    "naranja": "Naranja",
    "naranjax": "NaranjaX",
    "cabal": "Cabal",
    "american express": "American Express",
    "amex": "American Express",
}


def _parse_featured_plans(html: str, base_price: float) -> list[PaymentPlan]:
    """
    Scrape the 2-3 featured div.opcion_tarjeta blocks from the product sidebar.

    Used as a fallback when the product ID can't be extracted. Returns only
    the best sin-interés option per card with no issuer tagging.
    """
    soup = BeautifulSoup(html, "lxml")
    plans: list[PaymentPlan] = []
    seen: set[tuple[str, int]] = set()

    for container in soup.select("div.opcion_tarjeta"):
        img = container.select_one("img.img-tarjeta")
        if not img:
            continue
        card_name = (img.get("alt") or "").strip()
        if not card_name:
            continue

        text_div = container.select_one("div.texto_tarjeta")
        if not text_div:
            continue
        bolds = text_div.find_all("b")
        if len(bolds) < 2:
            continue

        try:
            count = int(bolds[0].get_text(strip=True))
        except (ValueError, TypeError):
            continue

        am = _FEATURED_AMOUNT_RE.search(bolds[1].get_text(strip=True))
        if not am:
            continue
        amount = _parse_amount(am.group(1))
        if amount <= 0:
            continue

        key = (card_name, count)
        if key in seen:
            continue
        seen.add(key)

        total_cost = amount * count
        has_interest = total_cost > base_price * 1.02
        interest_rate = round((total_cost / base_price) - 1.0, 6) if has_interest else 0.0

        card_system = _CARD_MAP.get(card_name.lower(), card_name)
        plans.append(PaymentPlan(
            card_system=card_system,
            card_issuer=None,
            installment_count=count,
            has_interest=has_interest,
            interest_rate=interest_rate,
            amount_per_installment=round(amount, 2),
        ))

    plans.sort(key=lambda p: (p.card_system, p.installment_count))
    return plans
