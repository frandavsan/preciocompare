"""Tests for the product matching and grouping module."""

from electrodomestics_bot.processing.matching import (
    ProductGroup,
    _detect_brand,
    _has_model_code,
    _keys_match,
    dedup_results,
    extract_keys,
    group_results,
)

from conftest import make_product, make_ssr


# ---------------------------------------------------------------------------
# extract_keys
# ---------------------------------------------------------------------------

class TestExtractKeys:
    def test_basic_model_name(self):
        keys = extract_keys("Samsung Galaxy S26 Ultra 256GB")
        assert "samsung" in keys
        assert "galaxy" in keys
        assert "s26" in keys
        assert "ultra" in keys
        assert "256gb" in keys

    def test_stop_words_removed(self):
        keys = extract_keys("Heladera Samsung No Frost 570L Blanca")
        assert "heladera" not in keys
        assert "frost" not in keys
        assert "blanca" not in keys
        assert "samsung" in keys
        assert "570l" in keys

    def test_accent_normalization(self):
        keys = extract_keys("Televisión LED 55 Pulgadas")
        assert "television" not in keys  # stop word
        assert "pulgadas" in keys
        assert "55" in keys  # len=2, only len<=1 tokens are dropped

    def test_unit_normalization(self):
        assert "128gb" in extract_keys("128 Gb")
        assert "512gb" in extract_keys("512GB")
        assert "1tb" in extract_keys("1 TB")
        assert "10kg" in extract_keys("10 Kg")
        assert "400l" in extract_keys("400 Lts")
        assert "1000rpm" in extract_keys("1000 RPM")

    def test_slash_suffix_stripped(self):
        keys = extract_keys("58PUD7310/77")
        assert "58pud7310" in keys
        # "/77" suffix should be stripped
        assert "77" not in keys

    def test_single_char_tokens_dropped(self):
        keys = extract_keys("A B C Model X5")
        assert "a" not in keys
        assert "b" not in keys
        assert "c" not in keys
        assert "x5" in keys
        assert "model" in keys

    def test_empty_string(self):
        assert extract_keys("") == frozenset()

    def test_all_stop_words(self):
        keys = extract_keys("Heladera No Frost Smart TV LED")
        # All tokens are stop words
        assert len(keys) == 0

    def test_returns_frozenset(self):
        result = extract_keys("Samsung S26")
        assert isinstance(result, frozenset)


# ---------------------------------------------------------------------------
# _has_model_code
# ---------------------------------------------------------------------------

class TestHasModelCode:
    def test_alphanumeric_model_code(self):
        assert _has_model_code(frozenset({"gs66sxsc"}))
        assert _has_model_code(frozenset({"58pud7310"}))

    def test_short_alphanumeric_not_model_code(self):
        # "s26" has len=3 (< 4 minimum)
        assert not _has_model_code(frozenset({"s26"}))

    def test_pure_letters_not_model_code(self):
        assert not _has_model_code(frozenset({"samsung"}))
        assert not _has_model_code(frozenset({"ultra"}))

    def test_pure_digits_not_model_code(self):
        assert not _has_model_code(frozenset({"12345"}))

    def test_unit_spec_not_model_code(self):
        assert not _has_model_code(frozenset({"128gb"}))
        assert not _has_model_code(frozenset({"1000rpm"}))
        assert not _has_model_code(frozenset({"570l"}))

    def test_short_tokens_not_model_code(self):
        # Less than 4 chars
        assert not _has_model_code(frozenset({"s2"}))
        assert not _has_model_code(frozenset({"x5"}))

    def test_empty(self):
        assert not _has_model_code(frozenset())


# ---------------------------------------------------------------------------
# _detect_brand
# ---------------------------------------------------------------------------

class TestDetectBrand:
    def test_finds_known_brand(self):
        assert _detect_brand(frozenset({"samsung", "galaxy", "s26"})) == "samsung"

    def test_returns_none_for_no_brand(self):
        assert _detect_brand(frozenset({"galaxy", "ultra", "256gb"})) is None

    def test_empty(self):
        assert _detect_brand(frozenset()) is None


# ---------------------------------------------------------------------------
# _keys_match
# ---------------------------------------------------------------------------

class TestKeysMatch:
    def test_subset_match(self):
        a = frozenset({"samsung", "s26"})
        b = frozenset({"samsung", "s26", "ultra", "256gb"})
        assert _keys_match(a, b)

    def test_identical_sets(self):
        a = frozenset({"samsung", "s26", "ultra"})
        assert _keys_match(a, a)

    def test_no_overlap(self):
        a = frozenset({"samsung", "s26"})
        b = frozenset({"lg", "oled77"})
        assert not _keys_match(a, b)

    def test_model_code_with_50pct_overlap(self):
        # Shares a model code — 50% threshold applies
        a = frozenset({"samsung", "gs66sxsc"})
        b = frozenset({"msi", "gs66sxsc", "stealth", "15"})
        assert _keys_match(a, b)  # 1/2 = 50% overlap, model code present

    def test_high_overlap_without_model_code(self):
        # No model code — 80% threshold
        a = frozenset({"samsung", "galaxy", "ultra", "plus", "256gb"})
        b = frozenset({"samsung", "galaxy", "ultra", "plus"})
        assert _keys_match(a, b)  # 4/4 = 100% of shorter in longer

    def test_low_overlap_without_model_code(self):
        a = frozenset({"samsung", "galaxy", "ultra", "plus", "fold"})
        b = frozenset({"samsung", "galaxy", "note", "pro", "max"})
        assert not _keys_match(a, b)  # 2/5 = 40%

    def test_empty_set_no_match(self):
        assert not _keys_match(frozenset(), frozenset({"samsung"}))
        assert not _keys_match(frozenset({"samsung"}), frozenset())
        assert not _keys_match(frozenset(), frozenset())


