"""Tests for the SQLite cache layer."""

from electrodomestics_bot.fetching.cache import (
    _norm,
    all_known_queries,
    get_product_by_url,
    get_query_products,
    has_query,
    insert_new_products,
    product_count,
    record_query,
    run_migrations,
    upsert_products,
)
from electrodomestics_bot.models import Installment

from conftest import make_product


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_creates_schema(self, cache_db):
        tables = {
            r["name"]
            for r in cache_db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "products" in tables
        assert "installments" in tables
        assert "installment_cards" in tables
        assert "queries" in tables
        assert "query_products" in tables
        assert "schema_version" in tables

    def test_schema_version_is_current(self, cache_db):
        row = cache_db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == 2

    def test_idempotent(self, cache_db):
        # Running migrations again should not raise
        run_migrations(cache_db)
        row = cache_db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == 2


# ---------------------------------------------------------------------------
# _norm
# ---------------------------------------------------------------------------

class TestNorm:
    def test_lowercases(self):
        assert _norm("PS5") == "ps5"

    def test_strips_whitespace(self):
        assert _norm("  PS5  ") == "ps5"

    def test_combined(self):
        assert _norm("  Samsung S26  ") == "samsung s26"


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------

class TestUpsertProducts:
    def test_insert_and_retrieve(self, cache_db):
        p = make_product(name="Samsung S26", sku="SKU1", price=500_000, url="https://store.com/s26")
        upsert_products(cache_db, "store_a", [p])

        result = get_product_by_url(cache_db, "store_a", "https://store.com/s26")
        assert result is not None
        assert result.name == "Samsung S26"
        assert result.price == 500_000
        assert result.sku == "SKU1"

    def test_upsert_updates_existing(self, cache_db):
        p1 = make_product(name="Samsung S26", price=500_000, url="https://store.com/s26")
        upsert_products(cache_db, "store_a", [p1])

        p2 = make_product(name="Samsung S26 Updated", price=450_000, url="https://store.com/s26")
        upsert_products(cache_db, "store_a", [p2])

        result = get_product_by_url(cache_db, "store_a", "https://store.com/s26")
        assert result.name == "Samsung S26 Updated"
        assert result.price == 450_000

    def test_with_installments(self, cache_db):
        inst = Installment(count=12, amount=41_666.67, cards=["Visa", "Mastercard"])
        p = make_product(name="Samsung S26", url="https://store.com/s26", installments=[inst])
        upsert_products(cache_db, "store_a", [p])

        result = get_product_by_url(cache_db, "store_a", "https://store.com/s26")
        assert len(result.installments) == 1
        assert result.installments[0].count == 12
        assert result.installments[0].amount == 41_666.67
        assert "Visa" in result.installments[0].cards
        assert "Mastercard" in result.installments[0].cards

    def test_product_count(self, cache_db):
        p1 = make_product(url="https://store.com/1")
        p2 = make_product(url="https://store.com/2")
        upsert_products(cache_db, "store_a", [p1, p2])

        assert product_count(cache_db, "store_a") == 2
        assert product_count(cache_db, "store_b") == 0


class TestInsertNewProducts:
    def test_inserts_new(self, cache_db):
        p = make_product(name="Samsung S26", url="https://store.com/s26")
        insert_new_products(cache_db, "store_a", [p])

        result = get_product_by_url(cache_db, "store_a", "https://store.com/s26")
        assert result is not None
        assert result.name == "Samsung S26"

    def test_skips_existing(self, cache_db):
        p1 = make_product(name="Samsung S26 Original", price=500_000, url="https://store.com/s26")
        upsert_products(cache_db, "store_a", [p1])

        p2 = make_product(name="Samsung S26 New", price=450_000, url="https://store.com/s26")
        insert_new_products(cache_db, "store_a", [p2])

        # Original should be preserved
        result = get_product_by_url(cache_db, "store_a", "https://store.com/s26")
        assert result.name == "Samsung S26 Original"
        assert result.price == 500_000


# ---------------------------------------------------------------------------
# Query tracking
# ---------------------------------------------------------------------------

class TestQueryTracking:
    def test_has_query_false_initially(self, cache_db):
        assert not has_query(cache_db, "store_a", "ps5")

    def test_record_and_check_query(self, cache_db):
        p = make_product(url="https://store.com/ps5")
        upsert_products(cache_db, "store_a", [p])
        record_query(cache_db, "store_a", "PS5", ["https://store.com/ps5"])

        assert has_query(cache_db, "store_a", "PS5")
        assert has_query(cache_db, "store_a", "ps5")  # case-insensitive
        assert has_query(cache_db, "store_a", "  PS5  ")  # whitespace-stripped

    def test_get_query_products(self, cache_db):
        p1 = make_product(name="PS5 Console", url="https://store.com/ps5")
        p2 = make_product(name="PS5 Controller", url="https://store.com/ps5-ctrl")
        upsert_products(cache_db, "store_a", [p1, p2])
        record_query(cache_db, "store_a", "ps5", [
            "https://store.com/ps5",
            "https://store.com/ps5-ctrl",
        ])

        products = get_query_products(cache_db, "store_a", "ps5")
        assert len(products) == 2
        names = {p.name for p in products}
        assert "PS5 Console" in names
        assert "PS5 Controller" in names

    def test_all_known_queries(self, cache_db):
        p = make_product(url="https://store.com/1")
        upsert_products(cache_db, "store_a", [p])
        record_query(cache_db, "store_a", "ps5", ["https://store.com/1"])
        record_query(cache_db, "store_a", "xbox", ["https://store.com/1"])

        queries = all_known_queries(cache_db)
        assert ("store_a", "ps5") in queries
        assert ("store_a", "xbox") in queries

    def test_query_not_found_returns_empty(self, cache_db):
        products = get_query_products(cache_db, "store_a", "nonexistent")
        assert products == []
