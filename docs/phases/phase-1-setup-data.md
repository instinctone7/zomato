# Phase 1: Project Setup & Data Pipeline

> **Zomato-1 Implementation Plan**  
> **Phase:** 1 of 5  
> **Focus:** Repository skeleton, dev environment, dataset loading & preprocessing  
> **Est. Effort:** 1–2 days  
> **Depends on:** Nothing — this is the foundation  
> **Next Phase:** [Phase 2 — Input & Filter Engine](./phase-2-input-filter.md)

---

## Goal

Establish the project skeleton, dev environment, and a clean, in-memory restaurant dataset ready for querying. Every subsequent phase depends on this being correct.

---

## Milestone

> **✅ Done when:**  
> Running the following prints a valid `(rows, columns)` tuple from the real Zomato dataset:
> ```bash
> python -c "
> from src.data.loader import load_dataset
> from src.data.preprocessor import preprocess
> df = preprocess(load_dataset())
> print(df.shape, df.columns.tolist())
> "
> ```

---

## Tasks

### 1.1 — Repository & Environment Setup

- [ ] Create the full project directory structure:
  ```
  zomato-1/
  ├── docs/
  │   ├── phases/
  │   ├── problemstatement.md
  │   ├── architecture.md
  │   └── implementation-plan.md
  ├── src/
  │   ├── __init__.py
  │   ├── data/
  │   │   └── __init__.py
  │   ├── input/
  │   │   └── __init__.py
  │   ├── filter/
  │   │   └── __init__.py
  │   ├── prompt/
  │   │   └── __init__.py
  │   ├── llm/
  │   │   └── __init__.py
  │   └── output/
  │       └── __init__.py
  ├── tests/
  ├── .env.example
  ├── requirements.txt
  └── README.md
  ```

- [ ] Create `requirements.txt`:
  ```
  datasets>=2.14.0
  pandas>=2.0.0
  python-dotenv>=1.0.0
  groq>=0.9.0
  groq>=0.9.0
  rich>=13.0.0
  streamlit>=1.30.0
  pytest>=8.0.0
  ```

- [ ] Create `.env.example`:
  ```env
  GROQ_API_KEY=your_key_here
  GROQ_API_KEY=your_key_here
  LLM_PROVIDER=groq
  LLM_TEMPERATURE=0.3
  MAX_CANDIDATES=15
  TOP_N_RESULTS=5
  ```

- [ ] Run `pip install -r requirements.txt` and verify no errors

---

### 1.2 — Dataset Loader (`src/data/loader.py`)

**What it does:** Loads the HuggingFace dataset and returns a raw Pandas DataFrame. Runs once at startup.

**Interface:**
```python
def load_dataset() -> pd.DataFrame:
    """
    Load Zomato dataset from HuggingFace Hub.
    Returns raw DataFrame. HF caches locally after first run (~/.cache/huggingface).
    Raises SystemExit with a clear message if load fails.
    """
```

**Implementation steps:**
- [ ] Import `datasets` and `pandas`
- [ ] Call `datasets.load_dataset("ManikaSaini/zomato-restaurant-recommendation", split="train")`
- [ ] Convert to Pandas: `.to_pandas()`
- [ ] Log row count and column names on successful load
- [ ] Wrap in try/except: catch `ConnectionError` / `FileNotFoundError` → print clear fatal message and `sys.exit(1)`

---

### 1.3 — Preprocessor (`src/data/preprocessor.py`)

**What it does:** Cleans, normalizes, and enriches the raw DataFrame. The result is the in-memory dataset used for all filter queries.

**Interface:**
```python
def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and enrich raw Zomato DataFrame.
    Returns cleaned DataFrame with standardized columns.
    """
```

**Transformations (implement each as a private `_step_name()` function):**

| Step | Function | Logic |
|---|---|---|
| Drop null rows | `_drop_nulls()` | Drop rows where `name`, `city`, or `aggregate_rating` is null |
| Drop low-signal | `_drop_low_votes()` | Drop rows where `votes` < 10 |
| Normalize cities | `_normalize_cities()` | `.str.strip().str.title()` on `city` column |
| Normalize cuisines | `_normalize_cuisines()` | Split comma-separated string → Python list, lowercase + strip each tag |
| Add budget tier | `_add_budget_tier()` | New column: `low` if cost_for_two < 400, `medium` if 400–1000, `high` if > 1000 |
| Rename columns | `_rename_columns()` | `aggregate_rating` → `rating`, `average_cost_for_two` → `cost_for_two` |
| Reset index | `_reset_index()` | `.reset_index(drop=True)` after all drops |

- [ ] Log how many rows were dropped at each step (use `print` or `logging`)
- [ ] `preprocess()` calls each private function in order and returns final DataFrame

---

### 1.4 — Tests (`tests/test_loader.py` + `tests/test_preprocessor.py`)

**`test_loader.py`:**
- [ ] Test: `load_dataset()` returns a non-empty DataFrame
- [ ] Test: DataFrame has expected columns (at minimum: `name`, `city`, `cuisines`, `aggregate_rating`, `votes`)

**`test_preprocessor.py`:**
- [ ] Test: No null values in `name`, `city`, `rating` after preprocessing
- [ ] Test: `budget_tier` column exists and only contains `low`, `medium`, `high`
- [ ] Test: `cuisines` column contains lists (not strings)
- [ ] Test: `city` values are title-cased (no lowercase or ALL-CAPS)
- [ ] Test: Rows with `votes` < 10 are removed
- [ ] Test: Row count after preprocessing ≤ row count before

---

## Files Produced

| File | Purpose |
|---|---|
| `src/data/loader.py` | HuggingFace dataset loading |
| `src/data/preprocessor.py` | Cleaning, normalization, budget bucketing |
| `src/__init__.py` + sub-package `__init__.py` files | Package structure |
| `requirements.txt` | Python dependencies |
| `.env.example` | API key template |
| `tests/test_loader.py` | Loader unit tests |
| `tests/test_preprocessor.py` | Preprocessor unit tests |

---

## Notes & Gotchas

> [!NOTE]
> HuggingFace caches the dataset at `~/.cache/huggingface/` after the first download. Subsequent runs load from disk instantly.

> [!WARNING]
> The raw dataset may have inconsistent column names across versions. Always reference columns by the renamed, normalized names from `_rename_columns()` — never the raw HuggingFace names — in downstream modules.

> [!TIP]
> Run preprocessor steps individually in a Jupyter notebook or `python -i` REPL first to sanity-check each transformation before wiring them together.
