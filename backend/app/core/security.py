from datetime import UTC, datetime, timedelta
from typing import Any

import uuid

# Patch passlib's detect_wrap_bug for modern bcrypt
import passlib.handlers.bcrypt
passlib.handlers.bcrypt.detect_wrap_bug = lambda *args: False

from passlib.context import CryptContext
import jwt
import structlog
from jwt import InvalidTokenError

from app.core.config import settings
from app.services.cache import get_redis

log = structlog.get_logger()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
DUMMY_PASSWORD_HASH = pwd_context.hash("dummy_password")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return pwd_context.hash(plain)


def verify_password(candidate: str, hashed: str) -> bool:
    """Verify *candidate* against a bcrypt *hashed* value."""
    return pwd_context.verify(candidate, hashed)


def create_access_token(subject: str, role: str | None = None, user_id: str | None = None, expires_delta: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires,
        "type": "access",
        "role": role,
        "user_id": user_id,
        "jti": jti,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, role: str | None = None, user_id: str | None = None) -> str:
    expires = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires,
        "type": "refresh",
        "role": role,
        "user_id": user_id,
        "jti": jti,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        log.debug("jwt_decode_failed", error=type(exc).__name__)
        return None
    if payload.get("type") != expected_type or not payload.get("sub"):
        return None
    return payload

def decode_access_token(token: str) -> dict[str, Any] | None:
    return decode_token(token, "access")

def decode_refresh_token(token: str) -> dict[str, Any] | None:
    return decode_token(token, "refresh")


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """Blocklist a JWT by its jti until its natural expiry."""
    if ttl_seconds > 0:
        await get_redis().set(f"revoked:jti:{jti}", "1", ex=ttl_seconds)


async def revoke_user_tokens(user_id: str, ttl_seconds: int) -> None:
    """Blocklist all tokens for a user until their natural expiry."""
    if ttl_seconds > 0:
        await get_redis().set(f"revoked:user:{user_id}", "1", ex=ttl_seconds)


async def is_token_revoked(jti: str, user_id: str | None = None) -> bool:
    revoked = await get_redis().exists(f"revoked:jti:{jti}") == 1
    if not revoked and user_id:
        revoked = await get_redis().exists(f"revoked:user:{user_id}") == 1
    return revoked
