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

from pydantic import BaseModel, Field


class InstallmentResponse(BaseModel):
    count: int = Field(description="Number of installments")
    amount: float = Field(description="Amount per installment in ARS")
    cards: list[str] = Field(
        description="Card networks or banks offering this option. "
        "Empty in fast mode (detail=false); populated in detail mode."
    )


class ProductResponse(BaseModel):
    name: str = Field(description="Product name as listed by the store")
    sku: Optional[str] = Field(description="Store SKU or reference ID")
    price: Optional[float] = Field(
        description="Final selling price in ARS. Null if the store did not return a price."
    )
    currency: str = Field(description="Currency code, always 'ARS'")
    url: str = Field(description="Direct URL to the product page on the store")
    installments: list[InstallmentResponse] = Field(
        description="Interest-free installment options only. Empty list if none available."
    )
    free_shipping: bool = Field(
        description="Whether home delivery is free (based on Buenos Aires postal code)"
    )
    international: Optional[bool] = Field(
        description="True = international marketplace product, "
        "False = domestic, null = concept not applicable to this store"
    )
    available: bool = Field(description="Whether the product is currently in stock")

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
    status: StoreStatus = Field(
        description="'ok' = results returned successfully, "
        "'error' = store fetch failed, "
        "'timeout' = store did not respond in time"
    )
    result_count: int = Field(description="Number of matching products returned by this store")
    error_detail: Optional[str] = Field(
        None,
        description="Error type and message (e.g. 'ConnectionError: 503'). "
        "Only populated when status is 'error' or 'timeout'.",
    )
    duration_ms: Optional[int] = Field(
        None, description="Wall-clock time for this store's fetch in milliseconds"
    )


class SearchResponse(BaseModel):
    query: str = Field(description="The original search query")
    results: dict[str, list[ProductResponse]] = Field(
        description="Products grouped by store name. Every configured store appears as a key, "
        "even if it returned zero results."
    )
    store_status: dict[str, StoreStatusResponse] = Field(
        default={},
        description="Per-store fetch metadata: status, result count, timing, and error details",
    )
