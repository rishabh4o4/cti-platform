import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


async def init_redis() -> None:
    """Initialise the shared Redis client. Called once from the FastAPI lifespan."""
    global _redis_client
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> Redis:
    """Return the initialised Redis client. Lazily initializes if needed."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


# Expose redis_client as a module-level alias so health.py can import it
# without changing its import line.  The attribute is populated after init_redis().
class _LazyRedis:
    """Thin proxy that forwards attribute access to the live client."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_redis(), name)


redis_client = _LazyRedis()


async def close_redis() -> None:
    if _redis_client is not None:
        await _redis_client.aclose()


async def get_json(key: str) -> dict[str, Any] | list[Any] | None:
    value = await get_redis().get(key)
    if value is None:
        return None
    return json.loads(value)


async def set_json(key: str, value: dict[str, Any] | list[Any], ttl_seconds: int) -> None:
    await get_redis().set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def delete_key(key: str) -> None:
    await get_redis().delete(key)
