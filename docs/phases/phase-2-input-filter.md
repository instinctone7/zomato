# Phase 2: Input Parsing & Filter Engine

> **Zomato-1 Implementation Plan**  
> **Phase:** 2 of 5  
> **Focus:** Validating user preferences and producing a filtered shortlist of restaurant candidates  
> **Est. Effort:** 1–2 days  
> **Depends on:** [Phase 1 — Setup & Data Pipeline](./phase-1-setup-data.md)  
> **Next Phase:** [Phase 3 — Prompt Builder & LLM Integration](./phase-3-prompt-llm.md)

---

## Goal

Accept raw user preferences (location, budget, cuisine, rating, free-text notes), validate and normalize them into a typed object, then query the in-memory dataset to produce a filtered and sorted shortlist of up to 15–20 restaurant candidates ready to be passed to the LLM.

---

## Milestone

> **✅ Done when:**  
> Running the following prints a JSON list of real restaurant candidates matching the given preferences:
> ```bash
> python -c "
> from src.data.loader import load_dataset
> from src.data.preprocessor import preprocess
> from src.input.parser import parse_preferences
> from src.filter.engine import get_candidates
> import json
>
> df = preprocess(load_dataset())
> prefs = parse_preferences({
>     'location': 'bangalore',
>     'budget': 'medium',
>     'cuisine': 'Italian',
>     'min_rating': 4.0,
>     'extra_prefs': 'quiet ambiance'
> })
> result = get_candidates(df, prefs)
> print(json.dumps(result['candidates'][:3], indent=2))
> "
> ```

---

## Tasks

### 2.1 — Input Parser (`src/input/parser.py`)

**What it does:** Takes a raw dictionary of user inputs (from CLI or Streamlit form), validates each field, normalizes values, and returns a typed `UserPreferences` object.

**Dataclass:**
```python
from dataclasses import dataclass

@dataclass
class UserPreferences:
    location: str        # Normalized city name e.g. "Bangalore"
    budget_tier: str     # "low" | "medium" | "high"
    budget_range: tuple  # (min_cost, max_cost) in ₹
    cuisine: str         # e.g. "Italian" or "Any"
    min_rating: float    # 0.0 – 5.0
    extra_prefs: str     # Optional free-text, max 200 chars
    raw_query: str       # Original unmodified input string for LLM context
```

**Main function:**
```python
def parse_preferences(raw: dict) -> UserPreferences:
    """
    Validate and normalize raw user input dict into UserPreferences.
    Raises ValueError with a user-friendly message on invalid input.
    """
```

**Validation rules:**

| Field | Required | Rule |
|---|---|---|
| `location` | ✅ Yes | Must be non-empty string; normalize via alias map; raise if empty |
| `budget` | ✅ Yes | Must be `low`, `medium`, or `high` (case-insensitive) |
| `cuisine` | ❌ No | Default `"Any"`; strip whitespace |
| `min_rating` | ❌ No | Default `3.0`; clamp to `0.0–5.0`; must be a number |
| `extra_prefs` | ❌ No | Default `""`; truncate to 200 characters |

**City alias map (implement in parser, expand over time):**
```python
CITY_ALIASES: dict[str, str] = {
    "blr": "Bangalore",
    "bengaluru": "Bangalore",
    "del": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi",
    "mum": "Mumbai",
    "bombay": "Mumbai",
    "hyd": "Hyderabad",
    "chn": "Chennai",
    "madras": "Chennai",
    "kol": "Kolkata",
    "calcutta": "Kolkata",
    "pun": "Pune",
    "gurgaon": "Gurugram",
}

def normalize_city(raw_city: str) -> str:
    """Normalize city name via alias map, then title-case."""
```

**Budget → range mapping:**
```python
BUDGET_RANGES: dict[str, tuple] = {
    "low":    (0, 400),
    "medium": (400, 1000),
    "high":   (1000, 999_999),
}
```

- [ ] Implement `UserPreferences` dataclass
- [ ] Implement `normalize_city()` with alias map
- [ ] Implement `parse_preferences()` with all validation rules
- [ ] Compose `raw_query` string from all fields for LLM context:  
  `f"{location}, {budget_tier} budget, {cuisine} cuisine, rating ≥ {min_rating}. {extra_prefs}"`

---

### 2.2 — Filter Engine (`src/filter/engine.py`)

**What it does:** Queries the in-memory cleaned DataFrame using the parsed preferences. Implements a 4-stage strategy: hard filter → sort → take top N → fallback if needed.

