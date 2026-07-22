import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import get_settings
from app.db.base import Base, async_engine
from app.ollama.client import OllamaClient
from app.qdrant.client import QdrantStore
from app.routers import health


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    qdrant = QdrantStore(app.state.settings)
    try:
        await qdrant.ensure_collection()
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("Qdrant bootstrap skipped: %s", e)
    app.state.qdrant = qdrant

    yield

    await async_engine.dispose()
    await app.state.ollama.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Manual RAG Chatbot", lifespan=_lifespan)
    app.state.settings = settings
    app.state.ollama = OllamaClient(settings)

    app.include_router(health.router)
    return app


app = create_app()
