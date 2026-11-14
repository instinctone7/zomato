"""Unit tests for src/llm/parser.py"""

import json
import os
import pytest

from src.llm.parser import parse_response, _try_parse_json, _fallback_response


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_candidates(n: int = 3) -> list[dict]:
    """Return a list of minimal candidate dicts with real names."""
    names = ["Truffles", "The Black Pearl", "Meghana Foods", "Fenny's", "Toscano"]
    return [
        {
            "name": names[i % len(names)],
            "city": "Bangalore",
            "location": "Koramangala",
            "cuisines": ["italian", "continental"],
            "rating": 4.5 - i * 0.1,
            "votes": 300 - i * 20,
            "cost_for_two": 600 + i * 50,
            "budget_tier": "medium",
            "restaurant_type": "Casual Dining",
            "has_online_delivery": True,
            "has_table_booking": False,
        }
        for i in range(n)
    ]


def _make_valid_llm_json(candidates: list[dict], n_recs: int = 2) -> str:
    """Build a valid LLM JSON string referencing real candidate names."""
    recs = [
        {
            "rank": i + 1,
            "name": candidates[i]["name"],
            "explanation": f"Great pick #{i + 1} for your preferences.",
            "trade_offs": "Can get busy on weekends." if i == 0 else "",
        }
        for i in range(min(n_recs, len(candidates)))
    ]
    return json.dumps({
        "recommendations": recs,
        "summary": "Top recommendations based on your preferences.",
    })


# ---------------------------------------------------------------------------
# _try_parse_json tests
# ---------------------------------------------------------------------------

