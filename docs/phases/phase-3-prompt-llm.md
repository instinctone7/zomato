# Phase 3: Prompt Builder & LLM Integration

> **Zomato-1 Implementation Plan**  
> **Phase:** 3 of 5  
> **Focus:** Assembling the LLM prompt, calling Groq, and parsing structured recommendations  
> **Est. Effort:** 1–2 days  
> **Depends on:** [Phase 2 — Input & Filter Engine](./phase-2-input-filter.md)  
> **Next Phase:** [Phase 4 — Output Formatter & CLI](./phase-4-output-cli.md)

---

## Goal

Turn the filtered candidate list and user preferences into a well-structured LLM prompt, call the Groq API, and parse the response into a structured list of ranked recommendations with AI-generated explanations. Handle all API and parsing failures gracefully.

---

## Milestone

> **✅ Done when:**  
> Running the following prints a JSON list of ranked recommendations with `explanation` and `trade_offs` fields:
> ```bash
> python -c "
> from src.data.loader import load_dataset
> from src.data.preprocessor import preprocess
> from src.input.parser import parse_preferences
> from src.filter.engine import get_candidates
> from src.prompt.builder import build_prompt
> from src.prompt.templates import SYSTEM_PROMPT
> from src.llm.client import call_llm
> from src.llm.parser import parse_response
> import json
>
> df = preprocess(load_dataset())
> prefs = parse_preferences({'location': 'Bangalore', 'budget': 'medium', 'cuisine': 'Any', 'min_rating': 4.0})
> result = get_candidates(df, prefs)
> prompt = build_prompt(prefs, result['candidates'])
> raw = call_llm(SYSTEM_PROMPT, prompt)
> recs = parse_response(raw, result['candidates'])
> print(json.dumps(recs['recommendations'][:2], indent=2))
> "
> ```

---

## Tasks

### 3.1 — Prompt Templates (`src/prompt/templates.py`)

**What it does:** Stores all prompt text as module-level string constants. No logic — only text. All template slots use `{placeholder}` syntax for `.format()` substitution in the builder.

**System prompt (static — set once per session):**
```python
SYSTEM_PROMPT = """
You are an expert restaurant recommendation assistant with deep knowledge of dining preferences.

You will receive:
1. A user's dining preferences (location, budget, cuisine, rating threshold, additional notes)
2. A list of restaurant candidates filtered from a real dataset

Your task:
- Reason step-by-step about how well each candidate fits the user's stated preferences
- Consider all preference dimensions: location fit, budget alignment, cuisine match, rating quality, and free-text notes
- Rank the candidates from best to worst overall fit
- Select the top 3 to 5 restaurants only

Return ONLY a valid JSON object — no prose, no markdown, no code fences — matching this exact schema:

{
  "recommendations": [
    {
      "rank": <integer starting at 1>,
      "name": <exact restaurant name from the candidates list>,
      "explanation": "<2–3 sentences explaining why this restaurant fits the user's preferences>",
      "trade_offs": "<1 sentence about any drawbacks, or empty string if none>"
    }
  ],
  "summary": "<1–2 sentence overall summary of the top recommendations>"
}

Important rules:
- Only recommend restaurants that appear in the candidates list
- Do not invent restaurants or details not present in the data
- If fewer than 3 candidates are a good fit, return only the good ones
"""
```

**User prompt template (dynamic — filled per request):**
```python
USER_PROMPT_TEMPLATE = """
## User Preferences
- Location: {location}
- Budget: {budget_tier} (₹{budget_min}–₹{budget_max} for two people)
- Cuisine: {cuisine}
- Minimum Rating: {min_rating} / 5.0
- Additional notes: {extra_prefs}

## Restaurant Candidates
{candidates_table}

## Your Task
Reason step-by-step about each candidate above, then return the top 3–5 as a JSON object matching the schema in your instructions.
"""
```

- [ ] Write `SYSTEM_PROMPT` constant
- [ ] Write `USER_PROMPT_TEMPLATE` constant
- [ ] Add a module docstring explaining: "No logic here — edit text only"

---

