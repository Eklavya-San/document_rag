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
        assert points[0]["payload"]["filename"] == "m.pdf"
        assert points[0]["payload"]["language"] == "auto"
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
