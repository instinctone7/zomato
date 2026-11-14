# Phase 4 Evaluation Criteria: Output Formatter & CLI Wiring

> **Zomato-1** · Phase 4 of 5  
> **Evaluates:** Terminal rendering quality, CLI wiring completeness, interactive + non-interactive modes, error handling  
> **Phase file:** [phase-4-output-cli.md](./phase-4-output-cli.md)

---

## ✅ Pass Criteria (must ALL be true to proceed to Phase 5)

### E4-1 · Output Formatter — CLI Rendering

| Check | Expected |
|---|---|
| `render_cli()` importable from `src.output.formatter` | No `ImportError` |
| `render_cli()` runs without exception on valid input | No crash with well-formed result dict |
| Header panel is printed | Contains city, budget, cuisine context |
| Each recommendation renders as a separate panel/block | Visual separation between recommendations |
| Rating displayed with `/5.0` | e.g., `"4.5 / 5.0"` |
| Cost displayed with `₹` prefix | e.g., `"₹600"` |
| Delivery and booking flags rendered as `Yes`/`No` | Not `True`/`False` |
| AI explanation text visible | Non-empty `explanation` field displayed |
| Trade-off rendered in distinct style (yellow/warning) | Visually different from explanation |
| Summary line rendered at bottom | Present and non-empty |
| `render_streamlit()` stub exists | Present — raises `NotImplementedError` or is a placeholder |

**Verification command:**
```bash
python -c "
import json
from src.output.formatter import render_cli
from src.input.parser import parse_preferences

prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium'})
mock_result = {
    'recommendations': [{
        'rank': 1, 'name': 'Test Place', 'location': 'Koramangala', 'cuisines': ['Italian'],
        'rating': 4.5, 'votes': 1200, 'cost_for_two': 700, 'budget_tier': 'medium',
        'restaurant_type': 'Casual Dining', 'has_online_delivery': True,
        'has_table_booking': False, 'explanation': 'Great match for your preferences.',
        'trade_offs': 'Gets busy on weekends.'
    }],
    'summary': 'Top pick in Bangalore.',
    'ai_ranking': True,
    'fallback_triggered': False,
    'fallback_reason': ''
}
render_cli(mock_result, prefs)
print('render_cli ran without error ✅')
"
```

---

### E4-2 · CLI — Non-interactive Mode (Flags)

| Check | Expected |
|---|---|
| `--location` flag accepted | No argument error |
| `--budget` flag accepted | No argument error |
| `--cuisine` flag accepted (optional) | No argument error; defaults to `"Any"` if omitted |
| `--rating` flag accepted (optional) | No argument error; defaults to `3.0` if omitted |
| `--prefs` flag accepted (optional) | No argument error; defaults to `""` if omitted |
| `--dry-run` flag accepted | No argument error |
| Running with all flags produces output | No crash, recommendations printed |
| Running with only required flags works | `--location` + `--budget` is sufficient |

**Verification command:**
```bash
python src/main.py --location Bangalore --budget medium --cuisine Italian --rating 4.0 --prefs "quiet"
```
> Expected: Recommendations printed to terminal. Exit code 0.

```bash
python src/main.py --location Bangalore --budget medium
```
> Expected: Recommendations printed using defaults for optional flags. Exit code 0.

---

### E4-3 · CLI — Dry Run Mode

| Check | Expected |
|---|---|
| `--dry-run` skips the LLM call | No network call made |
| Assembled prompt is printed to terminal | Prompt text visible including candidate table |
| System prompt is printed | `SYSTEM_PROMPT` text visible |
| Candidate table is included | Markdown table with real data printed |
| Exit code is 0 | No error |

**Verification command:**
```bash
python src/main.py --location Bangalore --budget medium --dry-run
```
> Expected: Full prompt printed. No LLM API call. No recommendations card. Exit code 0.

---

### E4-4 · CLI — Interactive Mode

