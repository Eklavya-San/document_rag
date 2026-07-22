# Plan 1 — Scaffolding & Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project skeleton, env-driven config, a FastAPI app with a health endpoint, and typed clients for Postgres, Qdrant, and the external Ollama — all runnable via `docker compose up` with zero domain logic yet.

**Architecture:** A Python FastAPI backend (`api/`) behind a React frontend (`web/`, stubbed here), a Postgres container for metadata + chat history, a Qdrant container for vectors, and an external Ollama reached via `OLLAMA_BASE_URL`. All config flows through a pydantic-settings `Settings` object loaded from `.env`.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, pydantic-settings, SQLAlchemy 2.0 (async) + asyncpg, qdrant-client, httpx, pytest + pytest-asyncio + aiosqlite (for unit tests), Docker Compose.

## Global Constraints

- Python 3.11; dependencies pinned in `api/requirements.txt`.
- All env-dependent values come from `.env` via `app.config.Settings`; no hardcoded model names, URLs, or DB credentials.
- A committed `.env.example` documents every variable; the real `.env` is gitignored.
- Embedding vector dimension (`EMBED_DIM`) drives Qdrant collection creation at startup.
- External Ollama only — no Ollama container in `docker-compose.yml`.
- No auth/user management in this plan (v1 scope cut).
- Tests run without external services: DB unit tests use aiosqlite; Qdrant/Ollama clients are tested with mocks.

## File Structure (this plan)

```
.env.example
.gitignore
docker-compose.yml
api/
  Dockerfile
  requirements.txt
  app/
    __init__.py
    config.py          # Settings (pydantic-settings) — single source of config
    main.py            # FastAPI app factory + startup hooks
    db/
      __init__.py
      base.py          # async engine, session factory, Base
      models.py        # documents, chat_sessions, chat_messages ORM models
    qdrant/
      __init__.py
      client.py        # QdrantClient wrapper + ensure_collection(dim)
    ollama/
      __init__.py
      client.py        # OllamaClient (httpx) + health check
    routers/
      __init__.py
      health.py        # GET /health
  tests/
    __init__.py
    conftest.py
    test_config.py
    test_health.py
    test_db.py
    test_qdrant.py
    test_llama.py
```

Each file has one responsibility: `config.py` owns settings, `db/base.py` owns the engine/session, `db/models.py` owns ORM definitions, `qdrant/client.py` owns vector-store connectivity, `ollama/client.py` owns the LLM/embedding endpoint, `routers/health.py` owns the health route, `main.py` wires them.

---

### Task 1: Repo scaffolding + `.env.example` + `.gitignore`

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `api/requirements.txt`

**Interfaces:**
- Produces: `.env.example` (the canonical list of env vars the rest of the plan reads).

- [ ] **Step 1: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/

# Env / secrets
.env

# Frontend
web/node_modules/
web/dist/

# Data
/data/
```

- [ ] **Step 2: Create `.env.example`**

```dotenv
# --- Ollama (external) ---
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:32b
OLLAMA_EMBED_MODEL=bge-m3
EMBED_DIM=1024
OLLAMA_NUM_PARALLEL=2

# --- Retrieval / RAG ---
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=50
RETRIEVAL_TOP_K=5
RERANK_ENABLED=false
CHAT_HISTORY_TURNS=6
NO_CONTEXT_THRESHOLD=0.35

# --- Stores ---
QDRANT_URL=http://qdrant:6333
POSTGRES_DSN=postgresql+asyncpg://rag:rag@postgres:5432/rag
DATA_DIR=/data/manuals

# --- App ---
API_HOST=0.0.0.0
API_PORT=8000
```

- [ ] **Step 3: Create `api/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic-settings==2.3.4
SQLAlchemy==2.0.30
asyncpg==0.29.0
aiosqlite==0.20.0
qdrant-client==1.9.1
httpx==0.27.0
python-multipart==0.0.9
pytest==8.2.2
pytest-asyncio==0.23.7
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore .env.example api/requirements.txt
git commit -m "chore: repo scaffolding, .env.example, requirements"
```

---

### Task 2: Settings module (`app/config.py`)

**Files:**
- Create: `api/app/__init__.py`
- Create: `api/app/config.py`
- Create: `api/tests/__init__.py`
- Create: `api/tests/conftest.py`
- Create: `api/tests/test_config.py`

**Interfaces:**
- Produces: `Settings` class and `get_settings()` factory. Properties used by later tasks: `ollama_base_url`, `ollama_llm_model`, `ollama_embed_model`, `embed_dim`, `ollama_num_parallel`, `chunk_size_tokens`, `chunk_overlap_tokens`, `retrieval_top_k`, `rerank_enabled`, `chat_history_turns`, `no_context_threshold`, `qdrant_url`, `postgres_dsn`, `data_dir`, `api_host`, `api_port`.

- [ ] **Step 1: Write the failing test**

`api/tests/test_config.py`:
```python
import os
from app.config import get_settings


