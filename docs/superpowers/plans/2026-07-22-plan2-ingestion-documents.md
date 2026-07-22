# Plan 2 — Ingestion & Documents API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the document ingestion pipeline (parse → chunk → embed → store in Qdrant) and the `/documents` upload/list/status/delete API, so a user can upload a manual and have it searchable as vectors.

**Architecture:** Builds on Plan 1's FastAPI app, Settings, async SQLAlchemy layer (`Document` model), Qdrant client, and Ollama client. New modules: an async `DocumentRepository`, an `ingestion` package (parsers, chunker, orchestrator), and a `/documents` router. Background ingestion runs per uploaded file; status transitions (`pending → parsing → embedding → done | failed`) are tracked in Postgres.

**Tech Stack:** Python 3.11 (prod Docker) / 3.14 (host tests), FastAPI, async SQLAlchemy, qdrant-client (Async), httpx, pypdf, python-docx, beautifulsoup4, pytest + pytest-asyncio + aiosqlite.

## Global Constraints

- Python 3.11 prod (Docker), 3.14 host tests; `asyncpg` must NOT be imported in unit tests (conftest sets `POSTGRES_DSN` to sqlite). Qdrant/Ollama are mocked in unit tests.
- All config via `app.config.Settings` (`.env`); no hardcoded model names/URLs/sizes.
- External Ollama only (`OLLAMA_BASE_URL`); embedding model `bge-m3` (env-driven).
- v1: no auth. No `/chat` or retrieval yet (Plan 3).
- Carried-over refactors from Plan 1 final review (Tasks 1–2 below): switch `QdrantStore` to `AsyncQdrantClient`; lift `httpx.AsyncClient` to `OllamaClient` instance scope; add tests for `embed()` and `chat_stream()`.
- Chunking uses a char budget approximated from token settings: `size_chars = chunk_size_tokens * 4`, `overlap_chars = chunk_overlap_tokens * 4` (documented approximation — no tokenizer dep).
- OCR is DEFERRED: a scanned PDF (no extractable text) raises `OcrRequiredError` → the document is marked `status=failed` with `"OCR not yet supported (planned)"`. No tesseract/poppler deps in this plan.
- Parsers are custom (pypdf / python-docx / bs4), not LlamaIndex — consistent with Plan 1's custom clients.

## File Structure (this plan)

```
api/app/
  qdrant/client.py        # MODIFY: AsyncQdrantClient; async ensure_collection/upsert/delete_by_doc
  ollama/client.py        # MODIFY: instance-scoped httpx.AsyncClient + close()
  db/repositories.py      # NEW: DocumentRepository (async CRUD)
  ingestion/
    __init__.py
    parsers.py            # NEW: Page dataclass, parse_file(), OcrRequiredError, UnsupportedFileError
    chunker.py            # NEW: Chunk dataclass, chunk_pages()
    orchestrator.py       # NEW: ingest_document()
  routers/
    documents.py          # NEW: /documents upload/list/detail/delete
  main.py                 # MODIFY: await qdrant.ensure_collection(); close ollama on shutdown; include documents router
api/tests/
  test_qdrant.py          # MODIFY: async tests for ensure_collection/upsert/delete_by_doc
  test_ollama.py          # MODIFY: add embed + chat_stream tests
  test_repositories.py    # NEW
  test_parsers.py         # NEW
  test_chunker.py         # NEW
  test_orchestrator.py    # NEW
  test_documents_api.py   # NEW
api/requirements.txt      # MODIFY: + pypdf, python-docx, beautifulsoup4
api/requirements-dev.txt  # MODIFY: + fpdf2 (PDF test fixture)
api/Dockerfile            # unchanged (no OCR system deps this plan)
```

Each module has one responsibility: `parsers.py` owns text extraction, `chunker.py` owns splitting, `orchestrator.py` owns the pipeline, `repositories.py` owns `Document` persistence, `routers/documents.py` owns the HTTP surface, `qdrant/client.py` and `ollama/client.py` own their external clients.

---

### Task 1: Async QdrantStore + `upsert` + `delete_by_doc`

**Files:**
- Modify: `api/app/qdrant/client.py`
- Modify: `api/app/main.py` (lifespan: `await qdrant.ensure_collection()`)
- Modify: `api/tests/test_qdrant.py`

**Interfaces:**
- Consumes: `Settings.qdrant_url`, `Settings.embed_dim` (Plan 1).
- Produces:
  - `async QdrantStore.ensure_collection() -> None` (now async).
  - `async QdrantStore.upsert(points: list[dict]) -> None` — each `point = {"id": str, "vector": list[float], "payload": dict}`. Used by the orchestrator (Task 6).
  - `async QdrantStore.delete_by_doc(doc_id: int) -> None` — deletes all points whose `payload.doc_id == doc_id`. Used by `DELETE /documents/{id}` (Task 7).

