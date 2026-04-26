from typing import Optional

from ...models import Installment
from ..platforms.vtex import VtexAdapter


class CastilloAdapter(VtexAdapter):
    name = "castillo"
    base_url = "https://www.castillo.com.ar"
    # Tucumán capital. Free shipping is real *within* Castillo's delivery zone (4xxx
    # postals), but outside it the simulation returns zero SLAs → free_shipping=False.
    # The override that previously forced True everywhere has been removed so that
    # CABA-postal queries (1425) correctly report no free shipping.
    postal_code = "4000"

    def _is_international(self, product: dict) -> Optional[bool]:
        return None  # regional store — "international" concept does not apply

    # Castillo shows the same card options for every product on their website.
    # The VTEX API returns extra cards/tiers that the frontend doesn't display.
    _INSTALLMENT_CARDS: dict[int, list[str]] = {
        3:  ["Visa", "Mastercard", "American Express", "Naranja"],
        6:  ["Visa", "Mastercard", "American Express", "Naranja"],
        9:  ["Visa", "Mastercard", "American Express", "Naranja"],
        10: ["Naranja"],
        12: ["Visa", "Mastercard"],
    }

    def _extract_installments(self, product: dict) -> list[Installment]:
        base = super()._extract_installments(product)
        # Build a lookup: count → amount (take the first amount seen per count)
        amount_by_count: dict[int, float] = {}
        for inst in base:
            if inst.count not in amount_by_count:
                amount_by_count[inst.count] = inst.amount
        return [
            Installment(count=count, amount=amount_by_count[count], cards=cards)
            for count, cards in sorted(self._INSTALLMENT_CARDS.items())
            if count in amount_by_count
        ]
