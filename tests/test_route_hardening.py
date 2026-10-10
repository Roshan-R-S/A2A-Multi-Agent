"""Offline route, missing-resource and local API security checks."""
import pytest
from fastapi.testclient import TestClient
from memory.store import ConversationMemory
from web_api.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / 'routes.sqlite3')
    with TestClient(app) as web:
        yield web, tmp_path / 'routes.sqlite3'


@pytest.mark.parametrize('path', ['/api/not-a-real-route', '/api/private/guess', '/api/conversations/x/y'])
def test_unknown_api_path_is_real_404(client, path):
    web, _ = client
    response = web.get(path)
    assert response.status_code == 404
    assert response.headers['cache-control'] == 'no-store'


def test_wrong_http_method_is_405(client):
    web, _ = client
    assert web.post('/api/health').status_code == 405


def test_missing_conversation_is_404_and_saved_conversation_is_found(client):
    web, database = client
    assert web.get('/api/conversations/does_not_exist').status_code == 404
    ConversationMemory(database).add_exchange('saved', 'Hello', 'Hi')
    response = web.get('/api/conversations/saved')
    assert response.status_code == 200
    assert [entry['role'] for entry in response.json()] == ['user', 'assistant']
    assert web.delete('/api/conversations/saved').status_code == 200
    assert web.get('/api/conversations/saved').status_code == 404


def test_invalid_conversation_id_is_422(client):
    web, _ = client
    assert web.get('/api/conversations/invalid%20name').status_code == 422


@pytest.mark.parametrize('origin', ['https://malicious.example', 'null', 'http://127.0.0.1:5174'])
def test_untrusted_browser_origin_is_rejected(client, origin):
    web, _ = client
    response = web.get('/api/conversations', headers={'origin': origin})
    assert response.status_code == 403
    assert response.headers['cache-control'] == 'no-store'


def test_cross_site_fetch_without_origin_is_rejected(client):
    web, _ = client
    assert web.get('/api/health', headers={'Sec-Fetch-Site':'cross-site'}).status_code == 403


@pytest.mark.parametrize('origin', ['http://127.0.0.1:5173', 'http://localhost:5173'])
def test_expected_dev_origins_are_allowed(client, origin):
    web, _ = client
    assert web.get('/api/health', headers={'origin': origin}).status_code == 200


def test_sensitive_responses_never_cached(client):
    web, _ = client
    response = web.get('/api/conversations')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['referrer-policy'] == 'no-referrer'
    missing = web.get('/api/nope')
    assert missing.headers['cache-control'] == 'no-store'


def test_invalid_host_still_rejected(client):
    web, _ = client
    assert web.get('/api/health', headers={'host': 'outside.example'}).status_code == 400
