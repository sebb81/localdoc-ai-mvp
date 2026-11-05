"""Unit tests use generated, non-sensitive PDFs. No Ollama/network required."""
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
        assert payload['think'] is False
        assert 'EXTRAITS' in payload['messages'][1]['content']
        return {'message': {'content': 'La migration IPv6 est progressive [S1].'}}
    monkeypatch.setattr(engine, 'ollama_request', fake)
    result = engine.answer_from_sources('Quelle migration est prévue ?',
        [{'source_id': 'S1', 'page': 1, 'text': 'La migration IPv6 est progressive.'}], 'rag-webnn-phi4')
    assert called == ['/api/chat']
    assert result['warning'] is None
    assert result['sources'][0]['source_id'] == 'S1'


def test_empty_generation_keeps_sources_and_explains_failure(monkeypatch):
    doc, _ = engine.add_document(b'Le projet utilise le langage Python.', 'projet.txt')
    monkeypatch.setattr(engine, 'ollama_request', lambda *a, **kw: {
        'message': {'content': '', 'thinking': 'internal'}, 'done_reason': 'length'})
    result = engine.answer_from_sources('Quel langage utilise le projet ?', [{'source_id': 'S1', 'page': 1, 'text': 'Le projet utilise le langage Python.'}], 'rag-webnn-phi4')
    assert result['answer']
    assert 'internal' not in result['answer']
    assert 'jetons' in result['warning']
    assert result['sources']




def test_missing_ollama_runtime_has_actionable_error(monkeypatch):
    from urllib.error import HTTPError
    def fail(*args, **kwargs):
        raise HTTPError('http://127.0.0.1:11434/api/chat', 500, 'Internal Server Error',
                        {}, io.BytesIO(b'{"error":"llama-server binary not found"}'))
    monkeypatch.setattr(engine, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='Installation Ollama incomplète'):
        engine.ollama_request('/api/chat', {'model': 'phi4'})




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