### 3.2 — Prompt Builder (`src/prompt/builder.py`)

**What it does:** Fills `USER_PROMPT_TEMPLATE` with real data. Formats candidates as a markdown table for token efficiency.

**Interface:**
```python
def build_prompt(prefs: UserPreferences, candidates: list[dict]) -> str:
    """
    Assemble the user prompt string.
    Candidates formatted as a markdown table inside the prompt.
    Returns the filled prompt string ready to send to the LLM.
    """
```

**Candidate table columns** (include these, in this order):

| Column header | Source field |
|---|---|
| `#` | Row index (1, 2, 3…) |
| `Name` | `name` |
| `Location` | `location` |
| `Cuisines` | `cuisines` joined with `, ` |
| `Rating` | `rating` |
| `Votes` | `votes` |
| `Cost for 2` | `cost_for_two` with `₹` prefix |
| `Type` | `restaurant_type` |
| `Delivery` | `has_online_delivery` as `Yes`/`No` |
| `Booking` | `has_table_booking` as `Yes`/`No` |

**Implementation:**
- [ ] Implement `_format_candidates_table(candidates: list[dict]) -> str` as a private helper that returns a markdown table string
- [ ] Implement `build_prompt()` using `USER_PROMPT_TEMPLATE.format(...)` with all slots filled
- [ ] Truncate `candidates` to `int(os.getenv("MAX_CANDIDATES", 15))` before building table
- [ ] Handle empty `extra_prefs` gracefully (replace with `"None specified"`)

---

### 3.3 — LLM Client (`src/llm/client.py`)

**What it does:** Abstracts over the Groq SDK. Accepts system + user prompts, returns raw response text. Handles retries and timeouts.

**Interface:**
```python
def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call the configured LLM provider with the given prompts.
    Returns raw response text (expected to be JSON).
    Raises LLMError on unrecoverable failure after retries.
    """

class LLMError(Exception):
    """Raised when the LLM call fails after all retries."""

class LLMTimeoutError(LLMError):
    """Raised when the LLM call exceeds the timeout threshold."""
```

**Groq path:**
```python
# When LLM_PROVIDER == "groq" (default)
import groq as genai

# groq client init(api_key=os.getenv("GROQ_API_KEY"))
model = genai.GenerativeModel(
    model_name="llama-3.1-70b-versatile",
    system_instruction=system_prompt,
    generation_config=genai.types.GenerationConfig(
        temperature=float(os.getenv("LLM_TEMPERATURE", 0.3)),
        max_output_tokens=1200,
    )
)
response = model.generate_content(user_prompt)
return response.text
```


```python
# When LLM_PROVIDER == "openai"
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(
    model="llama-3.1-70b-versatile",
    temperature=float(os.getenv("LLM_TEMPERATURE", 0.3)),
    max_tokens=1200,
    response_format={"type": "json_object"},
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
)
return response.choices[0].message.content
```

**Retry logic:**
- [ ] On `RateLimitError` (or HTTP 429): retry up to 3 times with exponential backoff — wait 2s, then 4s, then 8s
- [ ] Wrap entire call in `signal.alarm(15)` timeout (or `threading.Timer`) — raise `LLMTimeoutError` if exceeded
- [ ] Log each retry attempt with wait time
- [ ] After 3 failed retries: raise `LLMError`

**Implementation steps:**
- [ ] Implement `_call_groq(system_prompt, user_prompt) -> str`
- [ ] Implement `# (removed — single Groq provider)
- [ ] Implement retry wrapper `_with_retry(fn, max_attempts=3) -> str`
- [ ] Implement `call_llm()` dispatching on `LLM_PROVIDER` env var

---

### 3.4 — Response Parser (`src/llm/parser.py`)

**What it does:** Parses the LLM's raw text response into a validated Python dict. Enriches each recommendation with the full restaurant data from the candidates list. Falls back gracefully on parse failure.

**Interface:**
```python
def parse_response(raw_response: str, candidates: list[dict]) -> dict:
    """
    Parse and validate LLM JSON response.
    Enriches recommendations with full candidate data.
    Falls back to rating-sorted candidates on parse failure.

    Returns:
    {
        "recommendations": list[dict],  # Enriched, ranked recs
        "summary": str,
        "ai_ranking": bool              # False if fallback was used
    }
    """
