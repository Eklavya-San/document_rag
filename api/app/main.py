from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from app.config import get_settings
from app.logging_config import setup_logging
from app.db.base import Base, async_engine, session_factory, _apply_startup_indexes
from app.ollama.client import OllamaClient
from app.qdrant.client import QdrantStore
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.rate import limiter
from app.routers import health, documents, chat


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("Starting up FastAPI application and initializing database schema")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_startup_indexes)

    qdrant = QdrantStore(app.state.settings)
    try:
        await qdrant.ensure_collection()
        logger.info("Qdrant collection bootstrap successful")
    except Exception as e:
        logger.warning("Qdrant bootstrap skipped or failed: {}", e)
    app.state.qdrant = qdrant

    yield

    logger.info("Shutting down application and closing database and store connections")
    await async_engine.dispose()
    await app.state.ollama.close()
    await app.state.qdrant.close()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    logger.info("Initializing FastAPI app with configured settings")

    app = FastAPI(title="Manual RAG Chatbot", lifespan=_lifespan)
    app.state.settings = settings
    app.state.ollama = OllamaClient(settings)
    app.state.session_factory = session_factory
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    return app


app = create_app()
