import secrets
from datetime import timedelta, datetime, UTC

from fastapi import APIRouter, HTTPException, Request, status, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import uuid
import json
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, is_token_revoked, verify_password, revoke_token, DUMMY_PASSWORD_HASH
from app.schemas.auth import TokenRequest, TokenResponse, Principal
from app.api.deps import get_db, require_dashboard_principal
from app.models.user import User
from app.models.audit import AuditLog
from fastapi import Response

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


@router.post("/token", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def issue_token(
    request: Request,
    response: Response,
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    ip_address = request.client.host if request.client else "unknown"

    if not user:
        verify_password(payload.password, DUMMY_PASSWORD_HASH)
        db.add(AuditLog(analyst="system", action="USER_LOGIN_FAILED", details={"username": payload.username, "ip_address": ip_address}))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not verify_password(payload.password, user.hashed_password):
        db.add(AuditLog(analyst="system", action="USER_LOGIN_FAILED", details={"username": payload.username, "ip_address": ip_address}))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    if not user.is_active:
        db.add(AuditLog(analyst="system", action="USER_LOGIN_FAILED", details={"username": payload.username, "ip_address": ip_address, "reason": "Inactive user"}))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive or deleted."
        )

    user.last_login = datetime.now(UTC)
    db.add(AuditLog(analyst=user.username, action="USER_LOGIN", details={"ip_address": ip_address}))
    await db.commit()

    access_token = create_access_token(
        subject=user.username,
        role=user.role,
        user_id=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = create_refresh_token(
        subject=user.username,
        role=user.role,
        user_id=str(user.id),
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
        
    payload = decode_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    if payload.get("jti") and await is_token_revoked(payload["jti"], payload.get("user_id")):
        raise HTTPException(status_code=401, detail="Token revoked")
        
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive or deleted.")
        
    db.add(AuditLog(
        analyst_id=user.id,
        analyst=user.username,
        action="TOKEN_REFRESHED",
        details={"ip_address": request.client.host if request.client else "unknown"}
    ))
    await db.commit()
        
    access_token = create_access_token(
        subject=user.username,
        role=user.role,
        user_id=str(user.id),
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return TokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_dashboard_principal)
):
    ip_address = request.client.host if request.client else "unknown"
    db.add(AuditLog(analyst=principal.subject, action="USER_LOGOUT", details={"ip_address": ip_address}))
    await db.commit()
    if principal.jti and principal.exp:
        ttl = max(0, principal.exp - int(datetime.now(UTC).timestamp()))
        await revoke_token(str(principal.jti), ttl)
        
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_refresh_token(refresh_token)
        if payload and payload.get("jti") and payload.get("exp"):
            ttl = max(0, payload["exp"] - int(datetime.now(UTC).timestamp()))
            await revoke_token(str(payload["jti"]), ttl)
            
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh",
        httponly=True,
        secure=True,
        samesite="strict"
    )
    return None
