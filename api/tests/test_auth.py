import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from app.auth import require_api_key


def _app():
    app = FastAPI()

    @app.get("/protected")
    async def protected(_=Depends(require_api_key)):
        return {"ok": True}
    return app


def test_no_key_rejected_when_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(_app())
    r = client.get("/protected")
    assert r.status_code == 401


def test_correct_key_accepted(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(_app())
    r = client.get("/protected", headers={"X-API-Key": "secret"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_auth_disabled_when_key_unset(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(_app())
    r = client.get("/protected")
    assert r.status_code == 200
