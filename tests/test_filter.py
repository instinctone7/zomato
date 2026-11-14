"""Unit tests for src/filter/engine.py"""

import pandas as pd
import pytest

from src.filter.engine import get_candidates, _hard_filter, _sort_and_limit
from src.input.parser import UserPreferences


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

def _make_prefs(**kwargs) -> UserPreferences:
    """Create a UserPreferences object with sensible defaults."""
    defaults = dict(
        location="Bangalore",
        budget_tier="medium",
        budget_range=(400, 1000),
        cuisine="Any",
        min_rating=3.0,
        extra_prefs="",
        raw_query="Bangalore, medium budget",
    )
    defaults.update(kwargs)
    return UserPreferences(**defaults)


def _make_df() -> pd.DataFrame:
    """Return a minimal cleaned DataFrame that mirrors preprocessor output."""
    return pd.DataFrame({
        "name": [
            "Top Italian Bangalore",    # Bangalore, medium, Italian, 4.8
            "Good Indian Bangalore",    # Bangalore, medium, Indian, 4.2
            "Low Budget Cafe",          # Bangalore, low, Any, 4.0
            "Delhi Dhaba",              # Delhi, medium, Indian, 4.5
            "Cheap Delhi Spot",         # Delhi, low, Chinese, 3.5
            "Pricey Bangalore",         # Bangalore, high, Continental, 4.6
            "Low Rated Place",          # Bangalore, medium, Indian, 2.0
        ],
        "city": [
            "Bangalore", "Bangalore", "Bangalore",
            "Delhi", "Delhi",
            "Bangalore",
            "Bangalore",
        ],
        "cuisines": [
            ["italian", "continental"],
            ["indian", "chinese"],
            ["cafe", "snacks"],
            ["indian"],
            ["chinese"],
            ["continental"],
            ["indian"],
        ],
        "rating": [4.8, 4.2, 4.0, 4.5, 3.5, 4.6, 2.0],
        "votes":  [300, 150, 80, 200, 60, 400, 20],
        "cost_for_two": [700, 600, 250, 500, 200, 1500, 650],
        "budget_tier": [
            "medium", "medium", "low",
            "medium", "low",
            "high",
            "medium",
        ],
        "has_online_delivery": [True, True, False, True, True, False, True],
        "has_table_booking":   [False, True, False, True, False, True, False],
        "restaurant_type": [
            "Casual Dining", "Casual Dining", "Quick Bites",
            "Casual Dining", "Quick Bites",
            "Fine Dining",
            "Casual Dining",
        ],
    })


@pytest.fixture
def df():
    return _make_df()


# ---------------------------------------------------------------------------
# get_candidates — happy path
# ---------------------------------------------------------------------------

