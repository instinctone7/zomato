# Phase 5: Streamlit UI & Hardening

> **Zomato-1 Implementation Plan**  
> **Phase:** 5 of 5  
> **Focus:** Web UI via Streamlit, edge-case hardening, full test suite, and project documentation  
> **Est. Effort:** 1–2 days  
> **Depends on:** [Phase 4 — Output Formatter & CLI](./phase-4-output-cli.md)  
> **Next Phase:** None — this is the final PoC milestone 🎉

---

## Goal

Add a polished web-based interface via Streamlit so non-technical users can interact with the system through a browser. Harden all 6 edge-case failure scenarios, complete the test suite, and write the README so the project is ready to share or demo.

---

## Milestone

> **✅ Done when:**
> 1. `streamlit run app.py` opens a working web UI in the browser — full end-to-end flow functions
> 2. `pytest tests/ -v` passes all tests with no failures
> 3. `README.md` enables a new developer to clone, install, and run the project in under 5 minutes
> 4. All 6 error edge cases from `architecture.md §7` are handled gracefully in both CLI and UI

---

## Tasks

### 5.1 — Streamlit App (`app.py`)

**What it does:** Provides a clean browser-based UI with filter inputs on one side and recommendation cards on the other. Calls the same pipeline as the CLI but renders via Streamlit components.

**Page layout:**
```python
st.set_page_config(
    page_title="🍽️ Zomato AI Recommender",
    page_icon="🍽️",
    layout="wide"
)
```

**Two-column layout:**
```
┌───────────────────┬────────────────────────────────────────┐
│  Sidebar (left)   │  Main content (right)                  │
│                   │                                        │
│  🍽️ Filters       │  Results appear here after search      │
│                   │                                        │
│  City             │  ┌──────────────────────────────────┐  │
│  [selectbox]      │  │ ⭐ #1 — Restaurant Name           │  │
│                   │  │ 📍 Location  💰 Cost  🍕 Cuisine  │  │
│  Budget           │  │                                  │  │
│  [radio]          │  │ 🤖 AI Explanation text...        │  │
│                   │  │    [▼ Read more]                 │  │
│  Cuisine          │  └──────────────────────────────────┘  │
│  [text_input]     │                                        │
│                   │  ┌──────────────────────────────────┐  │
│  Min Rating       │  │ ⭐ #2 — ...                       │  │
│  [slider]         │  └──────────────────────────────────┘  │
│                   │                                        │
│  Extra prefs      │  ✨ Summary line                       │
│  [text_area]      │                                        │
│                   │                                        │
│  [🔍 Search]      │                                        │
└───────────────────┴────────────────────────────────────────┘
```

**Sidebar components:**

| Component | Streamlit widget | Notes |
|---|---|---|
| City | `st.selectbox` | Populated from `df["city"].unique()` sorted |
| Budget | `st.radio` | Options: `low`, `medium`, `high` |
| Cuisine | `st.text_input` | Optional; placeholder `"Any cuisine"` |
| Min Rating | `st.slider` | Range `0.0–5.0`, step `0.5`, default `3.0` |
| Extra prefs | `st.text_area` | Optional; `max_chars=200`; placeholder `"e.g. quiet, good for dates"` |
| Search button | `st.button("🔍 Find Restaurants")` | Triggers pipeline |

**Main content — results rendering:**

```python
def render_streamlit(result: dict) -> None:
    # Implement in src/output/formatter.py (was stub in Phase 4)
    # For each recommendation:
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"{'⭐' * round(rec['rating'])}  #{rec['rank']} — {rec['name']}")
            st.caption(f"📍 {rec['location']}  |  🍕 {', '.join(rec['cuisines'])}")
        with col2:
            st.metric("Rating", f"{rec['rating']} / 5")
            st.metric("Cost for 2", f"₹{rec['cost_for_two']}")

        with st.expander("🤖 Why this restaurant?"):
            st.write(rec["explanation"])
            if rec.get("trade_offs"):
                st.warning(f"⚠️ Trade-off: {rec['trade_offs']}")

        st.divider()
```

**State management:**
- [ ] Use `st.session_state` to cache the loaded+preprocessed DataFrame across reruns (avoid reloading on every button click)
- [ ] Use `st.spinner("🤖 Asking AI to rank restaurants...")` during LLM call
- [ ] Store last result in `st.session_state["last_result"]` so it persists across sidebar changes

**Implementation steps:**
- [ ] Implement full `app.py` with sidebar + main layout
- [ ] Implement `render_streamlit()` in `src/output/formatter.py` (replace the Phase 4 stub)
- [ ] Wire up dataset caching via `@st.cache_data` on the load+preprocess step:
  ```python
  @st.cache_data
  def load_and_preprocess():
      return preprocess(load_dataset())
  ```
- [ ] Add `st.error()` for unrecoverable failures
- [ ] Add `st.warning()` when fallback was triggered

---

### 5.2 — Edge Case Hardening

Complete handling for all 6 scenarios from `architecture.md §7`:

| # | Scenario | Location to fix | Implementation |
|---|---|---|---|
| 1 | No restaurants match filters | `filter/engine.py` | 4-stage fallback already in Phase 2 — verify all branches tested |
| 2 | LLM API rate limit | `llm/client.py` | Exponential backoff already in Phase 3 — verify 3-retry limit enforced |
| 3 | LLM returns malformed JSON | `llm/parser.py` | 3-attempt parse strategy already in Phase 3 — verify fallback activates correctly |
| 4 | LLM API timeout | `llm/client.py` | 15s timeout already in Phase 3 — verify `LLMTimeoutError` is caught in `main.py` and `app.py` |
| 5 | Dataset load failure | `data/loader.py` | Add try/except → `st.error()` in `app.py`, `sys.exit(1)` in `main.py` |
| 6 | Invalid user input | `input/parser.py` | `ValueError` already raised — catch in `app.py` with `st.error()` |

