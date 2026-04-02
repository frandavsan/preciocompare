from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Optional, TYPE_CHECKING

StoreStatus = Literal["ok", "error", "timeout"]


@dataclass
class Installment:
    count: int              # number of installments
    amount: float           # amount per installment
    cards: list[str] = field(default_factory=list)  # payment systems offering this option

    def to_dict(self) -> dict:
        return {"count": self.count, "amount": self.amount, "cards": self.cards}


@dataclass
class StoreSearchResult:
    """Per-store result from search_all_stores — carries status alongside products."""
    products: list["ProductResult"] = field(default_factory=list)
    status: StoreStatus = "ok"
    error_detail: Optional[str] = None    # e.g. "ConnectionError: 503"
    duration_ms: Optional[int] = None


@dataclass
class ProductResult:
    name: str
    sku: str
    price: Optional[float]
    currency: str
    url: str
    installments: list[Installment] = field(default_factory=list)
    free_shipping: bool = False
    international: Optional[bool] = False
    available: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "sku": self.sku,
            "price": self.price,
            "currency": self.currency,
            "url": self.url,
            "installments": [i.to_dict() for i in self.installments],
            "free_shipping": self.free_shipping,
            "international": self.international,
            "available": self.available,
        }


# ---------------------------------------------------------------------------
# Pydantic response models (API layer)
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class InstallmentResponse(BaseModel):
    count: int
    amount: float
    cards: list[str]


class ProductResponse(BaseModel):
    name: str
    sku: Optional[str]
    price: Optional[float]
    currency: str
    url: str
    installments: list[InstallmentResponse]
    free_shipping: bool
    international: Optional[bool]
    available: bool

    @classmethod
    def from_dataclass(cls, p: "ProductResult") -> "ProductResponse":
        return cls(
            name=p.name,
            sku=p.sku,
            price=p.price,
            currency=p.currency,
            url=p.url,
            installments=[
                InstallmentResponse(count=i.count, amount=i.amount, cards=i.cards)
                for i in p.installments
            ],
            free_shipping=p.free_shipping,
            international=p.international,
            available=p.available,
        )


class StoreStatusResponse(BaseModel):
    status: StoreStatus
    result_count: int
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None


class SearchResponse(BaseModel):
    query: str
    results: dict[str, list[ProductResponse]]
    store_status: dict[str, StoreStatusResponse] = {}