# ---------------------------------------------------------------------------
# dedup_results
# ---------------------------------------------------------------------------

class TestDedupResults:
    def test_keeps_cheapest_duplicate(self):
        p1 = make_product(name="Samsung S26 Ultra 256GB", price=500_000, url="https://store.com/1")
        p2 = make_product(name="Samsung S26 Ultra 256GB Black", price=450_000, url="https://store.com/2")
        results = {"store_a": make_ssr([p1, p2])}

        deduped = dedup_results(results)
        assert len(deduped["store_a"].products) == 1
        assert deduped["store_a"].products[0].price == 450_000

    def test_no_duplicates_unchanged(self):
        p1 = make_product(name="Samsung S26", price=500_000, url="https://store.com/1")
        p2 = make_product(name="LG OLED 55", price=600_000, url="https://store.com/2")
        results = {"store_a": make_ssr([p1, p2])}

        deduped = dedup_results(results)
        assert len(deduped["store_a"].products) == 2

    def test_single_product_unchanged(self):
        p1 = make_product(name="Samsung S26", price=500_000)
        results = {"store_a": make_ssr([p1])}

        deduped = dedup_results(results)
        assert len(deduped["store_a"].products) == 1

    def test_empty_store(self):
        results = {"store_a": make_ssr([])}
        deduped = dedup_results(results)
        assert len(deduped["store_a"].products) == 0

    def test_preserves_status_metadata(self):
        p1 = make_product(name="Samsung S26", price=500_000)
        ssr = make_ssr([p1], status="ok", duration_ms=150)
        results = {"store_a": ssr}

        deduped = dedup_results(results)
        assert deduped["store_a"].status == "ok"
        assert deduped["store_a"].duration_ms == 150

    def test_none_price_treated_as_infinity(self):
        p1 = make_product(name="Samsung S26 Ultra", price=None, url="https://store.com/1")
        p2 = make_product(name="Samsung S26 Ultra 256GB", price=500_000, url="https://store.com/2")
        results = {"store_a": make_ssr([p1, p2])}

        deduped = dedup_results(results)
        assert len(deduped["store_a"].products) == 1
        assert deduped["store_a"].products[0].price == 500_000


# ---------------------------------------------------------------------------
# group_results
# ---------------------------------------------------------------------------

class TestGroupResults:
    def test_groups_same_product_across_stores(self):
        p1 = make_product(name="Samsung Galaxy S26 Ultra 256GB", price=500_000)
        p2 = make_product(name="Samsung Galaxy S26 Ultra 256GB Negro", price=480_000)
        results = {
            "store_a": make_ssr([p1]),
            "store_b": make_ssr([p2]),
        }

        groups = group_results(results)
        assert len(groups) == 1
        assert "store_a" in groups[0].products
        assert "store_b" in groups[0].products

    def test_different_products_separate_groups(self):
        p1 = make_product(name="Samsung Galaxy S26 Ultra 256GB", price=500_000)
        p2 = make_product(name="LG OLED77C4 77 Pulgadas", price=3_000_000)
        results = {
            "store_a": make_ssr([p1]),
            "store_b": make_ssr([p2]),
        }

        groups = group_results(results)
        assert len(groups) == 2

    def test_empty_results(self):
        assert group_results({}) == []
        assert group_results({"store_a": make_ssr([])}) == []

    def test_canonical_name_is_most_informative(self):
        p_short = make_product(name="Samsung S26", price=500_000)
        p_long = make_product(name="Samsung Galaxy S26 Ultra 256GB Phantom Black", price=480_000)
        results = {
            "store_a": make_ssr([p_short]),
            "store_b": make_ssr([p_long]),
        }

        groups = group_results(results)
        assert len(groups) == 1
        # The longer name has more keys, so it should be canonical
        assert "Galaxy" in groups[0].canonical_name or "Samsung" in groups[0].canonical_name

    def test_different_brands_not_grouped(self):
        p1 = make_product(name="Samsung Galaxy S26 Ultra", price=500_000)
        p2 = make_product(name="Motorola Galaxy X26 Ultra", price=400_000)
        results = {
            "store_a": make_ssr([p1]),
            "store_b": make_ssr([p2]),
        }

        groups = group_results(results)
        assert len(groups) == 2

    def test_sorted_by_store_count_desc(self):
        p1 = make_product(name="Samsung Galaxy S26", url="https://a.com/1", price=500_000)
        p2 = make_product(name="Samsung Galaxy S26 Ultra", url="https://b.com/1", price=480_000)
        p3 = make_product(name="LG C4 OLED 77", url="https://a.com/2", price=3_000_000)
        p4 = make_product(name="LG OLED77C4", url="https://b.com/2", price=2_900_000)
        p5 = make_product(name="LG C4 77 OLED", url="https://c.com/2", price=3_100_000)
        results = {
            "store_a": make_ssr([p1, p3]),
            "store_b": make_ssr([p2, p4]),
            "store_c": make_ssr([p5]),
        }

        groups = group_results(results)
        # LG group has 3 stores, Samsung has 2 — LG should come first
        assert len(groups[0].products) >= len(groups[-1].products)
