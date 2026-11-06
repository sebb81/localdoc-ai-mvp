"""Unit tests use generated, non-sensitive PDFs. No llama.cpp/network required."""
import io

import pytest
from pypdf import PdfWriter

from localdoc import engine


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(engine, 'UPLOADS', tmp_path / 'uploads')
    monkeypatch.setattr(engine, 'DB_PATH', tmp_path / 'test.sqlite3')
    engine.initialize()


def sample_pdf():
    # PDF file with verifiable author metadata, without needing OCR or a model.
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_metadata({'/Author': 'Alice Martin', '/Title': 'Document de test'})
    memory = io.BytesIO()
    writer.write(memory)
    return memory.getvalue()


def test_metadata_author_does_not_need_llm():
    # Metadata-only PDF is intentionally rejected (no text), so use text document
    # to test retrieval separately and direct PDF extraction below.
    pages, title, author, origin, missing = engine.read_document(sample_pdf(), 'test.pdf')
    assert len(pages) == 1
    assert author == 'Alice Martin'
    assert title == 'Document de test'
    assert origin == 'metadata'
    assert missing == 1


def test_text_upload_lexical_search_and_deletion():
    raw = ('Le rapport examine la cybersécurité des transactions et ses risques. ' * 24).encode()
    doc, duplicate = engine.add_document(raw, 'audit.txt')
    assert not duplicate
    hits = engine.lexical_search(doc['id'], 'Quels risques de cybersécurité ?', count=5)
    assert hits
    assert hits[0]['page'] == 1
    assert 'cybersécurité' in hits[0]['content']
    assert engine.add_document(raw, 'copie.txt')[1]
    engine.delete_document(doc['id'])
    assert not engine.list_documents()
    with pytest.raises(KeyError):
        engine.get_document(doc['id'])




def test_reject_unsupported_and_empty():
    with pytest.raises(ValueError):
        engine.add_document(b'test', 'image.png')
    with pytest.raises(ValueError):
        engine.add_document(b'    ', 'vide.txt')


def test_citation_and_local_model_request(monkeypatch):
    doc, _ = engine.add_document(('La stratégie prévoit une migration progressive vers IPv6. ' * 20).encode(), 'plan.txt')
    called = []
    def fake(endpoint, payload, timeout=120):
        called.append(endpoint)
        assert payload['model'] == engine.CHAT_MODEL
        assert payload['max_tokens'] == 480
        assert 'options' not in payload
        assert 'EXTRAITS' in payload['messages'][1]['content']
        return {'choices': [{'message': {'content': 'La migration IPv6 est progressive [S1].'}}], 'usage': {'prompt_tokens': 90, 'completion_tokens': 12}, 'timings': {'prompt_ms': 250, 'predicted_ms': 500}}
    monkeypatch.setattr(engine, 'llama_request', fake)
    result = engine.answer_from_sources('Quelle migration est prévue ?',
        [{'source_id': 'S1', 'page': 1, 'text': 'La migration IPv6 est progressive.'}], 'rag-webnn-phi4')
    assert called == ['/v1/chat/completions']
    assert result['warning'] is None
    assert result['generation_stats']['prompt_tokens'] == 90
    assert result['generation_stats']['generation_seconds'] == 0.5
    assert result['sources'][0]['source_id'] == 'S1'


def test_empty_generation_keeps_sources_and_explains_failure(monkeypatch):
    doc, _ = engine.add_document(b'Le projet utilise le langage Python.', 'projet.txt')
    monkeypatch.setattr(engine, 'llama_request', lambda *a, **kw: {
        'choices': [{'message': {'content': '', 'reasoning_content': 'internal'}, 'finish_reason': 'length'}]})
    result = engine.answer_from_sources('Quel langage utilise le projet ?', [{'source_id': 'S1', 'page': 1, 'text': 'Le projet utilise le langage Python.'}], 'rag-webnn-phi4')
    assert result['answer']
    assert 'internal' not in result['answer']
    assert 'jetons' in result['warning']
    assert result['sources']




