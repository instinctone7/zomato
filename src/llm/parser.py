"""
LLM response parser for the Zomato AI Recommender.

Parses raw LLM text into structured recommendations.
Implements a 3-attempt JSON extraction strategy and a rating-sorted fallback.
"""

import json
import os
import re
import warnings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_response(raw_response: str, candidates: list[dict]) -> dict:
    """
    Parse and validate the LLM's raw text response into structured recommendations.

    Enriches each recommendation with the full restaurant data from candidates
    (looked up by name). Skips recommendations where the LLM hallucinated a
    restaurant name not present in the candidates list.

    Parsing attempts (in order):
      1. Direct json.loads() on the full response string.
      2. Extract JSON from a markdown code fence (```json ... ``` or ``` ... ```).
      3. Slice from the first '{' to the last '}' and try json.loads().
      4. Fallback: return candidates sorted by rating with generic explanations.

    Args:
        raw_response: Raw string returned by call_llm().
        candidates:   Filtered restaurant dicts from get_candidates().

    Returns:
        dict with keys:
            "recommendations" — list[dict], enriched and ranked
            "summary"         — str
            "ai_ranking"      — bool (False when fallback was used)
    """
    top_n = int(os.getenv("TOP_N_RESULTS", 5))

    parsed = _try_parse_json(raw_response)

    if parsed is None:
        print("   ⚠️  LLM response could not be parsed as JSON — using rating-sorted fallback.")
        return _fallback_response(candidates, top_n)

    # Schema validation
    if not isinstance(parsed.get("recommendations"), list):
        print("   ⚠️  LLM response missing 'recommendations' list — using fallback.")
        return _fallback_response(candidates, top_n)

    if not isinstance(parsed.get("summary"), str):
        parsed["summary"] = "Here are the top restaurant picks based on your preferences."

    # Build a lookup map: lowercase name → candidate dict
    candidate_map = {c["name"].lower(): c for c in candidates}

    enriched = []
    for rec in parsed["recommendations"]:
        # Validate required keys
        if not isinstance(rec, dict) or not all(k in rec for k in ("rank", "name", "explanation")):
            print(f"   ⚠️  Skipping malformed recommendation (missing keys): {rec}")
            continue
        if not isinstance(rec['name'], str) or not isinstance(rec['explanation'], str) or not rec['explanation'].strip():
            continue

        rec_name = str(rec["name"])
        match = candidate_map.get(rec_name.lower())

        if match is None:
            print(f"   ⚠️  Hallucination guard: '{rec_name}' not in candidates — skipped.")
            continue

        # Merge candidate data into the recommendation
        enriched_rec = {**match, 'rank': len(enriched) + 1,
                        'explanation': rec['explanation'],
                        'trade_offs': rec.get('trade_offs') if isinstance(rec.get('trade_offs'), str) else ''}
        # Guarantee trade_offs key exists
        enriched_rec.setdefault("trade_offs", "")
        enriched.append(enriched_rec)

    # Deduplicate by name (keep first occurrence = highest rank)
    seen: set[str] = set()
    deduped = []
    for rec in enriched:
        key = rec["name"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(rec)

    # Cap at TOP_N_RESULTS
    final = deduped[:top_n]

    if not final:
        print("   ⚠️  All LLM recommendations were filtered out — using fallback.")
        return _fallback_response(candidates, top_n)

    return {
        "recommendations": final,
        "summary": parsed["summary"],
        "ai_ranking": True,
    }


# ---------------------------------------------------------------------------
# Private — JSON extraction
# ---------------------------------------------------------------------------

def _try_parse_json(text: str) -> dict | None:
    """
    Try three strategies to extract a JSON object from raw LLM text.

    Args:
        text: Raw LLM response string.

    Returns:
        Parsed dict on success, None if all strategies fail.
    """
    if not text or not text.strip():
        return None

    # Attempt 1: direct parse
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: extract from code fence  ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    match = fence_pattern.search(text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Attempt 3: slice from first '{' to last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None


# ---------------------------------------------------------------------------
# Private — fallback
# ---------------------------------------------------------------------------

def _fallback_response(candidates: list[dict], top_n: int) -> dict:
    """
    Build a fallback response from the top-N candidates sorted by rating.

    Used when the LLM response cannot be parsed or all recommendations
    were filtered out by the hallucination guard.

    Args:
        candidates: Filtered restaurant dicts from get_candidates().
        top_n:      Maximum number of results to return.

    Returns:
        Standard response dict with ai_ranking=False.
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (c.get("rating", 0), c.get("votes", 0)),
        reverse=True,
    )

    recommendations = []
    for i, candidate in enumerate(sorted_candidates[:top_n]):
        rec = {**candidate}
        rec["rank"] = i + 1
        rec["explanation"] = "Highly rated match for your filters."
        rec.setdefault("trade_offs", "")
        recommendations.append(rec)

    return {
        "recommendations": recommendations,
        "summary": "AI ranking unavailable — showing top results by rating.",
        "ai_ranking": False,
    }