**Main function:**
```python
def get_candidates(
    df: pd.DataFrame,
    prefs: UserPreferences,
    max_candidates: int = 15
) -> dict:
    """
    Filter restaurant DataFrame by preferences.

    Returns:
    {
        "candidates": list[dict],       # Up to max_candidates restaurants
        "fallback_triggered": bool,     # True if filters were relaxed
        "fallback_reason": str          # Description of what was relaxed
    }
    """
```

**4-stage implementation:**

```
┌─────────────────────────────────────────────────────────────┐
│  Stage 1 — Hard Filters (all applied with AND logic)        │
│                                                             │
│  df[df["city"] == prefs.location]                           │
│  df[df["budget_tier"] == prefs.budget_tier]                 │
│  df[df["rating"] >= prefs.min_rating]                       │
│  if prefs.cuisine != "Any":                                 │
│      df[df["cuisines"].apply(                               │
│          lambda tags: prefs.cuisine.lower() in tags)]       │
├─────────────────────────────────────────────────────────────┤
│  Stage 2 — Soft Sort                                        │
│                                                             │
│  .sort_values(["rating", "votes"], ascending=False)         │
├─────────────────────────────────────────────────────────────┤
│  Stage 3 — Limit                                            │
│                                                             │
│  .head(max_candidates)                                      │
├─────────────────────────────────────────────────────────────┤
│  Stage 4 — Fallback (only if Stage 1 returns 0 rows)        │
│                                                             │
│  Attempt A: Relax budget — try adjacent tiers               │
│    medium → try [low, high]; low → try [medium]; etc.       │
│  Attempt B: Relax cuisine → set cuisine = "Any"             │
│  Attempt C: Return empty list + user-facing message         │
└─────────────────────────────────────────────────────────────┘
```

**Fallback tier adjacency:**
```python
BUDGET_FALLBACK_ORDER: dict[str, list[str]] = {
    "low":    ["low", "medium"],
    "medium": ["medium", "low", "high"],
    "high":   ["high", "medium"],
}
```

**Implementation steps:**
- [ ] Implement `_hard_filter(df, prefs) -> pd.DataFrame` (Stage 1)
- [ ] Implement `_sort_and_limit(df, max_candidates) -> pd.DataFrame` (Stages 2 + 3)
- [ ] Implement `_fallback(df, prefs, max_candidates) -> tuple[list[dict], str]` (Stage 4)
- [ ] Implement `get_candidates()` calling the above in order
- [ ] Convert result rows to `dict` using `.to_dict(orient="records")`
- [ ] Log candidate count found at each stage

---

### 2.3 — Tests

**`tests/test_parser.py`:**
- [ ] Test: Valid full input → correct `UserPreferences` object
- [ ] Test: `"bangalore"` → normalized to `"Bangalore"`
- [ ] Test: `"blr"` alias → `"Bangalore"`
- [ ] Test: Missing `location` → raises `ValueError`
- [ ] Test: `budget = "MEDIUM"` (uppercase) → normalized to `"medium"`
- [ ] Test: Invalid budget → raises `ValueError`
- [ ] Test: `min_rating = 6.0` → clamped to `5.0`
- [ ] Test: `extra_prefs` > 200 chars → truncated to 200

**`tests/test_filter.py`:**
- [ ] Test: Exact match returns non-empty candidate list
- [ ] Test: Candidates are sorted by rating descending
- [ ] Test: Candidate count ≤ `max_candidates`
- [ ] Test: Cuisine filter correctly excludes non-matching restaurants
- [ ] Test: `cuisine = "Any"` returns all cuisines
- [ ] Test: No match → `fallback_triggered = True`
- [ ] Test: Fallback relaxes budget correctly
- [ ] Test: Fallback relaxes cuisine when budget relaxation also fails

---

## Files Produced

| File | Purpose |
|---|---|
| `src/input/parser.py` | `UserPreferences` dataclass + validation logic |
| `src/filter/engine.py` | 4-stage filter + fallback logic |
| `tests/test_parser.py` | Input parser unit tests |
| `tests/test_filter.py` | Filter engine unit tests |

---

## Notes & Gotchas

> [!NOTE]
> The cuisine filter uses `in` membership on the normalized list (e.g., `"italian" in ["american", "italian", "continental"]`). This is case-sensitive after normalization — ensure both the dataset cuisines and user input are lowercased before comparison.

> [!WARNING]
> Some dataset cities may not perfectly match user expectations (e.g., dataset uses `"New Delhi"` but user types `"Delhi"`). The city alias map is the fix — keep it maintained as new cities are tested.

> [!TIP]
> Test the filter engine against the actual dataset (not mocks) at least once — schema surprises from the real data are common and cheap to catch early.
