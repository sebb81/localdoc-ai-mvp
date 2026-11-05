"""LocalDoc RAG: WebNN retrieval in the browser, Phi-4 generation in local Ollama."""
from __future__ import annotations

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.initialize()
    yield


app = FastAPI(title="LocalDoc RAG WebNN", version="0.2.0", lifespan=lifespan, docs_url=None, redoc_url=None)

@app.get('/api/documents')
def documents():
    return engine.list_documents()


@app.post('/api/documents')
async def upload(file: UploadFile = File(...)):
    try:
        # Reject oversized uploads before reading or parsing the document.
        raw = await file.read(engine.MAX_BYTES + 1)
        doc, duplicate = await asyncio.to_thread(engine.add_document, raw, file.filename or 'document.pdf')
        return {'document': doc, 'duplicate': duplicate}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f'Erreur de lecture du document : {exc}') from exc
    finally:
        await file.close()


@app.get('/api/documents/{doc_id}/original')
def original(doc_id: str):
    try:
        d = engine.get_document(doc_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    path = engine.UPLOADS / (doc_id + d['file_ext'])
    return FileResponse(path, media_type='application/pdf' if d['file_ext']=='.pdf' else 'text/plain',
                        filename=d['name'], content_disposition_type='inline')


@app.delete('/api/documents/{doc_id}')
def delete(doc_id: str):
    try:
        engine.delete_document(doc_id)
        return {'deleted': True}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class Generation(Question):
    chunk_ids: list[int] = Field(min_length=1, max_length=6)


@app.get('/api/health')
def health():
    return {'application': 'localdoc-rag-webnn', 'chat_model': engine.CHAT_MODEL,
            'retrieval': 'browser-webnn', 'generation': 'ollama-local'}


@app.get('/api/webnn/documents/{doc_id}/chunks')
def chunks(doc_id: str):
    try:
        doc = engine.get_document(doc_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    with engine.get_db() as db:
        rows = db.execute('SELECT id,page,content FROM chunks WHERE doc_id=? ORDER BY id', (doc_id,)).fetchall()
    return {'document': doc, 'chunks': [dict(r) for r in rows]}


@app.post('/api/webnn/documents/{doc_id}/lexical')
def lexical(doc_id: str, request: Question):
    try:
        engine.get_document(doc_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return engine.lexical_search(doc_id, request.question)


def generate(doc_id, request):
    # The browser sends IDs only. Source text and pages always come from this document's DB rows.
    engine.get_document(doc_id)
    ids = list(dict.fromkeys(request.chunk_ids))
    with engine.get_db() as db:
        rows = db.execute(f'SELECT id,page,content FROM chunks WHERE doc_id=? AND id IN ({",".join("?" for _ in ids)})',
                          (doc_id, *ids)).fetchall()
    by_id = {r['id']: r for r in rows}
    if any(chunk_id not in by_id for chunk_id in ids):
        raise ValueError('Un passage sélectionné est absent de ce document. Réindexez le document.')
    sources = [{'source_id': f'S{i}', 'page': by_id[chunk_id]['page'], 'text': by_id[chunk_id]['content']}
               for i, chunk_id in enumerate(ids, 1)]
    return engine.answer_from_sources(request.question, sources, 'rag-webnn-phi4')


@app.post('/api/webnn/documents/{doc_id}/generate')
async def answer(doc_id: str, request: Generation):
    try:
        return await asyncio.to_thread(generate, doc_id, request)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


dist = Path(__file__).resolve().parent.parent / 'web' / 'dist'
if dist.exists():
    app.mount('/', StaticFiles(directory=dist, html=True), name='webnn-ui')
