"""RAG contract: browser retrieval never supplies trusted source text."""
import pytest
from fastapi.testclient import TestClient
from localdoc import engine
from localdoc.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(engine, 'UPLOADS', tmp_path / 'uploads')
    monkeypatch.setattr(engine, 'DB_PATH', tmp_path / 'db.sqlite3')
    with TestClient(app) as client:
        yield client


def test_import_retrieve_generate_with_verified_sources(client, monkeypatch):
    response = client.post('/api/documents', files={'file': ('fiction.txt', 'Le budget de Novara est de 48275 euros.'.encode())})
    assert response.status_code == 200
    doc_id = response.json()['document']['id']
    chunks = client.get(f'/api/webnn/documents/{doc_id}/chunks').json()['chunks']
    hits = client.post(f'/api/webnn/documents/{doc_id}/lexical', json={'question': 'Quel est le budget de Novara ?'}).json()
    assert hits[0]['id'] == chunks[0]['id']
    def generate(endpoint, payload, timeout=120):
        assert endpoint == '/api/chat'
        assert payload['model'] == 'phi4'
        assert '48275 euros' in payload['messages'][1]['content']
        assert '[S1] PAGE 1' in payload['messages'][1]['content']
        return {'message': {'content': 'Le budget est de 48275 euros [S1].'}}
    monkeypatch.setattr(engine, 'ollama_request', generate)
    result = client.post(f'/api/webnn/documents/{doc_id}/generate', json={
        'question': 'Quel est le budget ?', 'chunk_ids': [hits[0]['id']]})
    assert result.status_code == 200
    assert result.json()['sources'][0]['page'] == 1
    assert result.json()['warning'] is None
    assert result.json()['mode'] == 'rag-webnn-phi4'


def test_reject_passage_from_other_document(client, monkeypatch):
    first = engine.add_document(b'Le document alpha concerne le projet fictif Alpha.', 'alpha.txt')[0]
    other = engine.add_document(b'Le document beta concerne le projet fictif Beta.', 'beta.txt')[0]
    other_chunk = client.get(f'/api/webnn/documents/{other["id"]}/chunks').json()['chunks'][0]['id']
    def unexpected(*args, **kwargs):
        pytest.fail('No model call allowed with foreign source IDs')
    monkeypatch.setattr(engine, 'ollama_request', unexpected)
    result = client.post(f'/api/webnn/documents/{first["id"]}/generate', json={
        'question': 'Quel projet ?', 'chunk_ids': [other_chunk]})
    assert result.status_code == 400
    assert client.post(f'/api/webnn/documents/{first["id"]}/generate', json={
        'question': 'Quel projet ?', 'chunk_ids': []}).status_code == 422


def test_only_webnn_routes_are_exposed(client):
    routes = {route.path for route in app.routes}
    assert '/api/webnn/documents/{doc_id}/generate' in routes
    assert '/api/documents/{doc_id}/ask' not in routes
    assert '/api/documents/{doc_id}/embed' not in routes
    assert client.get('/diagnostic.html').status_code == 404
