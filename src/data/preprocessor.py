"""Data cleaning, normalization, and enrichment for the Zomato AI Recommender."""

import pandas as pd
from ftfy import fix_text


# ---------------------------------------------------------------------------
# Column name mapping from raw HuggingFace names → standardized names
# ---------------------------------------------------------------------------
COLUMN_RENAMES: dict[str, str] = {
    "aggregate_rating": "rating",
    "average_cost_for_two": "cost_for_two",
    "rate": "rating",
    "approx_cost(for two people)": "cost_for_two",
    "rest_type": "restaurant_type",
    "online_order": "has_online_delivery",
    "book_table": "has_table_booking",
    # Add further mappings here if the dataset schema ever changes.
}

# ---------------------------------------------------------------------------
# Budget tier thresholds (₹ cost for two people)
# ---------------------------------------------------------------------------
BUDGET_LOW_MAX = 400       # cost_for_two < 400  → "low"
BUDGET_MEDIUM_MAX = 1000   # 400 ≤ cost_for_two ≤ 1000 → "medium"
                           # cost_for_two > 1000 → "high"

MIN_VOTES = 10             # Rows with fewer votes are considered low-signal


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and enrich the raw Zomato DataFrame.

    Applies the following transformations in order:
      1. Rename columns to standardized snake_case names.
      2. Drop rows with null values in critical fields.
      3. Drop rows with low vote counts (< MIN_VOTES).
      4. Normalize city names (strip + title-case).
      5. Normalize cuisines (split string → list of lowercase tags).
      6. Impute missing cost_for_two with median, then add budget_tier column.
      7. Reset the integer index.

    Args:
        df: Raw DataFrame from load_dataset().

    Returns:
        pd.DataFrame: Cleaned, enriched DataFrame ready for filtering.

    Raises:
        SystemExit: If the cleaned DataFrame is empty or missing required columns.
    """
    print(f"\n🔧 Preprocessing dataset ({len(df):,} rows)...")
    df = df.copy()

    df = _rename_columns(df)
    for column in ('name', 'location', 'city', 'restaurant_type'):
        if column in df.columns:
            df[column] = df[column].map(
                lambda value: fix_text(value).strip() if isinstance(value, str) else value
            )
    # The source is the Bangalore dataset; its location field is a locality.
    if "city" not in df.columns and "listed_in(city)" in df.columns:
        df["city"] = "Bangalore"
    _assert_required_columns(df)
    df["rating"] = pd.to_numeric(
        df["rating"].map(lambda value: str(value).split("/")[0].strip()), errors="coerce"
    )
    for column in ("has_online_delivery", "has_table_booking"):
        if column in df.columns:
            df[column] = df[column].map(
                lambda value: str(value).strip().lower() in {"yes", "true", "1"}
            )

    df = _drop_nulls(df)
    df = _drop_low_votes(df)
    df = _normalize_cities(df)
    df = _normalize_cuisines(df)
    df = _impute_cost(df)
    df = _add_budget_tier(df)
    df = _reset_index(df)

    if len(df) == 0:
        print(
            "❌ ERROR: Dataset is empty after preprocessing. "
            "All rows were dropped by quality filters.",
            file=__import__("sys").stderr,
        )
        __import__("sys").exit(1)

    print(f"✅ Preprocessing complete: {len(df):,} rows retained.\n")
    return df


# ---------------------------------------------------------------------------
# Private step functions
# ---------------------------------------------------------------------------

def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw HuggingFace column names to standardized snake_case names."""
    existing_renames = {k: v for k, v in COLUMN_RENAMES.items() if k in df.columns}
    df = df.rename(columns=existing_renames)
    if existing_renames:
        print(f"   ↳ Renamed columns: {existing_renames}")
    return df


def _assert_required_columns(df: pd.DataFrame) -> None:
    """Raise SystemExit if any required column is missing after rename."""
    required = {"name", "city", "rating", "votes", "cuisines"}
    missing = required - set(df.columns)
    if missing:
        import sys
        print(
            f"❌ ERROR: Dataset is missing required columns after renaming: {missing}\n"
            f"   Available columns: {df.columns.tolist()}\n"
            f"   The dataset schema may have changed. Update COLUMN_RENAMES in preprocessor.py.",
            file=sys.stderr,
        )
        sys.exit(1)


def _drop_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where name, city, or rating is null."""
    before = len(df)
    df = df.dropna(subset=["name", "city", "rating"])
    dropped = before - len(df)
    print(f"   ↳ Dropped {dropped:,} rows with null name/city/rating.")
    return df


def _drop_low_votes(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with fewer than MIN_VOTES votes (low-signal entries)."""
    before = len(df)
    # votes column may be float after null handling — coerce safely
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0)
    df = df[df["votes"] >= MIN_VOTES]
    dropped = before - len(df)
    print(f"   ↳ Dropped {dropped:,} rows with fewer than {MIN_VOTES} votes.")
    return df


def _normalize_cities(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and title-case all city names."""
    df["city"] = df["city"].astype(str).str.strip().str.title()
    return df


def _normalize_cuisines(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the cuisines column from a comma-separated string to a list of
    lowercase, stripped cuisine tags. Null values become empty lists.
    """
    def _parse(value) -> list[str]:
        if pd.isna(value) or str(value).strip() == "":
            return []
        return [tag.strip().lower() for tag in str(value).split(",") if tag.strip()]

    df["cuisines"] = df["cuisines"].apply(_parse)
    return df


def _impute_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    Impute missing or zero cost_for_two with the column median.
    Ensures budget_tier bucketing is meaningful for all rows.
    """
    if "cost_for_two" not in df.columns:
        # Column might not exist in some dataset versions — create with 0
        df["cost_for_two"] = 0

    df["cost_for_two"] = pd.to_numeric(
        df["cost_for_two"].map(lambda value: str(value).replace(",", "")), errors="coerce"
    )
    median_cost = df["cost_for_two"].median()
    null_count = df["cost_for_two"].isna().sum()
    zero_count = (df["cost_for_two"] == 0).sum()

    if null_count > 0:
        df["cost_for_two"] = df["cost_for_two"].fillna(median_cost)
        print(f"   ↳ Imputed {null_count:,} null cost values with median (₹{median_cost:.0f}).")
    if zero_count > 0:
        df.loc[df["cost_for_two"] == 0, "cost_for_two"] = median_cost
        print(f"   ↳ Replaced {zero_count:,} zero cost values with median (₹{median_cost:.0f}).")

    return df


def _add_budget_tier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a budget_tier column bucketing cost_for_two into low / medium / high.

    Thresholds (₹ cost for two):
        low    : < 400
        medium : 400 – 1000
        high   : > 1000
    """
    def _tier(cost: float) -> str:
        if cost < BUDGET_LOW_MAX:
            return "low"
        elif cost <= BUDGET_MEDIUM_MAX:
            return "medium"
        else:
            return "high"

    df["budget_tier"] = df["cost_for_two"].apply(_tier)
    counts = df["budget_tier"].value_counts().to_dict()
    print(f"   ↳ Budget tiers assigned: {counts}")
    return df


def _reset_index(df: pd.DataFrame) -> pd.DataFrame:
    """Reset integer index after all row drops."""
    return df.reset_index(drop=True)
