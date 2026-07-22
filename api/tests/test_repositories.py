import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.repositories import DocumentRepository


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield DocumentRepository(session)
    await engine.dispose()


async def test_create_and_get(repo):
    doc = await repo.create("manual.pdf")
    assert doc.id is not None
    assert doc.status == "pending"
    fetched = await repo.get(doc.id)
    assert fetched.filename == "manual.pdf"


async def test_list_all(repo):
    await repo.create("a.pdf")
    await repo.create("b.pdf")
    docs = await repo.list_all()
    assert len(docs) == 2


async def test_set_status_updates_fields(repo):
    doc = await repo.create("manual.pdf")
    await repo.set_status(doc.id, "done", chunk_count=12, parser_used="pdf")
    fetched = await repo.get(doc.id)
    assert fetched.status == "done"
    assert fetched.chunk_count == 12
    assert fetched.parser_used == "pdf"


async def test_set_failed_records_error(repo):
    doc = await repo.create("manual.pdf")
    await repo.set_status(doc.id, "failed", error="boom")
    fetched = await repo.get(doc.id)
    assert fetched.status == "failed"
    assert fetched.error == "boom"


async def test_delete_removes_row(repo):
    doc = await repo.create("manual.pdf")
    await repo.delete(doc.id)
    assert await repo.get(doc.id) is None


async def test_set_status_updates_without_prior_get():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.db.base import Base
    from app.db.repositories import DocumentRepository
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        repo = DocumentRepository(session)
        doc = await repo.create("m.pdf")
        await repo.set_status(doc.id, "done", chunk_count=3, parser_used="pdf")
        refetched = await repo.get(doc.id)
        assert refetched.status == "done"
        assert refetched.chunk_count == 3
        assert refetched.parser_used == "pdf"
    await engine.dispose()
