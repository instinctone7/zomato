"""UI regression tests execute the real Streamlit entry point without network."""
from pathlib import Path

from streamlit.testing.v1 import AppTest
import streamlit as st

from src import service
from src.llm.client import LLMError

APP = Path(__file__).resolve().parents[1] / 'app.py'


def new_app():
    return AppTest.from_file(str(APP), default_timeout=15)


def test_discovery_without_api_key(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    app = new_app().run()
    assert not app.exception
    assert len(app.selectbox) == 4
    assert any('AI ranking is not configured' in item.value for item in app.info)
    assert any('Good places' in item.value for item in app.subheader)


def test_submit_and_rerun_do_not_repeat_provider_calls(monkeypatch):
    calls = []
    def rank(system, prompt):
        calls.append(prompt)
        return '{"recommendations":[{"rank":1,"name":"Smoor","explanation":"A cafe within your budget."}],"summary":"Your cafe shortlist."}'
    monkeypatch.setattr(service, 'call_llm', rank)
    app = new_app().run()
    app.selectbox(key='location').set_value('Indiranagar')
    app.selectbox(key='cuisine').set_value('Cafe')
    app.selectbox(key='rating').set_value(4.0)
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['result']['ai_ranking'] is True
    assert len(calls) == 1
    app.run()
    assert len(calls) == 1
    assert app.session_state['result']['summary'] == 'Your cafe shortlist.'
    other = new_app().run()
    assert 'result' not in other.session_state
    assert len(calls) == 1


def test_provider_timeout_and_invalid_output_are_labeled(monkeypatch):
    def fail(*_):
        raise LLMError('Unavailable')
    monkeypatch.setattr(service, 'call_llm', fail)
    app = new_app().run()
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['result']['ai_ranking'] is False
    assert any('temporarily unavailable' in item.value for item in app.info)
    monkeypatch.setattr(service, 'call_llm', lambda *_: 'not valid json')
    app.button[0].click().run()
    assert not app.exception
    assert any('could not rank' in item.value for item in app.info)


def test_relaxed_filters_are_visible(monkeypatch):
    monkeypatch.setattr(service, 'call_llm', lambda *_: '{"recommendations":[]}')
    app = new_app().run()
    app.selectbox(key='cuisine').set_value('Bbq')
    app.selectbox(key='rating').set_value(4.5)
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state['result']['fallback_triggered']
    assert any('Relaxed filters' in item.value for item in app.warning)


def test_missing_artifact_has_a_useful_message(monkeypatch):
    import src.data.loader as loader
    monkeypatch.setattr(loader, 'DEFAULT_ARTIFACT', APP.parent / 'data' / 'missing.parquet')
    app = new_app().run()
    assert not app.exception
    assert any('Restaurant data could not be loaded' in item.value for item in app.error)
    assert not app.button


def test_cloud_secrets_enable_ai_configuration(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', '')
    app = new_app()
    app.secrets['GROQ_API_KEY'] = 'test-config-only-not-a-real-key'
    app.run()
    assert not app.exception
    assert not any('AI ranking is not configured' in item.value for item in app.info)
