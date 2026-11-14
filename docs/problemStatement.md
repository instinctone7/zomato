# Problem Statement: AI-Powered Restaurant Recommendation System

> **Project Codename:** Zomato-1  
> **Domain:** Food-tech / AI-assisted discovery  
> **Status:** Pre-development (planning phase)

---

## 1. Background & Motivation

Restaurant discovery is a daily challenge for millions of users. Existing platforms like Zomato and Swiggy surface restaurants using rigid, filter-based search — but they fall short when a user has nuanced or multi-dimensional preferences (e.g., *"a mid-budget South Indian place near me that is good for a family lunch and not too spicy"*). Traditional keyword/filter systems cannot reason across those dimensions simultaneously.

Large Language Models (LLMs) have demonstrated strong capabilities in natural language understanding, reasoning, and explanation generation. By combining structured restaurant data with LLM reasoning, we can build a recommendation engine that:

- Understands **free-form, conversational user preferences**
- **Reasons and ranks** candidates instead of just filtering them
- **Explains** each recommendation in plain language, building user trust

This project is a proof-of-concept (PoC) for such a system, inspired by the Zomato use case and built with a real-world restaurant dataset.

---

## 2. Problem We Are Solving

### 2.1 Core Problem

> **Users cannot easily find the right restaurant when their preferences are complex, contextual, or hard to express as simple filters.**

Existing keyword/filter-based discovery:
- Cannot handle implicit preferences (e.g., "a quiet place for a business dinner")
- Cannot reason across multiple constraints simultaneously
- Gives no explanation for why a restaurant was surfaced
- Treats all results equally — no intelligent ranking

### 2.2 Target Users

| User Persona | Pain Point |
|---|---|
| Casual diner | Overwhelmed by too many choices, no personalization |
| Traveller in a new city | No local context, doesn't know what areas/cuisines to trust |
| Family outing planner | Needs to satisfy multiple people's constraints at once |
| Budget-conscious professional | Wants value-for-money, balanced against quality |

---

## 3. Project Objective

Design and implement an **AI-powered restaurant recommendation service** that:

1. **Ingests** a real-world restaurant dataset (Zomato data from Hugging Face)
2. **Accepts** natural language or structured user preferences
3. **Filters and prepares** candidate restaurants from the dataset
4. **Leverages an LLM** to rank candidates and generate personalized, human-readable explanations
5. **Presents** clear, actionable top recommendations to the user

---

## 4. Dataset

**Source:** [Zomato Restaurant Recommendation Dataset — Hugging Face](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)

### Key Fields

| Field | Description |
|---|---|
| `name` | Restaurant name |
| `location` / `city` | Geographic location (city, neighborhood) |
| `cuisines` | Comma-separated list of cuisine types |
| `average_cost_for_two` | Estimated cost for two people |
| `aggregate_rating` | Zomato user rating (0–5) |
| `votes` | Number of user votes (popularity signal) |
| `has_online_delivery` | Whether online delivery is available |
| `has_table_booking` | Whether table booking is available |
| `restaurant_type` | Type (Casual Dining, Café, Quick Bites, etc.) |

### Data Preprocessing Steps

- Remove rows with missing critical fields (name, location, rating)
- Normalize cost buckets: **low** (< ₹400), **medium** (₹400–₹1000), **high** (> ₹1000)
- Lowercase and deduplicate cuisine tags
- Filter out restaurants with very low vote counts (< 10) for quality signal

---

## 5. System Architecture & Workflow

```
User Input (preferences)
        │
        ▼
  ┌─────────────────────┐
  │  Input Parser        │  — Normalize location, budget, cuisine, rating
  └────────┬────────────┘
           │
           ▼
  ┌─────────────────────┐
  │  Data Filter Layer   │  — Query dataset: match location, budget, cuisine,
  │  (Pandas / SQL)      │    minimum rating → candidate list (top ~10–20)
  └────────┬────────────┘
           │
           ▼
  ┌─────────────────────┐
  │  Prompt Builder      │  — Construct structured LLM prompt with candidate
  │                      │    data + user preferences
  └────────┬────────────┘
           │
           ▼
  ┌─────────────────────┐
  │  LLM Reasoning Layer │  — Rank candidates, explain fit, flag trade-offs
  │  (Gemini / OpenAI)   │
  └────────┬────────────┘
           │
           ▼
  ┌─────────────────────┐
  │  Output Formatter    │  — Present top 3–5 recommendations with
  │                      │    name, cuisine, rating, cost, AI explanation
  └─────────────────────┘
```

---

## 6. User Input Specification

The system collects the following user preferences:

| Preference | Type | Example |
|---|---|---|
| Location / City | String | `"Bangalore"`, `"Delhi"` |
| Budget | Enum | `low` / `medium` / `high` |
| Cuisine | String (optional) | `"Italian"`, `"Chinese"`, `"Any"` |
| Minimum rating | Float (optional) | `3.5`, `4.0` |
| Free-text preference | String (optional) | `"family-friendly"`, `"quiet ambiance"`, `"good for dates"` |

---

## 7. LLM Integration

### Role of the LLM

The LLM is **not** doing data retrieval. It receives a pre-filtered shortlist of restaurants and is asked to:

1. **Rank** the candidates by fit to the user's preferences
2. **Explain** why each top pick is a good match
3. **Flag trade-offs** (e.g., "slightly over budget but highly rated")
4. Optionally **summarize** the recommendation in one sentence

### Prompt Design Principles

- Provide structured candidate data in a consistent format (JSON or markdown table)
- Clearly state user preferences in the prompt
- Ask the LLM to reason step-by-step before giving the final ranking
- Constrain output format for easy parsing (e.g., numbered list with fixed fields)

---

## 8. Expected Output Format

For each recommendation:

```
🍽️  #1 — Truffles (Casual Dining)
   📍 Koramangala, Bangalore
   🍕 Cuisine: American, Continental
   ⭐ Rating: 4.5 / 5  (2,300 votes)
   💰 Cost for two: ~₹600 (Medium)
   🤖 Why: Matches your budget and location. Highly rated for its relaxed
          ambiance — excellent for a family lunch. Known for burgers and
          continental options the whole family will enjoy.
```

---

## 9. Technical Stack (Proposed)

| Layer | Technology |
|---|---|
| Data handling | Python, Pandas, Hugging Face `datasets` |
| LLM | Groq API (llama-3.1-70b-versatile) |
| Interface | CLI (PoC) → Streamlit/Gradio UI (stretch goal) |
| Dataset source | Hugging Face Hub |
| Configuration | `.env` for API keys |

---

## 10. Success Criteria

| Criterion | Target |
|---|---|
| Data loaded and filtered correctly | 100% of valid rows processable |
| Response latency | < 10 seconds end-to-end |
| Recommendation relevance | LLM picks match user filters in ≥ 90% of test cases |
| Explanation quality | Each recommendation has a human-readable, non-generic reason |
| Edge case handling | Graceful fallback when no restaurants match filters |

---

## 11. Out of Scope (for PoC)

- Real-time restaurant data or live APIs
- User accounts / saved preferences
- Map integration or geospatial distance calculation
- Review sentiment analysis
- Mobile/native app

---

## 12. Future Enhancements

- **RAG-based retrieval** — embed restaurant descriptions and retrieve by semantic similarity
- **Conversational interface** — multi-turn dialogue to refine preferences
- **Live data integration** — connect to Zomato/Swiggy public APIs
- **Personalization** — learn from past user choices
- **Multi-modal** — include restaurant photos in the prompt context
