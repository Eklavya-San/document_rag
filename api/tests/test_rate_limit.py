import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.db.base import Base, get_session
from app.main import create_app
from app.config import get_settings


def test_chat_rate_limit_returns_429(monkeypatch, tmp_path):
    monkeypatch.setenv("CHAT_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init_db())

    async def override_get_session():
        async with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    app.state.session_factory = factory

    class FakeOllama:
        async def embed(self, texts):
            return [[0.1] for _ in texts]

        async def chat_stream(self, messages):
            yield "ok"

        async def ping(self):
            return True

        async def close(self):
            pass

    class FakeQdrant:
        async def search(self, vector, top_k):
            return []

        async def ping(self):
            return True

        async def close(self):
            pass

    app.state.ollama = FakeOllama()
    app.state.qdrant = FakeQdrant()
    client = TestClient(app)

    for _ in range(2):
        assert client.post("/chat", json={"question": "q"}).status_code == 200
    assert client.post("/chat", json={"question": "q"}).status_code == 429