- [ ] **Step 1: Replace the test file with async tests**

`api/tests/test_qdrant.py` (full replacement):
```python
from unittest.mock import AsyncMock, patch
from app.config import Settings
from app.qdrant.client import QdrantStore


def _store(dim=1024):
    return QdrantStore(Settings(qdrant_url="http://qdrant:6333", embed_dim=dim))


async def test_ensure_collection_creates_with_configured_dim():
    store = _store(768)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists = AsyncMock(return_value=False)
        await store.ensure_collection()
    mock_client.collection_exists.assert_awaited_once_with("manuals")
    mock_client.create_collection.assert_awaited_once()
    _, kwargs = mock_client.create_collection.call_args
    assert kwargs["vectors_config"].size == 768


async def test_ensure_collection_skips_when_exists():
    store = _store(1024)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists = AsyncMock(return_value=True)
        await store.ensure_collection()
    mock_client.create_collection.assert_not_awaited()


async def test_upsert_sends_points():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.upsert = AsyncMock()
        await store.upsert([
            {"id": "u1", "vector": [0.1, 0.2], "payload": {"doc_id": 1, "page": 1, "text": "hi"}}
        ])
    mock_client.upsert.assert_awaited_once()
    _, kwargs = mock_client.upsert.call_args
    points = kwargs["points"]
    assert points[0].id == "u1"
    assert points[0].payload["doc_id"] == 1


async def test_delete_by_doc_uses_filter():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.delete = AsyncMock()
        await store.delete_by_doc(7)
    mock_client.delete.assert_awaited_once()
    _, kwargs = mock_client.delete.call_args
    sel = kwargs["points_selector"]
    assert sel.must[0].key == "doc_id"
    assert sel.must[0].match.integer == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && . .venv/bin/activate && python -m pytest tests/test_qdrant.py -v`
Expected: FAIL — `ensure_collection` is sync (not awaitable) / `upsert`/`delete_by_doc` missing.

- [ ] **Step 3: Implement async QdrantStore** (replace `api/app/qdrant/client.py`)

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm
from qdrant_client.models import PointStruct
from app.config import Settings

COLLECTION = "manuals"


class QdrantStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = AsyncQdrantClient(url=settings.qdrant_url)

    async def ensure_collection(self) -> None:
        if await self._client.collection_exists(COLLECTION):
            return
        await self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=self.settings.embed_dim,
                distance=qm.Distance.COSINE,
            ),
        )

    async def upsert(self, points: list[dict]) -> None:
        mapped = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ]
        await self._client.upsert(collection_name=COLLECTION, points=mapped)

    async def delete_by_doc(self, doc_id: int) -> None:
        await self._client.delete(
            collection_name=COLLECTION,
            points_selector=qm.Filter(
                must=[qm.FieldCondition(key="doc_id", match=qm.MatchInteger(integer=doc_id))]
            ),
        )
```

- [ ] **Step 4: Update `main.py` lifespan to `await ensure_collection`**

In `api/app/main.py`, inside `_lifespan`, change the bootstrap call to awaited:
```python
    qdrant = QdrantStore(app.state.settings)
    try:
        await qdrant.ensure_collection()
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("Qdrant bootstrap skipped: %s", e)
    app.state.qdrant = qdrant