def test_llama_error_and_connection_failure(monkeypatch):
    from urllib.error import HTTPError, URLError
    def fail(*args, **kwargs):
        raise HTTPError('http://127.0.0.1:8081/v1/chat/completions', 503, 'Unavailable',
                        {}, io.BytesIO(b'{"error":{"message":"model is loading"}}'))
    monkeypatch.setattr(engine, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='model is loading'):
        engine.llama_request('/v1/chat/completions', {})
    def offline(*args, **kwargs):
        raise URLError('connection refused')
    monkeypatch.setattr(engine, 'urlopen', offline)
    with pytest.raises(RuntimeError, match='demarrer-webnn.bat'):
        engine.llama_request('/v1/chat/completions', {})


def test_llama_http_contract(monkeypatch):
    import json
    from contextlib import contextmanager

    @contextmanager
    def respond(request, timeout):
        assert request.full_url == engine.LLAMA_URL + '/v1/chat/completions'
        assert request.get_method() == 'POST'
        assert request.get_header('Content-type') == 'application/json'
        assert json.loads(request.data)['messages'][0]['content'] == 'Question française'
        assert timeout == 240
        yield io.BytesIO(b'{"choices":[{"message":{"content":"OK [S1]"}}]}')

    monkeypatch.setattr(engine, 'urlopen', respond)
    result = engine.llama_request('/v1/chat/completions', {
        'messages': [{'role': 'user', 'content': 'Question française'}]})
    assert result['choices'][0]['message']['content'] == 'OK [S1]'


def test_complete_pdf_to_retrieved_page():
    reportlab = pytest.importorskip('reportlab')
    from reportlab.pdfgen import canvas
    from fastapi.testclient import TestClient
    from localdoc.main import app
    memory = io.BytesIO()
    c = canvas.Canvas(memory, pagesize=(595, 842))
    c.setAuthor('Paul Bernard')
    c.setTitle('Rapport interne de synthèse')
    for i in range(1, 9):
        c.drawString(50, 750, f'Chapitre {i} du rapport interne.')
        if i == 7:
            c.drawString(50, 720, 'Le code projet est ZEPHYR-2026 et concerne la fiabilite du controle.')
        else:
            c.drawString(50, 720, f'Les informations de ce chapitre concernent la section {i}.')
        c.showPage()
    c.save()
    raw = memory.getvalue()
    with TestClient(app) as client:
        r = client.post('/api/documents', files={'file': ('rapport.pdf', raw, 'application/pdf')})
        assert r.status_code == 200, r.text
        doc = r.json()['document']
        assert doc['num_pages'] == 8
        details = client.get(f"/api/webnn/documents/{doc['id']}/chunks").json()
        assert details['document']['author'] == 'Paul Bernard'
        hits = engine.lexical_search(doc['id'], 'Quel code projet ZEPHYR-2026 ?')
        assert hits[0]['page'] == 7
        original = client.get(f"/api/documents/{doc['id']}/original")
        assert original.status_code == 200
        assert original.content == raw
        assert client.delete(f"/api/documents/{doc['id']}").status_code == 200


def test_large_document_150_pages():
    pytest.importorskip('reportlab')
    from reportlab.pdfgen import canvas
    memory = io.BytesIO()
    c = canvas.Canvas(memory, pagesize=(595, 842))
    for page in range(1, 151):
        c.drawString(42, 730, f'Page {page} : description generale du projet.')
        if page == 149:
            c.drawString(42, 710, 'Le processus ICARUS confie la validation finale au comite de controle.')
        c.showPage()
    c.save()
    doc, duplicate = engine.add_document(memory.getvalue(), '150pages.pdf')
    assert doc['num_pages'] == 150
    hits = engine.lexical_search(doc['id'], 'ICARUS validation controle')
    assert any(h['page'] == 149 for h in hits)
