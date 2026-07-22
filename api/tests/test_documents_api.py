from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base, get_session
from app.main import create_app
from app.config import get_settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Per-test sqlite FILE (so the background task's own session sees committed rows),
    # a fake qdrant/ollama, and app.state.session_factory pointed at the same factory.
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
    app.state.qdrant = AsyncMock()
    app.state.ollama = AsyncMock()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_creates_row_and_runs_ingest(client, monkeypatch):
    # Patch the background ingest (referenced by name in the router wrapper) to mark the doc done.
    import app.routers.documents as docs
    async def fake_ingest(doc_id, file_path, filename, repo, embedder, qdrant, settings):
        await repo.set_status(doc_id, "done", chunk_count=1, parser_used="pdf")
    monkeypatch.setattr(docs, "ingest_document", fake_ingest)

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


def test_delete_removes_row(client, monkeypatch):
    import app.routers.documents as docs
    async def fake_ingest(doc_id, file_path, filename, repo, embedder, qdrant, settings):
        await repo.set_status(doc_id, "done", chunk_count=1, parser_used="pdf")
    monkeypatch.setattr(docs, "ingest_document", fake_ingest)

    files = {"file": ("m.pdf", b"%PDF-1.4 fake", "application/pdf")}
    doc_id = client.post("/documents/upload", files=files).json()["id"]
    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 204
    assert client.get(f"/documents/{doc_id}").status_code == 404


def test_upload_rejects_unsupported_type(client):
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    r = client.post("/documents/upload", files=files)
    assert r.status_code == 400
    assert "Unsupported" in r.json()["detail"]
