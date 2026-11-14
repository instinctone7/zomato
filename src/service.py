"""Framework-independent restaurant discovery and recommendation service."""
import pandas as pd

from src.filter.engine import get_candidates
from src.input.parser import parse_preferences
from src.llm.client import LLMError, call_llm
from src.llm.parser import parse_response
from src.prompt.builder import build_prompt
from src.prompt.templates import SYSTEM_PROMPT

RESTAURANT_COLUMNS = ['name', 'city', 'location', 'cuisines', 'rating', 'votes',
                      'cost_for_two', 'budget_tier', 'restaurant_type',
                      'has_online_delivery', 'has_table_booking']


def prepare_restaurants(data):
    columns = [column for column in RESTAURANT_COLUMNS if column in data.columns]
    data = data[columns].sort_values('votes', ascending=False)
    keys = ['name', 'location'] if 'location' in data else ['name', 'city']
    return data.drop_duplicates(keys).reset_index(drop=True)


def records(data):
    # Pandas NaNs must become JSON nulls, not nonstandard NaN values.
    return data.astype(object).where(pd.notna(data), None).to_dict('records')


def get_options(data):
    localities = data['location'].dropna().astype(str).str.strip().str.title().unique() if 'location' in data else []
    return {'locations': sorted(set(data['city']) | set(localities)),
            'cuisines': sorted({tag.title() for tags in data['cuisines'] for tag in tags}),
            'restaurant_count': len(data)}


def get_discovery(data):
    data = data.sort_values(['rating', 'votes'], ascending=False)
    # Give the discovery view distinct restaurants, not repeated branches.
    return records(data.drop_duplicates('name').head(6))


def recommend(data, raw_preferences):
    prefs = parse_preferences(raw_preferences)
    mask = data['city'].str.casefold() == prefs.location.casefold()
    if 'location' in data:
        mask = mask | (data['location'].fillna('').str.strip().str.casefold() == prefs.location.casefold())
    local = data[mask].copy()
    local['city'] = prefs.location
    # The LLM identifies candidates by name: give each name one unambiguous branch.
    local = local.sort_values(['rating', 'votes'], ascending=False).drop_duplicates('name')
    filtered = get_candidates(local, prefs)
    candidates = filtered['candidates']
    if not candidates:
        return {'recommendations': [], 'summary': 'No restaurants found here. Try another location.',
                'ai_ranking': False, 'fallback_triggered': False, 'fallback_reason': ''}
    # Sanitize missing scalars before building the prompt and JSON response.
    candidates = records(pd.DataFrame(candidates))
    notice = ''
    try:
        prompt = build_prompt(prefs, candidates)
        if filtered['fallback_triggered']:
            prompt += ('\n\nSearch adjustment: ' + filtered['fallback_reason'] +
                       '\nThese are the closest available alternatives. Rank the best of these '
                       'candidates and explain the mismatches honestly in trade_offs. '
                       'Do not return an empty list solely because the original filters were relaxed.')
        raw = call_llm(SYSTEM_PROMPT, prompt)
    except LLMError:
        raw = ''
        notice = 'AI ranking is temporarily unavailable. Results are sorted by rating.'
    result = parse_response(raw, candidates)
    if not result['ai_ranking'] and not notice:
        notice = 'AI could not rank these matches. Results are sorted by rating.'
    return {**result, 'fallback_triggered': filtered['fallback_triggered'],
            'fallback_reason': filtered['fallback_reason'], 'notice': notice}
