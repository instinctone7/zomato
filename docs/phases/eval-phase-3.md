# Phase 3 Evaluation Criteria: Prompt Builder & LLM Integration

> **Zomato-1** · Phase 3 of 5  
> **Evaluates:** Prompt quality, LLM API integration, response parsing, hallucination guard, fallback  
> **Phase file:** [phase-3-prompt-llm.md](./phase-3-prompt-llm.md)

---

## ✅ Pass Criteria (must ALL be true to proceed to Phase 4)

### E3-1 · Prompt Templates

| Check | Expected |
|---|---|
| `SYSTEM_PROMPT` importable from `src.prompt.templates` | No `ImportError` |
| `USER_PROMPT_TEMPLATE` importable | No `ImportError` |
| `SYSTEM_PROMPT` instructs LLM to return JSON only | Contains "JSON" and schema definition |
| `SYSTEM_PROMPT` instructs LLM to only use provided candidates | Contains phrasing like "only recommend restaurants from the candidates list" |
| `USER_PROMPT_TEMPLATE` contains all required slots | `{location}`, `{budget_tier}`, `{budget_min}`, `{budget_max}`, `{cuisine}`, `{min_rating}`, `{extra_prefs}`, `{candidates_table}` |

**Verification command:**
```bash
python -c "
from src.prompt.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
assert 'JSON' in SYSTEM_PROMPT
assert '{location}' in USER_PROMPT_TEMPLATE
assert '{candidates_table}' in USER_PROMPT_TEMPLATE
assert '{budget_tier}' in USER_PROMPT_TEMPLATE
print('Templates valid ✅')
"
```

---

### E3-2 · Prompt Builder Output

| Check | Expected |
|---|---|
| `build_prompt()` returns a string | `isinstance(result, str)` |
| Output contains user's location | Location string appears in prompt |
| Output contains user's budget tier | Budget tier string appears in prompt |
| Output contains a markdown table of candidates | `|` characters present, table has header row |
| Candidate table row count ≤ MAX_CANDIDATES | No more than 15 rows by default |
| Empty `extra_prefs` renders as `"None specified"` | Not an empty line or blank |
| Cuisines rendered as comma-separated string | `["italian", "continental"]` → `"italian, continental"` |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
from src.input.parser import parse_preferences
from src.filter.engine import get_candidates
from src.prompt.builder import build_prompt

df = preprocess(load_dataset())
prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium'})
result = get_candidates(df, prefs)
prompt = build_prompt(prefs, result['candidates'])

