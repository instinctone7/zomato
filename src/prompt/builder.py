"""
Prompt builder for the Zomato AI Recommender.

Fills USER_PROMPT_TEMPLATE with real preference data and formats
the candidate list as a markdown table for token efficiency.
"""

import os

from src.input.parser import UserPreferences
from src.prompt.templates import USER_PROMPT_TEMPLATE


def build_prompt(prefs: UserPreferences, candidates: list[dict]) -> str:
    """
    Assemble the user-turn prompt string from preferences and filtered candidates.

    Candidates are formatted as a markdown table (more readable and
    token-efficient than raw JSON for structured tabular data).
    The list is capped at MAX_CANDIDATES (default 15) before building.

    Args:
        prefs:      Validated UserPreferences from parse_preferences().
        candidates: Filtered restaurant dicts from get_candidates().

    Returns:
        Filled prompt string ready to pass to call_llm() as user_prompt.
    """
    max_candidates = int(os.getenv("MAX_CANDIDATES", 15))
    capped = candidates[:max_candidates]

    candidates_table = _format_candidates_table(capped)
    extra_prefs = prefs.extra_prefs.strip() or "None specified"

    return USER_PROMPT_TEMPLATE.format(
        location=prefs.location,
        budget_tier=prefs.budget_tier,
        budget_min=prefs.budget_range[0],
        budget_max=prefs.budget_range[1],
        cuisine=prefs.cuisine,
        min_rating=prefs.min_rating,
        extra_prefs=extra_prefs,
        candidates_table=candidates_table,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_candidates_table(candidates: list[dict]) -> str:
    """
    Render a list of restaurant dicts as a GitHub-style markdown table.

    Columns (in order):
        # | Name | Location | Cuisines | Rating | Votes | Cost for 2 | Type | Delivery | Booking

    Args:
        candidates: List of restaurant dicts (from get_candidates()).

    Returns:
        Markdown table string. Returns "(no candidates)" if list is empty.
    """
    if not candidates:
        return "(no candidates found for the given filters)"

    headers = [
        "#", "Name", "Location", "Cuisines",
        "Rating", "Votes", "Cost for 2", "Type", "Delivery", "Booking",
    ]

    rows = []
    for i, r in enumerate(candidates, start=1):
        cuisines_str = ", ".join(r.get("cuisines") or []) or "—"
        cost = r.get("cost_for_two")
        cost_str = f"₹{int(cost)}" if cost is not None else "—"
        delivery = "Yes" if r.get("has_online_delivery") else "No"
        booking  = "Yes" if r.get("has_table_booking") else "No"

        rows.append([
            str(i),
            str(r.get("name", "—")),
            str(r.get("location") or r.get("city") or "—"),
            cuisines_str,
            str(r.get("rating", "—")),
            str(int(r.get("votes", 0))),
            cost_str,
            str(r.get("restaurant_type", "—")),
            delivery,
            booking,
        ])

    # Build markdown table
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    header_row = "| " + " | ".join(headers) + " |"
    data_rows = ["| " + " | ".join(row) + " |" for row in rows]

    return "\n".join([header_row, separator] + data_rows)
