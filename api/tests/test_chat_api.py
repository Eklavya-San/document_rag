import json
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
    assert tokens == "I couldn't find this in the manuals."
    assert [e for e in events if e["type"] == "sources"][0]["sources"] == []


def test_chat_ollama_unreachable_returns_503(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = DeadOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)

    r = client.post("/chat", json={"question": "how to calibrate?"})
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"].lower()


def test_chat_returns_404_for_missing_session(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "x", "session_id": 999999})
    assert r.status_code == 404


def test_session_messages_404_for_missing_session(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.get("/chat/sessions/999999/messages")
    assert r.status_code == 404
