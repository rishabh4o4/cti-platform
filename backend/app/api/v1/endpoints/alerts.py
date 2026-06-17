import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.api.deps import require_admin, get_db, require_dashboard_principal, require_role
from app.domain.enums import RiskLabel, SourceType, Role
from app.schemas.alert import (
    AlertConfigRequest,
    AlertConfigResponse,
    AlertRead,
    AlertResolveRequest,
)
from app.schemas.auth import Principal
from app.services.alerts import get_alert_config, list_alerts, resolve_alert, set_alert_config
from app.models.audit import AuditLog
import json
from app.core.security import decode_access_token, is_token_revoked
from app.services.websocket import manager

router = APIRouter()


@router.get("/", response_model=list[AlertRead])
async def get_alerts(
    severity: RiskLabel | None = None,
    source: SourceType | None = None,
    resolved: bool | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[AlertRead]:
    return await list_alerts(
        db,
        severity=severity,
        source=source,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )


@router.patch("/{alert_id}/resolve", response_model=AlertRead)
async def resolve_alert_endpoint(
    alert_id: uuid.UUID,
    payload: AlertResolveRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> AlertRead:
    alert = await resolve_alert(
        db,
        alert_id=alert_id,
        resolved_by=principal.subject,
        analyst_note=payload.analyst_note,
        suppress_minutes=payload.suppress_minutes,
        commit=False,
    )
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
        
    db.add(AuditLog(
        content_id=alert.content_id,
        analyst=principal.subject,
        action="ALERT_RESOLVED",
        details={"alert_id": str(alert_id), "note": payload.analyst_note}
    ))
    await db.commit()
        
    return AlertRead.model_validate(alert)


# IMPORTANT: Route registration order matters in FastAPI.
# Static paths (/config) MUST be declared before parameterised paths (/{alert_id})
# to prevent the parameter from shadowing the static route.
@router.get("/config", response_model=AlertConfigResponse)
async def read_alert_config(
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> AlertConfigResponse:
    return await get_alert_config()


@router.post("/config", response_model=AlertConfigResponse)
async def update_alert_config(
    payload: AlertConfigRequest,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_admin()),
) -> AlertConfigResponse:
    if payload.critical_threshold < payload.high_threshold:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="critical_threshold must be greater than or equal to high_threshold.",
        )
        
    old_config = await get_alert_config()
    new_config = await set_alert_config(payload)
    
    db.add(AuditLog(
        analyst=principal.subject,
        action="CONFIG_UPDATED",
        details={
            "previous": old_config.model_dump(),
            "new": new_config.model_dump()
        }
    ))
    await db.commit()
    
    return new_config

@router.websocket("/ws")
async def websocket_alerts(websocket: WebSocket):
    requested = websocket.scope.get("subprotocols", [])
    if requested and "v1.alerts" not in requested:
        await websocket.close(code=status.WS_1002_PROTOCOL_ERROR, reason="Unsupported subprotocol")
        return
    
    await websocket.accept(subprotocol="v1.alerts" if "v1.alerts" in requested else None)
    try:
        data = await websocket.receive_json()
        if not isinstance(data, dict) or data.get("type") != "auth" or not data.get("token"):
            await websocket.close(code=4001, reason="Missing or invalid auth frame")
            return
            
        token = data.get("token")
        payload = decode_access_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return
            
        if payload.get("jti") and await is_token_revoked(payload["jti"], payload.get("user_id")):
            await websocket.close(code=4001, reason="Token revoked")
            return
            
        accepted = await manager.connect(websocket)
        if not accepted:
            return
            
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        await websocket.close(code=4001, reason="Invalid frame")