def test_settings_reads_env_defaults():
    os.environ["OLLAMA_BASE_URL"] = "http://gpu-box:11434"
    os.environ["OLLAMA_LLM_MODEL"] = "command-r35b"
    os.environ["EMBED_DIM"] = "768"
    os.environ["RERANK_ENABLED"] = "true"
    s = get_settings()
    assert s.ollama_base_url == "http://gpu-box:11434"
    assert s.ollama_llm_model == "command-r35b"
    assert s.embed_dim == 768
    assert s.rerank_enabled is True
    assert s.retrieval_top_k == 5  # default retained
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Write minimal implementation**

`api/app/__init__.py`: (empty file)
```python
```

`api/app/config.py`:
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama (external)
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:32b"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024
    ollama_num_parallel: int = 2

    # Retrieval / RAG
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    retrieval_top_k: int = 5
    rerank_enabled: bool = False
    chat_history_turns: int = 6
    no_context_threshold: float = 0.35

    # Stores
    qdrant_url: str = "http://qdrant:6333"
    postgres_dsn: str = "postgresql+asyncpg://rag:rag@postgres:5432/rag"
    data_dir: str = "/data/manuals"

    # App
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`api/tests/__init__.py`: (empty file)
```python
```

`api/tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/__init__.py api/app/config.py api/tests/__init__.py api/tests/conftest.py api/tests/test_config.py
git commit -m "feat: env-driven Settings module with tests"
```

---

### Task 3: FastAPI app skeleton + `GET /health`

**Files:**
- Create: `api/app/routers/__init__.py`
- Create: `api/app/routers/health.py`
- Create: `api/app/main.py`
- Create: `api/tests/test_health.py`

**Interfaces:**
- Consumes: `get_settings()` from Task 2.
- Produces: `app.main.create_app() -> FastAPI` (used by `Dockerfile`/uvicorn in Task 7 and by every later router registration).

- [ ] **Step 1: Write the failing test**

`api/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "config" in body
    assert body["config"]["ollama_llm_model"]


def test_health_reports_ollama_unreachable():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.json()["dependencies"]["ollama"] in ("ok", "unreachable")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write minimal implementation**

`api/app/routers/__init__.py`: (empty)
```python
```

`api/app/routers/health.py`:
```python
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    settings = request.app.state.settings
    ollama = request.app.state.ollama
    ollama_status = "ok" if await ollama.ping() else "unreachable"
    return {
        "status": "ok",
        "config": {
            "ollama_base_url": settings.ollama_base_url,
            "ollama_llm_model": settings.ollama_llm_model,
            "ollama_embed_model": settings.ollama_embed_model,
            "embed_dim": settings.embed_dim,
        },
        "dependencies": {"ollama": ollama_status},
    }
```

`api/app/main.py`:
```python
from fastapi import FastAPI
from app.config import get_settings
from app.ollama.client import OllamaClient
from app.routers import health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Manual RAG Chatbot")
    app.state.settings = settings
    app.state.ollama = OllamaClient(settings)

    app.include_router(health.router)
    return app


