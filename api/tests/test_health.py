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