class TestGetCandidatesHappyPath:
    def test_returns_dict_with_required_keys(self, df):
        prefs = _make_prefs()
        result = get_candidates(df, prefs)
        assert "candidates" in result
        assert "fallback_triggered" in result
        assert "fallback_reason" in result

    def test_returns_non_empty_candidates_on_match(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium", min_rating=3.0)
        result = get_candidates(df, prefs)
        assert len(result["candidates"]) > 0

    def test_fallback_not_triggered_on_exact_match(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium")
        result = get_candidates(df, prefs)
        assert result["fallback_triggered"] is False
        assert result["fallback_reason"] == ""

    def test_candidates_are_list_of_dicts(self, df):
        prefs = _make_prefs()
        result = get_candidates(df, prefs)
        assert isinstance(result["candidates"], list)
        for rec in result["candidates"]:
            assert isinstance(rec, dict)

    def test_candidate_dicts_have_required_fields(self, df):
        prefs = _make_prefs()
        result = get_candidates(df, prefs)
        required_keys = {"name", "city", "cuisines", "rating", "votes", "cost_for_two", "budget_tier"}
        for rec in result["candidates"]:
            assert required_keys.issubset(rec.keys()), f"Missing keys in: {rec.keys()}"


# ---------------------------------------------------------------------------
# get_candidates — sorting
# ---------------------------------------------------------------------------

class TestSorting:
    def test_candidates_sorted_by_rating_descending(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium", min_rating=0.0)
        result = get_candidates(df, prefs)
        ratings = [r["rating"] for r in result["candidates"]]
        assert ratings == sorted(ratings, reverse=True), "Not sorted by rating DESC"

    def test_equal_rating_sorted_by_votes_descending(self):
        """When ratings are equal, higher votes should come first."""
        df_tie = pd.DataFrame({
            "name": ["A", "B"],
            "city": ["Bangalore", "Bangalore"],
            "cuisines": [["indian"], ["indian"]],
            "rating": [4.5, 4.5],
            "votes": [50, 300],
            "cost_for_two": [600, 600],
            "budget_tier": ["medium", "medium"],
            "has_online_delivery": [True, True],
            "has_table_booking": [False, False],
            "restaurant_type": ["Casual Dining", "Casual Dining"],
        })
        prefs = _make_prefs(min_rating=0.0)
        result = get_candidates(df_tie, prefs)
        assert result["candidates"][0]["name"] == "B"  # higher votes first


# ---------------------------------------------------------------------------
# get_candidates — count limiting
# ---------------------------------------------------------------------------

class TestCountLimiting:
    def test_candidate_count_respects_max(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium", min_rating=0.0)
        result = get_candidates(df, prefs, max_candidates=2)
        assert len(result["candidates"]) <= 2

    def test_max_candidates_zero_clamped_to_one(self, df):
        prefs = _make_prefs()
        result = get_candidates(df, prefs, max_candidates=0)
        assert len(result["candidates"]) <= 1


# ---------------------------------------------------------------------------
# get_candidates — cuisine filter
# ---------------------------------------------------------------------------

class TestCuisineFilter:
    def test_cuisine_filter_applied(self, df):
        prefs = _make_prefs(cuisine="Italian", min_rating=0.0)
        result = get_candidates(df, prefs)
        for rec in result["candidates"]:
            assert "italian" in rec["cuisines"], (
                f"Non-Italian restaurant in results: {rec['name']}"
            )

    def test_cuisine_any_returns_all_cuisines(self, df):
        prefs_any = _make_prefs(cuisine="Any", min_rating=0.0)
        prefs_italian = _make_prefs(cuisine="Italian", min_rating=0.0)
        result_any = get_candidates(df, prefs_any)
        result_italian = get_candidates(df, prefs_italian)
        # "Any" should return >= Italian-specific results
        assert len(result_any["candidates"]) >= len(result_italian["candidates"])

    def test_cuisine_filter_is_case_insensitive(self, df):
        prefs_upper = _make_prefs(cuisine="ITALIAN", min_rating=0.0)
        prefs_lower = _make_prefs(cuisine="italian", min_rating=0.0)
        r_upper = get_candidates(df, prefs_upper)
        r_lower = get_candidates(df, prefs_lower)
        names_upper = {r["name"] for r in r_upper["candidates"]}
        names_lower = {r["name"] for r in r_lower["candidates"]}
        assert names_upper == names_lower


# ---------------------------------------------------------------------------
# get_candidates — rating filter
# ---------------------------------------------------------------------------

class TestRatingFilter:
    def test_min_rating_filter_applied(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium", min_rating=4.0)
        result = get_candidates(df, prefs)
        for rec in result["candidates"]:
            assert rec["rating"] >= 4.0, (
                f"Restaurant with rating {rec['rating']} below threshold"
            )

    def test_low_rated_place_excluded(self, df):
        prefs = _make_prefs(location="Bangalore", budget_tier="medium", min_rating=3.0)
        result = get_candidates(df, prefs)
        names = [r["name"] for r in result["candidates"]]
        assert "Low Rated Place" not in names  # rating=2.0, below 3.0


# ---------------------------------------------------------------------------
# get_candidates — fallback strategy
# ---------------------------------------------------------------------------

class TestFallbackStrategy:
    def test_fallback_triggered_when_no_exact_match(self, df):
        # Request high-budget Italian in Bangalore — no match in test data
        prefs = _make_prefs(
            location="Bangalore",
            budget_tier="high",
            cuisine="Italian",
            min_rating=4.0,
        )
        result = get_candidates(df, prefs)
        assert result["fallback_triggered"] is True

    def test_fallback_reason_non_empty_on_trigger(self, df):
        prefs = _make_prefs(
            location="Bangalore",
            budget_tier="high",
            cuisine="Italian",
            min_rating=4.0,
        )
        result = get_candidates(df, prefs)
        assert isinstance(result["fallback_reason"], str)
        assert len(result["fallback_reason"]) > 0

    def test_no_match_at_all_returns_empty_list(self, df):
        # City not in dataset — will fall through all fallbacks
        prefs = _make_prefs(
            location="Atlantis",
            budget_tier="low",
            cuisine="Martian",
            min_rating=5.0,
        )
        result = get_candidates(df, prefs)
        assert result["candidates"] == []
        assert result["fallback_triggered"] is True
        assert "Atlantis" in result["fallback_reason"]

    def test_fallback_budget_relaxation(self, df):
        """medium → relaxes to low or high to find results."""
        # Only low-budget restaurants exist in Bangalore for "cafe" cuisine
        prefs = _make_prefs(
            location="Bangalore",
            budget_tier="medium",
            cuisine="cafe",
            min_rating=0.0,
        )
        result = get_candidates(df, prefs)
        # Should fallback and find "Low Budget Cafe"
        assert result["fallback_triggered"] is True

    def test_fallback_cuisine_relaxation(self):
        """When budget fallback also fails, cuisine is relaxed to Any."""
        df_limited = pd.DataFrame({
            "name": ["Only One"],
            "city": ["Bangalore"],
            "cuisines": [["indian"]],
            "rating": [4.5],
            "votes": [100],
            "cost_for_two": [300],
            "budget_tier": ["low"],
            "has_online_delivery": [True],
            "has_table_booking": [False],
            "restaurant_type": ["Casual Dining"],
        })
        # medium budget + Italian → no match; fallback should find low + indian
        prefs = _make_prefs(
            location="Bangalore",
            budget_tier="medium",
            cuisine="Italian",
            min_rating=0.0,
        )
        result = get_candidates(df_limited, prefs)
        assert result["fallback_triggered"] is True
        # Should eventually find the one Indian low-budget place
        assert len(result["candidates"]) > 0


# ---------------------------------------------------------------------------
# JSON serializability
# ---------------------------------------------------------------------------

class TestJsonSerializability:
    def test_candidates_are_json_serializable(self, df):
        import json
        prefs = _make_prefs()
        result = get_candidates(df, prefs)
        # Should not raise
        json.dumps(result["candidates"])
