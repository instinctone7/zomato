"""Unit tests for src/data/preprocessor.py"""

import pandas as pd
import pytest

from src.data.preprocessor import preprocess, BUDGET_LOW_MAX, BUDGET_MEDIUM_MAX, MIN_VOTES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_raw_df(**overrides) -> pd.DataFrame:
    """Return a clean raw DataFrame that passes all preprocessing steps."""
    base = {
        "name": ["Alpha", "Beta", "Gamma", "Delta"],
        "city": ["bangalore", "DELHI", "Mumbai", "Chennai"],
        "cuisines": ["Indian, Chinese", "Italian", None, "Mexican"],
        "aggregate_rating": [4.2, 3.8, 4.5, 2.1],
        "votes": [150, 80, 500, 5],           # Delta has < MIN_VOTES
        "average_cost_for_two": [300, 700, 1200, 500],
        "has_online_delivery": [1, 0, 1, 0],
        "has_table_booking": [0, 1, 0, 1],
        "restaurant_type": ["Casual Dining", "Quick Bites", "Fine Dining", "Cafe"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


@pytest.fixture
def raw_df():
    return _make_raw_df()


@pytest.fixture
def clean_df(raw_df):
    return preprocess(raw_df)


# ---------------------------------------------------------------------------
# Tests — column renaming
# ---------------------------------------------------------------------------

class TestColumnRenames:
    def test_aggregate_rating_renamed_to_rating(self, clean_df):
        assert "rating" in clean_df.columns, "'rating' column missing after rename"
        assert "aggregate_rating" not in clean_df.columns

    def test_average_cost_renamed_to_cost_for_two(self, clean_df):
        assert "cost_for_two" in clean_df.columns, "'cost_for_two' column missing"
        assert "average_cost_for_two" not in clean_df.columns


# ---------------------------------------------------------------------------
# Tests — null dropping
# ---------------------------------------------------------------------------

class TestDropNulls:
    def test_no_null_name_after_preprocess(self, clean_df):
        assert clean_df["name"].isna().sum() == 0

    def test_no_null_city_after_preprocess(self, clean_df):
        assert clean_df["city"].isna().sum() == 0

    def test_no_null_rating_after_preprocess(self, clean_df):
        assert clean_df["rating"].isna().sum() == 0

    def test_rows_with_null_name_dropped(self):
        df = _make_raw_df()
        df.loc[0, "name"] = None
        result = preprocess(df)
        assert "Alpha" not in result["name"].values

    def test_rows_with_null_city_dropped(self):
        df = _make_raw_df()
        df.loc[1, "city"] = None
        result = preprocess(df)
        # Delta was already dropped for low votes; Beta dropped for null city
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# Tests — low vote dropping
# ---------------------------------------------------------------------------

class TestDropLowVotes:
    def test_rows_with_fewer_than_min_votes_removed(self, clean_df):
        assert (clean_df["votes"] >= MIN_VOTES).all(), (
            f"Some rows have votes < {MIN_VOTES}"
        )

    def test_delta_row_removed(self, raw_df, clean_df):
        # Delta has 5 votes — below MIN_VOTES=10
        assert "Delta" not in clean_df["name"].values

    def test_row_count_decreases_or_stays_same(self, raw_df, clean_df):
        assert len(clean_df) <= len(raw_df)


# ---------------------------------------------------------------------------
# Tests — city normalization
# ---------------------------------------------------------------------------

class TestNormalizeCities:
    def test_cities_are_title_cased(self, clean_df):
        for city in clean_df["city"]:
            assert city == city.title(), f"City not title-cased: {city!r}"

    def test_lowercase_city_normalized(self, clean_df):
        assert "Bangalore" in clean_df["city"].values

    def test_uppercase_city_normalized(self, clean_df):
        assert "Delhi" in clean_df["city"].values


# ---------------------------------------------------------------------------
# Tests — cuisine normalization
# ---------------------------------------------------------------------------

class TestNormalizeCuisines:
    def test_cuisines_column_contains_lists(self, clean_df):
        for val in clean_df["cuisines"]:
            assert isinstance(val, list), f"cuisines value is not a list: {val!r}"

    def test_cuisine_tags_are_lowercase(self, clean_df):
        for tags in clean_df["cuisines"]:
            for tag in tags:
                assert tag == tag.lower(), f"Cuisine tag not lowercase: {tag!r}"

    def test_comma_separated_string_split_correctly(self, clean_df):
        # "Indian, Chinese" → ["indian", "chinese"]
        alpha_row = clean_df[clean_df["name"] == "Alpha"]
        assert not alpha_row.empty
        cuisines = alpha_row.iloc[0]["cuisines"]
        assert "indian" in cuisines
        assert "chinese" in cuisines

    def test_null_cuisine_becomes_empty_list(self, clean_df):
        # Gamma had null cuisines
        gamma_row = clean_df[clean_df["name"] == "Gamma"]
        if not gamma_row.empty:
            assert gamma_row.iloc[0]["cuisines"] == []


# ---------------------------------------------------------------------------
# Tests — budget tier
# ---------------------------------------------------------------------------

class TestBudgetTier:
    def test_budget_tier_column_exists(self, clean_df):
        assert "budget_tier" in clean_df.columns

    def test_budget_tier_only_valid_values(self, clean_df):
        assert set(clean_df["budget_tier"].unique()).issubset({"low", "medium", "high"})

    def test_low_budget_assigned_correctly(self, clean_df):
        # Alpha cost=300 → low
        alpha = clean_df[clean_df["name"] == "Alpha"]
        if not alpha.empty:
            assert alpha.iloc[0]["budget_tier"] == "low"

    def test_medium_budget_assigned_correctly(self, clean_df):
        # Beta cost=700 → medium
        beta = clean_df[clean_df["name"] == "Beta"]
        if not beta.empty:
            assert beta.iloc[0]["budget_tier"] == "medium"

    def test_high_budget_assigned_correctly(self, clean_df):
        # Gamma cost=1200 → high
        gamma = clean_df[clean_df["name"] == "Gamma"]
        if not gamma.empty:
            assert gamma.iloc[0]["budget_tier"] == "high"

    def test_no_null_budget_tiers(self, clean_df):
        assert clean_df["budget_tier"].isna().sum() == 0


# ---------------------------------------------------------------------------
# Tests — empty dataset guard
# ---------------------------------------------------------------------------

class TestEmptyDatasetGuard:
    def test_all_rows_null_causes_sys_exit(self):
        """If all rows are dropped, preprocess must sys.exit(1)."""
        df = pd.DataFrame({
            "name": [None, None],
            "city": [None, None],
            "cuisines": [None, None],
            "aggregate_rating": [None, None],
            "votes": [0, 0],
            "average_cost_for_two": [0, 0],
            "has_online_delivery": [0, 0],
            "has_table_booking": [0, 0],
            "restaurant_type": ["Cafe", "Cafe"],
        })
        with pytest.raises(SystemExit) as exc_info:
            preprocess(df)
        assert exc_info.value.code == 1


def test_actual_bangalore_dataset_schema():
    raw = pd.DataFrame({
        'name': ['Cafe', 'Unrated'], 'location': ['Indiranagar', 'Jayanagar'],
        'listed_in(city)': ['Indiranagar', 'Jayanagar'],
        'rate': ['4.2/5', 'NEW'], 'votes': [100, 10],
        'cuisines': ['Cafe, Italian', 'Cafe'],
        'approx_cost(for two people)': ['1,200', '500'],
        'online_order': ['Yes', 'No'], 'book_table': ['No', 'No'],
    })
    result = preprocess(raw)
    assert len(result) == 1
    assert result.iloc[0]['city'] == 'Bangalore'
    assert result.iloc[0]['rating'] == 4.2
    assert result.iloc[0]['cost_for_two'] == 1200
    assert bool(result.iloc[0]['has_table_booking']) is False


def test_corrupted_restaurant_names_are_repaired():
    raw = _make_raw_df()
    name = 'Santé Spa Cuisine'
    for _ in range(3):
        name = name.encode('utf-8').decode('latin-1')
    raw.loc[0, 'name'] = name
    assert preprocess(raw).iloc[0]['name'] == 'Santé Spa Cuisine'
