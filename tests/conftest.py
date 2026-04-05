"""Shared fixtures for the test suite."""

import json
import sqlite3
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from electrodomestics_bot.models import Installment, ProductResult, StoreSearchResult

# ---------------------------------------------------------------------------
# Snapshot helpers — load recorded API/HTML fixtures from tests/snapshots/
# ---------------------------------------------------------------------------

SNAPSHOTS = Path(__file__).parent / "snapshots"


def load_snapshot(name: str) -> dict:
    return json.loads((SNAPSHOTS / name).read_text(encoding="utf-8"))


def load_snapshot_soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((SNAPSHOTS / name).read_text(encoding="utf-8"), "lxml")


# ---------------------------------------------------------------------------
# Factory helpers — build test objects with sensible defaults
# ---------------------------------------------------------------------------

def make_product(
    name: str = "Test Product",
    sku: str = "SKU001",
    price: float | None = 100_000.0,
    url: str = "https://store.com/product",
    installments: list[Installment] | None = None,
    free_shipping: bool = False,
    international: bool | None = False,
    available: bool = True,
) -> ProductResult:
    return ProductResult(
        name=name,
        sku=sku,
        price=price,
        currency="ARS",
        url=url,
        installments=installments or [],
        free_shipping=free_shipping,
        international=international,
        available=available,
    )


def make_ssr(
    products: list[ProductResult] | None = None,
    status: str = "ok",
    duration_ms: int | None = None,
) -> StoreSearchResult:
    return StoreSearchResult(products=products or [], status=status, duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Cache DB fixture — in-memory, fresh per test
# ---------------------------------------------------------------------------

@pytest.fixture
def cache_db():
    """In-memory SQLite DB with cache schema applied."""
    from electrodomestics_bot.fetching.cache import run_migrations

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    run_migrations(conn)
    yield conn
    conn.close()
