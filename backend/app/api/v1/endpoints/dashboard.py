from app.domain.enums import Role
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_dashboard_principal, require_role
from app.schemas.auth import Principal
from app.schemas.dashboard import DashboardSummaryResponse, HeatmapCell, TopThreatItem
from app.services.dashboard import get_dashboard_summary, get_heatmap, get_top_threats

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> DashboardSummaryResponse:
    return await get_dashboard_summary(db)


@router.get("/heatmap", response_model=list[HeatmapCell])
async def dashboard_heatmap(
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[HeatmapCell]:
    return await get_heatmap(db)


@router.get("/top-threats", response_model=list[TopThreatItem])
async def dashboard_top_threats(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: Principal = Depends(require_role([Role.VIEWER, Role.ANALYST])),
) -> list[TopThreatItem]:
    return await get_top_threats(db, limit=limit)
