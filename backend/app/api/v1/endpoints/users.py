import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, require_role, require_dashboard_principal, require_admin
from app.schemas.user import UserCreate, UserRead, UserUpdateRole
from app.schemas.auth import Principal
from app.models.user import User
from app.models.audit import AuditLog
from app.core.security import hash_password, revoke_user_tokens
from app.core.config import settings

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_model=List[UserRead])
async def get_users(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_admin()),
) -> List[UserRead]:
    result = await db.execute(select(User))
    return list(result.scalars().all())


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@_limiter.limit("30/hour")
async def create_user(
    request: Request,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin()),
) -> UserRead:
    result = await db.execute(select(User).where(User.username == payload.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    
    db.add(AuditLog(
        analyst_id=principal.user_id,
        analyst=principal.subject,
        action="USER_CREATED",
        details={"username": payload.username, "role": payload.role}
    ))
    
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
async def get_user_me(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_dashboard_principal),
) -> UserRead:
    if not principal.user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, principal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin()),
) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = False
    
    db.add(AuditLog(
        analyst_id=principal.user_id,
        analyst=principal.subject,
        action="USER_DEACTIVATED",
        details={"user_id": str(user_id), "username": user.username}
    ))
    
    await db.commit()
    await revoke_user_tokens(str(user_id), ttl_seconds=settings.jwt_access_token_expire_minutes * 60)


@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserUpdateRole,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin()),
) -> UserRead:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = payload.role
    
    db.add(AuditLog(
        analyst_id=principal.user_id,
        analyst=principal.subject,
        action="USER_ROLE_CHANGED",
        details={"user_id": str(user_id), "username": user.username, "new_role": payload.role}
    ))
    
    await db.commit()
    await db.refresh(user)
    await revoke_user_tokens(str(user_id), ttl_seconds=settings.jwt_access_token_expire_minutes * 60)
    return user
