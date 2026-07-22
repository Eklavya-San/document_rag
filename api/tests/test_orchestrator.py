import asyncio
import os
import tempfile
import threading
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
        all_points = [p for c in qdrant.upsert.call_args_list for p in c.kwargs["points"]]
        assert all_points
        assert all(p["payload"]["doc_id"] == doc.id for p in all_points)
        assert all_points[0]["payload"]["page"] == 1
        assert any("serviced" in p["payload"]["text"] for p in all_points)
        assert all(p["payload"]["filename"] == "m.pdf" for p in all_points)
        assert all(p["payload"]["language"] == "auto" for p in all_points)
        assert len(all_points) == fetched.chunk_count
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


async def test_parse_runs_off_event_loop_thread(monkeypatch):
    import app.ingestion.orchestrator as orch
    main_thread = threading.get_ident()
    seen = {}

    def spy_parse(path, filename):
        seen["thread"] = threading.get_ident()
        from app.ingestion.parsers import Page
        return [Page(number=1, text="serviced annually")]

    monkeypatch.setattr(orch, "parse_file", spy_parse)
    repo, doc, engine, session = await _repo_with_one_doc("m.pdf")
    embedder = AsyncMock(); embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock(); qdrant.upsert = AsyncMock()
    await ingest_document(doc.id, "/dev/null", "m.pdf", repo, embedder, qdrant, Settings())
    assert seen["thread"] != main_thread, "parse_file must run in a worker thread, not the event loop thread"
    await session.close(); await engine.dispose()


async def test_partial_failure_cleans_qdrant_and_marks_failed():
    repo, doc, engine, session = await _repo_with_one_doc("m.pdf")
    embedder = AsyncMock(); embedder.embed = AsyncMock(return_value=[[0.1, 0.2]])
    qdrant = AsyncMock()
    qdrant.upsert = AsyncMock(side_effect=RuntimeError("qdrant full"))
    qdrant.delete_by_doc = AsyncMock()
    await ingest_document(doc.id, "/dev/null", "m.pdf", repo, embedder, qdrant, Settings())
    fetched = await repo.get(doc.id)
    assert fetched.status == "failed"
    qdrant.delete_by_doc.assert_awaited_with(doc.id)
    await session.close(); await engine.dispose()


async def test_multi_batch_upserts_per_batch(monkeypatch):
    import app.ingestion.orchestrator as orch
    monkeypatch.setattr(orch, "EMBED_BATCH", 2)
    repo, doc, engine, session = await _repo_with_one_doc("m.pdf")
    # produce 5 chunks via a fake parse
    from app.ingestion.parsers import Page
    monkeypatch.setattr(orch, "parse_file", lambda p, f: [Page(number=1, text="c " * 4000)])
    embedder = AsyncMock()
    embedder.embed = AsyncMock(side_effect=lambda texts: [[0.1] for _ in texts])
    qdrant = AsyncMock(); qdrant.upsert = AsyncMock(); qdrant.delete_by_doc = AsyncMock()
    await ingest_document(doc.id, "/dev/null", "m.pdf", repo, embedder, qdrant, Settings())
    assert qdrant.upsert.await_count >= 3  # 5 chunks in batches of 2 -> 3 upserts
    total_points = sum(len(c.kwargs["points"]) for c in qdrant.upsert.call_args_list)
    assert total_points == 5
    fetched = await repo.get(doc.id)
    assert fetched.status == "done" and fetched.chunk_count == 5
    await session.close(); await engine.dispose()
