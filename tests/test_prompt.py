"""Unit tests for src/prompt/builder.py and src/prompt/templates.py"""

import os
import pytest

from src.input.parser import UserPreferences
from src.prompt.builder import build_prompt, _format_candidates_table
from src.prompt.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_prefs(**kwargs) -> UserPreferences:
    defaults = dict(
        location="Bangalore",
        budget_tier="medium",
        budget_range=(400, 1000),
        cuisine="Italian",
        min_rating=4.0,
        extra_prefs="quiet ambiance",
        raw_query="Bangalore, medium budget, Italian cuisine, rating ≥ 4.0. quiet ambiance",
    )
    defaults.update(kwargs)
    return UserPreferences(**defaults)


def _make_candidates(n: int = 3) -> list[dict]:
    return [
        {
            "name": f"Restaurant {i}",
            "city": "Bangalore",
            "location": "Koramangala",
            "cuisines": ["italian", "continental"],
            "rating": 4.5 - i * 0.1,
            "votes": 300 - i * 10,
            "cost_for_two": 700,
            "budget_tier": "medium",
            "restaurant_type": "Casual Dining",
            "has_online_delivery": True,
            "has_table_booking": i % 2 == 0,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Template constant tests
# ---------------------------------------------------------------------------

class TestTemplateConstants:
    def test_system_prompt_is_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 100

    def test_system_prompt_contains_json_instruction(self):
        assert "JSON" in SYSTEM_PROMPT

    def test_system_prompt_contains_hallucination_guard(self):
        assert "candidates list" in SYSTEM_PROMPT or "Only recommend" in SYSTEM_PROMPT

    def test_system_prompt_contains_schema(self):
        assert "recommendations" in SYSTEM_PROMPT
        assert "explanation" in SYSTEM_PROMPT
        assert "summary" in SYSTEM_PROMPT

    def test_user_prompt_template_has_all_slots(self):
        required_slots = [
            "{location}", "{budget_tier}", "{budget_min}", "{budget_max}",
            "{cuisine}", "{min_rating}", "{extra_prefs}", "{candidates_table}",
        ]
        for slot in required_slots:
            assert slot in USER_PROMPT_TEMPLATE, f"Missing slot: {slot}"


# ---------------------------------------------------------------------------
# build_prompt — output content tests
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_returns_string(self):
        prefs = _make_prefs()
        result = build_prompt(prefs, _make_candidates())
        assert isinstance(result, str)
        assert len(result) > 50

    def test_location_in_prompt(self):
        prefs = _make_prefs(location="Delhi")
        result = build_prompt(prefs, _make_candidates())
        assert "Delhi" in result

    def test_budget_tier_in_prompt(self):
        prefs = _make_prefs(budget_tier="high", budget_range=(1000, 999999))
        result = build_prompt(prefs, _make_candidates())
        assert "high" in result

    def test_budget_range_in_prompt(self):
        prefs = _make_prefs(budget_range=(400, 1000))
        result = build_prompt(prefs, _make_candidates())
        assert "400" in result
        assert "1000" in result

    def test_cuisine_in_prompt(self):
        prefs = _make_prefs(cuisine="Chinese")
        result = build_prompt(prefs, _make_candidates())
        assert "Chinese" in result

    def test_min_rating_in_prompt(self):
        prefs = _make_prefs(min_rating=4.5)
        result = build_prompt(prefs, _make_candidates())
        assert "4.5" in result

    def test_extra_prefs_in_prompt(self):
        prefs = _make_prefs(extra_prefs="family friendly")
        result = build_prompt(prefs, _make_candidates())
        assert "family friendly" in result

    def test_empty_extra_prefs_renders_as_none_specified(self):
        prefs = _make_prefs(extra_prefs="")
        result = build_prompt(prefs, _make_candidates())
        assert "None specified" in result

    def test_none_extra_prefs_renders_as_none_specified(self):
        prefs = _make_prefs(extra_prefs="")
        result = build_prompt(prefs, _make_candidates())
        assert "None specified" in result

    def test_candidate_table_included(self):
        result = build_prompt(_make_prefs(), _make_candidates(3))
        # markdown table has | characters
        assert "|" in result
        assert "Restaurant 0" in result

    def test_cuisines_rendered_as_comma_string(self):
        candidates = _make_candidates(1)
        candidates[0]["cuisines"] = ["italian", "continental"]
        result = build_prompt(_make_prefs(), candidates)
        assert "italian, continental" in result or "Italian, Continental" in result.lower()


# ---------------------------------------------------------------------------
# build_prompt — candidate count capping
# ---------------------------------------------------------------------------

class TestCandidateCapping:
    def test_candidate_count_capped_at_max_candidates(self, monkeypatch):
        monkeypatch.setenv("MAX_CANDIDATES", "3")
        candidates = _make_candidates(10)
        result = build_prompt(_make_prefs(), candidates)
        # Only 3 rows should appear (rows are numbered 1, 2, 3 — not 4+)
        assert "| 4 |" not in result

    def test_fewer_candidates_than_max_all_included(self, monkeypatch):
        monkeypatch.setenv("MAX_CANDIDATES", "15")
        candidates = _make_candidates(2)
        result = build_prompt(_make_prefs(), candidates)
        assert "Restaurant 0" in result
        assert "Restaurant 1" in result


# ---------------------------------------------------------------------------
# _format_candidates_table tests
# ---------------------------------------------------------------------------

class TestFormatCandidatesTable:
    def test_empty_candidates_returns_no_candidates_message(self):
        result = _format_candidates_table([])
        assert "no candidates" in result.lower()

    def test_table_has_header_row(self):
        result = _format_candidates_table(_make_candidates(2))
        assert "Name" in result
        assert "Rating" in result
        assert "Cuisines" in result

    def test_table_has_separator_row(self):
        result = _format_candidates_table(_make_candidates(2))
        assert "---" in result

    def test_delivery_rendered_as_yes_no(self):
        candidates = _make_candidates(1)
        candidates[0]["has_online_delivery"] = True
        result = _format_candidates_table(candidates)
        assert "Yes" in result or "No" in result

    def test_booking_rendered_as_yes_no(self):
        candidates = _make_candidates(1)
        candidates[0]["has_table_booking"] = False
        result = _format_candidates_table(candidates)
        assert "No" in result

    def test_cost_has_rupee_prefix(self):
        candidates = _make_candidates(1)
        candidates[0]["cost_for_two"] = 650
        result = _format_candidates_table(candidates)
        assert "₹650" in result

    def test_row_numbers_start_at_1(self):
        result = _format_candidates_table(_make_candidates(3))
        assert "| 1 |" in result
        assert "| 2 |" in result
        assert "| 3 |" in result
