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

    async def chat_stream(self, messages, model=None):

        for p in ["Hel", "lo"]:
            yield p

    async def ping(self):
        return True


class FakeQdrant:
    async def search(self, vector, top_k):
        return [{"id": "c1", "text": "calibrate the sensor", "doc_id": 1, "filename": "m.pdf", "page": 3, "score": 0.9}]


class NoContextQdrant:
    async def search(self, vector, top_k):
        return [{"id": "c0", "text": "x", "doc_id": 1, "filename": "m.pdf", "page": 1, "score": 0.1}]


class DeadOllama:
    async def embed(self, texts):
        raise ConnectionError("ollama down")

    async def chat_stream(self, messages, model=None):

        return
        yield  # make it an async generator

    async def ping(self):
        return False


@pytest.fixture
def app_with_fakes(monkeypatch, tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables on the engine so that short-lived sessions (opened directly
    # from factory) also work.
    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio
    asyncio.run(_init_db())

    async def override_get_session():
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


def test_question_too_long(app_with_fakes, monkeypatch):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    from app.config import get_settings
    monkeypatch.setenv("MAX_QUESTION_CHARS", "10")
    get_settings.cache_clear()
    app.state.settings = get_settings()  # re-read with new env value
    client = _client(app)
    long_q = "x" * 100
    # chat streams; a 422 happens before streaming starts
    r = client.post("/chat", json={"question": long_q})
    assert r.status_code == 422


class StreamCrashOllama:
    async def embed(self, texts):
        return [[0.1, 0.2] for _ in texts]

    async def chat_stream(self, messages, model=None):

        yield "Hel"
        raise RuntimeError("boom")

    async def ping(self):
        return True


def test_503_does_not_create_session(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = DeadOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "how to calibrate?"})
    assert r.status_code == 503
    # a subsequent successful chat must start at session_id 1 (no orphan session from the 503)
    app.state.ollama = FakeOllama()
    r2 = client.post("/chat", json={"question": "how to calibrate?"})
    events = _parse_sse(r2.text)
    assert events[0]["session_id"] == 1


def test_partial_answer_persisted_on_stream_crash(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = StreamCrashOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "how to calibrate?"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    session_id = events[0]["session_id"]
    assert events[-1]["type"] == "done"
    hist = client.get(f"/chat/sessions/{session_id}/messages").json()
    roles = [m["role"] for m in hist]
    assert roles == ["user", "assistant"]
    assert hist[1]["content"] == "Hel"


def test_session_messages_pagination(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "q1"})
    sid = _parse_sse(r.text)[0]["session_id"]
    for q in ("q2", "q3"):
        client.post("/chat", json={"question": q, "session_id": sid})
    msgs = client.get(f"/chat/sessions/{sid}/messages?limit=2&offset=2").json()
    assert len(msgs) == 2  # 4 messages total, skip first 2


def test_chat_threads_filename_filter(app_with_fakes):
    app, factory = app_with_fakes
    seen = {}

    class Q:
        async def search(self, vector, top_k, query_filter=None):
            seen["filter"] = query_filter
            return [{"id":"a","text":"t","doc_id":1,"filename":"m.pdf","page":1,"score":0.9}]

    app.state.ollama = FakeOllama()
    app.state.qdrant = Q()
    client = _client(app)
    client.post("/chat", json={"question": "q", "filename": "m.pdf"})
    assert seen["filter"] is not None


def test_simple_question_uses_small_model(monkeypatch):
    from app.rag.router import pick_model
    from app.config import get_settings
    monkeypatch.setenv("TIERED_MODELS_ENABLED", "true")
    monkeypatch.setenv("OLLAMA_SMALL_LLM_MODEL", "qwen2.5:3b")
    get_settings.cache_clear()
    s = get_settings()
    assert pick_model("what is the voltage", s) == "qwen2.5:3b"
    assert pick_model("explain why the sensor fails and compare the calibration steps", s) == s.ollama_llm_model


def test_tokens_persisted_when_cost_tracking_on(app_with_fakes, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("COST_TRACKING_ENABLED", "true")
    get_settings.cache_clear()
    app, factory = app_with_fakes
    app.state.settings = get_settings()
    app.state.ollama = FakeOllama()

    app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "how to calibrate?"})
    session_id = _parse_sse(r.text)[0]["session_id"]
    hist = client.get(f"/chat/sessions/{session_id}/messages").json()
    assert hist[1]["tokens"] is not None and hist[1]["tokens"] > 0


def test_feedback_endpoint_persists_rating(app_with_fakes):
    app, factory = app_with_fakes
    app.state.ollama = FakeOllama(); app.state.qdrant = FakeQdrant()
    client = _client(app)
    r = client.post("/chat", json={"question": "q"})
    session_id = _parse_sse(r.text)[0]["session_id"]
    msg_id = client.get(f"/chat/sessions/{session_id}/messages").json()[1]["id"]
    fr = client.post(f"/chat/messages/{msg_id}/feedback", json={"rating": 1})
    assert fr.status_code == 204




