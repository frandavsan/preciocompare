"""Tier 3 — Megatone/Doofinder snapshot/contract tests.

Feeds recorded Doofinder and retornarplanes responses to MegatoneAdapter's
parser methods and asserts that field extraction still produces the expected
output. When Doofinder or Megatone changes their API shape, these tests break
at build time.
"""

import electrodomestics_bot.fetching.adapters  # noqa: F401  — avoid circular import
from electrodomestics_bot.fetching.platforms.megatone import MegatoneAdapter

from conftest import load_snapshot

_load = load_snapshot


class _TestAdapter(MegatoneAdapter):
    name = "test_megatone"
    base_url = "https://www.megatone.net"
    _doofinder_hashid = "test_hash"


_adapter = _TestAdapter()


class TestMegatoneProductParsing:
    """Standard in-stock product with free shipping and sin-interes installments."""

    RAW = _load("megatone_product.json")

    def test_extracts_name(self):
        result = _adapter._parse_product(self.RAW)
        assert result.name == "Samsung Galaxy S26 Ultra 256GB"

    def test_extracts_sku(self):
        result = _adapter._parse_product(self.RAW)
        assert result.sku == "MGT-S26-256"

    def test_extracts_sale_price_not_list_price(self):
        result = _adapter._parse_product(self.RAW)
        assert result.price == 1799000.0

    def test_extracts_url(self):
        result = _adapter._parse_product(self.RAW)
        assert result.url == "https://www.megatone.net/producto/samsung-galaxy-s26-ultra-256gb_MGT-S26-256"

    def test_available(self):
        result = _adapter._parse_product(self.RAW)
        assert result.available is True

    def test_free_shipping(self):
        result = _adapter._parse_product(self.RAW)
        assert result.free_shipping is True

    def test_not_international(self):
        result = _adapter._parse_product(self.RAW)
        assert result.international is False

    def test_has_sin_interes(self):
        assert _adapter._has_sin_interes(self.RAW) is True


class TestMegatoneInternationalProduct:
    """International marketplace product — no sin-interes, has Rebajas label."""

    RAW = _load("megatone_product_international.json")

    def test_international(self):
        result = _adapter._parse_product(self.RAW)
        assert result.international is True

    def test_no_free_shipping(self):
        result = _adapter._parse_product(self.RAW)
        assert result.free_shipping is False

    def test_no_sin_interes(self):
        assert _adapter._has_sin_interes(self.RAW) is False

    def test_available(self):
        result = _adapter._parse_product(self.RAW)
        assert result.available is True


class TestMegatoneUnavailableProduct:
    """Out-of-stock product."""

    RAW = _load("megatone_product_unavailable.json")

    def test_not_available(self):
        result = _adapter._parse_product(self.RAW)
        assert result.available is False

    def test_no_sin_interes(self):
        assert _adapter._has_sin_interes(self.RAW) is False

    def test_price_still_extracted(self):
        result = _adapter._parse_product(self.RAW)
        assert result.price == 899000.0


class TestMegatonePlansParsing:
    """retornarplanes response — sin-interes detection and card keyword mapping."""

    PLANS = _load("megatone_plans.json")["resumen"]

    def test_sin_interes_detection(self):
        sin_interes = [p for p in self.PLANS if _adapter._is_sin_interes(p)]
        assert len(sin_interes) == 3
        counts = sorted(int(p["cuotas"]) for p in sin_interes)
        assert counts == [3, 6, 12]

    def test_excludes_with_interest(self):
        with_interest = [p for p in self.PLANS if not _adapter._is_sin_interes(p)]
        assert len(with_interest) == 1
        assert int(with_interest[0]["cuotas"]) == 18


class TestMegatoneCardKeywords:
    """_card_name_from_tarjeta mapping from API labels to display names."""

    def test_visa(self):
        assert _adapter._card_name_from_tarjeta("VISA") == "Visa"

    def test_mastercard(self):
        assert _adapter._card_name_from_tarjeta("MASTERCARD") == "Mastercard"

    def test_amex(self):
        assert _adapter._card_name_from_tarjeta("AMERICAN EXPRESS") == "American Express"

    def test_mercado_pago(self):
        assert _adapter._card_name_from_tarjeta("MERCADO PAGO") == "Mercado Pago"

    def test_naranja(self):
        assert _adapter._card_name_from_tarjeta("NARANJA X") == "NaranjaX"

    def test_blacklisted_nativa(self):
        assert _adapter._card_name_from_tarjeta("NATIVA VISA") is None

    def test_unknown_card(self):
        assert _adapter._card_name_from_tarjeta("UNKNOWN CARD") is None


class TestMegatoneSortedTiers:
    """_sorted_tiers groups card_counts into descending (count, cards) tuples."""

    def test_groups_and_sorts(self):
        card_counts = {"Visa": 12, "Mastercard": 6, "Cabal": 6, "BNA": 18}
        tiers = MegatoneAdapter._sorted_tiers(card_counts)
        assert tiers[0] == (18, ["BNA"])
        assert tiers[1] == (12, ["Visa"])
        assert tiers[2][0] == 6
        assert sorted(tiers[2][1]) == ["Cabal", "Mastercard"]

    def test_empty_input(self):
        assert MegatoneAdapter._sorted_tiers({}) == []
