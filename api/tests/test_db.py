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
    from sqlalchemy import select
    cs = ChatSession(title="t")
    msg = ChatMessage(role="user", content="hi")
    cs.messages.append(msg)
    session.add(cs)
    await session.commit()
    assert cs.id is not None
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.session_id == cs.id)
    )
    persisted = result.scalar_one()
    assert persisted.role == "user"
    assert persisted.session_id == cs.id


async def test_session_id_index_exists():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.base import Base, _apply_startup_indexes
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_startup_indexes)
    async with engine.connect() as conn:
        import sqlalchemy
        result = await conn.execute(sqlalchemy.text("PRAGMA index_list('chat_messages')"))
        names = [row[1] for row in result]
    await engine.dispose()
    assert any("session_id" in n for n in names)


async def test_apply_startup_indexes_idempotent():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.db.base import Base, _apply_startup_indexes

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Apply twice to verify idempotency and savepoint exception handling
        await conn.run_sync(_apply_startup_indexes)
        await conn.run_sync(_apply_startup_indexes)
    await engine.dispose()
