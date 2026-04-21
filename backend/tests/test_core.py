"""Tests for core utility functions (matches_query)."""

from electrodomestics_bot.fetching.core import matches_query


class TestMatchesQuery:
    # --- Basic matching ---

    def test_exact_model_match(self):
        assert matches_query("Samsung Galaxy S26 Ultra 256GB", "S26")

    def test_case_insensitive(self):
        assert matches_query("SAMSUNG GALAXY S26", "samsung galaxy s26")

    def test_multi_word_query(self):
        assert matches_query("Samsung Galaxy S26 Ultra 256GB", "Samsung S26")

    def test_all_words_must_match(self):
        assert not matches_query("Samsung Galaxy S26 Ultra", "Samsung S27")

    # --- Accent normalization ---

    def test_accent_match(self):
        assert matches_query("Televisión Samsung 55", "television")

    def test_accent_in_query(self):
        assert matches_query("Telefono Motorola G15", "Teléfono")

    # --- Short token word boundary (gotcha #3) ---

    def test_short_token_word_boundary(self):
        # "TV" should NOT match "VTEX" (substring but not word boundary)
        assert not matches_query("VTEX Store Product", "TV")

    def test_short_token_matches_word(self):
        assert matches_query("Smart TV Samsung 55 Pulgadas", "TV")

    def test_lg_does_not_match_algo(self):
        assert not matches_query("ALGO Random Product", "LG")

    def test_lg_matches_lg_brand(self):
        assert matches_query("LG OLED 55 C4", "LG")

    def test_4k_word_boundary(self):
        assert matches_query("Samsung 55 4K UHD Smart TV", "4K")

    # --- Spacing and compacting ---

    def test_spaces_collapsed_for_long_tokens(self):
        # "512gb" should match "512 GB" after compact normalization
        assert matches_query("Samsung 512 GB Storage", "512gb")

    def test_sku_substring_match(self):
        assert matches_query("UN55PUD7310/77 Samsung", "55PUD7310")

    # --- Edge cases ---

    def test_empty_query_matches_everything(self):
        assert matches_query("Any Product Name", "")

    def test_empty_product_name(self):
        assert not matches_query("", "samsung")

    def test_special_regex_chars_in_query(self):
        # Regex metacharacters must be escaped, not interpreted as quantifiers
        assert not matches_query("Some Product", "a+")
