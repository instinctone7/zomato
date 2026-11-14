"""Single-process Streamlit app: run with `streamlit run app.py`."""
import os
from pathlib import Path

import streamlit as st

from src.data.loader import DEFAULT_ARTIFACT, SCHEMA_VERSION, load_prepared_dataset
from src import service
from src.output.formatter import render_streamlit

st.set_page_config(page_title='Zomato AI — Find your next favourite', page_icon='🍽️', layout='wide')


@st.cache_data(show_spinner=False, max_entries=2)
def load_catalog(artifact_path: str, artifact_version: tuple):
    # Version includes file mtimes/sizes and schema so replacing data invalidates cache.
    data = load_prepared_dataset(Path(artifact_path))
    return data, service.get_options(data), service.get_discovery(data)


def main():
    st.markdown('''<style>
    .block-container {max-width:1160px;padding-top:2.5rem}
    h1 {letter-spacing:-1.8px} h2 {letter-spacing:-.8px}
    [data-testid="stForm"] {background:white;border-radius:16px;padding:1.5rem}
    [data-testid="stMetric"] {background:#fff7f2;border-radius:10px;padding:.7rem}
    </style>''', unsafe_allow_html=True)
    st.markdown('### :red[zomato] · AI')
    st.caption('GOOD FOOD. GREAT PICKS.')
    st.title('Your next favourite is one craving away.')
    st.write('Little cafés. Big celebrations. Find a place that feels just right, with a little help from AI.')
    st.caption('Historical Bangalore restaurant data. Prices, availability, delivery, and booking options may have changed. Ambience suggestions are inferred, not verified.')

    path = DEFAULT_ARTIFACT
    try:
        meta = path.with_name('metadata.json')
        version = (SCHEMA_VERSION, path.stat().st_mtime_ns, path.stat().st_size, meta.stat().st_mtime_ns)
        with st.spinner('Getting the tables ready…'):
            data, options, discovery = load_catalog(str(path), version)
    except (OSError, ValueError, TypeError) as exc:
        st.error('Restaurant data could not be loaded. Rebuild the prepared dataset before starting this app.')
        st.caption('Maintainer: run `python scripts/prepare_dataset.py`, then restart the app.')
        st.stop()

    # Explicitly bridge app-wide secrets to the existing environment-based client.
    # This also works in Streamlit AppTest, which does not export secrets itself.
    try:
        for name in ('GROQ_API_KEY', 'LLM_PROVIDER', 'GROQ_MODEL',
                     'LLM_TEMPERATURE', 'MAX_CANDIDATES', 'TOP_N_RESULTS'):
            if name in st.secrets:
                os.environ[name] = str(st.secrets[name])
    except FileNotFoundError:
        pass
    key_ready = bool(os.getenv('GROQ_API_KEY', '').strip())
    if not key_ready:
        st.info('AI ranking is not configured. You can still browse and search restaurants sorted by rating. Add GROQ_API_KEY in Streamlit Secrets to enable AI.')

    st.subheader('What are you in the mood for?')
    with st.form('restaurant_search'):
        cols = st.columns(4)
        with cols[0]:
            locations = options['locations']
            location = st.selectbox('Location', locations, index=locations.index('Bangalore') if 'Bangalore' in locations else 0, key='location')
        with cols[1]:
            cuisine = st.selectbox('Cuisine', ['Any'] + options['cuisines'], format_func=lambda v: 'All cuisines' if v == 'Any' else v, key='cuisine')
        with cols[2]:
            budget = st.selectbox('Budget for two', ['low', 'medium', 'high'], index=1,
                                  format_func=lambda v: {'low':'Under ₹400', 'medium':'₹400 – ₹1,000', 'high':'Above ₹1,000'}[v], key='budget')
        with cols[3]:
            rating = st.selectbox('Minimum rating', [0.0, 3.0, 3.5, 4.0, 4.5], index=2,
                                  format_func=lambda v: 'Any rating' if v == 0 else f'{v:.1f} and above', key='rating')
        notes = st.text_input('Make it personal (optional)', max_chars=200, key='notes',
                              placeholder='A quiet date night? A relaxed family lunch?')
        submitted = st.form_submit_button('Find my favourites', type='primary', use_container_width=True)

    if submitted:
        try:
            with st.spinner('Finding your favourites…'):
                result = service.recommend(data, {'location':location, 'cuisine':cuisine,
                    'budget':budget, 'min_rating':rating, 'extra_prefs':notes})
            st.session_state['result'] = result
            st.session_state['search_label'] = f'{location} · {cuisine} · {budget} budget · {rating:.1f}+ rating'
        except (ValueError, TypeError):
            st.error('Please check your preferences and try again.')
        except Exception:
            # Do not expose secrets or raw provider errors to a visitor.
            st.error('The search could not be completed. Please try again.')

    if 'result' in st.session_state:
        st.caption('Showing results for: ' + st.session_state['search_label'])
        render_streamlit(st.session_state['result'])
    else:
        st.subheader('Good places. Great possibilities.')
        st.caption(f'{options["restaurant_count"]:,} restaurant branches to explore. Submit your preferences for a personal shortlist.')
        for offset in range(0, len(discovery), 3):
            columns = st.columns(3)
            for column, restaurant in zip(columns, discovery[offset:offset+3]):
                with column, st.container(border=True):
                    st.subheader(restaurant['name'])
                    st.caption(restaurant.get('location') or restaurant['city'])
                    st.write(' · '.join(restaurant['cuisines']))
                    st.metric('Rating', f'{restaurant["rating"]:.1f} ★')
                    st.write(f'₹{restaurant["cost_for_two"]:,.0f} for two')
    st.divider()
    st.caption('Made for the love of finding good food. Rankings use historical restaurant information and may not reflect current conditions.')


if __name__ == '__main__':
    main()
