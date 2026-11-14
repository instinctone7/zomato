# Phase 1 Evaluation Criteria: Setup & Data Pipeline

> **Zomato-1** · Phase 1 of 5  
> **Evaluates:** Repository structure, dataset loading, preprocessing correctness  
> **Phase file:** [phase-1-setup-data.md](./phase-1-setup-data.md)

---

## ✅ Pass Criteria (must ALL be true to proceed to Phase 2)

### E1-1 · Project Structure

| Check | Expected |
|---|---|
| `src/` directory exists with all sub-packages | `src/data/`, `src/input/`, `src/filter/`, `src/prompt/`, `src/llm/`, `src/output/` all present |
| Every sub-package has `__init__.py` | No `ModuleNotFoundError` on any `from src.X import Y` |
| `requirements.txt` exists | Present and non-empty |
| `.env.example` exists | Contains at minimum `GROQ_API_KEY`, `LLM_PROVIDER` entries |
| `tests/` directory exists | Present |

**Verification command:**
```bash
python -c "
import src.data, src.input, src.filter, src.prompt, src.llm, src.output
print('All packages importable ✅')
"
```

---

### E1-2 · Dependency Installation

| Check | Expected |
|---|---|
| `pip install -r requirements.txt` exits with code 0 | No installation errors |
| All key packages importable | `import datasets, pandas, dotenv, rich, streamlit, pytest` all succeed |

**Verification command:**
```bash
python -c "import datasets, pandas, dotenv, rich, streamlit, pytest; print('All deps installed ✅')"
```

---

### E1-3 · Dataset Loading (`src/data/loader.py`)

| Check | Expected |
|---|---|
| `load_dataset()` returns a DataFrame | Type is `pd.DataFrame` |
| DataFrame is non-empty | `len(df) > 0` |
| DataFrame contains required columns | At minimum: `name`, `city`, `cuisines`, `aggregate_rating`, `votes`, `average_cost_for_two` |
| No crash on second call | HuggingFace cache works; second call is instant |
| `ConnectionError` handled gracefully | Catch produces a readable message, not a Python traceback |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
df = load_dataset()
assert len(df) > 0, 'DataFrame is empty'
print(f'Loaded {len(df)} rows, {len(df.columns)} columns ✅')
print('Columns:', df.columns.tolist())
"
```

---

### E1-4 · Preprocessing Correctness (`src/data/preprocessor.py`)

| Check | Expected |
|---|---|
| Output DataFrame has no null `name` values | `df["name"].isna().sum() == 0` |
| Output DataFrame has no null `city` values | `df["city"].isna().sum() == 0` |
| Output DataFrame has no null `rating` values | `df["rating"].isna().sum() == 0` |
| All `votes` values ≥ 10 | `df["votes"].min() >= 10` |
| `budget_tier` column exists | `"budget_tier" in df.columns` |
| `budget_tier` only contains valid values | `set(df["budget_tier"].unique()) ⊆ {"low", "medium", "high"}` |
| `cuisines` column contains lists | `isinstance(df["cuisines"].iloc[0], list)` |
| `city` values are title-cased | `df["city"].str.istitle().all()` (or no ALL-CAPS / all-lowercase entries) |
| Row count after preprocess ≤ row count before | Rows only drop, never increase |
| `rating` column is renamed from `aggregate_rating` | `"rating" in df.columns` and `"aggregate_rating" not in df.columns` |

**Verification command:**
```bash
python -c "
from src.data.loader import load_dataset
from src.data.preprocessor import preprocess
raw = load_dataset()
df = preprocess(raw)
assert df['name'].isna().sum() == 0
assert df['city'].isna().sum() == 0
assert df['rating'].isna().sum() == 0
assert df['votes'].min() >= 10
assert 'budget_tier' in df.columns
assert set(df['budget_tier'].unique()).issubset({'low','medium','high'})
assert isinstance(df['cuisines'].iloc[0], list)
assert len(df) <= len(raw)
print(f'Preprocessing passed: {len(raw)} → {len(df)} rows ✅')
"
```

---

### E1-5 · Unit Tests

| Check | Expected |
|---|---|
| `tests/test_loader.py` exists | File present |
| `tests/test_preprocessor.py` exists | File present |
| All tests pass | `pytest tests/test_loader.py tests/test_preprocessor.py -v` exits with code 0 |
| Minimum test count | At least 2 tests in loader, at least 6 in preprocessor |

**Verification command:**
```bash
pytest tests/test_loader.py tests/test_preprocessor.py -v
```

---

## 🔴 Blocking Issues (Phase 2 cannot start if any of these are true)

- [ ] `load_dataset()` raises an unhandled exception
- [ ] `preprocess()` raises an unhandled exception on the real dataset
- [ ] `budget_tier` column is missing or has null values
- [ ] Any test file raises an import error

---

## 🟡 Non-blocking Warnings (acceptable for now, fix before Phase 5)

- Preprocessing takes > 30 seconds (consider optimizing column operations)
- Some city values are inconsistently cased (affects Phase 2 filter accuracy)
- `cuisines` split logic produces empty strings in lists (e.g., `["italian", ""]`)

---

## Scoring

| Category | Weight | Score |
|---|---|---|
| Project structure complete | 20% | __ / 20 |
| `load_dataset()` correct | 20% | __ / 20 |
| `preprocess()` correct | 40% | __ / 40 |
| Tests present and passing | 20% | __ / 20 |
| **Total** | **100%** | **__ / 100** |

> **Minimum to proceed:** 80 / 100 with no blocking issues.
