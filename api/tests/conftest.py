import os
import sys
from pathlib import Path

import pytest

# Unit tests run against sqlite so the asyncpg driver is never imported
# (asyncpg 0.29.0 does not build on Python 3.14; prod runs in 3.11 Docker).
os.environ.setdefault("POSTGRES_DSN", "sqlite+aiosqlite:////tmp/rag_test.db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