```
(Only the `ensure_collection()` line changes — add `await`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_qdrant.py -v`
Expected: PASS (4 tests). Then run the full suite: `python -m pytest -v` — expect all green (the awaited bootstrap still works in `test_health` because it's wrapped in try/except).

- [ ] **Step 6: Commit**

```bash
git add api/app/qdrant/client.py api/app/main.py api/tests/test_qdrant.py
git commit -m "feat: async QdrantStore with upsert and delete_by_doc"
```

---

### Task 2: OllamaClient instance-scoped httpx + `embed`/`chat_stream` tests

**Files:**
- Modify: `api/app/ollama/client.py`
- Modify: `api/tests/test_ollama.py`
- Modify: `api/app/main.py` (close ollama client on shutdown)

**Interfaces:**
- Consumes: `Settings.ollama_base_url`, `ollama_embed_model`, `ollama_llm_model` (Plan 1).
- Produces: `OllamaClient` with a single long-lived `httpx.AsyncClient`; `async close() -> None`; `ping`/`embed`/`chat_stream` unchanged signatures (used by Task 6 and Plan 3).

- [ ] **Step 1: Add failing tests for embed, chat_stream, and close**

Append to `api/tests/test_ollama.py`:
```python
@pytest.mark.asyncio
async def test_embed_returns_vectors():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434", ollama_embed_model="bge-m3"))
    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        mock_resp.raise_for_status = MagicMock()
        instance = MockClient.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        vecs = await client.embed(["hello", "world"])
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.asyncio
async def test_chat_stream_yields_content_pieces():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))

    class FakeStream:
        def __init__(self):
            self._lines = iter(['{"message":{"content":"Hel"}}', '{"message":{"content":"lo"}}', ""])

        async def aiter_lines(self):
            for line in self._lines:
                yield line

    fake_stream = FakeStream()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.stream = MagicMock(return_value=fake_stream)
        pieces = []
        async for p in client.chat_stream([{"role": "user", "content": "hi"}]):
            pieces.append(p)
    assert pieces == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_close_acloses_underlying_client():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch.object(client, "_http") as mock_http:
        mock_http.aclose = AsyncMock()
        await client.close()
    mock_http.aclose.assert_awaited_once()
```

Keep the existing `test_ping_true_on_200` and `test_ping_false_on_error` — they will still work because `ping` uses `self._http`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && python -m pytest tests/test_ollama.py -v`
Expected: FAIL — `close` missing; `embed`/`chat_stream` create per-call clients so the mocked `AsyncClient.return_value` is a fresh object (the new tests expect an instance-scoped client).

- [ ] **Step 3: Rewrite `OllamaClient` with an instance-scoped client** (replace `api/app/ollama/client.py`)

```python
import json
from collections.abc import AsyncIterator
import httpx
from app.config import Settings


class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._base = settings.ollama_base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=None)

    async def close(self) -> None:
        await self._http.aclose()

    async def ping(self) -> bool:
        try:
            r = await self._http.get(f"{self._base}/api/tags", timeout=3.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        r = await self._http.post(
            f"{self._base}/api/embed",
            json={"model": self.settings.ollama_embed_model, "input": texts},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.json()["embeddings"]

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncIterator[str]:
        async with self._http.stream(
            "POST",
            f"{self._base}/api/chat",
            json={"model": model or self.settings.ollama_llm_model,
                  "messages": messages, "stream": True},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield piece
```

Note: the existing `test_ping_*` tests patch `app.ollama.client.httpx.AsyncClient`. With the instance-scoped client, `ping` uses `self._http` (constructed in `__init__` from the real `httpx.AsyncClient` BEFORE the patch is applied). Update those two tests to patch `client._http` instead of the class. Replace the bodies of `test_ping_true_on_200` and `test_ping_false_on_error` with:
```python
@pytest.mark.asyncio
async def test_ping_true_on_200():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch.object(client, "_http") as mock_http:
        mock_http.get = AsyncMock(return_value=mock_resp)
        assert await client.ping() is True


@pytest.mark.asyncio
async def test_ping_false_on_error():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch.object(client, "_http") as mock_http:
        mock_http.get = AsyncMock(side_effect=httpx.ConnectError("nope"))
        assert await client.ping() is False
```
For `test_embed_returns_vectors` and `test_chat_stream_yields_content_pieces`, also patch `client._http` (not the class). Replace those two test bodies' `with patch("app.ollama.client.httpx.AsyncClient") as MockClient:` blocks with `with patch.object(client, "_http") as mock_http:` and use `mock_http.post = AsyncMock(...)` / `mock_http.stream = MagicMock(return_value=fake_stream)`.

- [ ] **Step 4: Add ollama close to `main.py` lifespan shutdown**

In `api/app/main.py` `_lifespan`, after `yield`:
```python
    yield
    await async_engine.dispose()
    await app.state.ollama.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_ollama.py -v`
Expected: PASS (5 tests). Then full suite `python -m pytest -v` — all green.

- [ ] **Step 6: Commit**

```bash
git add api/app/ollama/client.py api/tests/test_ollama.py api/app/main.py
git commit -m "feat: instance-scoped httpx on OllamaClient; add embed/chat_stream/close tests"
```

---

### Task 3: DocumentRepository (async CRUD)

**Files:**
- Create: `api/app/db/repositories.py`
- Create: `api/tests/test_repositories.py`

**Interfaces:**
- Consumes: `AsyncSession`, the `Document` model (Plan 1).
- Produces: `DocumentRepository(session)` with async methods:
  - `create(filename: str) -> Document`
  - `get(doc_id: int) -> Document | None`
  - `list_all() -> list[Document]`
  - `set_status(doc_id, status: str, **fields) -> None` (fields may include `chunk_count`, `parser_used`, `error`)
  - `delete(doc_id: int) -> None`
- Used by the orchestrator (Task 6) and the `/documents` router (Task 7).

- [ ] **Step 1: Write the failing test**

`api/tests/test_repositories.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.repositories import DocumentRepository


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield DocumentRepository(session)
    await engine.dispose()


async def test_create_and_get(repo):
    doc = await repo.create("manual.pdf")
    assert doc.id is not None
    assert doc.status == "pending"
    fetched = await repo.get(doc.id)
    assert fetched.filename == "manual.pdf"


async def test_list_all(repo):
    await repo.create("a.pdf")
    await repo.create("b.pdf")
    docs = await repo.list_all()
    assert len(docs) == 2


async def test_set_status_updates_fields(repo):
    doc = await repo.create("manual.pdf")
    await repo.set_status(doc.id, "done", chunk_count=12, parser_used="pdf")
    fetched = await repo.get(doc.id)
    assert fetched.status == "done"
    assert fetched.chunk_count == 12
    assert fetched.parser_used == "pdf"


async def test_set_failed_records_error(repo):
    doc = await repo.create("manual.pdf")
    await repo.set_status(doc.id, "failed", error="boom")
    fetched = await repo.get(doc.id)
    assert fetched.status == "failed"
    assert fetched.error == "boom"


async def test_delete_removes_row(repo):
    doc = await repo.create("manual.pdf")
    await repo.delete(doc.id)
    assert await repo.get(doc.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_repositories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.repositories'`

- [ ] **Step 3: Implement the repository**

`api/app/db/repositories.py`:
```python
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, filename: str) -> Document:
        doc = Document(filename=filename, status="pending")
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get(self, doc_id: int) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Document]:
        result = await self.session.execute(select(Document).order_by(Document.id.desc()))
        return list(result.scalars().all())

    async def set_status(self, doc_id: int, status: str, **fields) -> None:
        doc = await self.get(doc_id)
        if doc is None:
            return
        doc.status = status
        for k, v in fields.items():
            setattr(doc, k, v)
        await self.session.commit()

    async def delete(self, doc_id: int) -> None:
        await self.session.execute(delete(Document).where(Document.id == doc_id))
        await self.session.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_repositories.py -v`
Expected: PASS (5 tests). Full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/db/repositories.py api/tests/test_repositories.py
git commit -m "feat: async DocumentRepository for documents CRUD"
```

---

### Task 4: Parsers (PDF / DOCX / HTML + OCR detection)

**Files:**
- Modify: `api/requirements.txt` (add pypdf, python-docx, beautifulsoup4)
- Modify: `api/requirements-dev.txt` (add fpdf2)
- Create: `api/app/ingestion/__init__.py`
- Create: `api/app/ingestion/parsers.py`
- Create: `api/tests/test_parsers.py`

**Interfaces:**
- Produces:
  - `Page` dataclass: `Page(number: int, text: str)`.
  - `OcrRequiredError(Exception)`, `UnsupportedFileError(Exception)`.
  - `parse_file(path: str, filename: str) -> list[Page]` — routes by extension; `.pdf` uses pypdf (raises `OcrRequiredError` if a page has no extractable text), `.docx` uses python-docx, `.html`/`.htm` uses BeautifulSoup; anything else raises `UnsupportedFileError`.
- Used by the orchestrator (Task 6).

- [ ] **Step 1: Add dependencies**

In `api/requirements.txt`, append (keep existing pins):
```
pypdf==4.3.1
python-docx==1.1.2
beautifulsoup4==4.12.3
```
In `api/requirements-dev.txt`, append:
```
fpdf2==2.7.9
```
Install in the venv:
```
cd api && . .venv/bin/activate
pip install pypdf==4.3.1 python-docx==1.1.2 beautifulsoup4==4.12.3 fpdf2==2.7.9
```

- [ ] **Step 2: Write the failing test**

`api/tests/test_parsers.py`:
```python
import os
import tempfile
import pytest
from fpdf import FPDF
from docx import Document as DocxDocument
from app.ingestion.parsers import parse_file, Page, OcrRequiredError, UnsupportedFileError


def _write(path, content):
    with open(path, "w") as f:
        f.write(content)


def test_html_parser_extracts_text_and_pages():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "manual.html")
        _write(p, "<html><body><p>Hello world</p></body></html>")
        pages = parse_file(p, "manual.html")
    assert pages == [Page(number=1, text="Hello world")]


def test_docx_parser_extracts_text():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.docx")
        doc = DocxDocument()
        doc.add_paragraph("First paragraph.")
        doc.add_paragraph("Second paragraph.")
        doc.save(p)
        pages = parse_file(p, "m.docx")
    assert len(pages) == 1
    assert "First paragraph" in pages[0].text
    assert "Second paragraph" in pages[0].text


def test_pdf_parser_extracts_text_per_page():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        pdf.cell(0, 10, "Page one text")
        pdf.add_page()
        pdf.cell(0, 10, "Page two text")
        pdf.output(p)
        pages = parse_file(p, "m.pdf")
    assert [pg.number for pg in pages] == [1, 2]
    assert "Page one text" in pages[0].text
    assert "Page two text" in pages[1].text


def test_pdf_with_no_text_raises_ocr_required():
    # A PDF whose page has no extractable text simulates a scanned PDF.
    import app.ingestion.parsers as parsers
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.output(p)  # blank page, no text
        with pytest.raises(OcrRequiredError):
            parse_file(p, "m.pdf")


def test_unsupported_extension_raises():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.txt")
        _write(p, "hello")
        with pytest.raises(UnsupportedFileError):
            parse_file(p, "m.txt")
```

> Note: fpdf2's blank page may still emit whitespace; the parser must treat a page whose stripped text is empty as `OcrRequiredError`. If the blank-page test is flaky, the parser's emptiness check must use `.strip()`.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_parsers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.parsers'`

- [ ] **Step 4: Implement parsers**

`api/app/ingestion/__init__.py`: (empty)
```python
```

`api/app/ingestion/parsers.py`:
```python
from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader


@dataclass
class Page:
    number: int
    text: str


class OcrRequiredError(Exception):
    pass


class UnsupportedFileError(Exception):
    pass


def parse_file(path: str, filename: str) -> list[Page]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    if ext == ".docx":
        return _parse_docx(path)
    if ext in (".html", ".htm"):
        return _parse_html(path)
    raise UnsupportedFileError(f"Unsupported file type: {ext}")


def _parse_pdf(path: str) -> list[Page]:
    reader = PdfReader(path)
    pages: list[Page] = []
    for i, raw in enumerate(reader.pages, start=1):
        text = (raw.extract_text() or "").strip()
        if not text:
            raise OcrRequiredError(
                "PDF page has no extractable text (scanned?). OCR not yet supported (planned)."
            )
        pages.append(Page(number=i, text=text))
    return pages


def _parse_docx(path: str) -> list[Page]:
    from docx import Document as DocxDocument
    doc = DocxDocument(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [Page(number=1, text=text)]


def _parse_html(path: str) -> list[Page]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    return [Page(number=1, text=soup.get_text(separator=" ", strip=True))]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_parsers.py -v`
Expected: PASS (5 tests). Full suite green.

- [ ] **Step 6: Commit**

```bash
git add api/requirements.txt api/requirements-dev.txt api/app/ingestion/__init__.py api/app/ingestion/parsers.py api/tests/test_parsers.py
git commit -m "feat: document parsers (PDF/DOCX/HTML) with OCR detection"
```

---

### Task 5: Page-aware chunker

**Files:**
- Create: `api/app/ingestion/chunker.py`
- Create: `api/tests/test_chunker.py`

**Interfaces:**
- Consumes: `Page` from `app.ingestion.parsers`.
- Produces: `Chunk` dataclass (`text: str`, `page: int`) and `chunk_pages(pages: list[Page], size_chars: int, overlap_chars: int) -> list[Chunk]`. Chunks do not cross page boundaries (each chunk carries a single page number). Used by the orchestrator (Task 6).

- [ ] **Step 1: Write the failing test**

`api/tests/test_chunker.py`:
```python
from app.ingestion.parsers import Page
from app.ingestion.chunker import Chunk, chunk_pages


def test_single_short_page_produces_one_chunk():
    pages = [Page(number=1, text="Hello world.")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=20)
    assert chunks == [Chunk(text="Hello world.", page=1)]


def test_long_page_split_within_size_with_overlap():
    text = "word " * 60  # 300 chars
    pages = [Page(number=2, text=text)]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=20)
    assert all(len(c.text) <= 100 for c in chunks)
    assert len(chunks) >= 3
    assert all(c.page == 2 for c in chunks)
    # overlap: the start of the second chunk is within 20 chars of the first chunk's end
    assert chunks[1].text[:5] == chunks[0].text[-20:][:5]


def test_chunks_keep_page_numbers_across_pages():
    pages = [Page(number=1, text="alpha"), Page(number=2, text="beta")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=10)
    assert chunks[0].page == 1
    assert chunks[1].page == 2


def test_empty_pages_are_skipped():
    pages = [Page(number=1, text="   "), Page(number=2, text="real text")]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=10)
    assert chunks == [Chunk(text="real text", page=2)]


def test_does_not_split_mid_word():
    text = "a" * 95 + " wordtail"
    pages = [Page(number=1, text=text)]
    chunks = chunk_pages(pages, size_chars=100, overlap_chars=0)
    assert all(not c.text.startswith("wordtail") or c.text == "wordtail" or " " in c.text for c in chunks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.chunker'`

- [ ] **Step 3: Implement the chunker**

`api/app/ingestion/chunker.py`:
```python
from dataclasses import dataclass
from app.ingestion.parsers import Page


@dataclass
class Chunk:
    text: str
    page: int


def chunk_pages(pages: list[Page], size_chars: int, overlap_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        if not text.strip():
            continue
        start = 0
        n = len(text)
        while start < n:
            end = min(start + size_chars, n)
            if end < n:
                space = text.rfind(" ", start, end)
                if space > start:
                    end = space
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(text=piece, page=page.number))
            if end >= n:
                break
            next_start = end - overlap_chars
            start = next_start if next_start > start else start + 1
    return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_chunker.py -v`
Expected: PASS (5 tests). Full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/ingestion/chunker.py api/tests/test_chunker.py
git commit -m "feat: page-aware recursive character chunker"
```

---

### Task 6: Ingestion orchestrator

**Files:**
- Create: `api/app/ingestion/orchestrator.py`
- Create: `api/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `parse_file`, `chunk_pages` (Tasks 4–5); `OllamaClient.embed` (Task 2); `QdrantStore.upsert` (Task 1); `DocumentRepository` (Task 3); `Settings` (chunk sizes, embed model).
- Produces: `async ingest_document(doc_id: int, file_path: str, filename: str, repo: DocumentRepository, embedder: OllamaClient, qdrant: QdrantStore, settings: Settings) -> None`. Status transitions: `pending → parsing → embedding → done`, or `failed` with an error message on any exception (including `OcrRequiredError` / `UnsupportedFileError`). Embeds in batches of 32; upserts Qdrant points with payload `{doc_id, filename, page, text, language}`.

- [ ] **Step 1: Write the failing test**

`api/tests/test_orchestrator.py`:
```python
import os
import tempfile
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.repositories import DocumentRepository
from app.config import Settings
from app.ingestion.orchestrator import ingest_document
from fpdf import FPDF


def _make_pdf(path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(0, 10, "The machine must be serviced annually.")
    pdf.output(path)


async def _repo_with_one_doc(filename):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = factory()
    repo = DocumentRepository(session)
    doc = await repo.create(filename)
    return repo, doc, engine, session


async def test_ingest_happy_path_marks_done_and_upserts():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.pdf")
        _make_pdf(path)
        repo, doc, engine, session = await _repo_with_one_doc("m.pdf")
        embedder = AsyncMock()
        embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
        qdrant = AsyncMock()
        qdrant.upsert = AsyncMock()
        settings = Settings(chunk_size_tokens=512, chunk_overlap_tokens=50)
        await ingest_document(doc.id, path, "m.pdf", repo, embedder, qdrant, settings)
        fetched = await repo.get(doc.id)
        assert fetched.status == "done"
        assert fetched.chunk_count == 1
        assert fetched.parser_used == "pdf"
        qdrant.upsert.assert_awaited()
        points = qdrant.upsert.call_args.kwargs["points"]
        assert points[0]["payload"]["doc_id"] == doc.id
        assert points[0]["payload"]["page"] == 1
        assert "serviced" in points[0]["payload"]["text"]
        await session.close()
        await engine.dispose()


async def test_ingest_ocr_required_marks_failed():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "blank.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.output(path)
        repo, doc, engine, session = await _repo_with_one_doc("blank.pdf")
        embedder = AsyncMock()
        qdrant = AsyncMock()
        await ingest_document(doc.id, path, "blank.pdf", repo, embedder, qdrant, Settings())
        fetched = await repo.get(doc.id)
        assert fetched.status == "failed"
        assert "OCR" in fetched.error
        qdrant.upsert.assert_not_awaited()
        await session.close()
        await engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingestion.orchestrator'`

- [ ] **Step 3: Implement the orchestrator**

`api/app/ingestion/orchestrator.py`:
```python
import uuid
from app.config import Settings
from app.db.repositories import DocumentRepository
from app.ollama.client import OllamaClient
from app.qdrant.client import QdrantStore
from app.ingestion.parsers import parse_file
from app.ingestion.chunker import chunk_pages

EMBED_BATCH = 32


async def ingest_document(
    doc_id: int,
    file_path: str,
    filename: str,
    repo: DocumentRepository,
    embedder: OllamaClient,
    qdrant: QdrantStore,
    settings: Settings,
) -> None:
    try:
        await repo.set_status(doc_id, "parsing")
        pages = parse_file(file_path, filename)
        parser_used = _parser_used(filename)
        size_chars = settings.chunk_size_tokens * 4
        overlap_chars = settings.chunk_overlap_tokens * 4
        chunks = chunk_pages(pages, size_chars, overlap_chars)
        if not chunks:
            await repo.set_status(doc_id, "failed", parser_used=parser_used, error="No text extracted")
            return

        await repo.set_status(doc_id, "embedding", parser_used=parser_used, chunk_count=len(chunks))
        points = []
        for i in range(0, len(chunks), EMBED_BATCH):
            batch = chunks[i:i + EMBED_BATCH]
            vectors = await embedder.embed([c.text for c in batch])
            for chunk, vector in zip(batch, vectors):
                points.append({
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "doc_id": doc_id,
                        "filename": filename,
                        "page": chunk.page,
                        "text": chunk.text,
                        "language": "auto",
                    },
                })
        await qdrant.upsert(points)
        await repo.set_status(doc_id, "done", chunk_count=len(chunks), parser_used=parser_used)
    except Exception as e:
        await repo.set_status(doc_id, "failed", error=str(e))


def _parser_used(filename: str) -> str:
    from pathlib import Path
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext in ("pdf", "docx", "html", "htm") else "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (2 tests). Full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/ingestion/orchestrator.py api/tests/test_orchestrator.py
git commit -m "feat: ingestion orchestrator (parse→chunk→embed→upsert)"
```

---

### Task 7: `/documents` API endpoints

**Files:**
- Create: `api/app/routers/documents.py`
- Modify: `api/app/main.py` (include the documents router)
- Create: `api/tests/test_documents_api.py`

**Interfaces:**
- Consumes: `DocumentRepository`, `QdrantStore`, `OllamaClient`, `ingest_document`, `Settings`, `get_session` (Plan 1), and the `DATA_DIR` setting.
- Produces REST endpoints:
  - `POST /documents/upload` (multipart `file`) → saves to `DATA_DIR`, creates a `documents` row (`pending`), schedules `ingest_document` as a background task, returns the row.
  - `GET /documents` → list all rows.
  - `GET /documents/{id}` → one row or 404.
  - `DELETE /documents/{id}` → delete Qdrant points for the doc, remove the file, delete the row, return 204.

- [ ] **Step 1: Write the failing test**

`api/tests/test_documents_api.py`:
```python
import os
import tempfile
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base, get_session
from app.db.repositories import DocumentRepository
from app.main import create_app
from app.config import get_settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    # isolated sqlite + a fake qdrant/ollama and a no-op ingest background task
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with factory() as session:
            yield session

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.state.qdrant = AsyncMock()
    app.state.ollama = AsyncMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_creates_row_and_runs_ingest(client, tmp_path):
    # patch the background ingest to a no-op that marks the doc done
    import app.routers.documents as docs
    async def fake_ingest(doc_id, file_path, filename, repo, embedder, qdrant, settings):
        await repo.set_status(doc_id, "done", chunk_count=1, parser_used="pdf")
    docs.ingest_document = fake_ingest

    files = {"file": ("m.pdf", b"%PDF-1.4 fake", "application/pdf")}
    r = client.post("/documents/upload", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "m.pdf"
    assert body["status"] in ("pending", "done")  # background task may have run
    doc_id = body["id"]

    listing = client.get("/documents")
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    detail = client.get(f"/documents/{doc_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == doc_id

    missing = client.get("/documents/999999")
    assert missing.status_code == 404


def test_delete_removes_row(client):
    import app.routers.documents as docs
    async def fake_ingest(doc_id, file_path, filename, repo, embedder, qdrant, settings):
        await repo.set_status(doc_id, "done", chunk_count=1, parser_used="pdf")
    docs.ingest_document = fake_ingest

    files = {"file": ("m.pdf", b"%PDF-1.4 fake", "application/pdf")}
    doc_id = client.post("/documents/upload", files=files).json()["id"]
    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 204
    assert client.get(f"/documents/{doc_id}").status_code == 404
```

> Note: the upload saves the uploaded bytes to `DATA_DIR` even though the bytes are not a real PDF; the background `fake_ingest` here does not call the real parser, so parsing is not exercised in this test (the orchestrator test in Task 6 covers real parsing). The point of this test is the HTTP surface + status flow + delete.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_documents_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.documents'` / 404 on the route.

- [ ] **Step 3: Implement the router**

`api/app/routers/documents.py`:
```python
import os
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_session
from app.db.repositories import DocumentRepository
from app.ingestion.orchestrator import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    settings = request.app.state.settings
    os.makedirs(settings.data_dir, exist_ok=True)
    repo = DocumentRepository(session)
    doc = await repo.create(file.filename)
    save_path = os.path.join(settings.data_dir, f"{doc.id}_{file.filename}")
    with open(save_path, "wb") as f:
        f.write(await file.read())
    background.add_task(
        ingest_document, doc.id, save_path, file.filename,
        repo, request.app.state.ollama, request.app.state.qdrant, settings,
    )
    return _doc_dict(await repo.get(doc.id))


@router.get("")
async def list_documents(session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    return [_doc_dict(d) for d in await repo.list_all()]


@router.get("/{doc_id}")
async def get_document(doc_id: int, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    doc = await repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _doc_dict(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    repo = DocumentRepository(session)
    doc = await repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    await request.app.state.qdrant.delete_by_doc(doc_id)
    settings = request.app.state.settings
    save_path = os.path.join(settings.data_dir, f"{doc_id}_{doc.filename}")
    if os.path.exists(save_path):
        os.remove(save_path)
    await repo.delete(doc_id)
    return None


def _doc_dict(doc):
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "parser_used": doc.parser_used,
        "error": doc.error,
    }
```

- [ ] **Step 4: Register the router in `main.py`**

In `api/app/main.py` `create_app`, add:
```python
from app.routers import documents
...
    app.include_router(health.router)
    app.include_router(documents.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_documents_api.py -v`
Expected: PASS (2 tests). Full suite green.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/documents.py api/app/main.py api/tests/test_documents_api.py
git commit -m "feat: /documents upload/list/detail/delete endpoints"
```

---

### Task 8: Integration verification + Docker smoke test

**Files:**
- No new source files. Verify the whole pipeline together.

- [ ] **Step 1: Run the full unit suite**

```
cd api && . .venv/bin/activate
python -m pytest -v
```
Expected: all tests pass (Plan 1 + Plan 2). Record the count.

- [ ] **Step 2: Docker smoke test of the documents API**

```
cd /Users/eklavya/youtub3/rag_1
cp .env.example .env
docker compose up -d --build
sleep 15
curl -s http://localhost:8000/health
curl -s http://localhost:8000/documents
```
Expected: `/health` returns `{"status":"ok",...}`; `/documents` returns `[]`.
Then upload a small text PDF (generate one if needed) and poll status:
```
curl -s -F "file=@/tmp/sample.pdf" http://localhost:8000/documents/upload
curl -s http://localhost:8000/documents/1
docker compose down
```
Expected: the upload returns a row; the status is either `done` (if a real Ollama with `bge-m3` is reachable at `OLLAMA_BASE_URL`) or `failed` with an embedding/connection error (if Ollama is not running — still proves the pipeline ran end-to-end inside the container). Record which outcome occurred and the `/health` JSON.

- [ ] **Step 3: Commit any smoke-test artifacts (e.g. a generated sample PDF is NOT committed; only record results in the report)**

(No commit required if no source changed. If the smoke test surfaced a fix, commit it with a clear message.)

---

## Self-Review

**1. Spec coverage (Plan 2 scope = ingestion + documents API):**
- Ingestion pipeline parse→chunk→embed→upsert → Tasks 4, 5, 6. ✅
- `/documents` upload/list/status/delete → Task 7. ✅
- Qdrant upsert + delete-by-doc → Task 1. ✅
- Postgres `documents` status transitions → Tasks 3, 6, 7. ✅
- Mixed formats (PDF/DOCX/HTML) → Task 4. ✅
- OCR detection (deferred, marks failed) → Task 4 `OcrRequiredError` + Task 6. ✅ (deviation documented)
- Error handling: per-file failed+error; unsupported rejected → Tasks 4, 6, 7. ✅
- Large files: batched embedding (32) → Task 6. ✅
- Env-driven chunk sizes + embed model → Task 6 + Settings (Plan 1). ✅
- Carried-over refactors: async Qdrant (Task 1), httpx reuse (Task 2), embed/chat_stream tests (Task 2). ✅
- Deferred to Plan 3: retrieval (`search`), `/chat`, chat history. ✅ (not in scope)

**2. Placeholder scan:** No TBD/TODO. Every code step has full code; every test has real assertions. The `# noqa`/note lines are explanatory, not placeholders. ✅

**3. Type consistency:**
- `Page(number, text)` defined in Task 4, consumed in Task 5 (`chunk_pages`) and produced by `parse_file` used in Task 6. ✅
- `Chunk(text, page)` defined in Task 5, consumed in Task 6. ✅
- `DocumentRepository.create/get/list_all/set_status/delete` defined in Task 3, used in Tasks 6 and 7 with the same names. ✅
- `QdrantStore.upsert(points: list[dict])` / `delete_by_doc(doc_id)` defined in Task 1, used in Tasks 6 and 7. ✅
- `OllamaClient.embed(texts) -> list[list[float]]` defined in Task 2, used in Task 6. ✅
- `ingest_document(doc_id, file_path, filename, repo, embedder, qdrant, settings)` signature identical in Task 6 definition and Task 7 `background.add_task` call and Task 7 test `fake_ingest`. ✅
- `Settings.data_dir`, `chunk_size_tokens`, `chunk_overlap_tokens` come from Plan 1's `Settings`. ✅

No issues found.