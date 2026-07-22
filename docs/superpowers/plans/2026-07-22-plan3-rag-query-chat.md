# Plan 3 — RAG Query & Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the conversational Q&A layer: a `POST /chat` SSE endpoint that retrieves relevant manual chunks from Qdrant, streams a grounded answer from the Ollama LLM, emits source citations, and persists the conversation — plus a chat-history read endpoint for the frontend.

**Architecture:** Builds on Plan 1 (Settings, async SQLAlchemy, `ChatSession`/`ChatMessage` models, Ollama/Qdrant clients) and Plan 2 (ingestion, `DocumentRepository`). New: a `rag/` package (`Retriever`, prompt builder), a `ChatRepository`, and a `/chat` router. Query flow: embed question → Qdrant `search` (top-k) → no-context threshold → build prompt (system + context + history) → stream `chat_stream` tokens over SSE → emit sources → persist messages.

**Tech Stack:** Python 3.11 (prod Docker) / 3.14 (host tests), FastAPI `StreamingResponse` (SSE), async SQLAlchemy, qdrant-client (Async), httpx, pytest + pytest-asyncio + aiosqlite.

## Global Constraints

- Python 3.11 prod (Docker), 3.14 host tests; `asyncpg` must NOT be imported in unit tests (conftest sets `POSTGRES_DSN` to sqlite). Qdrant/Ollama are mocked in unit tests.
- All config via `app.config.Settings` (`.env`): `RETRIEVAL_TOP_K`, `NO_CONTEXT_THRESHOLD`, `RERANK_ENABLED`, `CHAT_HISTORY_TURNS`, `OLLAMA_LLM_MODEL`, `OLLAMA_EMBED_MODEL`.
- External Ollama only (`OLLAMA_BASE_URL`); LLM `qwen2.5:32b`, embeddings `bge-m3` (env-driven).
- v1: no auth. Pronoun/coreference query rewriting is NOT in scope.
- Hard rule: the LLM answers ONLY from retrieved context; if the top score is below `NO_CONTEXT_THRESHOLD` (or no hits), respond `"I couldn't find this in the manuals."` and do NOT call the LLM.
- If Ollama is unreachable during retrieval (embed fails), `POST /chat` returns HTTP 503 `"AI service unavailable"` (not a streamed error).
- Reranking is a placeholder: when `RERANK_ENABLED=true`, the retriever trims to the top 4 results. A real reranker model can replace this later (noted, not built).
- Chat history: the last `CHAT_HISTORY_TURNS` messages of the session are folded into the prompt. The current question is always passed separately (not duplicated from history).
- Deferred to a later polish plan (noted, not built here): real language detection (payload `language` is `"auto"`), `section` metadata in payloads, upload streaming, an asyncpg-backed integration test.

## File Structure (this plan)

```
api/app/rag/
  __init__.py
  retriever.py          # NEW: Source dataclass, Retriever.retrieve()
  prompt.py             # NEW: build_messages()
api/app/db/repositories.py   # MODIFY: add ChatRepository
api/app/qdrant/client.py     # MODIFY: search(), close()
api/app/ollama/client.py     # MODIFY: chat_stream read timeout
api/app/routers/chat.py      # NEW: POST /chat (SSE) + GET /chat/sessions/{id}/messages
api/app/main.py              # MODIFY: close qdrant on shutdown; include chat router
api/tests/
  test_qdrant.py             # MODIFY: + search + close tests
  test_chat_repository.py    # NEW
  test_retriever.py          # NEW
  test_prompt.py             # NEW
  test_chat_api.py           # NEW
```

Each module has one responsibility: `retriever.py` owns retrieval, `prompt.py` owns prompt assembly, `routers/chat.py` owns the chat HTTP surface, `ChatRepository` owns chat persistence.

---

### Task 1: `QdrantStore.search` + `close`; `chat_stream` read timeout

**Files:**
- Modify: `api/app/qdrant/client.py`
- Modify: `api/app/ollama/client.py`
- Modify: `api/app/main.py` (close qdrant on shutdown)
- Modify: `api/tests/test_qdrant.py`