| Check | Expected |
|---|---|
| Running `python src/main.py` with no flags shows prompts | Each field has a Rich prompt |
| Location prompt appears first | Visible prompt text |
| Budget prompt restricts to `low`/`medium`/`high` | Invalid input re-prompted |
| Cuisine and rating prompts show defaults | Default visible in prompt brackets |
| Extra prefs prompt is optional | Enter key skips it |
| Spinner shown during dataset load | "Loading dataset..." visible |
| Spinner shown during LLM call | "Asking AI..." visible |

> **Manual test:** Run `python src/main.py` with no flags. Enter values interactively. Verify all prompts appear in order.

---

### E4-5 · CLI — Error Handling

| Scenario | Expected CLI behavior |
|---|---|
| `--budget wrong_value` | Prints red error message: "Budget must be one of: low, medium, high" — exits with code 1 |
| `--location ""` (empty) | Prints red error: "Location is required" — exits with code 1 |
| `--rating 10` | Clamped to 5.0 with warning, continues |
| Zero candidates found | Prints "No restaurants found" with filter suggestions |
| LLM API call fails (rate limit) | Prints amber warning, shows rating-sorted fallback results |
| LLM times out | Prints "AI is taking too long" message, shows fallback results |
| `Ctrl+C` during prompts | Prints "Goodbye!" and exits cleanly (no traceback) |

**Verification commands:**
```bash
# Invalid budget
python src/main.py --location Bangalore --budget wrong
# Expected: Error message, exit code 1
echo "Exit code: $?"
```

```bash
# Ctrl+C test (manual)
python src/main.py
# Press Ctrl+C at any prompt
# Expected: "Goodbye!" message, no Python traceback
```

---

### E4-6 · Full End-to-End CLI Run

| Check | Expected |
|---|---|
| Complete run from flags to output takes < 15s | Measured wall-clock time |
| At least 1 recommendation printed | Cards visible in terminal |
| Each card has: name, location, cuisine, rating, cost, explanation | All fields rendered |
| No raw JSON printed to terminal | Zero `{`, `}`, `"rank":` visible in final output |
| Exit code is 0 | Confirmed with `echo $?` |

**Verification command:**
```bash
time python src/main.py --location Bangalore --budget medium --cuisine Any --rating 4.0
echo "Exit code: $?"
```
> Expected: Recommendations printed in < 15s. Exit code 0.

---

## 🔴 Blocking Issues

- [ ] `python src/main.py --location X --budget Y` crashes with an unhandled exception
- [ ] No output rendered — terminal is blank after LLM response
- [ ] Raw JSON visible in CLI output (formatter not wired)
- [ ] `--dry-run` still calls the LLM API
- [ ] `Ctrl+C` produces a Python traceback instead of graceful exit

---

## 🟡 Non-blocking Warnings

- Trade-off text not visually distinct from explanation text
- Summary line missing or not separated from recommendation cards
- Delivery/booking showing `True`/`False` instead of `Yes`/`No`
- No spinner during dataset load (acceptable, but adds to UX quality)
- `render_streamlit()` missing even as a stub

---

## UX Quality Rubric (Manual Assessment)

Rate each criterion 0–2:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **Readability** | Wall of text, no structure | Some structure | Clear panels, visual hierarchy |
| **Information density** | Key fields missing | Most fields present | All fields (name, loc, cuisine, rating, cost, delivery, explanation, trade-off) |
| **Error messages** | Python traceback | Generic "error occurred" | Clear, actionable, user-friendly message |
| **Loading feedback** | No feedback during wait | Static text | Animated spinner |
| **Summary** | Missing | Present but generic | Specific to the user's query |

**Target:** Average ≥ 1.5 / 2.0 per criterion.

---

## Scoring

| Category | Weight | Score |
|---|---|---|
| Output formatter renders correctly | 25% | __ / 25 |
| Non-interactive CLI flags work | 20% | __ / 20 |
| Dry-run mode works | 10% | __ / 10 |
| Interactive mode works | 15% | __ / 15 |
| Error handling complete | 20% | __ / 20 |
| UX quality (manual rubric) | 10% | __ / 10 |
| **Total** | **100%** | **__ / 100** |

> **Minimum to proceed:** 80 / 100 with no blocking issues.
