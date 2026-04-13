"""
Pricing store registry — maps stores to their platform and spreadsheet column.

Each adapter declares:
  - name: store identifier (matches fetching adapter name)
  - column: Excel column letter for writing rates (E, F, G, H)
  - platform: "vtex" or "magento" (determines plan extraction logic)
  - base_url: store base URL (used for Magento product page fetches)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PricingStore:
    """Configuration for a store in the pricing pipeline."""
    name: str
    column: str                          # Excel column letter (E, F, G, H)
    platform: Literal["vtex", "magento", "monteshermanos"]
    base_url: str
    verify_ssl: bool = True


PRICING_STORES: list[PricingStore] = [
    PricingStore(
        name="cetrogar",
        column="E",
        platform="magento",
        base_url="https://www.cetrogar.com.ar",
    ),
    PricingStore(
        name="oncity",
        column="F",
        platform="vtex",
        base_url="https://www.oncity.com",
        verify_ssl=False,
    ),
    PricingStore(
        name="castillo",
        column="G",
        platform="vtex",
        base_url="https://www.castillo.com.ar",
    ),
    PricingStore(
        name="monteshermanos",
        column="H",
        platform="monteshermanos",
        base_url="https://www.monteshermanos.com.ar",
    ),
]
