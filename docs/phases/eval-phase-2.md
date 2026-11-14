# Phase 2 Evaluation Criteria: Input Parsing & Filter Engine

> **Zomato-1** · Phase 2 of 5  
> **Evaluates:** Input validation, city normalization, candidate filtering, fallback strategy  
> **Phase file:** [phase-2-input-filter.md](./phase-2-input-filter.md)

---

## ✅ Pass Criteria (must ALL be true to proceed to Phase 3)

### E2-1 · UserPreferences Dataclass

| Check | Expected |
|---|---|
| `UserPreferences` importable from `src.input.parser` | No `ImportError` |
| Dataclass has all required fields | `location`, `budget_tier`, `budget_range`, `cuisine`, `min_rating`, `extra_prefs`, `raw_query` |
| `budget_range` is correct tuple for each tier | `low → (0, 400)`, `medium → (400, 1000)`, `high → (1000, 999999)` |
| `raw_query` is auto-composed from all fields | Contains location, budget, cuisine, rating info |

**Verification command:**
```bash
python -c "
from src.input.parser import parse_preferences
p = parse_preferences({'location': 'Bangalore', 'budget': 'medium', 'cuisine': 'Italian', 'min_rating': 4.0})
assert p.location == 'Bangalore'
assert p.budget_tier == 'medium'
assert p.budget_range == (400, 1000)
assert p.cuisine == 'Italian'
assert p.min_rating == 4.0
print('UserPreferences fields correct ✅')
"
```

---

### E2-2 · Input Validation

| Scenario | Expected behavior |
|---|---|
| `location = ""` | Raises `ValueError` |
| `budget = "expensive"` | Raises `ValueError` |
| `budget = "MEDIUM"` (uppercase) | Normalizes to `"medium"` — no error |
| `min_rating = 7.0` | Clamped to `5.0` |
| `min_rating = -2.0` | Clamped to `0.0` |
| `extra_prefs` > 200 chars | Truncated to exactly 200 chars |
| All optional fields omitted | Defaults applied: cuisine=`"Any"`, min_rating=`3.0`, extra_prefs=`""` |

**Verification command:**
```bash
python -c "
from src.input.parser import parse_preferences

# Test required field validation
try:
    parse_preferences({'location': '', 'budget': 'low'})
    assert False, 'Should have raised'
except ValueError:
    print('Empty location raises ValueError ✅')

# Test rating clamp
p = parse_preferences({'location': 'Delhi', 'budget': 'high', 'min_rating': 9.0})
assert p.min_rating == 5.0, f'Got {p.min_rating}'
print('Rating clamped correctly ✅')

# Test defaults
p = parse_preferences({'location': 'Mumbai', 'budget': 'low'})
assert p.cuisine == 'Any'
assert p.min_rating == 3.0
print('Defaults applied correctly ✅')
"
```

---

### E2-3 · City Alias Normalization

| Input | Expected output |
|---|---|
| `"bangalore"` | `"Bangalore"` |
| `"blr"` | `"Bangalore"` |
| `"DELHI"` | `"Delhi"` |
| `"new delhi"` | `"Delhi"` |
| `"bombay"` | `"Mumbai"` |
| `"  Bangalore  "` (extra spaces) | `"Bangalore"` |

**Verification command:**
```bash
python -c "
from src.input.parser import normalize_city
cases = [('bangalore','Bangalore'), ('blr','Bangalore'), ('DELHI','Delhi'), ('new delhi','Delhi'), ('bombay','Mumbai'), ('  Bangalore  ','Bangalore')]
for raw, expected in cases:
    result = normalize_city(raw)
    assert result == expected, f'{raw!r} → {result!r}, expected {expected!r}'
print('All city aliases normalize correctly ✅')
"
```

---

### E2-4 · Filter Engine — Happy Path

| Check | Expected |
|---|---|
| Returns a dict with keys `candidates`, `fallback_triggered`, `fallback_reason` | Type check passes |
| `candidates` is a list of dicts | Each element is a plain dict (JSON-serializable) |
| Candidates are sorted by `rating` descending | `candidates[0]["rating"] >= candidates[-1]["rating"]` |
| Candidate count ≤ `max_candidates` | `len(candidates) <= 15` (default) |
| `fallback_triggered = False` for exact match | No fallback when results exist |
| Each candidate dict has required fields | `name`, `city`, `cuisines`, `rating`, `votes`, `cost_for_two`, `budget_tier`, `restaurant_type` |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
from src.input.parser import parse_preferences
from src.filter.engine import get_candidates

