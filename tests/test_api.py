import pandas as pd
from fastapi.testclient import TestClient
from src.api import app


def client():
    app.state.restaurants = pd.DataFrame([
        dict(name='Sample Cafe', city='Bangalore', location='Indiranagar',
             rating=4.4, votes=200, cuisines=['cafe'], budget_tier='medium',
             cost_for_two=700, restaurant_type='Cafe'),
    ])
    return TestClient(app)


def test_options_and_discovery():
    api = client()
    assert 'Indiranagar' in api.get('/api/options').json()['locations']
    assert api.get('/api/restaurants').json()['restaurants'][0]['name'] == 'Sample Cafe'


def test_recommendation_uses_locality_and_real_candidates(monkeypatch):
    monkeypatch.setattr('src.service.call_llm', lambda *_: '{"recommendations":[{"rank":1,"name":"Sample Cafe","explanation":"A cafe within your budget."}],"summary":"Your pick."}')
    response = client().post('/api/recommendations', json={'location':'Indiranagar','budget':'medium','cuisine':'Cafe'})
    assert response.status_code == 200
    assert response.json()['ai_ranking'] is True
    assert response.json()['recommendations'][0]['cost_for_two'] == 700


def test_llm_failure_returns_labeled_fallback(monkeypatch):
    from src.llm.client import LLMError
    def fail(*_):
        raise LLMError('Unavailable')
    monkeypatch.setattr('src.service.call_llm', fail)
    response = client().post('/api/recommendations', json={})
    assert response.json()['ai_ranking'] is False
    assert response.json()['notice']


def test_empty_results_and_invalid_input():
    api = client()
    assert api.post('/api/recommendations', json={'location':'Unknown'}).json()['recommendations'] == []
    assert api.post('/api/recommendations', json={'min_rating':6}).status_code == 422


def test_relaxed_filters_are_explained_to_llm(monkeypatch):
    prompts = []
    def rank(system, prompt):
        prompts.append(prompt)
        return '{"recommendations":[{"rank":1,"name":"Sample Cafe","explanation":"An alternative cafe."}],"summary":"An alternative."}'
    monkeypatch.setattr('src.service.call_llm', rank)
    result = client().post('/api/recommendations',json={'cuisine':'Italian'}).json()
    assert result['fallback_triggered'] is True
    assert result['ai_ranking'] is True
    assert 'Search adjustment:' in prompts[0]
    assert result['fallback_reason'] in prompts[0]


def test_invalid_ai_response_is_labeled(monkeypatch):
    monkeypatch.setattr('src.service.call_llm', lambda *_: '{"recommendations":[null,5,"bad"]}')
    result = client().post('/api/recommendations',json={}).json()
    assert result['ai_ranking'] is False
    assert result['recommendations']
    assert result['notice']
