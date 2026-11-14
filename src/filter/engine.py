"""4-stage restaurant candidate filter engine for the Zomato AI Recommender."""

import os

import pandas as pd

from src.input.parser import UserPreferences


# ---------------------------------------------------------------------------
# Fallback budget adjacency order
# ---------------------------------------------------------------------------
BUDGET_FALLBACK_ORDER: dict[str, list[str]] = {
    "low":    ["low", "medium"],
    "medium": ["medium", "low", "high"],
    "high":   ["high", "medium"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_candidates(
    df: pd.DataFrame,
    prefs: UserPreferences,
    max_candidates: int | None = None,
) -> dict:
    """
    Filter the restaurant DataFrame by user preferences and return a ranked
    shortlist of candidates, ready to be passed to the LLM prompt builder.

    Uses a 4-stage strategy:
      1. Hard filter  — exact city / budget / rating / cuisine match
      2. Sort         — rating DESC, votes DESC
      3. Limit        — take top max_candidates rows
      4. Fallback     — if Stage 1 returns 0 rows, progressively relax filters

    Args:
        df:             Cleaned DataFrame from preprocess().
        prefs:          Validated UserPreferences from parse_preferences().
        max_candidates: Maximum rows to return. Reads MAX_CANDIDATES env var
                        if not provided; defaults to 15.

    Returns:
        dict with keys:
            "candidates"        — list[dict], up to max_candidates restaurants
            "fallback_triggered"— bool, True if any filter was relaxed
            "fallback_reason"   — str, human-readable explanation of relaxation
    """
    if max_candidates is None:
        max_candidates = int(os.getenv("MAX_CANDIDATES", 15))
    # Guard against misconfiguration
    max_candidates = max(1, max_candidates)

    # Stage 1 — exact hard filter
    filtered = _hard_filter(df, prefs)

    if len(filtered) > 0:
        candidates = _sort_and_limit(filtered, max_candidates)
        print(f"   ✅ Filter found {len(candidates)} candidate(s) (exact match).")
        return {
            "candidates": candidates,
            "fallback_triggered": False,
            "fallback_reason": "",
        }

    # Stage 4 — fallback
    print(f"   ⚠️  No exact matches — activating fallback strategy...")
    candidates, reason = _fallback(df, prefs, max_candidates)
    return {
        "candidates": candidates,
        "fallback_triggered": True,
        "fallback_reason": reason,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _hard_filter(df: pd.DataFrame, prefs: UserPreferences) -> pd.DataFrame:
    """
    Apply all hard (AND-logic) filters simultaneously.

    Filters applied:
      • city matches prefs.location (case-sensitive after both are title-cased)
      • budget_tier matches prefs.budget_tier
      • rating >= prefs.min_rating
      • if cuisine != "Any": cuisine tag present in restaurant's cuisines list

    Args:
        df:    Cleaned DataFrame.
        prefs: Validated user preferences.

    Returns:
        Filtered DataFrame (may be empty).
    """
    mask = (
        (df["city"] == prefs.location) &
        (df["budget_tier"] == prefs.budget_tier) &
        (df["rating"] >= prefs.min_rating)
    )

    if prefs.cuisine.lower() != "any":
        cuisine_lower = prefs.cuisine.lower()
        cuisine_mask = df["cuisines"].apply(
            lambda tags: cuisine_lower in tags if isinstance(tags, list) else False
        )
        mask = mask & cuisine_mask

    return df[mask].copy()


def _sort_and_limit(df: pd.DataFrame, max_candidates: int) -> list[dict]:
    """
    Sort DataFrame by rating (desc) then votes (desc), take top N, return as records.

    Args:
        df:             DataFrame to sort (already filtered).
        max_candidates: Maximum rows to return.

    Returns:
        list[dict]: JSON-serializable list of restaurant dicts.
    """
    sorted_df = df.sort_values(
        by=["rating", "votes"],
        ascending=[False, False],
    ).head(max_candidates)

    return _to_records(sorted_df)


def _fallback(
    df: pd.DataFrame,
    prefs: UserPreferences,
    max_candidates: int,
) -> tuple[list[dict], str]:
    """
    Progressive fallback strategy when the exact hard filter returns 0 rows.

    Attempt A: Relax budget — try adjacent budget tiers (keeping other filters).
    Attempt B: Relax cuisine — set to "Any" (across all budget tiers attempted).
    Attempt C: Return empty list with a clear no-results message.

    Args:
        df:             Full cleaned DataFrame.
        prefs:          Original user preferences.
        max_candidates: Row limit.

    Returns:
        (candidates: list[dict], fallback_reason: str)
    """
    # ── Attempt A: Relax budget tier ────────────────────────────────────────
    for tier in BUDGET_FALLBACK_ORDER.get(prefs.budget_tier, [prefs.budget_tier]):
        if tier == prefs.budget_tier:
            continue  # Already tried exact match — skip

        mask = (
            (df["city"] == prefs.location) &
            (df["budget_tier"] == tier) &
            (df["rating"] >= prefs.min_rating)
        )
        if prefs.cuisine.lower() != "any":
            cuisine_lower = prefs.cuisine.lower()
            mask = mask & df["cuisines"].apply(
                lambda tags: cuisine_lower in tags if isinstance(tags, list) else False
            )

        subset = df[mask]
        if len(subset) > 0:
            reason = (
                f"No '{prefs.budget_tier}' budget restaurants matched. "
                f"Showing '{tier}' budget results instead."
            )
            print(f"   ↳ Fallback A (budget relaxed to '{tier}'): {len(subset)} result(s).")
            return _sort_and_limit(subset, max_candidates), reason

    # ── Attempt B: Relax cuisine → "Any" ────────────────────────────────────
    if prefs.cuisine.lower() != "any":
        for tier in BUDGET_FALLBACK_ORDER.get(prefs.budget_tier, [prefs.budget_tier]):
            mask = (
                (df["city"] == prefs.location) &
                (df["budget_tier"] == tier) &
                (df["rating"] >= prefs.min_rating)
            )
            subset = df[mask]
            if len(subset) > 0:
                reason = (
                    f"No '{prefs.cuisine}' cuisine restaurants matched. "
                    f"Showing all cuisines with '{tier}' budget instead."
                )
                print(
                    f"   ↳ Fallback B (cuisine relaxed to 'Any', budget '{tier}'): "
                    f"{len(subset)} result(s)."
                )
                return _sort_and_limit(subset, max_candidates), reason

    # ── Attempt C: City-only fallback (ignore budget, cuisine, rating) ───────
    city_only = df[df["city"] == prefs.location]
    if len(city_only) > 0:
        reason = (
            f"No restaurants matched your filters in {prefs.location}. "
            f"Showing top-rated restaurants in {prefs.location} regardless of budget/cuisine."
        )
        print(f"   ↳ Fallback C (city-only): {len(city_only)} result(s).")
        return _sort_and_limit(city_only, max_candidates), reason

    # ── Complete no-match ────────────────────────────────────────────────────
    print(f"   ❌ No restaurants found for city '{prefs.location}' in the dataset.")
    return [], (
        f"No restaurants found in '{prefs.location}'. "
        f"Try a different city — common options include: "
        f"Bangalore, Delhi, Mumbai, Hyderabad, Chennai, Kolkata, Pune."
    )


def _to_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert a DataFrame to a list of plain dicts, making all values JSON-serializable.

    Converts numpy scalar types to Python natives so json.dumps() works without
    a custom encoder.

    Args:
        df: DataFrame to convert.

    Returns:
        list[dict]: JSON-serializable restaurant records.
    """
    records = df.to_dict(orient="records")
    clean = []
    for rec in records:
        clean_rec = {}
        for k, v in rec.items():
            # Convert numpy types → Python builtins
            if hasattr(v, "item"):
                v = v.item()
            # Ensure cuisines is always a plain list
            if k == "cuisines" and not isinstance(v, list):
                v = []
            clean_rec[k] = v
        clean.append(clean_rec)
    return clean