**Additional guards to add:**
- [ ] Input length guard: truncate `extra_prefs` to 200 chars before building prompt (add to `build_prompt()`)
- [ ] Response length guard: if LLM returns > 5 recommendations, cap at 5 in `parse_response()`
- [ ] Hallucination guard: if a recommended restaurant name doesn't match any candidate, skip it (already in Phase 3 — write an explicit test for this)
- [ ] Empty cuisine list guard: if `cuisines` field in a candidate is an empty list, render as `"Not specified"` in formatter

---

### 5.3 — Complete Test Suite

Finish all tests across all phases and add an integration smoke test.

**`tests/test_parser.py`** (Phase 2 — verify complete):
- [ ] 8+ unit tests covering: valid input, alias normalization, missing location, invalid budget (casing), clamped rating, truncated extra_prefs, raw_query composition, budget range mapping

**`tests/test_filter.py`** (Phase 2 — verify complete):
- [ ] 8+ unit tests covering: exact match, sort order, count cap, cuisine filter, `"Any"` cuisine, budget fallback, cuisine fallback, full no-match empty return

**`tests/test_prompt.py`** (Phase 3 — verify complete):
- [ ] 4+ unit tests covering: all pref fields in output, candidate count cap, empty extra_prefs handling, cuisines list → comma string

**`tests/test_llm_parser.py`** (Phase 3 — verify complete):
- [ ] 6+ unit tests covering: valid JSON, code-fenced JSON, malformed JSON fallback, hallucinated name skip, TOP_N cap, enrichment merge correctness

**New: `tests/test_integration.py`** (Phase 5):
```python
def test_full_pipeline_with_mock_llm(mock_llm_response):
    """
    End-to-end pipeline test with a mocked LLM call.
    Verifies the full flow from raw prefs dict → formatted result dict.
    """
```
- [ ] Use `unittest.mock.patch` to mock `call_llm()` with a canned valid JSON response
- [ ] Run the full pipeline: parse → filter → build_prompt → (mocked) call_llm → parse_response
- [ ] Assert result has `recommendations` list with ≥ 1 item
- [ ] Assert each recommendation has `rank`, `name`, `explanation`, `rating`, `cost_for_two`
- [ ] Assert `ai_ranking = True` (since mock returned valid JSON)

**Run all tests:**
```bash
pytest tests/ -v --tb=short
```

---

### 5.4 — README (`README.md`)

The README is the front door of the project. Must enable a new developer to be up and running in < 5 minutes.

**Sections:**
```markdown
# 🍽️ Zomato AI Recommender

One-paragraph description of what the project does and why.

## Demo
[Screenshot or GIF of the CLI or Streamlit UI]

## Setup

### Prerequisites
- Python 3.10+
- A Groq API key (free tier works)

### Installation
git clone ...
cd zomato-1
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GROQ_API_KEY

### Run (CLI)
python src/main.py

### Run (Web UI)
streamlit run app.py

### Run with flags (non-interactive)
python src/main.py --location Bangalore --budget medium --cuisine Italian --rating 4.0

### Dry run (see the prompt without calling the LLM)
python src/main.py --dry-run --location Delhi --budget low

## Architecture
See docs/architecture.md

## Dataset
Zomato Restaurant Recommendation Dataset — HuggingFace
https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation

## Project Structure
[Copy module tree from architecture.md §5]

## Running Tests
pytest tests/ -v
```

- [ ] Write all README sections above
- [ ] Add a screenshot of CLI output (take one after Phase 4 is complete)
- [ ] Add a screenshot of Streamlit UI (take one after `app.py` is complete)
- [ ] Link to `docs/architecture.md` and `docs/problemstatement.md`

---

### 5.5 — Inline Documentation Pass

Do a single pass across all `src/` files to ensure:
- [ ] Every public function has a docstring with: what it does, args, return value, exceptions raised
- [ ] Every module file has a 1-line module docstring at the top
- [ ] Every `# TODO` or `# FIXME` comment is resolved or converted to a GitHub issue

---

## Files Produced

| File | Purpose |
|---|---|
| `app.py` | Streamlit web UI entry point |
| `src/output/formatter.py` | `render_streamlit()` implemented (replaces Phase 4 stub) |
| `tests/test_integration.py` | End-to-end pipeline smoke test with mocked LLM |
| `README.md` | Project documentation and setup guide |

---

## Notes & Gotchas

> [!IMPORTANT]
> `@st.cache_data` on the data loading function is critical. Without it, Streamlit reloads and preprocesses the entire HuggingFace dataset on **every button click** — a 5–30 second freeze each time.

> [!TIP]
> For demos, pre-set the sidebar defaults to a city and preferences that you know returns good results (e.g., Bangalore, medium, Any, 4.0). This avoids the awkward "no results" edge case live.

> [!NOTE]
> Streamlit reruns the entire `app.py` script on every interaction. Use `st.session_state` to preserve expensive state (loaded DataFrame, last result) across reruns.

> [!WARNING]
> When running `streamlit run app.py`, the Streamlit server must have network access to call the Groq API. Ensure your `.env` is loaded correctly — Streamlit does not automatically load `.env` files. Add `from dotenv import load_dotenv; load_dotenv()` at the top of `app.py`.
