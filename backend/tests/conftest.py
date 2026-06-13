"""
Pytest configuration and shared fixtures.

The fixtures here ensure that:
- Tests never connect to a real Redis or PostgreSQL server.
- The FastAPI app's lifespan (init_redis, configure_logging) is fully mocked.
- A single TestClient is shared per test session for the basic suite.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

# ---------------------------------------------------------------------------
# Redis mock — replaces the real Redis client before the app module is used
# ---------------------------------------------------------------------------
_mock_redis = MagicMock()
_mock_redis.aclose = AsyncMock()
_mock_redis.ping = AsyncMock(return_value=True)
_mock_redis.get = AsyncMock(return_value=None)
_mock_redis.set = AsyncMock()
_mock_redis.delete = AsyncMock()
_mock_redis.exists = AsyncMock(return_value=0)


@pytest.fixture(scope="session", autouse=True)
def _patch_redis():
    """Patch cache.init_redis and get_redis for the entire test session."""
    with (
        patch("app.services.cache.init_redis", new_callable=AsyncMock),
        patch("app.services.cache.get_redis", return_value=_mock_redis),
        patch("app.services.cache._redis_client", _mock_redis),
    ):
        yield


# ---------------------------------------------------------------------------
# In-memory SQLite engine for fast unit tests
# ---------------------------------------------------------------------------
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(_TEST_DB_URL, future=True)
_test_session_maker = async_sessionmaker(
    _test_engine, expire_on_commit=False, class_=AsyncSession
)


@pytest.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session backed by an in-memory SQLite database."""
    from app.db.base import Base
    import app.models  # Ensure all models are loaded

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _test_session_maker() as session:
        yield session

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client(_patch_redis) -> TestClient:
    """Return a TestClient that does NOT start a real lifespan (no Redis/DB needed)."""
    from app.main import app

    # Override the lifespan so tests skip Redis init
    with patch("app.main.init_redis", new_callable=AsyncMock):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
