"""Unit tests for src/input/parser.py"""

import pytest

from src.input.parser import (
    UserPreferences,
    normalize_city,
    parse_preferences,
    BUDGET_RANGES,
    MAX_EXTRA_PREFS_LEN,
)


# ---------------------------------------------------------------------------
# normalize_city tests
# ---------------------------------------------------------------------------

class TestNormalizeCity:
    def test_lowercase_city_title_cased(self):
        assert normalize_city("bangalore") == "Bangalore"

    def test_uppercase_city_normalized(self):
        assert normalize_city("DELHI") == "Delhi"

    def test_extra_spaces_stripped(self):
        assert normalize_city("  Mumbai  ") == "Mumbai"

    def test_alias_blr(self):
        assert normalize_city("blr") == "Bangalore"

    def test_alias_bengaluru(self):
        assert normalize_city("bengaluru") == "Bangalore"

    def test_alias_new_delhi(self):
        assert normalize_city("new delhi") == "Delhi"

    def test_alias_bombay(self):
        assert normalize_city("bombay") == "Mumbai"

    def test_alias_madras(self):
        assert normalize_city("madras") == "Chennai"

    def test_alias_calcutta(self):
        assert normalize_city("calcutta") == "Kolkata"

    def test_alias_gurgaon(self):
        assert normalize_city("gurgaon") == "Gurugram"

    def test_unknown_city_title_cased(self):
        """Unknown cities should still be title-cased."""
        assert normalize_city("shimla") == "Shimla"

    def test_mixed_case_alias(self):
        assert normalize_city("BLR") == "Bangalore"


# ---------------------------------------------------------------------------
# parse_preferences — happy path
# ---------------------------------------------------------------------------

class TestParsePreferencesHappyPath:
    def test_full_valid_input(self):
        p = parse_preferences({
            "location": "Bangalore",
            "budget": "medium",
            "cuisine": "Italian",
            "min_rating": 4.0,
            "extra_prefs": "quiet ambiance",
        })
        assert isinstance(p, UserPreferences)
        assert p.location == "Bangalore"
        assert p.budget_tier == "medium"
        assert p.budget_range == (400, 1000)
        assert p.cuisine == "Italian"
        assert p.min_rating == 4.0
        assert p.extra_prefs == "quiet ambiance"

    def test_raw_query_composed(self):
        p = parse_preferences({
            "location": "Delhi",
            "budget": "low",
            "cuisine": "Chinese",
            "min_rating": 3.5,
            "extra_prefs": "family friendly",
        })
        assert "Delhi" in p.raw_query
        assert "low" in p.raw_query
        assert "Chinese" in p.raw_query
        assert "3.5" in p.raw_query

    def test_budget_range_low(self):
        p = parse_preferences({"location": "Mumbai", "budget": "low"})
        assert p.budget_range == BUDGET_RANGES["low"]

    def test_budget_range_high(self):
        p = parse_preferences({"location": "Mumbai", "budget": "high"})
        assert p.budget_range == BUDGET_RANGES["high"]


# ---------------------------------------------------------------------------
# parse_preferences — location validation
# ---------------------------------------------------------------------------

class TestLocationValidation:
    def test_empty_location_raises(self):
        with pytest.raises(ValueError, match="Location is required"):
            parse_preferences({"location": "", "budget": "low"})

    def test_whitespace_only_location_raises(self):
        with pytest.raises(ValueError, match="Location is required"):
            parse_preferences({"location": "   ", "budget": "low"})

    def test_missing_location_raises(self):
        with pytest.raises(ValueError, match="Location is required"):
            parse_preferences({"budget": "low"})

    def test_lowercase_location_normalized(self):
        p = parse_preferences({"location": "bangalore", "budget": "low"})
        assert p.location == "Bangalore"

    def test_alias_location_resolved(self):
        p = parse_preferences({"location": "blr", "budget": "low"})
        assert p.location == "Bangalore"


# ---------------------------------------------------------------------------
# parse_preferences — budget validation
# ---------------------------------------------------------------------------

class TestBudgetValidation:
    def test_invalid_budget_raises(self):
        with pytest.raises(ValueError, match="Invalid budget"):
            parse_preferences({"location": "Delhi", "budget": "expensive"})

    def test_missing_budget_raises(self):
        with pytest.raises(ValueError, match="Budget is required"):
            parse_preferences({"location": "Delhi"})

    def test_uppercase_budget_normalized(self):
        p = parse_preferences({"location": "Delhi", "budget": "MEDIUM"})
        assert p.budget_tier == "medium"

    def test_mixed_case_budget_normalized(self):
        p = parse_preferences({"location": "Delhi", "budget": "High"})
        assert p.budget_tier == "high"

    def test_all_valid_budgets_accepted(self):
        for budget in ["low", "medium", "high"]:
            p = parse_preferences({"location": "Delhi", "budget": budget})
            assert p.budget_tier == budget


# ---------------------------------------------------------------------------
# parse_preferences — optional fields & defaults
# ---------------------------------------------------------------------------

class TestOptionalFieldsAndDefaults:
    def test_cuisine_defaults_to_any(self):
        p = parse_preferences({"location": "Delhi", "budget": "low"})
        assert p.cuisine == "Any"

    def test_cuisine_none_defaults_to_any(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "cuisine": None})
        assert p.cuisine == "Any"

    def test_cuisine_empty_string_defaults_to_any(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "cuisine": ""})
        assert p.cuisine == "Any"

    def test_min_rating_defaults_to_3(self):
        p = parse_preferences({"location": "Delhi", "budget": "low"})
        assert p.min_rating == 3.0

    def test_extra_prefs_defaults_to_empty(self):
        p = parse_preferences({"location": "Delhi", "budget": "low"})
        assert p.extra_prefs == ""


# ---------------------------------------------------------------------------
# parse_preferences — rating clamping
# ---------------------------------------------------------------------------

class TestRatingClamping:
    def test_rating_above_5_clamped(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "min_rating": 6.0})
        assert p.min_rating == 5.0

    def test_rating_below_0_clamped(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "min_rating": -1.0})
        assert p.min_rating == 0.0

    def test_rating_exactly_5_accepted(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "min_rating": 5.0})
        assert p.min_rating == 5.0

    def test_rating_exactly_0_accepted(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "min_rating": 0.0})
        assert p.min_rating == 0.0

    def test_string_numeric_rating_coerced(self):
        p = parse_preferences({"location": "Delhi", "budget": "low", "min_rating": "4"})
        assert p.min_rating == 4.0

    def test_non_numeric_rating_raises(self):
        with pytest.raises(TypeError, match="min_rating must be a number"):
            parse_preferences({"location": "Delhi", "budget": "low", "min_rating": "four"})


# ---------------------------------------------------------------------------
# parse_preferences — extra_prefs truncation
# ---------------------------------------------------------------------------

class TestExtraPrefsTruncation:
    def test_long_extra_prefs_truncated(self):
        long_text = "x" * 500
        p = parse_preferences({
            "location": "Delhi",
            "budget": "low",
            "extra_prefs": long_text,
        })
        assert len(p.extra_prefs) == MAX_EXTRA_PREFS_LEN

    def test_short_extra_prefs_unchanged(self):
        p = parse_preferences({
            "location": "Delhi",
            "budget": "low",
            "extra_prefs": "quiet place",
        })
        assert p.extra_prefs == "quiet place"

    def test_exactly_200_chars_unchanged(self):
        text = "a" * 200
        p = parse_preferences({
            "location": "Delhi",
            "budget": "low",
            "extra_prefs": text,
        })
        assert len(p.extra_prefs) == 200