df = preprocess(load_dataset())
prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium'})
result = get_candidates(df, prefs)

assert isinstance(result['candidates'], list)
assert len(result['candidates']) > 0
assert len(result['candidates']) <= 15
assert result['fallback_triggered'] == False
ratings = [r['rating'] for r in result['candidates']]
assert ratings == sorted(ratings, reverse=True), 'Not sorted by rating'
print(f'Filter returned {len(result[\"candidates\"])} sorted candidates ✅')
"
```

---

### E2-5 · Filter Engine — Cuisine Filter

| Check | Expected |
|---|---|
| `cuisine = "Italian"` only returns restaurants with `"italian"` in their cuisines list | No non-Italian restaurants in results |
| `cuisine = "Any"` returns restaurants of all cuisines | No cuisine-based exclusions |
| Cuisine matching is case-insensitive | `"Italian"` matches `["italian", "continental"]` |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
from src.input.parser import parse_preferences
from src.filter.engine import get_candidates

df = preprocess(load_dataset())
prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium', 'cuisine': 'Chinese'})
result = get_candidates(df, prefs)
for r in result['candidates']:
    assert 'chinese' in r['cuisines'], f'Non-Chinese restaurant in results: {r[\"name\"]}'
print('Cuisine filter correct ✅')
"
```

---

### E2-6 · Filter Engine — Fallback Strategy

| Scenario | Expected `fallback_triggered` | Expected `fallback_reason` |
|---|---|---|
| Exact match exists | `False` | `""` |
| Budget mismatch (no medium results) | `True` | Contains `"budget"` |
| Cuisine + budget both have no results | `True` | Contains `"cuisine"` |
| No results after all fallbacks | `True` | `candidates` is `[]` |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
from src.input.parser import parse_preferences
from src.filter.engine import get_candidates

df = preprocess(load_dataset())

# Test zero-result fallback
prefs = parse_preferences({'location': 'Bangalore', 'budget': 'high', 'cuisine': 'Martian', 'min_rating': 5.0})
result = get_candidates(df, prefs)
assert result['fallback_triggered'] == True
print(f'Fallback triggered: {result[\"fallback_reason\"]} ✅')
"
```

---

### E2-7 · Unit Tests

| Check | Expected |
|---|---|
| `tests/test_parser.py` has ≥ 8 tests | `pytest --collect-only tests/test_parser.py` shows 8+ items |
| `tests/test_filter.py` has ≥ 8 tests | `pytest --collect-only tests/test_filter.py` shows 8+ items |
| All tests pass | Exit code 0 |

**Verification command:**
```bash
pytest tests/test_parser.py tests/test_filter.py -v
```

---

## 🔴 Blocking Issues

- [ ] `parse_preferences()` does not raise on missing `location`
- [ ] `parse_preferences()` does not raise on invalid `budget`
- [ ] `get_candidates()` returns unsorted results
- [ ] `get_candidates()` returns a plain list instead of `{"candidates": ..., "fallback_triggered": ..., "fallback_reason": ...}`
- [ ] Cuisine filter returns restaurants that don't match the requested cuisine

---

## 🟡 Non-blocking Warnings

- City alias map has fewer than 8 entries (some common aliases missing)
- `fallback_reason` string is not human-readable (too technical)
- Filter doesn't log candidate count at each stage

---

## Scoring

| Category | Weight | Score |
|---|---|---|
| `UserPreferences` dataclass correct | 15% | __ / 15 |
| Input validation rules enforced | 25% | __ / 25 |
| City alias normalization | 10% | __ / 10 |
| Filter happy path correct | 20% | __ / 20 |
| Fallback strategy works | 20% | __ / 20 |
| Tests present and passing | 10% | __ / 10 |
| **Total** | **100%** | **__ / 100** |

> **Minimum to proceed:** 80 / 100 with no blocking issues.
