from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

from sqlalchemy.pool import NullPool

import asyncio

_engine_cache = {}

def get_engine():
    loop = asyncio.get_running_loop()
    if loop not in _engine_cache:
        _engine_cache[loop] = create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            future=True,
            pool_pre_ping=True,
            poolclass=NullPool,
            connect_args={"server_settings": {"statement_timeout": "30000"}},
        )
    return _engine_cache[loop]

def async_session_maker():
    return async_sessionmaker(
        get_engine(),
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
