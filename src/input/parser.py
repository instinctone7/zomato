"""User input parsing and validation for the Zomato AI Recommender."""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# City alias map — maps common abbreviations / alternate names → canonical name
# ---------------------------------------------------------------------------
CITY_ALIASES: dict[str, str] = {
    # Bangalore
    "blr": "Bangalore",
    "bengaluru": "Bangalore",
    "bangalore": "Bangalore",
    # Delhi
    "del": "Delhi",
    "new delhi": "Delhi",
    "ncr": "Delhi",
    "delhi": "Delhi",
    # Mumbai
    "mum": "Mumbai",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    # Hyderabad
    "hyd": "Hyderabad",
    "hyderabad": "Hyderabad",
    # Chennai
    "chn": "Chennai",
    "madras": "Chennai",
    "chennai": "Chennai",
    # Kolkata
    "kol": "Kolkata",
    "calcutta": "Kolkata",
    "kolkata": "Kolkata",
    # Pune
    "pun": "Pune",
    "pune": "Pune",
    # Gurugram / Gurgaon
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    # Ahmedabad
    "amd": "Ahmedabad",
    "ahmedabad": "Ahmedabad",
    # Jaipur
    "jaipur": "Jaipur",
    # Noida
    "noida": "Noida",
    # Faridabad
    "faridabad": "Faridabad",
    # Ghaziabad
    "ghaziabad": "Ghaziabad",
    # Agra
    "agra": "Agra",
    # Lucknow
    "lucknow": "Lucknow",
    # Indore
    "indore": "Indore",
    # Bhopal
    "bhopal": "Bhopal",
    # Chandigarh
    "chd": "Chandigarh",
    "chandigarh": "Chandigarh",
    # Coimbatore
    "coimbatore": "Coimbatore",
    # Vadodara
    "vadodara": "Vadodara",
    # Nashik
    "nashik": "Nashik",
    # Patna
    "patna": "Patna",
    # Surat
    "surat": "Surat",
    # Visakhapatnam
    "vizag": "Visakhapatnam",
    "visakhapatnam": "Visakhapatnam",
}

# ---------------------------------------------------------------------------
# Budget tier → cost range mapping (₹ for two people)
# ---------------------------------------------------------------------------
BUDGET_RANGES: dict[str, tuple[int, int]] = {
    "low":    (0, 400),
    "medium": (400, 1000),
    "high":   (1000, 999_999),
}

VALID_BUDGETS = set(BUDGET_RANGES.keys())

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CUISINE = "Any"
DEFAULT_MIN_RATING = 3.0
DEFAULT_EXTRA_PREFS = ""
MAX_EXTRA_PREFS_LEN = 200


# ---------------------------------------------------------------------------
# UserPreferences dataclass
# ---------------------------------------------------------------------------

@dataclass
class UserPreferences:
    """
    Validated, normalized representation of a user's restaurant preferences.

    Attributes:
        location:     Canonical city name (e.g. "Bangalore").
        budget_tier:  One of "low", "medium", "high".
        budget_range: (min_cost, max_cost) in ₹ for two people.
        cuisine:      Cuisine preference or "Any".
        min_rating:   Minimum acceptable Zomato rating (0.0–5.0).
        extra_prefs:  Free-text additional preferences (max 200 chars).
        raw_query:    Human-readable summary of all preferences for LLM context.
    """
    location: str
    budget_tier: str
    budget_range: tuple[int, int]
    cuisine: str
    min_rating: float
    extra_prefs: str
    raw_query: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_city(raw_city: str) -> str:
    """
    Normalize a raw city string to its canonical title-cased name.

    Looks up the lowercased, stripped input in CITY_ALIASES first.
    If not found in the alias map, falls back to str.title() normalization.

    Args:
        raw_city: Raw city string from user input (any case, may have spaces).

    Returns:
        Canonical city name (title-cased).
    """
    cleaned = raw_city.strip().lower()
    if cleaned in CITY_ALIASES:
        return CITY_ALIASES[cleaned]
    # Not in alias map — title-case and return as-is; filter may still match.
    return raw_city.strip().title()


def parse_preferences(raw: dict) -> UserPreferences:
    """
    Validate and normalize a raw user input dictionary into a UserPreferences object.

    Args:
        raw: Dictionary with keys: location, budget, cuisine (opt),
             min_rating (opt), extra_prefs (opt).

    Returns:
        UserPreferences: Validated, normalized preferences.

    Raises:
        ValueError: If location is empty or budget is invalid.
        TypeError:  If min_rating cannot be coerced to a float.
    """
    # ── Location (required) ──────────────────────────────────────────────────
    raw_location = raw.get("location", "")
    if not isinstance(raw_location, str) or not raw_location.strip():
        raise ValueError(
            "Location is required and cannot be empty. "
            "Please provide a city name (e.g. 'Bangalore', 'Delhi')."
        )
    location = normalize_city(raw_location)

    # ── Budget (required) ────────────────────────────────────────────────────
    raw_budget = raw.get("budget", "")
    if not isinstance(raw_budget, str) or not raw_budget.strip():
        raise ValueError(
            "Budget is required. Must be one of: low, medium, high."
        )
    budget_tier = raw_budget.strip().lower()
    if budget_tier not in VALID_BUDGETS:
        raise ValueError(
            f"Invalid budget '{raw_budget}'. Must be one of: "
            f"{', '.join(sorted(VALID_BUDGETS))}."
        )
    budget_range = BUDGET_RANGES[budget_tier]

    # ── Cuisine (optional, default "Any") ────────────────────────────────────
    raw_cuisine = raw.get("cuisine", DEFAULT_CUISINE) or DEFAULT_CUISINE
    cuisine = raw_cuisine.strip() or DEFAULT_CUISINE

    # ── Min rating (optional, default 3.0, clamped 0.0–5.0) ─────────────────
    raw_rating = raw.get("min_rating", DEFAULT_MIN_RATING)
    try:
        min_rating = float(raw_rating)
    except (TypeError, ValueError):
        raise TypeError(
            f"min_rating must be a number between 0.0 and 5.0, got: {raw_rating!r}"
        )
    if min_rating > 5.0:
        print(f"   ⚠️  min_rating {min_rating} clamped to 5.0")
        min_rating = 5.0
    elif min_rating < 0.0:
        print(f"   ⚠️  min_rating {min_rating} clamped to 0.0")
        min_rating = 0.0

    # ── Extra prefs (optional, truncated to 200 chars) ───────────────────────
    raw_extra = raw.get("extra_prefs", DEFAULT_EXTRA_PREFS) or DEFAULT_EXTRA_PREFS
    extra_prefs = str(raw_extra).strip()[:MAX_EXTRA_PREFS_LEN]

    # ── Compose raw_query for LLM context ────────────────────────────────────
    extra_part = f" {extra_prefs}" if extra_prefs else ""
    raw_query = (
        f"{location}, {budget_tier} budget, {cuisine} cuisine, "
        f"rating ≥ {min_rating}.{extra_part}"
    )

    return UserPreferences(
        location=location,
        budget_tier=budget_tier,
        budget_range=budget_range,
        cuisine=cuisine,
        min_rating=min_rating,
        extra_prefs=extra_prefs,
        raw_query=raw_query,
    )
