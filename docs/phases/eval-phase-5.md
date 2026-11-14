# Phase 5 Evaluation Criteria: Streamlit UI & Hardening

> **Zomato-1** · Phase 5 of 5  
> **Evaluates:** Streamlit UI functionality, edge-case coverage, test suite completeness, documentation quality  
> **Phase file:** [phase-5-ui-polish.md](./phase-5-ui-polish.md)

---

## ✅ Pass Criteria (all must be true for the PoC to be considered complete)

### E5-1 · Streamlit App Launches

| Check | Expected |
|---|---|
| `streamlit run app.py` starts without error | Server starts, URL printed |
| App loads in browser | No blank page, no unhandled exception |
| `load_dotenv()` called at top of `app.py` | API key available to Groq SDK |
| Dataset loaded with `@st.cache_data` | Confirmed by checking function decorator |
| App title and icon visible | `"🍽️ Zomato AI Recommender"` in browser tab |

**Verification command:**
```bash
streamlit run app.py &
sleep 5
curl -s http://localhost:8501 | grep -q "Zomato" && echo "App running ✅" || echo "App not found ❌"
```

> Then manually open `http://localhost:8501` and verify UI renders.

---

### E5-2 · Streamlit UI — Input Controls

| Component | Check | Expected |
|---|---|---|
| City selector | Shows `st.selectbox` or `st.text_input` | Populated with cities from dataset |
| Budget | Shows `st.radio` with 3 options | `low`, `medium`, `high` selectable |
| Cuisine | Shows `st.text_input` | Optional; placeholder text visible |
| Min Rating | Shows `st.slider` | Range 0.0–5.0, step 0.5 |
| Extra prefs | Shows `st.text_area` | Optional; `max_chars=200` |
| Search button | Shows `st.button` | Visible and clickable |

**Manual test:** Open `http://localhost:8501`. Verify all 6 input controls are visible and interactive.

---

### E5-3 · Streamlit UI — Search Flow

| Step | Expected |
|---|---|
| Click "🔍 Find Restaurants" | Spinner shown: "🤖 Asking AI to rank restaurants..." |
| After spinner resolves | Recommendation cards appear in main area |
| Each card shows: name, location, cuisine, rating, cost | All fields visible |
| "Why this restaurant?" expandable | `st.expander` present and toggleable |
| Expanding shows full AI explanation | Explanation text visible |
| Trade-off shown as `st.warning` if present | Amber warning box visible |
| Summary shown below cards | Present and non-empty |

**Manual test:** Enter `Bangalore`, `medium`, `Any`, `4.0` → click search → verify full output.

---

### E5-4 · Streamlit UI — State & Caching

| Check | Expected |
|---|---|
| Changing sidebar filters and clicking search again works | New results shown — no crash |
| Changing budget does NOT reload dataset | Dataset reuse from `@st.cache_data` (fast requery) |
| Last results persist when user scrolls | Results don't disappear mid-scroll |
| App handles multiple searches in sequence | No accumulating errors or stale state |

**Manual test:** Run 3 consecutive searches with different cities. All should return results without page refresh or crash.

---

### E5-5 · Streamlit UI — Error Handling

| Scenario | Expected UI behavior |
|---|---|
| Search with no results | `st.warning("No restaurants found...")` visible |
| LLM API rate limit | `st.warning` with fallback results shown |
| LLM timeout | `st.warning("AI is taking too long...")` with fallback results |
| Invalid city (not in dataset) | `st.warning` suggesting available cities |
| Missing API key | `st.error("GROQ_API_KEY not set...")` on page load |

**Manual test:** Set `GROQ_API_KEY=""` in `.env`, rerun `streamlit run app.py`. Verify error shown immediately.

---

### E5-6 · Edge Case Coverage (from `edgecase.md`)

All 🔴 Critical and 🟠 High edge cases must be handled. Verify each:

| Edge Case | ID | Verification |
|---|---|---|
| Empty location | EC-I-01 | `parse_preferences({'location': ''})` raises `ValueError` |
| Invalid budget | EC-I-04 | `parse_preferences({'location': 'X', 'budget': 'wrong'})` raises `ValueError` |
| Rating clamp | EC-I-05 | `parse_preferences(..., min_rating=9)` → `min_rating == 5.0` |
| Extra prefs truncated | EC-I-07 | 300-char input → 200-char `extra_prefs` |
| Dataset load failure | EC-D-01 | Mock `ConnectionError` → readable error message, no traceback |
| Zero candidates | EC-F-01 | Zero candidates → no LLM call, user-friendly message |
| LLM API key missing | EC-L-01 | Missing key → clear error at startup |
| LLM rate limit | EC-L-02 | Mock 429 → retry 3 times → fallback results |
| LLM timeout | EC-L-03 | Mock slow response → `LLMTimeoutError` → fallback |
| Empty LLM response | EC-L-04 | Empty string → fallback, `ai_ranking = False` |
| LLM hallucination | EC-L-06 | Unknown name in response → skipped, warning logged |
| Zero output recommendations | EC-O-04 | Empty recs → "No recommendations" message shown |
| Streamlit missing API key | EC-S-02 | `load_dotenv()` at top of `app.py`; `st.error()` if still missing |