**Interfaces:**
- Produces:
  - `async QdrantStore.search(query_vector: list[float], top_k: int) -> list[dict]` — each dict: `{"text", "doc_id", "filename", "page", "score"}`. Used by the Retriever (Task 3).
  - `async QdrantStore.close() -> None` — closes the underlying client; called in lifespan shutdown.
- `OllamaClient.chat_stream` gains a read timeout so a stalled Ollama doesn't hang the stream indefinitely.

- [ ] **Step 1: Add failing tests**

Append to `api/tests/test_qdrant.py`:
```python
async def test_search_maps_hits_to_dicts():
    store = _store()
    fake_hit = MagicMock()
    fake_hit.score = 0.91
    fake_hit.payload = {"text": "calibrate", "doc_id": 1, "filename": "m.pdf", "page": 3}
    with patch.object(store, "_client") as mock_client:
        mock_client.search = AsyncMock(return_value=[fake_hit])
        results = await store.search([0.1, 0.2], top_k=5)
    mock_client.search.assert_awaited_once()
    _, kwargs = mock_client.search.call_args
    assert kwargs["collection_name"] == "manuals"
    assert kwargs["limit"] == 5
    assert results == [{"text": "calibrate", "doc_id": 1, "filename": "m.pdf", "page": 3, "score": 0.91}]


async def test_close_closes_underlying_client():
    store = _store()
    with patch.object(store, "_client") as mock_client:
        mock_client.close = AsyncMock()
        await store.close()
    mock_client.close.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && . .venv/bin/activate && python -m pytest tests/test_qdrant.py -v`
Expected: FAIL — `search`/`close` missing.

- [ ] **Step 3: Implement `search` and `close`** (add to `api/app/qdrant/client.py`)

```python
    async def search(self, query_vector: list[float], top_k: int) -> list[dict]:
        results = await self._client.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "text": r.payload.get("text", ""),
                "doc_id": r.payload.get("doc_id"),
                "filename": r.payload.get("filename", ""),
                "page": r.payload.get("page"),
                "score": r.score,
            }
            for r in results
        ]

    async def close(self) -> None:
        await self._client.close()
```

- [ ] **Step 4: Add a read timeout to `chat_stream`**

In `api/app/ollama/client.py`, change the `chat_stream` stream call to pass a read timeout:
```python
        async with self._http.stream(
            "POST",
            f"{self._base}/api/chat",
            json={"model": model or self.settings.ollama_llm_model,
                  "messages": messages, "stream": True},
            timeout=httpx.Timeout(None, read=120.0),
        ) as r:
```
(Only the `timeout=httpx.Timeout(None, read=120.0)` kwarg is added; the rest is unchanged.)

- [ ] **Step 5: Close qdrant in `main.py` lifespan shutdown**

In `api/app/main.py` `_lifespan`, after `yield`, the shutdown half should be:
```python
    yield
    await async_engine.dispose()
    await app.state.ollama.close()
    await app.state.qdrant.close()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_qdrant.py -v` then `python -m pytest -v`
Expected: qdrant tests PASS (6 total); full suite green.

- [ ] **Step 7: Commit**

```bash
git add api/app/qdrant/client.py api/app/ollama/client.py api/app/main.py api/tests/test_qdrant.py
git commit -m "feat: QdrantStore.search/close + chat_stream read timeout"
```

---

### Task 2: ChatRepository (sessions + messages)

**Files:**
- Modify: `api/app/db/repositories.py` (add `ChatRepository`)
- Create: `api/tests/test_chat_repository.py`

**Interfaces:**
- Consumes: `AsyncSession`, the `ChatSession`/`ChatMessage` models (Plan 1).
- Produces `ChatRepository(session)` with async methods:
  - `create_session(title: str | None = None) -> ChatSession`
  - `get_session(session_id: int) -> ChatSession | None`
  - `add_message(session_id: int, role: str, content: str, sources_json: dict | list | None = None) -> ChatMessage`
  - `list_messages(session_id: int, limit: int) -> list[ChatMessage]` — the last `limit` messages, oldest-first.
