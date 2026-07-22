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
    cs = ChatSession(title="t")
    msg = ChatMessage(role="user", content="hi")
    cs.messages.append(msg)
    session.add(cs)
    await session.commit()
    assert cs.id is not None
    assert cs.messages[0].role == "user"
