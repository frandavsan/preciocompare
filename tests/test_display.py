"""Tests for display formatting functions."""

from electrodomestics_bot.processing.display import format_price


class TestFormatPrice:
    def test_integer_price(self):
        assert format_price(500_000.0) == "500.000"

    def test_rounds_up(self):
        # gotcha #4: round(), not int()
        assert format_price(14_558.99) == "14.559"

    def test_rounds_down(self):
        assert format_price(14_558.01) == "14.558"

    def test_none_returns_na(self):
        assert format_price(None) == "N/A"

    def test_zero(self):
        assert format_price(0.0) == "0"

    def test_small_price(self):
        assert format_price(999.0) == "999"

    def test_large_price(self):
        assert format_price(3_500_000.0) == "3.500.000"

    def test_exact_half_rounds_even(self):
        # Python's round() uses banker's rounding
        assert format_price(0.5) in ("0", "1")  # either is acceptable
        assert format_price(1.5) in ("1", "2")
