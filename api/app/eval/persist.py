from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import EvalRun


async def persist_run(session: AsyncSession, summary: dict) -> EvalRun:
    run = EvalRun(summary=summary)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
