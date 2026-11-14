# Phase 4: Output Formatter & CLI Wiring

> **Zomato-1 Implementation Plan**  
> **Phase:** 4 of 5  
> **Focus:** Rendering recommendations to the terminal and wiring all 5 layers into a runnable CLI  
> **Est. Effort:** 1 day  
> **Depends on:** [Phase 3 — Prompt Builder & LLM Integration](./phase-3-prompt-llm.md)  
> **Next Phase:** [Phase 5 — Streamlit UI & Hardening](./phase-5-ui-polish.md)

---

## Goal

Render the structured recommendation output as a beautiful, readable terminal experience using the `rich` library. Then wire all five pipeline layers (Input → Data → Filter → LLM → Output) into a single entry point (`src/main.py`) that works both interactively and via CLI flags.

---

## Milestone

> **✅ Done when:**  
> Running the following produces a fully formatted, end-to-end recommendation in the terminal — no errors, no raw JSON visible:
> ```bash
> python src/main.py \
>   --location Bangalore \
>   --budget medium \
>   --cuisine Italian \
>   --rating 4.0 \
>   --prefs "quiet, good for a date"
> ```
> And running `python src/main.py` (no flags) triggers a clean interactive prompt session.

---

## Tasks

### 4.1 — Output Formatter (`src/output/formatter.py`)

**What it does:** Takes the structured recommendations dict and renders it as Rich-formatted terminal output. Also defines the `render_streamlit()` stub used in Phase 5.

**Interface:**
```python
def render_cli(result: dict, prefs: "UserPreferences") -> None:
    """
    Print ranked recommendations to terminal using Rich.
    result: output of parse_response()
    prefs: UserPreferences (used for header context)
    """

def render_streamlit(result: dict) -> None:
    """
    Render recommendation cards in Streamlit.
    Implemented in Phase 5. Stub only here.
    """
```

**CLI rendering layout:**

```
┌─────────────────────────────────────────────────────────┐
│  🍽️  Zomato AI Recommendations                          │
│  Bangalore · Medium Budget · Italian · Rating ≥ 4.0    │
└─────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────
 🍽️  #1 — Truffles  (Casual Dining)
─────────────────────────────────────────────────────────
  📍  Koramangala, Bangalore
  🍕  American, Continental
  ⭐  4.5 / 5.0   (2,300 votes)
  💰  ~₹600  ·  Medium budget
  🛵  Delivery: Yes   |   📅 Booking: No

  🤖  Why this restaurant:
      Truffles is a top-rated comfort food spot in Koramangala,
      perfectly matching your medium budget. Known for its relaxed
      ambiance, it is an excellent choice for a quiet evening out.

  ⚠️  Trade-off: Can get crowded on weekend evenings.
─────────────────────────────────────────────────────────

... (repeat for #2, #3 ...)

✨  Summary: These 3 picks offer the best value for a quiet,
    romantic Italian-leaning dinner in Bangalore at a medium budget.
```

**Rich components to use:**

| UI element | Rich component |
|---|---|
| Header box | `rich.panel.Panel` with title |
| Separator | `rich.rule.Rule` |
| Each rec card | `rich.panel.Panel` with subtitle |
| Rating stars | Plain string `"⭐ 4.5 / 5.0"` |
| AI explanation | `rich.text.Text` with word wrap |
| Trade-off line | Yellow `rich.text.Text` prefixed with `"⚠️"` |
| Summary line | Italic `rich.text.Text` |
| Fallback warning | `rich.console.Console.print("[amber]⚠️ No exact match...")`  |
| LLM spinner | `rich.console.Console.status("🤖 Asking AI...")` (used in main.py) |

**Implementation steps:**
- [ ] Implement `_render_header(prefs) -> Panel`
- [ ] Implement `_render_card(rec: dict, rank: int) -> Panel` for a single recommendation
- [ ] Implement `_render_summary(summary: str) -> Text`
- [ ] Implement `_render_fallback_warning(reason: str) -> None` (prints amber warning)
- [ ] Implement `render_cli()` calling the above in order across all recommendations
- [ ] Add `render_streamlit()` as a stub with `raise NotImplementedError("Implemented in Phase 5")`

---

### 4.2 — Main Entry Point (`src/main.py`)

**What it does:** The single runnable file that wires all layers together. Supports both interactive (prompted) and non-interactive (CLI flags) modes.

