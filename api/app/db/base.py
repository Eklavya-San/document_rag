from collections.abc import AsyncIterator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from loguru import logger
from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
logger.debug("Initializing SQLAlchemy async engine for DSN: {}", _settings.postgres_dsn.split("@")[-1])
async_engine = create_async_engine(_settings.postgres_dsn, future=True)
session_factory = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    logger.debug("Opening AsyncSession")
    async with session_factory() as session:
        try:
            yield session
        except Exception as exc:
            logger.error("Error during database session context: {}", exc)
            raise
        finally:
            logger.debug("Closed AsyncSession")


def _apply_startup_indexes(conn) -> None:
    """Idempotent indexes and column migrations for existing DBs.

    Each ALTER runs in its own savepoint so a 'column already exists' error
    on Postgres (which aborts the whole transaction) only rolls back the
    savepoint, not the outer create_all transaction.
    """
    logger.info("Applying startup index migrations on database connection")
    try:
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)"))
        logger.debug("Index 'ix_chat_messages_session_id' verified or created successfully")
    except Exception as exc:
        logger.warning("Failed to create index ix_chat_messages_session_id: {}", exc)

    for stmt in (
        "ALTER TABLE chat_messages ADD COLUMN grounded BOOLEAN",
        "ALTER TABLE chat_messages ADD COLUMN tokens INTEGER",
    ):
        try:
            with conn.begin_nested():
                conn.execute(text(stmt))
                logger.info("Executed schema migration: {}", stmt)
        except Exception as exc:
            logger.debug("Migration statement {!r} skipped or failed: {}", stmt, exc)