```

**Parsing strategy (attempt in order):**

```
Attempt 1: json.loads(raw_response)
    ↓ fails?
Attempt 2: Extract JSON from code fence
    regex: r'```(?:json)?\s*(\{.*?\})\s*```'  with re.DOTALL
    then json.loads(match.group(1))
    ↓ fails?
Attempt 3: Find first '{' and last '}', try json.loads on that slice
    ↓ fails?
Fallback: Return top-N candidates sorted by rating
    with explanation = "Highly rated match for your filters."
    and ai_ranking = False
```

**Enrichment step** (after successful parse):
- For each `recommendation` in LLM response, look up the matching candidate by `name`
- Merge full candidate fields (rating, cost, location, cuisines, etc.) into the recommendation dict
- If a recommended name doesn't match any candidate (LLM hallucinated): skip it, log a warning

**Schema validation:**
- [ ] Assert `"recommendations"` key exists and is a list
- [ ] Assert `"summary"` key exists and is a string
- [ ] For each recommendation, assert `rank`, `name`, `explanation` keys exist
- [ ] Cap total results at `int(os.getenv("TOP_N_RESULTS", 5))`

**Fallback return format:**
```python
{
    "recommendations": [
        {
            "rank": i + 1,
            "name": candidate["name"],
            "explanation": "Highly rated match for your filters.",
            "trade_offs": "",
            **candidate   # all candidate fields merged in
        }
        for i, candidate in enumerate(candidates[:5])
    ],
    "summary": "AI ranking unavailable — showing top results by rating.",
    "ai_ranking": False
}
```

**Tests (`tests/test_llm_parser.py`):**
- [ ] Test: Valid JSON string → parsed correctly
- [ ] Test: JSON inside ` ```json ... ``` ` code fence → parsed correctly
- [ ] Test: Malformed JSON → fallback triggered, `ai_ranking = False`
- [ ] Test: LLM-hallucinated restaurant name → skipped with warning
- [ ] Test: Result capped at `TOP_N_RESULTS`
- [ ] Test: Enrichment merges all candidate fields correctly

---

### 3.5 — Prompt Builder Test (`tests/test_prompt.py`)

- [ ] Test: All `UserPreferences` fields appear in the built prompt
- [ ] Test: Candidate count in table ≤ `MAX_CANDIDATES`
- [ ] Test: Empty `extra_prefs` renders as `"None specified"` not blank
- [ ] Test: Cuisines list rendered as comma-separated string in table

---

## Files Produced

| File | Purpose |
|---|---|
| `src/prompt/templates.py` | `SYSTEM_PROMPT` and `USER_PROMPT_TEMPLATE` constants |
| `src/prompt/builder.py` | `build_prompt()` — fills template with real data |
| `src/llm/client.py` | `call_llm()` — Groq abstraction with retry |
| `src/llm/parser.py` | `parse_response()` — JSON parsing with fallback |
| `tests/test_prompt.py` | Prompt builder unit tests |
| `tests/test_llm_parser.py` | Response parser unit tests |

---

## Notes & Gotchas

> [!IMPORTANT]
> The system prompt explicitly instructs the LLM to **only recommend restaurants from the candidates list**. This prevents hallucination. Reinforce this in the user prompt too if hallucinations occur during testing.

> [!WARNING]
> Groq's response sometimes wraps JSON in a code fence (` ```json ... ``` `) even when instructed not to. The 3-attempt parse strategy in `parse_response()` handles this — do not remove the code fence extraction step.

> [!TIP]
> Set `LLM_TEMPERATURE=0.0` during development/testing to get fully deterministic LLM output, making test failures reproducible. Switch to `0.3` for production use.

> [!NOTE]
> `llama-3.1-70b-versatile` is recommended for the PoC — it's significantly cheaper and faster than Pro while still producing high-quality ranking and explanation outputs for this use case.