class TestTryParseJson:
    def test_valid_json_parsed(self):
        raw = json.dumps({"recommendations": [], "summary": "test"})
        result = _try_parse_json(raw)
        assert result == {"recommendations": [], "summary": "test"}

    def test_json_in_code_fence_parsed(self):
        payload = {"recommendations": [{"rank": 1, "name": "X", "explanation": "y", "trade_offs": ""}], "summary": "s"}
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = _try_parse_json(raw)
        assert result is not None
        assert result["summary"] == "s"

    def test_json_in_plain_code_fence_parsed(self):
        payload = {"recommendations": [], "summary": "ok"}
        raw = f"```\n{json.dumps(payload)}\n```"
        result = _try_parse_json(raw)
        assert result is not None

    def test_json_embedded_in_prose_extracted(self):
        payload = {"recommendations": [], "summary": "here"}
        raw = f"Sure! Here is the result: {json.dumps(payload)} Hope that helps!"
        result = _try_parse_json(raw)
        assert result is not None
        assert result["summary"] == "here"

    def test_completely_malformed_returns_none(self):
        result = _try_parse_json("This is just plain text, no JSON here.")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _try_parse_json("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        result = _try_parse_json("   \n\t  ")
        assert result is None


# ---------------------------------------------------------------------------
# parse_response — happy path
# ---------------------------------------------------------------------------

class TestParseResponseHappyPath:
    def test_returns_dict_with_required_keys(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates)
        result = parse_response(raw, candidates)
        assert "recommendations" in result
        assert "summary" in result
        assert "ai_ranking" in result

    def test_ai_ranking_true_on_valid_json(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates)
        result = parse_response(raw, candidates)
        assert result["ai_ranking"] is True

    def test_recommendations_is_list(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates)
        result = parse_response(raw, candidates)
        assert isinstance(result["recommendations"], list)

    def test_each_rec_has_rank_name_explanation(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates)
        result = parse_response(raw, candidates)
        for rec in result["recommendations"]:
            assert "rank" in rec
            assert "name" in rec
            assert "explanation" in rec

    def test_enrichment_adds_candidate_fields(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates, n_recs=1)
        result = parse_response(raw, candidates)
        rec = result["recommendations"][0]
        # Candidate fields should be merged in
        assert "rating" in rec
        assert "cost_for_two" in rec
        assert "cuisines" in rec

    def test_trade_offs_key_always_present(self):
        candidates = _make_candidates(3)
        # LLM response without trade_offs key
        payload = {
            "recommendations": [{"rank": 1, "name": candidates[0]["name"], "explanation": "great"}],
            "summary": "top pick",
        }
        result = parse_response(json.dumps(payload), candidates)
        for rec in result["recommendations"]:
            assert "trade_offs" in rec

    def test_summary_returned(self):
        candidates = _make_candidates(3)
        raw = _make_valid_llm_json(candidates)
        result = parse_response(raw, candidates)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# parse_response — fallback cases
# ---------------------------------------------------------------------------

class TestParseResponseFallback:
    def test_malformed_json_triggers_fallback(self):
        candidates = _make_candidates(3)
        result = parse_response("this is not json at all", candidates)
        assert result["ai_ranking"] is False

    def test_empty_response_triggers_fallback(self):
        candidates = _make_candidates(3)
        result = parse_response("", candidates)
        assert result["ai_ranking"] is False

    def test_wrong_schema_triggers_fallback(self):
        candidates = _make_candidates(3)
        # Uses "results" instead of "recommendations"
        raw = json.dumps({"results": [], "summary": "test"})
        result = parse_response(raw, candidates)
        assert result["ai_ranking"] is False

    def test_fallback_has_generic_summary(self):
        candidates = _make_candidates(3)
        result = parse_response("bad json", candidates)
        assert "AI ranking unavailable" in result["summary"] or "rating" in result["summary"]

    def test_fallback_sorted_by_rating(self):
        candidates = _make_candidates(5)
        # Shuffle ratings deliberately
        candidates[0]["rating"] = 3.0
        candidates[1]["rating"] = 4.9
        result = parse_response("bad json", candidates)
        ratings = [r["rating"] for r in result["recommendations"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_fallback_has_explanation(self):
        candidates = _make_candidates(3)
        result = parse_response("bad json", candidates)
        for rec in result["recommendations"]:
            assert rec["explanation"]


# ---------------------------------------------------------------------------
# parse_response — hallucination guard
# ---------------------------------------------------------------------------

class TestHallucinationGuard:
    def test_hallucinated_name_skipped(self):
        candidates = _make_candidates(2)
        payload = {
            "recommendations": [
                {"rank": 1, "name": "FakeRestaurantThatDoesNotExist", "explanation": "great", "trade_offs": ""},
            ],
            "summary": "top pick",
        }
        result = parse_response(json.dumps(payload), candidates)
        # Hallucinated name should not appear — fallback activated
        names = [r["name"] for r in result["recommendations"]]
        assert "FakeRestaurantThatDoesNotExist" not in names

    def test_hallucinated_name_triggers_fallback(self):
        candidates = _make_candidates(2)
        payload = {
            "recommendations": [
                {"rank": 1, "name": "MadeUpPlace", "explanation": "x", "trade_offs": ""},
            ],
            "summary": "x",
        }
        result = parse_response(json.dumps(payload), candidates)
        assert result["ai_ranking"] is False

    def test_valid_name_case_insensitive_match(self):
        candidates = _make_candidates(2)
        # LLM returns name with different casing
        payload = {
            "recommendations": [
                {"rank": 1, "name": candidates[0]["name"].upper(), "explanation": "great", "trade_offs": ""},
            ],
            "summary": "ok",
        }
        result = parse_response(json.dumps(payload), candidates)
        # Should match (case-insensitive lookup)
        assert result["ai_ranking"] is True
        assert len(result["recommendations"]) == 1


# ---------------------------------------------------------------------------
# parse_response — deduplication and capping
# ---------------------------------------------------------------------------

class TestDeduplicationAndCapping:
    def test_duplicate_names_deduplicated(self):
        candidates = _make_candidates(3)
        payload = {
            "recommendations": [
                {"rank": 1, "name": candidates[0]["name"], "explanation": "first", "trade_offs": ""},
                {"rank": 2, "name": candidates[0]["name"], "explanation": "duplicate", "trade_offs": ""},
                {"rank": 3, "name": candidates[1]["name"], "explanation": "second", "trade_offs": ""},
            ],
            "summary": "test",
        }
        result = parse_response(json.dumps(payload), candidates)
        names = [r["name"] for r in result["recommendations"]]
        assert len(names) == len(set(names)), "Duplicate names found"

    def test_results_capped_at_top_n(self, monkeypatch):
        monkeypatch.setenv("TOP_N_RESULTS", "2")
        candidates = _make_candidates(5)
        payload = {
            "recommendations": [
                {"rank": i + 1, "name": candidates[i]["name"], "explanation": "ok", "trade_offs": ""}
                for i in range(5)
            ],
            "summary": "all five",
        }
        result = parse_response(json.dumps(payload), candidates)
        assert len(result["recommendations"]) <= 2

    def test_fallback_capped_at_top_n(self, monkeypatch):
        monkeypatch.setenv("TOP_N_RESULTS", "2")
        candidates = _make_candidates(5)
        result = parse_response("bad json", candidates)
        assert len(result["recommendations"]) <= 2


# ---------------------------------------------------------------------------
# parse_response — code-fence JSON (LLM wraps in code fence)
# ---------------------------------------------------------------------------

class TestCodeFenceParsing:
    def test_json_in_json_code_fence(self):
        candidates = _make_candidates(2)
        payload = {
            "recommendations": [
                {"rank": 1, "name": candidates[0]["name"], "explanation": "great", "trade_offs": ""},
            ],
            "summary": "top pick",
        }
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = parse_response(raw, candidates)
        assert result["ai_ranking"] is True

    def test_json_in_plain_code_fence(self):
        candidates = _make_candidates(2)
        payload = {
            "recommendations": [
                {"rank": 1, "name": candidates[0]["name"], "explanation": "great", "trade_offs": ""},
            ],
            "summary": "top pick",
        }
        raw = f"```\n{json.dumps(payload)}\n```"
        result = parse_response(raw, candidates)
        assert result["ai_ranking"] is True


def test_ai_cannot_overwrite_verified_restaurant_data():
    candidates = _make_candidates(1)
    raw = json.dumps({'recommendations': [{'rank': 'oops', 'name': candidates[0]['name'],
                      'explanation': 'A suitable pick.', 'rating': 99, 'cost_for_two': 1,
                      'cuisines': 'made up', 'trade_offs': {'invalid': True}}]})
    rec = parse_response(raw, candidates)['recommendations'][0]
    assert rec['rating'] == candidates[0]['rating']
    assert rec['cost_for_two'] == candidates[0]['cost_for_two']
    assert rec['cuisines'] == candidates[0]['cuisines']
    assert rec['rank'] == 1
    assert rec['trade_offs'] == ''