assert isinstance(prompt, str)
assert 'Bangalore' in prompt
assert 'medium' in prompt.lower()
assert '|' in prompt  # markdown table
assert 'None specified' in prompt or prefs.extra_prefs in prompt
print('Prompt built correctly ✅')
print(f'Prompt length: {len(prompt)} chars, ~{len(prompt)//4} tokens')
"
```

---

### E3-3 · LLM Client — Connectivity

| Check | Expected |
|---|---|
| `call_llm()` importable from `src.llm.client` | No `ImportError` |
| Calling with valid prompts returns a non-empty string | `len(response) > 0` |
| Response looks like JSON (starts with `{`) | `response.strip().startswith("{")` or contains JSON |
| `LLMError` and `LLMTimeoutError` importable | Custom exception classes exist |
| Missing API key → clear error message | Not a raw SDK `AuthenticationError` traceback |

**Verification command (requires real API key in .env):**
```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from src.llm.client import call_llm
from src.prompt.templates import SYSTEM_PROMPT

test_prompt = 'Return this JSON: {\"recommendations\": [], \"summary\": \"test\"}'
response = call_llm(SYSTEM_PROMPT, test_prompt)
assert isinstance(response, str)
assert len(response) > 0
print(f'LLM responded with {len(response)} chars ✅')
print('First 200 chars:', response[:200])
"
```

---

### E3-4 · Response Parser — Happy Path

| Check | Expected |
|---|---|
| `parse_response()` importable from `src.llm.parser` | No `ImportError` |
| Returns dict with `recommendations`, `summary`, `ai_ranking` keys | Schema check passes |
| `recommendations` is a list | `isinstance(result["recommendations"], list)` |
| Each recommendation has `rank`, `name`, `explanation` | Key presence check |
| Each recommendation is enriched with candidate data | `"rating"`, `"cost_for_two"`, `"cuisines"` present in each rec |
| `ai_ranking = True` for valid JSON response | Confirms real LLM ranking was used |
| Result capped at TOP_N (default 5) | `len(result["recommendations"]) <= 5` |

**Verification command:**
```bash
python -c "
import json
from src.llm.parser import parse_response

candidates = [
    {'name': 'Truffles', 'city': 'Bangalore', 'cuisines': ['American'], 'rating': 4.5, 'votes': 2300, 'cost_for_two': 600, 'budget_tier': 'medium', 'restaurant_type': 'Casual Dining', 'has_online_delivery': True, 'has_table_booking': False},
]
valid_json = json.dumps({
    'recommendations': [{'rank': 1, 'name': 'Truffles', 'explanation': 'Great match.', 'trade_offs': ''}],
    'summary': 'Top pick.'
})
result = parse_response(valid_json, candidates)
assert result['ai_ranking'] == True
assert result['recommendations'][0]['rating'] == 4.5
print('Happy path parse correct ✅')
"
```

---

### E3-5 · Response Parser — Fallback Cases

| Scenario | Expected |
|---|---|
| Completely invalid JSON | `ai_ranking = False`, fallback results returned |
| JSON in code fence (` ```json ... ``` `) | Parsed correctly, `ai_ranking = True` |
| Empty string response | `ai_ranking = False`, fallback results returned |
| Wrong schema (`{"results": [...]}`) | `ai_ranking = False`, fallback results returned |
| LLM recommends unknown restaurant name | That recommendation skipped, warning logged |
| LLM returns 8 recommendations | Capped at 5 |
| LLM returns duplicate restaurant names | Deduplicated — only first occurrence kept |

**Verification command:**
```bash
python -c "
from src.llm.parser import parse_response

candidates = [{'name': 'Real Place', 'rating': 4.5, 'cost_for_two': 500, 'cuisines': ['Indian'], 'city': 'Bangalore', 'votes': 100, 'budget_tier': 'medium', 'restaurant_type': 'Casual', 'has_online_delivery': True, 'has_table_booking': False}]

# Test malformed JSON
result = parse_response('this is not json', candidates)
assert result['ai_ranking'] == False
print('Malformed JSON fallback ✅')

# Test hallucinated name
import json
fake_json = json.dumps({'recommendations': [{'rank': 1, 'name': 'Fake Place', 'explanation': 'x', 'trade_offs': ''}], 'summary': 'x'})
result = parse_response(fake_json, candidates)
names = [r['name'] for r in result['recommendations']]
assert 'Fake Place' not in names
print('Hallucination guard works ✅')
"
```

---

### E3-6 · End-to-End LLM Round Trip (Integration Smoke Test)

Run the full Phase 1 → 2 → 3 pipeline with a real LLM call and verify the output shape.

| Check | Expected |
|---|---|
| Pipeline runs without exception | No unhandled errors |
| Result has ≥ 1 recommendation | LLM returned at least one valid result |
| Each recommendation has a non-empty `explanation` | LLM generated real explanations, not empty strings |
| `explanation` is not generic boilerplate for all recs | At least some variation between explanations |
| `summary` is non-empty | LLM generated a summary |

**Verification command:**
```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
from src.input.parser import parse_preferences
from src.filter.engine import get_candidates
from src.prompt.builder import build_prompt
from src.prompt.templates import SYSTEM_PROMPT
from src.llm.client import call_llm
from src.llm.parser import parse_response

df = preprocess(load_dataset())
prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium', 'cuisine': 'Any', 'min_rating': 4.0})
candidates_result = get_candidates(df, prefs)
prompt = build_prompt(prefs, candidates_result['candidates'])
raw = call_llm(SYSTEM_PROMPT, prompt)
result = parse_response(raw, candidates_result['candidates'])

assert len(result['recommendations']) >= 1
assert all(r['explanation'] for r in result['recommendations'])
assert result['summary']
print(f'End-to-end passed: {len(result[\"recommendations\"])} recommendations ✅')
print('Summary:', result['summary'])
"
```

---

### E3-7 · Unit Tests

| Check | Expected |
|---|---|
| `tests/test_prompt.py` has ≥ 4 tests | File present with 4+ tests |
| `tests/test_llm_parser.py` has ≥ 6 tests | File present with 6+ tests |
| All tests pass without real API calls | Mock-based, no network required |

**Verification command:**
```bash
pytest tests/test_prompt.py tests/test_llm_parser.py -v
```

---

## 🔴 Blocking Issues

- [ ] `call_llm()` raises unhandled exception on valid input
- [ ] `parse_response()` crashes (not returns fallback) on malformed JSON
- [ ] Hallucination guard missing — `parse_response()` enriches a hallucinated name instead of skipping it
- [ ] `SYSTEM_PROMPT` does not instruct LLM to return JSON — LLM returns prose consistently
- [ ] End-to-end round trip produces 0 recommendations

---

## 🟡 Non-blocking Warnings

- Prompt token count > 2000 (consider trimming candidate fields)
- LLM explanations are all identical or very generic (may need prompt tuning)
- Retry logic not tested (no test for rate limit mock)
- `call_llm()` doesn't log token usage

---

## Recommendation Quality Rubric

For each LLM-generated recommendation, score these criteria manually:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **Relevance** | Doesn't match any preference | Matches some preferences | Matches all stated preferences |
| **Explanation specificity** | Generic ("good restaurant") | Mentions 1 preference | Mentions ≥ 2 specific preferences |
| **Accuracy** | Contradicts actual data | Loosely based on data | Directly references actual rating/cost/cuisine |
| **Trade-off honesty** | Empty or false | Vague mention | Specific, accurate trade-off |

**Target:** Average score ≥ 1.5 / 2.0 per criterion across 5 test queries.

---

## Scoring

| Category | Weight | Score |
|---|---|---|
| Prompt templates correct | 10% | __ / 10 |
| Prompt builder output quality | 15% | __ / 15 |
| LLM client connects and returns response | 20% | __ / 20 |
| Response parser happy path | 20% | __ / 20 |
| Fallback cases handled correctly | 20% | __ / 20 |
| Tests present and passing | 15% | __ / 15 |
| **Total** | **100%** | **__ / 100** |

> **Minimum to proceed:** 80 / 100 with no blocking issues.
