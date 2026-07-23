import asyncio
from app.observability import timed, metrics_snapshot, reset


async def test_timed_records_stage():
    reset()
    async with timed("embed"):
        await asyncio.sleep(0)
    snap = metrics_snapshot()
    assert "embed" in snap
    assert snap["embed"]["count"] == 1


async def test_metrics_p50_p99():
    reset()
    for _ in range(10):
        async with timed("search"):
            await asyncio.sleep(0)
    snap = metrics_snapshot()
    assert snap["search"]["p50"] >= 0
    assert snap["search"]["p99"] >= 0