**Full pipeline flow:**
```python
def main():
    # ── Startup ─────────────────────────────────────
    # 1. Parse CLI args (argparse)
    # 2. Load & preprocess dataset (once — before input prompt)
    #    Show: "⏳ Loading dataset..." spinner

    # ── Input ────────────────────────────────────────
    # 3. Collect preferences:
    #    - If CLI flags provided → use them (non-interactive)
    #    - Else → prompt user interactively with rich.Prompt.ask()

    # ── Filter ───────────────────────────────────────
    # 4. Run filter engine
    #    Show: "🔍 Found {N} candidates matching your preferences."
    #    If fallback_triggered: show warning

    # ── LLM ─────────────────────────────────────────
    # 5. Build prompt
    # 6. Call LLM (inside rich spinner: "🤖 Asking AI to rank...")
    # 7. Parse response

    # ── Output ───────────────────────────────────────
    # 8. Render CLI output
```

**CLI arguments (via `argparse`):**

| Flag | Type | Description |
|---|---|---|
| `--location` | `str` | City name |
| `--budget` | `str` | `low` / `medium` / `high` |
| `--cuisine` | `str` | Cuisine type (default: `"Any"`) |
| `--rating` | `float` | Minimum rating (default: `3.0`) |
| `--prefs` | `str` | Free-text additional preferences |
| `--dry-run` | `flag` | Print assembled prompt, skip LLM call |
| `--max-candidates` | `int` | Override `MAX_CANDIDATES` env var |
| `--top-n` | `int` | Override `TOP_N_RESULTS` env var |

**Interactive prompts (when no flags given):**
```python
from rich.prompt import Prompt, FloatPrompt

location = Prompt.ask("📍 City / Location")
budget   = Prompt.ask("💰 Budget", choices=["low", "medium", "high"])
cuisine  = Prompt.ask("🍕 Cuisine (press Enter for any)", default="Any")
rating   = FloatPrompt.ask("⭐ Minimum rating", default=3.0)
prefs    = Prompt.ask("📝 Any other preferences? (optional)", default="")
```

**`--dry-run` mode:**
- Skip the `call_llm()` step entirely
- Print the assembled system + user prompt to terminal
- Print the top-N candidates as a formatted table
- Exit cleanly — useful for prompt debugging without spending API tokens

**Error handling in `main()`:**

| Error | Handling |
|---|---|
| `ValueError` from parser | Print red error message, exit with code 1 |
| Empty candidate list | Print "No restaurants found" message with suggestions (try relaxing filters) |
| `LLMError` | Print amber warning, show rating-sorted fallback results |
| `LLMTimeoutError` | Print "AI is taking too long" message, show fallback results |
| `KeyboardInterrupt` | Print `"\n👋 Goodbye!"` and exit cleanly |

**Implementation steps:**
- [ ] Implement `_parse_args() -> argparse.Namespace`
- [ ] Implement `_collect_interactive() -> dict` (rich prompts)
- [ ] Implement `_collect_from_args(args) -> dict` (from argparse namespace)
- [ ] Implement `main()` following the pipeline flow above
- [ ] Add `if __name__ == "__main__": main()` guard at bottom

---

## Files Produced

| File | Purpose |
|---|---|
| `src/output/formatter.py` | `render_cli()` with Rich panels + `render_streamlit()` stub |
| `src/main.py` | Full pipeline entry point, interactive + non-interactive |

---

## Notes & Gotchas

> [!IMPORTANT]
> Load the dataset **before** prompting the user for preferences. The HuggingFace dataset download (first run only) can take 10–30 seconds — it's better UX to do it at startup than to show a loading delay mid-session after the user has already typed their preferences.

> [!TIP]
> Use `--dry-run` mode extensively during Phase 3 and 4 development to iterate on the prompt without burning API quota. It's also useful for demos where you want to show the prompt design.

> [!NOTE]
> The `--dry-run` flag should print the **fully assembled prompt** (with real candidate data filled in), not the template. This makes it genuinely useful for debugging LLM behavior.

> [!WARNING]
> `argparse` and `rich.Prompt` don't mix perfectly — if any CLI flags are provided, skip **all** interactive prompts and use defaults for missing optional fields. Don't prompt for some fields and read others from flags in the same run.