- Used by the `/chat` router (Task 5).

- [ ] **Step 1: Write the failing test**

`api/tests/test_chat_repository.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.repositories import ChatRepository


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield ChatRepository(session)
    await engine.dispose()


async def test_create_and_get_session(repo):
    sess = await repo.create_session("how to calibrate?")
    assert sess.id is not None
    fetched = await repo.get_session(sess.id)
    assert fetched.title == "how to calibrate?"


async def test_add_and_list_messages(repo):
    sess = await repo.create_session()
    await repo.add_message(sess.id, "user", "hi")
    await repo.add_message(sess.id, "assistant", "hello", sources_json=[{"filename": "m.pdf", "page": 1}])
    msgs = await repo.list_messages(sess.id, limit=10)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].sources_json == [{"filename": "m.pdf", "page": 1}]


async def test_list_messages_returns_last_n_oldest_first(repo):
    sess = await repo.create_session()
    for i in range(5):
        await repo.add_message(sess.id, "user", f"q{i}")
    msgs = await repo.list_messages(sess.id, limit=3)
    assert [m.content for m in msgs] == ["q2", "q3", "q4"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_chat_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChatRepository'` (or `AttributeError`).

- [ ] **Step 3: Implement `ChatRepository`** (append to `api/app/db/repositories.py`)

