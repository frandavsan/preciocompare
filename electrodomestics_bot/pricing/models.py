"""
Data models for the pricing spreadsheet feature.

These are intentionally separate from the main ProductResult/Installment models
in models.py — the pricing pipeline has different data needs (interest rates,
sin/con distinction, card issuers) that don't belong in the search pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PaymentPlan:
    """A single installment plan from a store, with interest rate data."""
    card_system: str              # "Visa", "Mastercard", "NaranjaX", "Mercado Pago"
    card_issuer: str | None       # "Macro", "Nacion", "Santander", None (generic)
    installment_count: int        # 1, 3, 6, 9...
    has_interest: bool            # True = con interes
    interest_rate: float          # total cost rate as decimal (0.1952 = 19.52%)
    amount_per_installment: float # customer pays this per period


@dataclass
class PricingResult:
    """All payment plans fetched from a single store for a single product."""
    store_name: str
    product_name: str
    product_url: str
    base_price: float             # reference price for rate calculation
    plans: list[PaymentPlan] = field(default_factory=list)
    status: Literal["ok", "error"] = "ok"
    error_detail: str | None = None


InterestType = Literal["sin", "con", "unknown"]


@dataclass
class TemplateRow:
    """A row parsed from the Excel template — identifies which data point to fill."""
    excel_row: int                # 1-based row number in the spreadsheet
    card_label: str               # column A: "VISA/MASTERCARD/AMEX", "NARANJAX", etc.
    installment_count: int        # column B: 1, 3, 6, 9...
    description: str              # column I: "3 sin int Macro", "Naranja 9 c/i", etc.
    interest_type: InterestType   # parsed from description: "sin", "con", or "unknown"
    cards: frozenset[str]         # normalized card systems this row matches
    issuer: str | None            # bank issuer if applicable ("Macro", "Nacion", etc.)
