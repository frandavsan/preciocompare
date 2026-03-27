from typing import Optional

from ..models import Installment
from ..platforms.vtex import VtexAdapter


class CastilloAdapter(VtexAdapter):
    name = "castillo"
    base_url = "https://www.castillo.com.ar"
    postal_code = "4000"  # Tucuman capital; default 1425 (BsAs) returns zero shipping SLAs
    _free_shipping_override = True  # all deliveries are free; skip shipping simulation

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