**Verification command:**
```bash
python -c "
# Run all critical edge case checks
from src.input.parser import parse_preferences, normalize_city
from src.llm.parser import parse_response

# EC-I-01
try: parse_preferences({'location': '', 'budget': 'low'})
except ValueError: print('EC-I-01 ✅')

# EC-I-04
try: parse_preferences({'location': 'X', 'budget': 'wrong'})
except ValueError: print('EC-I-04 ✅')

# EC-I-05
p = parse_preferences({'location': 'X', 'budget': 'low', 'min_rating': 9.0})
assert p.min_rating == 5.0; print('EC-I-05 ✅')

# EC-I-07
p = parse_preferences({'location': 'X', 'budget': 'low', 'extra_prefs': 'x' * 300})
assert len(p.extra_prefs) == 200; print('EC-I-07 ✅')

# EC-L-04 (empty LLM response)
result = parse_response('', [])
assert result['ai_ranking'] == False; print('EC-L-04 ✅')

# EC-L-06 (hallucination guard)
import json
fake = json.dumps({'recommendations': [{'rank':1,'name':'FakeName','explanation':'x','trade_offs':''}],'summary':'x'})
result = parse_response(fake, [{'name':'RealPlace','rating':4.0,'cost_for_two':500,'cuisines':['Indian'],'city':'Bangalore','votes':100,'budget_tier':'medium','restaurant_type':'Casual','has_online_delivery':True,'has_table_booking':False}])
assert all(r['name'] != 'FakeName' for r in result['recommendations']); print('EC-L-06 ✅')
"
```

---

### E5-7 · Full Test Suite

| Check | Expected |
|---|---|
| `tests/test_parser.py` — ≥ 8 tests, all pass | `pytest tests/test_parser.py -v` exit 0 |
| `tests/test_filter.py` — ≥ 8 tests, all pass | `pytest tests/test_filter.py -v` exit 0 |
| `tests/test_prompt.py` — ≥ 4 tests, all pass | `pytest tests/test_prompt.py -v` exit 0 |
| `tests/test_llm_parser.py` — ≥ 6 tests, all pass | `pytest tests/test_llm_parser.py -v` exit 0 |
| `tests/test_integration.py` exists with ≥ 1 test | Integration smoke test with mocked LLM |
| All tests combined pass | `pytest tests/ -v` exit code 0 |
| No tests require real API calls | All LLM calls mocked in tests |

**Verification command:**
```bash
pytest tests/ -v --tb=short
echo "Exit code: $?"
```
> Expected: All green. Exit code 0.

---

### E5-8 · README Quality

| Section | Check |
|---|---|
| Project description | 1–2 paragraphs explaining what the project does |
| Prerequisites | Python version + API key requirement listed |
| Installation steps | `git clone`, `pip install`, `.env` setup instructions |
| CLI usage | `python src/main.py` and flags shown |
| Streamlit usage | `streamlit run app.py` shown |
| Non-interactive example | Full flag example with real values |
| Dry-run example | `--dry-run` flag shown |
| Architecture link | Links to `docs/architecture.md` |
| Dataset link | HuggingFace URL present |
| Test command | `pytest tests/ -v` shown |

**Manual check:** Read README as if you're a new developer. Can you set up and run the project in < 5 minutes following only the README?

---

### E5-9 · Code Quality & Documentation

| Check | Expected |
|---|---|
| Every public function has a docstring | `name`, `args`, `return`, `raises` documented |
| Every module has a 1-line module docstring | First line of each `src/**/*.py` file |
| No `TODO` or `FIXME` comments remain | `grep -r "TODO\|FIXME" src/` returns nothing |
| No hardcoded API keys in code | `grep -r "AIzaSy\|sk-" src/` returns nothing |

**Verification command:**
```bash
grep -r "TODO\|FIXME" src/ && echo "⚠️ TODOs remain" || echo "No TODOs ✅"
grep -r "AIzaSy\|sk-" src/ && echo "⚠️ Hardcoded keys found!" || echo "No hardcoded keys ✅"
```

---

## 🔴 Blocking Issues (project is NOT complete if any of these are true)

- [ ] `streamlit run app.py` crashes on startup
- [ ] Search flow crashes on any valid input
- [ ] `pytest tests/` exits with failures
- [ ] Any 🔴 Critical edge case from `edgecase.md` is unhandled
- [ ] API key hardcoded anywhere in `src/`
- [ ] README does not contain setup instructions

---

## 🟡 Non-blocking Warnings (acceptable for PoC, fix before production)

- Streamlit app has no loading indicator on initial dataset load
- Search results don't persist on page refresh (session state cleared)
- No screenshot in README
- Some 🟡 Medium edge cases untested
- City selector is free-text instead of `st.selectbox` (limits discoverability)

---

## Final Project Scoring

| Category | Weight | Score |
|---|---|---|
| Streamlit app launches and renders | 15% | __ / 15 |
| UI input controls complete | 10% | __ / 10 |
| Search flow end-to-end in browser | 20% | __ / 20 |
| Edge case coverage (Critical + High) | 20% | __ / 20 |
| Full test suite passing | 20% | __ / 20 |
| README quality | 10% | __ / 10 |
| Code quality & docstrings | 5% | __ / 5 |
| **Total** | **100%** | **__ / 100** |

> **Project complete at:** 85 / 100 with no blocking issues.

---

## Cumulative Phase Scorecard

| Phase | Score | Status |
|---|---|---|
| Phase 1 — Setup & Data | __ / 100 | ⬜ |
| Phase 2 — Input & Filter | __ / 100 | ⬜ |
| Phase 3 — Prompt & LLM | __ / 100 | ⬜ |
| Phase 4 — Output & CLI | __ / 100 | ⬜ |
| Phase 5 — UI & Polish | __ / 100 | ⬜ |
| **Overall** | **__ / 500** | |
