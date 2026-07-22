from fastapi.testclient import TestClient
from app.main import create_app


class FakeOllama:
    def __init__(self, ok): self._ok = ok
    async def ping(self): return self._ok


class FakeQdrant:
    def __init__(self, ok): self._ok = ok
    async def ping(self): return self._ok


def _client(ollama_ok=True, qdrant_ok=True):
    app = create_app()
    app.state.ollama = FakeOllama(ollama_ok)
    app.state.qdrant = FakeQdrant(qdrant_ok)
    return TestClient(app)


def test_health_returns_ok():
    r = _client().get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["config"]["ollama_llm_model"]
    assert body["dependencies"]["ollama"] == "ok"
    assert body["dependencies"]["qdrant"] == "ok"


def test_health_reports_dependencies_unreachable():
    r = _client(ollama_ok=False, qdrant_ok=False).get("/health")
    deps = r.json()["dependencies"]
    assert deps["ollama"] == "unreachable"
    assert deps["qdrant"] == "unreachable"
