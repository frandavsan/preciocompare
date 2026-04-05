"""Tier 3 — VTEX snapshot/contract tests.

Feeds recorded API responses to VtexAdapter's parser methods and asserts
that field extraction still produces the expected output. When VTEX changes
their API shape, these tests break at build time — before it hits production.
"""

import electrodomestics_bot.fetching.adapters  # noqa: F401  — avoid circular import
from electrodomestics_bot.fetching.platforms.vtex import VtexAdapter

from conftest import SNAPSHOTS, load_snapshot

_load = load_snapshot


class _TestAdapter(VtexAdapter):
    name = "test_store"
    base_url = "https://www.teststore.com.ar"


_adapter = _TestAdapter()


class TestVtexProductExtraction:
    """International multi-seller product with installments."""

    PRODUCT = _load("vtex_product.json")

    def test_extracts_price_from_real_seller(self):
        assert _adapter._extract_price(self.PRODUCT) == 1499999.99

    def test_skips_dummy_seller(self):
        item = self.PRODUCT["items"][0]
        seller = _adapter._get_real_seller(item)
        assert seller["sellerId"] == "mktplace01"
        assert seller["commertialOffer"]["Price"] == 1499999.99

    def test_extracts_product_reference(self):
        assert self.PRODUCT["productReference"] == "SM-S926BZKDARO"

    def test_extracts_fallback_ref_id(self):
        assert _adapter._extract_ref(self.PRODUCT) == "SM-S926BZKD"

    def test_detects_international_from_categories(self):
        assert _adapter._is_international(self.PRODUCT) is True

    def test_detects_international_from_clusters(self):
        product = {**self.PRODUCT, "categories": ["/Telefonía/"]}
        assert _adapter._is_international(product) is True

    def test_is_available(self):
        assert _adapter._is_available(self.PRODUCT) is True

    def test_extracts_installments(self):
        installments = _adapter._extract_installments(self.PRODUCT)
        # Should have 2 tiers: 3x AmEx and 6x Visa+Mastercard
        # Excludes: 1x (count<=1), 12x Visa (has interest), 3x debit (wrong group)
        assert len(installments) == 2
        counts = [i.count for i in installments]
        assert 3 in counts
        assert 6 in counts

    def test_installments_exclude_debit(self):
        installments = _adapter._extract_installments(self.PRODUCT)
        all_cards = [card for i in installments for card in i.cards]
        assert "Débito Visa" not in all_cards

    def test_installments_exclude_interest(self):
        installments = _adapter._extract_installments(self.PRODUCT)
        # 12x Visa has InterestRate=5.99, should be excluded
        counts = [i.count for i in installments]
        assert 12 not in counts

    def test_installment_cards_grouped(self):
        installments = _adapter._extract_installments(self.PRODUCT)
        six_x = next(i for i in installments if i.count == 6)
        assert "Visa" in six_x.cards
        assert "Mastercard" in six_x.cards

    def test_installment_amounts(self):
        installments = _adapter._extract_installments(self.PRODUCT)
        three_x = next(i for i in installments if i.count == 3)
        assert three_x.amount == 500000.0
        six_x = next(i for i in installments if i.count == 6)
        assert six_x.amount == 250000.0


class TestVtexUnavailableProduct:
    """Product with zero stock — still has a price but is not available."""

    PRODUCT = _load("vtex_unavailable_product.json")

    def test_not_available(self):
        assert _adapter._is_available(self.PRODUCT) is False

    def test_price_still_extracted(self):
        assert _adapter._extract_price(self.PRODUCT) == 899999.0

    def test_not_international(self):
        assert _adapter._is_international(self.PRODUCT) is False

    def test_no_installments(self):
        assert _adapter._extract_installments(self.PRODUCT) == []


class TestVtexLegacyNormalization:
    """Legacy catalog API product — different format for link and productClusters."""

    RAW = _load("vtex_legacy_product.json")

    def test_link_stripped_to_relative(self):
        normalized = _adapter._normalize_legacy_product(self.RAW)
        assert normalized["link"] == "/samsung-galaxy-s26-ultra-256gb/p"

    def test_clusters_converted_to_list(self):
        normalized = _adapter._normalize_legacy_product(self.RAW)
        clusters = normalized["productClusters"]
        assert isinstance(clusters, list)
        assert {"id": "628", "name": "Full Catalogo"} in clusters
        assert {"id": "700", "name": "Compra Internacional"} in clusters

    def test_international_detected_after_normalization(self):
        normalized = _adapter._normalize_legacy_product(self.RAW)
        assert _adapter._is_international(normalized) is True

    def test_price_extracted(self):
        normalized = _adapter._normalize_legacy_product(self.RAW)
        assert _adapter._extract_price(normalized) == 1499999.99
