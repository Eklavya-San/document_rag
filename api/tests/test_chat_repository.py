import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base
from app.db.repositories import ChatRepository


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        yield ChatRepository(session)
    await engine.dispose()


async def test_create_and_get_session(repo):
    sess = await repo.create_session("how to calibrate?")
    assert sess.id is not None
    fetched = await repo.get_session(sess.id)
    assert fetched.title == "how to calibrate?"


async def test_add_and_list_messages(repo):
    sess = await repo.create_session()
    await repo.add_message(sess.id, "user", "hi")
    await repo.add_message(sess.id, "assistant", "hello", sources_json=[{"filename": "m.pdf", "page": 1}])
    msgs = await repo.list_messages(sess.id, limit=10)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].sources_json == [{"filename": "m.pdf", "page": 1}]


async def test_list_messages_returns_last_n_oldest_first(repo):
    sess = await repo.create_session()
    for i in range(5):
        await repo.add_message(sess.id, "user", f"q{i}")
    msgs = await repo.list_messages(sess.id, limit=3)
    assert [m.content for m in msgs] == ["q2", "q3", "q4"]
