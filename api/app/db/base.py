from collections.abc import AsyncIterator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
async_engine = create_async_engine(_settings.postgres_dsn, future=True)
session_factory = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


import logging

logger = logging.getLogger(__name__)


def _apply_startup_indexes(conn) -> None:
    """Idempotent indexes and column migrations for existing DBs.

    Each ALTER runs in its own savepoint so a 'column already exists' error
    on Postgres (which aborts the whole transaction) only rolls back the
    savepoint, not the outer create_all transaction.
    """
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_messages_session_id ON chat_messages (session_id)"))
    for stmt in (
        "ALTER TABLE chat_messages ADD COLUMN grounded BOOLEAN",
        "ALTER TABLE chat_messages ADD COLUMN tokens INTEGER",
    ):
        try:
            with conn.begin_nested():
                conn.execute(text(stmt))
        except Exception as exc:
            logger.debug("Migration statement %r skipped or failed: %s", stmt, exc)


