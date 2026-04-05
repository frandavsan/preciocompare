"""Tier 3 — Fravega snapshot/contract tests.

Feeds recorded GraphQL responses to FravegaAdapter's parser methods and asserts
that field extraction still produces the expected output. When Fravega changes
their GQL schema, these tests break at build time.
"""

import electrodomestics_bot.fetching.adapters  # noqa: F401  — avoid circular import
from electrodomestics_bot.fetching.platforms.fravega import FravegaAdapter

from conftest import load_snapshot

_load = load_snapshot


class _TestAdapter(FravegaAdapter):
    name = "test_fravega"
    base_url = "https://www.fravega.com"


_adapter = _TestAdapter()


class TestFravegaSearchItemInternational:
    """International product with 12-cuota installments."""

    ITEM = _load("fravega_search_item.json")

    def test_extracts_price(self):
        assert FravegaAdapter._extract_price(self.ITEM) == 1899999.0

    def test_extracts_sku(self):
        assert FravegaAdapter._extract_sku(self.ITEM) == "SKU-S26-256"

    def test_extracts_seller_id(self):
        assert FravegaAdapter._extract_seller_id(self.ITEM) == "seller-fravega-01"

    def test_detects_international(self):
        assert FravegaAdapter._extract_international(self.ITEM) is True

    def test_extracts_installments_fast(self):
        installments = FravegaAdapter._extract_installments_fast(self.ITEM, 1899999.0)
        assert len(installments) == 1
        assert installments[0].count == 12
        assert installments[0].amount == round(1899999.0 / 12, 2)
        assert installments[0].cards == []

    def test_ignores_non_installment_labels(self):
        installments = FravegaAdapter._extract_installments_fast(self.ITEM, 1899999.0)
        # "Envío gratis" should not produce an installment
        assert all(i.count > 1 for i in installments)


class TestFravegaDomesticItem:
    """Domestic product — sellerCondition is empty."""

    ITEM = _load("fravega_search_item_domestic.json")

    def test_not_international(self):
        assert FravegaAdapter._extract_international(self.ITEM) is False

    def test_extracts_price(self):
        assert FravegaAdapter._extract_price(self.ITEM) == 899000.0

    def test_extracts_18_cuotas(self):
        installments = FravegaAdapter._extract_installments_fast(self.ITEM, 899000.0)
        assert len(installments) == 1
        assert installments[0].count == 18
        assert installments[0].amount == round(899000.0 / 18, 2)


class TestFravegaMissingFields:
    """Edge cases: missing or malformed nested structures."""

    def test_price_none_when_no_skus(self):
        assert FravegaAdapter._extract_price({}) is None

    def test_sku_none_when_no_skus(self):
        assert FravegaAdapter._extract_sku({}) is None

    def test_seller_id_none_when_no_sellers(self):
        assert FravegaAdapter._extract_seller_id({}) is None

    def test_not_international_when_no_condition(self):
        assert FravegaAdapter._extract_international({}) is False

    def test_installments_fast_with_no_price(self):
        item = _load("fravega_search_item.json")
        installments = FravegaAdapter._extract_installments_fast(item, None)
        assert len(installments) == 1
        assert installments[0].amount == 0.0


class TestFravegaParsePlans:
    """Plans GQL response parsing — mirrors website display logic."""

    PLANS = _load("fravega_plans.json")

    def test_base_network_counts(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        cards_by_count = {i.count: i.cards for i in result}
        # Visa and Mastercard both have generic 6x
        assert "Visa" in cards_by_count[6]
        assert "Mastercard" in cards_by_count[6]

    def test_issuer_shown_when_exceeds_base(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        cards_by_count = {i.count: i.cards for i in result}
        # BNA offers 12x via Visa, but Visa generic is only 6x → BNA shown at 12x
        assert "Banco Nación" in cards_by_count[12]

    def test_issuer_suppressed_when_matches_base(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        cards_by_count = {i.count: i.cards for i in result}
        # BBVA offers 6x via Visa, same as Visa generic → BBVA suppressed
        six_x_cards = cards_by_count[6]
        assert "BBVA" not in six_x_cards

    def test_excludes_with_interest(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        # 12x Visa with interest should not appear as a separate Visa entry
        cards_by_count = {i.count: i.cards for i in result}
        assert "Visa" not in cards_by_count.get(12, [])

    def test_excludes_single_installment(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        counts = [i.count for i in result]
        assert 1 not in counts

    def test_amounts_are_zero(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        # _parse_plans sets amount=0.0; caller fills in price/count
        assert all(i.amount == 0.0 for i in result)

    def test_sorted_descending(self):
        result = FravegaAdapter._parse_plans(self.PLANS)
        counts = [i.count for i in result]
        assert counts == sorted(counts, reverse=True)