```python
from sqlalchemy import select
from sqlalchemy.sql import func
from app.db.models import ChatSession, ChatMessage


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, title: str | None = None) -> ChatSession:
        sess = ChatSession(title=title)
        self.session.add(sess)
        await self.session.commit()
        await self.session.refresh(sess)
        return sess

    async def get_session(self, session_id: int) -> ChatSession | None:
        result = await self.session.execute(select(ChatSession).where(ChatSession.id == session_id))
        return result.scalar_one_or_none()

    async def add_message(self, session_id: int, role: str, content: str, sources_json=None) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content, sources_json=sources_json)
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def list_messages(self, session_id: int, limit: int) -> list[ChatMessage]:
        # last `limit` messages, returned oldest-first
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(reversed(result.scalars().all()))
```
(Keep the existing `DocumentRepository` unchanged. `AsyncSession` is already imported at the top of the file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_chat_repository.py -v` then `python -m pytest -v`
Expected: PASS (3 tests); full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/db/repositories.py api/tests/test_chat_repository.py
git commit -m "feat: ChatRepository for sessions and messages"
```

---

### Task 3: Retriever

**Files:**
- Create: `api/app/rag/__init__.py`
- Create: `api/app/rag/retriever.py`
- Create: `api/tests/test_retriever.py`

**Interfaces:**
- Consumes: `OllamaClient.embed` (Plan 2), `QdrantStore.search` (Task 1), `Settings`.
- Produces:
  - `Source` dataclass: `Source(text: str, doc_id: int, filename: str, page: int, score: float)`.
  - `Retriever(embedder, qdrant, settings)` with `async retrieve(question: str) -> list[Source]`. Returns the top-`retrieval_top_k` hits sorted by score desc; returns `[]` if there are no hits OR the best score is below `no_context_threshold`. If `rerank_enabled`, trims to the top 4.

- [ ] **Step 1: Write the failing test**

`api/tests/test_retriever.py`:
```python
from unittest.mock import AsyncMock
from app.config import Settings
from app.rag.retriever import Retriever, Source


async def test_retrieve_returns_sources_sorted():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"text": "b", "doc_id": 1, "filename": "m.pdf", "page": 2, "score": 0.8},
        {"text": "a", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.9},
    ])
    r = Retriever(embedder, qdrant, Settings(retrieval_top_k=5, no_context_threshold=0.35))
    sources = await r.retrieve("how to calibrate?")
    assert sources == [
        Source(text="a", doc_id=1, filename="m.pdf", page=1, score=0.9),
        Source(text="b", doc_id=1, filename="m.pdf", page=2, score=0.8),
    ]
    embedder.embed.assert_awaited_once_with(["how to calibrate?"])


async def test_retrieve_below_threshold_returns_empty():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=[
        {"text": "x", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.2},
    ])
    r = Retriever(embedder, qdrant, Settings(no_context_threshold=0.35))
    assert await r.retrieve("anything") == []


async def test_retrieve_rerank_enabled_trims_to_four():
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=[[0.1]])
    hits = [{"text": str(i), "doc_id": 1, "filename": "m.pdf", "page": i, "score": 0.9 - i * 0.01} for i in range(6)]
    qdrant = AsyncMock()
    qdrant.search = AsyncMock(return_value=hits)
    r = Retriever(embedder, qdrant, Settings(retrieval_top_k=6, rerank_enabled=True, no_context_threshold=0.35))
    sources = await r.retrieve("q")
    assert len(sources) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_retriever.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rag.retriever'`.

- [ ] **Step 3: Implement the retriever**

`api/app/rag/__init__.py`: (empty)
```python
```

`api/app/rag/retriever.py`:
```python
from dataclasses import dataclass
from app.config import Settings


@dataclass
class Source:
    text: str
    doc_id: int
    filename: str
    page: int
    score: float


class Retriever:
    def __init__(self, embedder, qdrant, settings: Settings):
        self.embedder = embedder
        self.qdrant = qdrant
        self.settings = settings

    async def retrieve(self, question: str) -> list[Source]:
        vectors = await self.embedder.embed([question])
        query_vector = vectors[0]
        hits = await self.qdrant.search(query_vector, self.settings.retrieval_top_k)
        if not hits:
            return []
        hits_sorted = sorted(hits, key=lambda h: h["score"], reverse=True)
        if hits_sorted[0]["score"] < self.settings.no_context_threshold:
            return []
        sources = [
            Source(
                text=h["text"],
                doc_id=h["doc_id"],
                filename=h["filename"],
                page=h["page"],
                score=h["score"],
            )
            for h in hits_sorted
        ]
        if self.settings.rerank_enabled:
            sources = sources[:4]
        return sources
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_retriever.py -v` then `python -m pytest -v`
Expected: PASS (3 tests); full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/rag/__init__.py api/app/rag/retriever.py api/tests/test_retriever.py
git commit -m "feat: Retriever with no-context threshold and rerank trim"
```

---

### Task 4: Prompt builder

**Files:**
- Create: `api/app/rag/prompt.py`
- Create: `api/tests/test_prompt.py`

**Interfaces:**
- Consumes: `Source` from `app.rag.retriever`.
- Produces: `build_messages(question: str, sources: list[Source], history: list[ChatMessage]) -> list[dict]` — Ollama chat messages: a system message (answer only from context, cite `[filename, page]`), a context block, the prior `history` messages (role/content), and the current user question last.

- [ ] **Step 1: Write the failing test**

`api/tests/test_prompt.py`:
```python
from app.rag.retriever import Source
from app.rag.prompt import build_messages
from app.db.models import ChatMessage


def _msg(role, content):
    return ChatMessage(id=1, session_id=1, role=role, content=content)


def test_build_messages_system_context_history_question():
    sources = [Source(text="calibrate the sensor", doc_id=1, filename="m.pdf", page=3, score=0.9)]
    history = [_msg("user", "earlier question"), _msg("assistant", "earlier answer")]
    messages = build_messages("how to calibrate?", sources, history)

    assert messages[0]["role"] == "system"
    assert "only" in messages[0]["content"].lower() and "context" in messages[0]["content"].lower()

    # context block contains the source with a citation marker
    context_text = " ".join(m["content"] for m in messages if m["role"] == "system")
    assert "m.pdf" in context_text and "3" in context_text and "calibrate the sensor" in context_text

    # history then current question last
    assert {"role": "user", "content": "earlier question"} in messages
    assert {"role": "assistant", "content": "earlier answer"} in messages
    assert messages[-1] == {"role": "user", "content": "how to calibrate?"}


def test_build_messages_empty_history():
    sources = [Source(text="t", doc_id=1, filename="a.pdf", page=1, score=0.5)]
    messages = build_messages("q", sources, [])
    assert messages[-1] == {"role": "user", "content": "q"}
    assert sum(1 for m in messages if m["role"] == "user") == 1  # only the current question
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.rag.prompt'`.

- [ ] **Step 3: Implement the prompt builder**

`api/app/rag/prompt.py`:
```python
from app.rag.retriever import Source
from app.db.models import ChatMessage

SYSTEM = (
    "You are a technical-manual assistant. Answer the user's question using ONLY the "
    "provided context from the manuals. If the context does not contain the answer, say "
    "\"I couldn't find this in the manuals.\" When you use information from the context, "
    "cite the source as [filename, page]."
)


def build_messages(question: str, sources: list[Source], history: list[ChatMessage]) -> list[dict]:
    context_lines = [f"[{s.filename}, p.{s.page}]: {s.text}" for s in sources]
    context_block = "Context from manuals:\n" + "\n".join(context_lines) if context_lines else ""
    system_content = SYSTEM + ("\n\n" + context_block if context_block else "")
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question})
    return messages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_prompt.py -v` then `python -m pytest -v`
Expected: PASS (2 tests); full suite green.

- [ ] **Step 5: Commit**

```bash
git add api/app/rag/prompt.py api/tests/test_prompt.py
git commit -m "feat: prompt builder with system rule, context, history"
```

---

### Task 5: `/chat` SSE endpoint + history endpoint

**Files:**
- Create: `api/app/routers/chat.py`
- Modify: `api/app/main.py` (include the chat router)
- Create: `api/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `ChatRepository`, `Retriever`, `build_messages`, `OllamaClient.chat_stream`, `Settings`, `get_session`, `session_factory`.
- Produces:
  - `POST /chat` — body `{question: str, session_id: int | None}`. Creates a session if `session_id` is null. SSE response (`text/event-stream`) with events: `{"type":"session","session_id":N}`, then `{"type":"token","content":"..."}` per token, then `{"type":"sources","sources":[...]}`, then `{"type":"done"}`. If no context: a single `token` event with `"I couldn't find this in the manuals."`, empty `sources`, `done` (no LLM call). If Ollama is unreachable at retrieval: HTTP 503 `{"detail":"AI service unavailable"}`.
  - `GET /chat/sessions/{session_id}/messages` — list messages for a session (oldest-first), each `{role, content, sources}`.

**Design note:** Retrieval (which calls Ollama `embed`) runs BEFORE the `StreamingResponse` is returned, so an unreachable Ollama becomes a clean 503 (you cannot change status after streaming starts). The user message + session + history are read in the request session before streaming. The assistant message is persisted DURING streaming using a fresh session from `app.state.session_factory` (the request session is not guaranteed to be usable for commits inside the streaming body).

- [ ] **Step 1: Write the failing test**

`api/tests/test_chat_api.py`:
```python
import json
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base, get_session
from app.main import create_app
from app.config import get_settings


class FakeOllama:
    async def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def chat_stream(self, messages):
        for p in ["Hel", "lo"]:
            yield p

    async def ping(self):
        return True


class FakeQdrant:
    async def search(self, vector, top_k):
        return [{"text": "calibrate the sensor", "doc_id": 1, "filename": "m.pdf", "page": 3, "score": 0.9}]


class NoContextQdrant:
    async def search(self, vector, top_k):
        return [{"text": "x", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.1}]


class DeadOllama:
    async def embed(self, texts):
        raise ConnectionError("ollama down")

    async def chat_stream(self, messages):
        return
        yield  # make it an async generator

    async def ping(self):
        return False


@pytest.fixture
def app_with_fakes(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
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
    app.state.session_factory = factory
    return app, factory


def _client(app):
    return TestClient(app)


def _parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        for line in block.strip().splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_chat_streams_answer_sources_and_persists(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)

    r = client.post("/chat", json={"question": "how to calibrate?"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert events[0]["type"] == "session"
    session_id = events[0]["session_id"]
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert tokens == "Hello"
    sources = [e for e in events if e["type"] == "sources"][0]["sources"]
    assert sources[0]["filename"] == "m.pdf" and sources[0]["page"] == 3
    assert events[-1]["type"] == "done"

    # history persisted
    hist = client.get(f"/chat/sessions/{session_id}/messages")
    assert hist.status_code == 200
    roles = [m["role"] for m in hist.json()]
    assert roles == ["user", "assistant"]
    assert hist.json()[1]["sources"][0]["filename"] == "m.pdf"


def test_chat_no_context_replies_not_found(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = NoContextQdrant()
    client = _client(app)

    r = client.post("/chat", json={"question": "something unrelated"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    tokens = "".join(e["content"] for e in events if e["type"] == "token")
    assert "couldn't find" in tokens
    assert [e for e in events if e["type"] == "sources"][0]["sources"] == []


def test_chat_ollama_unreachable_returns_503(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = DeadOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)

    r = client.post("/chat", json={"question": "how to calibrate?"})
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()
```

> Note: `TestClient(app)` is used WITHOUT `with` so the lifespan does not run and the fixture's fake `app.state.qdrant`/`app.state.ollama` stay in place. `TestClient.post` against an SSE `StreamingResponse` collects the full body into `r.text`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_chat_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.routers.chat'` / 404 on `/chat`.

- [ ] **Step 3: Implement the chat router**

`api/app/routers/chat.py`:
```python
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_session
from app.db.repositories import ChatRepository
from app.rag.retriever import Retriever
from app.rag.prompt import build_messages

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str
    session_id: int | None = None


@router.post("")
async def chat(req: ChatRequest, request: Request, session: AsyncSession = Depends(get_session)):
    settings = request.app.state.settings
    repo = ChatRepository(session)

    if req.session_id:
        sess = await repo.get_session(req.session_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="session not found")
    else:
        sess = await repo.create_session(title=req.question[:80])
    await repo.add_message(sess.id, "user", req.question)
    history = await repo.list_messages(sess.id, settings.chat_history_turns)
    # history is oldest-first and ends with the user message just added; drop it so the
    # current question (passed separately to build_messages) is not duplicated.
    prior_history = history[:-1]

    ollama = request.app.state.ollama
    qdrant = request.app.state.qdrant
    retriever = Retriever(ollama, qdrant, settings)

    try:
        sources = await retriever.retrieve(req.question)
    except Exception:
        raise HTTPException(status_code=503, detail="AI service unavailable")

    session_id = sess.id
    source_dicts = [_source_dict(s) for s in sources]

    if not sources:
        async def no_context():
            yield _sse({"type": "session", "session_id": session_id})
            text = "I couldn't find this in the manuals."
            yield _sse({"type": "token", "content": text})
            async with request.app.state.session_factory() as s:
                await ChatRepository(s).add_message(session_id, "assistant", text, sources_json=[])
            yield _sse({"type": "sources", "sources": []})
            yield _sse({"type": "done"})
        return StreamingResponse(no_context(), media_type="text/event-stream")

    messages = build_messages(req.question, sources, prior_history)

    async def generate():
        yield _sse({"type": "session", "session_id": session_id})
        collected = []
        async for piece in ollama.chat_stream(messages):
            collected.append(piece)
            yield _sse({"type": "token", "content": piece})
        answer = "".join(collected)
        async with request.app.state.session_factory() as s:
            await ChatRepository(s).add_message(session_id, "assistant", answer, sources_json=source_dicts)
        yield _sse({"type": "sources", "sources": source_dicts})
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/sessions/{session_id}/messages")
async def list_session_messages(session_id: int, session: AsyncSession = Depends(get_session)):
    repo = ChatRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    msgs = await repo.list_messages(session_id, limit=1000)
    return [
        {"role": m.role, "content": m.content, "sources": m.sources_json or []}
        for m in msgs
    ]


def _sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _source_dict(s) -> dict:
    return {"filename": s.filename, "page": s.page, "text": s.text, "score": s.score}
```

- [ ] **Step 4: Register the chat router in `main.py`**

In `api/app/main.py` `create_app`, add:
```python
from app.routers import chat
...
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd api && python -m pytest tests/test_chat_api.py -v` then `python -m pytest -v`
Expected: PASS (3 tests); full suite green.

- [ ] **Step 6: Commit**

```bash
git add api/app/routers/chat.py api/app/main.py api/tests/test_chat_api.py
git commit -m "feat: /chat SSE endpoint with retrieval, sources, history; session messages endpoint"
```

---

### Task 6: Integration verification + Docker smoke test

**Files:**
- No new source files unless the smoke test surfaces a bug.

- [ ] **Step 1: Run the full unit suite**

```
cd /Users/eklavya/youtub3/rag_1/api && . .venv/bin/activate
python -m pytest -v
```
Expected: all tests pass (Plan 1 + Plan 2 + Plan 3). Record the count.

- [ ] **Step 2: Docker smoke test of `/chat`**

```
cd /Users/eklavya/youtub3/rag_1
cp .env.example .env
docker compose up -d --build
sleep 20
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{"question":"how do I calibrate the sensor?"}'
docker compose down
```
Expected: `/health` → `{"status":"ok",...}`. `/chat` returns HTTP 503 with `"AI service unavailable"` because external Ollama is not running (the retrieval `embed` call fails) — this proves the 503 path works in the container. If Ollama IS reachable with `bge-m3` + `qwen2.5:32b` pulled AND a document has been ingested, expect an SSE stream with tokens + sources. Record the outcome (503 vs streamed).

- [ ] **Step 3: Commit any bug fix surfaced by the smoke test (if none, no commit)**

---

## Self-Review

**1. Spec coverage (Plan 3 scope = retrieval + chat):**
- Query flow embed→search→threshold→prompt→stream→sources→persist → Tasks 3, 4, 5. ✅
- `QdrantStore.search` → Task 1. ✅
- Chat history (last CHAT_HISTORY_TURNS folded in, current question separate) → Tasks 2, 4, 5. ✅
- No-context → "I couldn't find this in the manuals" (no LLM call) → Tasks 3, 5. ✅
- Ollama unreachable → 503 → Task 5. ✅
- SSE streaming with sources → Task 5. ✅
- Source citations (filename + page) → Tasks 4, 5. ✅
- Concurrency (async streaming) → Task 5 + Plan 1/2 async clients. ✅
- Optional rerank (trim to 4) → Task 3. ✅
- Deferred (language detection, section, upload streaming, asyncpg integration test) → documented, not built. ✅
- Plan 2 hardening carried in: Qdrant `close` + `chat_stream` read timeout → Task 1. ✅

**2. Placeholder scan:** No TBD/TODO. The Task 4 illustrative-then-corrected function is explicit (the corrected version is the requirement). Every test has real assertions. ✅

**3. Type consistency:**
- `Source(text, doc_id, filename, page, score)` defined in Task 3, used in Tasks 4 and 5. ✅
- `Retriever(embedder, qdrant, settings).retrieve(question) -> list[Source]` consistent across Tasks 3 and 5. ✅
- `QdrantStore.search(vector, top_k) -> list[dict]` with keys `{text, doc_id, filename, page, score}` defined in Task 1, consumed in Task 3. ✅
- `ChatRepository.create_session/get_session/add_message/list_messages` defined in Task 2, used in Task 5. ✅
- `build_messages(question, sources, history) -> list[dict]` defined in Task 4, used in Task 5. ✅
- `app.state.session_factory` (exposed in Plan 2 Task 7) reused in Task 5 for streaming-time persistence. ✅

No issues found.