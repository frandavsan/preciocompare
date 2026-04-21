"""Tier 3 — Magento snapshot/contract tests.

Feeds recorded HTML snippets to MagentoAdapter's parser methods and asserts
that field extraction still produces the expected output. When a Magento store
changes their markup, these tests break at build time.
"""

import electrodomestics_bot.fetching.adapters  # noqa: F401  — avoid circular import
from electrodomestics_bot.fetching.platforms.magento import MagentoAdapter

from conftest import load_snapshot_soup

_load_soup = load_snapshot_soup


class _TestAdapter(MagentoAdapter):
    name = "test_store"
    base_url = "https://www.teststore.com.ar"


_adapter = _TestAdapter()


class TestMagentoSearchItem:
    """Standard search result <li> with ajaxWishlist data and installments."""

    SOUP = _load_soup("magento_search_item.html")
    LI = SOUP.find("li")

    def test_extracts_name_from_wishlist(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["name"] == "Televisor Samsung 55 4K UHD Smart TV UN55DU7000"

    def test_extracts_sku_from_wishlist(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["sku"] == "UN55DU7000GCZB"

    def test_extracts_price(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["price"] == 549999.50

    def test_extracts_url(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["url"] == "https://www.teststore.com.ar/televisor-samsung-55-4k-uhd-smart-tv.html"

    def test_extracts_installment_count(self):
        item = _adapter._parse_search_item(self.LI)
        assert len(item["installments"]) == 1
        assert item["installments"][0].count == 18

    def test_extracts_installment_amount(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["installments"][0].amount == 30555.53

    def test_installments_have_no_cards(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["installments"][0].cards == []


class TestMagentoNoWishlist:
    """Search result using Amasty_Label instead of ajaxWishlist — falls back to img alt."""

    SOUP = _load_soup("magento_search_item_no_wishlist.html")
    LI = SOUP.find("li")

    def test_falls_back_to_img_alt(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["name"] == "Heladera Samsung 394L No Frost"

    def test_sku_is_none(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["sku"] is None

    def test_price_extracted(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["price"] == 899000.0

    def test_no_installments(self):
        item = _adapter._parse_search_item(self.LI)
        assert item["installments"] == []


class TestMagentoPlaceholder:
    """BrainDW recommendation placeholder <li> — should be rejected."""

    SOUP = _load_soup("magento_search_item_placeholder.html")
    LI = SOUP.find("li")

    def test_returns_none(self):
        assert _adapter._parse_search_item(self.LI) is None


class TestMagentoCardLogos:
    """Card name extraction from Summa Solutions logo image filenames."""

    SOUP = _load_soup("magento_card_logos.html")
    DIV = SOUP.find("div", class_="payment-info-image")

    def test_extracts_all_cards(self):
        cards = _adapter._cards_from_image_div(self.DIV)
        assert "Visa" in cards
        assert "Mastercard" in cards
        assert "NaranjaX" in cards
        assert "American Express" in cards
        assert "Cabal" in cards

    def test_card_count(self):
        cards = _adapter._cards_from_image_div(self.DIV)
        assert len(cards) == 5

    def test_no_duplicates(self):
        cards = _adapter._cards_from_image_div(self.DIV)
        assert len(cards) == len(set(cards))