app = create_app()
```

Note: `app.ollama.client.OllamaClient` is created in Task 6. To keep this task independently testable, create a minimal stub now and replace it in Task 6.

`api/app/ollama/__init__.py`: (empty)
```python
```

`api/app/ollama/client.py` (stub — replaced fully in Task 6):
```python
class OllamaClient:
    def __init__(self, settings):
        self.settings = settings

    async def ping(self) -> bool:
        return False  # replaced in Task 6
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_health.py -v`
Expected: PASS (ollama reports "unreachable" against the stub)

- [ ] **Step 5: Commit**

```bash
git add api/app/routers/__init__.py api/app/routers/health.py api/app/main.py api/app/ollama/__init__.py api/app/ollama/client.py api/tests/test_health.py
git commit -m "feat: FastAPI app factory and /health endpoint"
```

---

### Task 4: Postgres async layer + ORM models

**Files:**
- Create: `api/app/db/__init__.py`
- Create: `api/app/db/base.py`
- Create: `api/app/db/models.py`
- Create: `api/tests/test_db.py`
- Create: `api/pytest.ini`
- Modify: `api/tests/conftest.py` (add sqlite test-DSN so `asyncpg` is never imported on the host)

**Interfaces:**
- Consumes: `Settings.postgres_dsn` from Task 2.
- Produces: `Base` (DeclarativeBase), `async_engine`, `get_session()` async generator, and ORM models `Document`, `ChatSession`, `ChatMessage`. Later plans use `Document` (ingestion) and `ChatSession`/`ChatMessage` (chat history).

**Test environment note (important):** Production uses `postgresql+asyncpg://` and runs in the Python 3.11 Docker container, where `asyncpg==0.29.0` installs cleanly. Unit tests run on the host (Python 3.14, where `asyncpg` does NOT build). To keep unit tests working without `asyncpg`, `conftest.py` sets `POSTGRES_DSN` to a sqlite file **before any app import**, so the module-level engine in `base.py` and the app lifespan both bind to sqlite and the `asyncpg` driver is never imported. The corrected test below creates its own sqlite engine bound to the real `Base`/`Document` (no `importlib.reload` — reloading breaks the model→`Base` binding).

- [ ] **Step 1: Add test config and write the failing test**

`api/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

Modify `api/tests/conftest.py` to (replaces the Task 2 version):
```python
import os
import sys
from pathlib import Path

import pytest

