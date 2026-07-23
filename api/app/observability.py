import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

_BUFFER: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))


def reset() -> None:
    _BUFFER.clear()


@asynccontextmanager
async def timed(stage: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        _BUFFER[stage].append((time.perf_counter() - start) * 1000.0)


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[idx]


def metrics_snapshot() -> dict:
    out = {}
    for stage, dq in _BUFFER.items():
        vals = list(dq)
        out[stage] = {
            "count": len(vals),
            "p50": _pct(vals, 0.5),
            "p99": _pct(vals, 0.99),
        }
    return out
