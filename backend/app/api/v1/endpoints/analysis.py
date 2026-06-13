from app.domain.enums import Role
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.schemas.analysis import (
    AnalysisResultRead,
    AnalysisResultUpdate,
    AnalysisStatsResponse,
    AnalysisTriggerResponse,
    RiskLabelCount,
    SourceCount,
)
from app.schemas.auth import Principal
from app.services.analysis import enqueue_reanalysis, get_analysis_stats, get_latest_analysis
from app.models.audit import AuditLog

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


@router.get("/stats", response_model=AnalysisStatsResponse)
async def analysis_stats(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> AnalysisStatsResponse:
    total, label_counts, source_breakdown, distribution = await get_analysis_stats(db)
    return AnalysisStatsResponse(
        total_analyzed=total,
        label_counts=[
            RiskLabelCount(label=label, count=count) for label, count in label_counts
        ],
        source_breakdown=[
            SourceCount(source=str(source), count=count) for source, count in source_breakdown
        ],
        score_distribution=distribution,
    )


@router.post(
    "/trigger/{content_id}",
    response_model=AnalysisTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@_limiter.limit("5/minute")
async def trigger_analysis(
    request: Request,
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> AnalysisTriggerResponse:
    enqueued = await enqueue_reanalysis(db, content_id)
    if not enqueued:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content item not found.",
        )
        
    db.add(AuditLog(
        content_id=content_id,
        analyst_id=principal.user_id,
        analyst=principal.subject,
        action="ANALYSIS_TRIGGERED",
        details={"content_id": str(content_id)}
    ))
    await db.commit()
    
    return AnalysisTriggerResponse(
        content_id=content_id,
        enqueued=True,
        message="Analysis workflow enqueued.",
    )


@router.get("/{content_id}", response_model=AnalysisResultRead)
async def get_analysis(
    content_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> AnalysisResultRead:
    analysis = await get_latest_analysis(db, content_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found.",
        )
    return AnalysisResultRead.model_validate(analysis)


@router.patch("/{content_id}", response_model=AnalysisResultRead)
async def update_analysis(
    content_id: uuid.UUID,
    payload: AnalysisResultUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_role([Role.ANALYST])),
) -> AnalysisResultRead:
    analysis = await get_latest_analysis(db, content_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis result not found.",
        )
    
    if payload.tactics is not None:
        analysis.tactics = payload.tactics
        audit = AuditLog(
            content_id=content_id,
            analyst=principal.subject,
            action="ANALYSIS_UPDATED",
            details={"field": "tactics", "value": payload.tactics}
        )
        db.add(audit)
    if payload.techniques is not None:
        analysis.techniques = payload.techniques
        audit = AuditLog(
            content_id=content_id,
            analyst=principal.subject,
            action="ANALYSIS_UPDATED",
            details={"field": "techniques", "value": payload.techniques}
        )
        db.add(audit)
        
    await db.commit()
    await db.refresh(analysis)
    return AnalysisResultRead.model_validate(analysis)