# Unit tests run against sqlite so the asyncpg driver is never imported
# (asyncpg 0.29.0 does not build on Python 3.14; prod runs in 3.11 Docker).
os.environ.setdefault("POSTGRES_DSN", "sqlite+aiosqlite:////tmp/rag_test.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
```

`api/tests/test_db.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.models import Document, ChatSession, ChatMessage


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_can_insert_and_read_document(session: AsyncSession):
    doc = Document(filename="manual.pdf", status="pending")
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    assert doc.id is not None
    assert doc.status == "pending"
    assert doc.chunk_count == 0


async def test_chat_session_has_messages_relationship(session: AsyncSession):
    cs = ChatSession(title="t")
    msg = ChatMessage(role="user", content="hi")
    cs.messages.append(msg)
    session.add(cs)
    await session.commit()
    await session.refresh(cs)
    assert cs.id is not None
    assert cs.messages[0].role == "user"
```

- [ ] **Step 2: Install test deps and run test to verify it fails**

Install (host venv; do NOT install `asyncpg` — tests use sqlite):
```
cd api && . .venv/bin/activate
pip install SQLAlchemy==2.0.30 aiosqlite==0.20.0 pytest-asyncio==0.23.7
```
Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write minimal implementation**

`api/app/db/__init__.py`: (empty)
```python
```

`api/app/db/base.py`:
```python
from collections.abc import AsyncIterator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
async_engine = create_async_engine(_settings.postgres_dsn, future=True)
_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session
```

`api/app/db/models.py`:
```python
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    parser_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    session: Mapped["ChatSession"] = relationship(back_populates="messages")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Wire table creation into app startup**

Add to `api/app/main.py` `create_app`, before `return app`:
```python
from contextlib import asynccontextmanager
from app.db.base import Base, async_engine


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Manual RAG Chatbot", lifespan=_lifespan)
    app.state.settings = settings
    app.state.ollama = OllamaClient(settings)
    app.include_router(health.router)
    return app
```

- [ ] **Step 6: Commit**

```bash
git add api/app/db/ api/tests/test_db.py api/app/main.py
git commit -m "feat: async SQLAlchemy layer + documents/chat ORM models"
```

---

### Task 5: Qdrant client + `ensure_collection(dim)`

**Files:**
- Create: `api/app/qdrant/__init__.py`
- Create: `api/app/qdrant/client.py`
- Create: `api/tests/test_qdrant.py`

**Interfaces:**
- Consumes: `Settings.qdrant_url`, `Settings.embed_dim`, `Settings.ollama_embed_model`.
- Produces: `QdrantStore` with `ensure_collection() -> None`. Later plans call `ensure_collection()` at startup and add `upsert()`/`search()` methods.

- [ ] **Step 1: Write the failing test**

`api/tests/test_qdrant.py`:
```python
from unittest.mock import MagicMock, patch
from app.config import Settings
from app.qdrant.client import QdrantStore


def test_ensure_collection_creates_with_configured_dim():
    settings = Settings(qdrant_url="http://qdrant:6333", embed_dim=768, ollama_embed_model="bge-m3")
    store = QdrantStore(settings)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists.return_value = False
        store.ensure_collection()
    mock_client.collection_exists.assert_called_once_with("manuals")
    mock_client.create_collection.assert_called_once()
    _, kwargs = mock_client.create_collection.call_args
    assert kwargs["vectors_config"].size == 768  # VectorParams is a pydantic model


def test_ensure_collection_skips_when_exists():
    settings = Settings(qdrant_url="http://qdrant:6333", embed_dim=1024)
    store = QdrantStore(settings)
    with patch.object(store, "_client") as mock_client:
        mock_client.collection_exists.return_value = True
        store.ensure_collection()
    mock_client.create_collection.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_qdrant.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.qdrant'`

- [ ] **Step 3: Write minimal implementation**

`api/app/qdrant/__init__.py`: (empty)
```python
```

`api/app/qdrant/client.py`:
```python
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

COLLECTION = "manuals"


class QdrantStore:
    def __init__(self, settings):
        self.settings = settings
        self._client = QdrantClient(url=settings.qdrant_url)

    def ensure_collection(self) -> None:
        if self._client.collection_exists(COLLECTION):
            return
        self._client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(
                size=self.settings.embed_dim,
                distance=qm.Distance.COSINE,
            ),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_qdrant.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/qdrant/ api/tests/test_qdrant.py
git commit -m "feat: Qdrant client with env-driven collection bootstrap"
```

---

### Task 6: Ollama client (httpx) + `ping()`

**Files:**
- Modify: `api/app/ollama/client.py` (replace stub from Task 3)
- Create: `api/tests/test_ollama.py`

**Interfaces:**
- Consumes: `Settings.ollama_base_url`, `Settings.ollama_llm_model`, `Settings.ollama_embed_model`.
- Produces: `OllamaClient.ping() -> bool`, `OllamaClient.embed(texts: list[str]) -> list[list[float]]`, `OllamaClient.chat_stream(messages, model) -> AsyncIterator[str]` (signatures used by Plans 2 & 3; only `ping` is exercised here, but defining the others now locks the interface).

- [ ] **Step 1: Write the failing test**

`api/tests/test_ollama.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.config import Settings
from app.ollama.client import OllamaClient


@pytest.mark.asyncio
async def test_ping_true_on_200():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        instance = MockClient.return_value
        instance.__aenter__.return_value = instance
        instance.get = AsyncMock(return_value=mock_resp)
        assert await client.ping() is True


@pytest.mark.asyncio
async def test_ping_false_on_error():
    client = OllamaClient(Settings(ollama_base_url="http://gpu:11434"))
    with patch("app.ollama.client.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__.return_value = instance
        instance.get = AsyncMock(side_effect=httpx.ConnectError("nope"))
        assert await client.ping() is False
```

> Note: add `from unittest.mock import MagicMock` to the imports at the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_ollama.py -v`
Expected: FAIL — `ping` returns the stub's hardcoded `False`, so `test_ping_true_on_200` fails.

- [ ] **Step 3: Write minimal implementation** (replace `api/app/ollama/client.py`)

```python
from collections.abc import AsyncIterator
import httpx


class OllamaClient:
    def __init__(self, settings):
        self.settings = settings
        self._base = settings.ollama_base_url.rstrip("/")

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{self._base}/api/embed",
                json={"model": self.settings.ollama_embed_model, "input": texts},
            )
            r.raise_for_status()
            return r.json()["embeddings"]

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream(
                "POST",
                f"{self._base}/api/chat",
                json={"model": model or self.settings.ollama_llm_model,
                      "messages": messages, "stream": True},
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    import json
                    chunk = json.loads(line)
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        yield piece
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_ollama.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/ollama/client.py api/tests/test_ollama.py
git commit -m "feat: Ollama httpx client with ping, embed, chat_stream"
```

---

### Task 7: Qdrant bootstrap at startup + `docker-compose.yml` + `Dockerfile`

**Files:**
- Modify: `api/app/main.py` (add Qdrant ensure_collection to lifespan)
- Create: `api/Dockerfile`
- Create: `docker-compose.yml`
- Create: `web/Dockerfile` (stub, used in Plan 4)

**Interfaces:**
- Produces: a runnable stack via `docker compose up` exposing the API on `API_PORT`.

- [ ] **Step 1: Add Qdrant bootstrap to app lifespan**

In `api/app/main.py`, inside `_lifespan`, after the `create_all` block and before `yield`:
```python
from app.qdrant.client import QdrantStore

    qdrant = QdrantStore(app.state.settings)
    qdrant.ensure_collection()
    app.state.qdrant = qdrant
```

- [ ] **Step 2: Create `api/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `web/Dockerfile` (stub for Plan 4)**

```dockerfile
FROM nginx:alpine
# Replaced in Plan 4 with the built React SPA.
COPY index.html /usr/share/nginx/html/index.html
```

And create `web/index.html`:
```html
<!doctype html><html><body>Frontend comes in Plan 4.</body></html>
```

- [ ] **Step 4: Create `docker-compose.yml`**

```yaml
services:
  web:
    build: ./web
    ports:
      - "8080:80"
    depends_on: [api]

  api:
    build: ./api
    env_file: .env
    environment:
      - POSTGRES_DSN=postgresql+asyncpg://rag:rag@postgres:5432/rag
      - QDRANT_URL=http://qdrant:6333
      - DATA_DIR=/data/manuals
    volumes:
      - manuals:/data/manuals
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_started

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: rag
      POSTGRES_PASSWORD: rag
      POSTGRES_DB: rag
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rag"]
      interval: 5s
      timeout: 3s
      retries: 10

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrantdata:/qdrant/storage

volumes:
  manuals:
  pgdata:
  qdrantdata:
```

- [ ] **Step 5: Integration smoke test**

Run:
```bash
docker compose up -d --build
sleep 10
curl -s http://localhost:8000/health
docker compose down
```
Expected: JSON with `"status":"ok"` and `"dependencies":{"ollama":"unreachable"}` (Ollama is external/not running here).

- [ ] **Step 6: Commit**

```bash
git add api/app/main.py api/Dockerfile web/Dockerfile web/index.html docker-compose.yml
git commit -m "feat: docker-compose stack + Qdrant bootstrap at startup"
```

---

## Self-Review

**1. Spec coverage (Plan 1 scope = scaffolding + infra + clients):**
- `.env`-driven config → Task 1 (`.env.example`) + Task 2 (`Settings`). ✅
- External Ollama, no Ollama container → Task 6 (client) + Task 7 (compose has no ollama service). ✅
- Postgres metadata + chat history schema → Task 4 (`Document`, `ChatSession`, `ChatMessage`). ✅
- Qdrant collection with env-driven `EMBED_DIM` → Task 5. ✅
- Concurrency-ready async API → Task 3 (FastAPI async) + Task 6 (httpx async). ✅
- Health endpoint for Ollama reachability → Task 3 + Task 6. ✅
- Items deferred to later plans (ingestion, retrieval, `/chat`, `/documents`, frontend) are intentionally out of Plan 1 scope and listed in the roadmap. ✅

**2. Placeholder scan:** No TBD/TODO/"add error handling" steps. The Task 3 Ollama stub is explicitly marked and replaced in Task 6 — not a placeholder, it's a staged interface. ✅

**3. Type consistency:** `Settings` field names (`ollama_base_url`, `ollama_llm_model`, `ollama_embed_model`, `embed_dim`, `qdrant_url`, `postgres_dsn`) are used identically in Tasks 2, 3, 5, 6, 7. `OllamaClient.__init__(settings)`, `QdrantStore.__init__(settings)` signatures match across consumers. `Base`, `get_session`, `Document` referenced consistently in Task 4 and main.py. ✅

No issues found.