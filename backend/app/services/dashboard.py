from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RiskLabel, SourceType
from app.models.alert import Alert
from app.models.analysis import AnalysisResult
from app.models.content import ContentItem
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    HeatmapCell,
    TopThreatItem,
    TrendPoint,
)
from app.services.cache import get_json, set_json
from app.utils.datetime import utcnow

DASHBOARD_SUMMARY_KEY = "dashboard:summary"


async def get_dashboard_summary(db: AsyncSession) -> DashboardSummaryResponse:
    cached = await get_json(DASHBOARD_SUMMARY_KEY)
    if cached:
        return DashboardSummaryResponse.model_validate(cached)

    now = utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    total_result = await db.execute(
        select(func.count())
        .select_from(ContentItem)
        .where(
            ContentItem.deleted_at.is_(None),
            ContentItem.collected_at >= last_24h,
        )
    )
    total_items_24h = int(total_result.scalar_one())

    open_alerts_result = await db.execute(
        select(func.count()).select_from(Alert).where(Alert.resolved.is_(False))
    )
    open_alerts = int(open_alerts_result.scalar_one())

    avg_result = await db.execute(select(func.coalesce(func.avg(AnalysisResult.risk_score), 0.0)))
    average_risk_score = round(float(avg_result.scalar_one()), 2)

    source_rows = await db.execute(
        select(ContentItem.source, func.count())
        .where(ContentItem.deleted_at.is_(None))
        .group_by(ContentItem.source)
    )
    items_by_source = {SourceType(row[0]): int(row[1]) for row in source_rows.all()}

    trunc_expr = func.date_trunc("day", ContentItem.collected_at)
    trend_rows = await db.execute(
        select(trunc_expr.label("day_trunc"), func.count())
        .where(ContentItem.deleted_at.is_(None), ContentItem.collected_at >= last_7d)
        .group_by(text("1"))
        .order_by(text("1"))
    )
    seven_day_trend = [TrendPoint(day=row[0].date(), count=int(row[1])) for row in trend_rows.all()]

    response = DashboardSummaryResponse(
        total_items_24h=total_items_24h,
        open_alerts=open_alerts,
        average_risk_score=average_risk_score,
        items_by_source=items_by_source,
        seven_day_trend=seven_day_trend,
    )
    await set_json(DASHBOARD_SUMMARY_KEY, response.model_dump(mode="json"), ttl_seconds=60)
    return response


async def get_heatmap(db: AsyncSession) -> list[HeatmapCell]:
    rows = await db.execute(
        select(ContentItem.source, AnalysisResult.risk_label, func.count())
        .join(AnalysisResult, AnalysisResult.content_id == ContentItem.id)
        .where(ContentItem.deleted_at.is_(None))
        .group_by(ContentItem.source, AnalysisResult.risk_label)
        .order_by(ContentItem.source, AnalysisResult.risk_label)
    )
    return [
        HeatmapCell(source=SourceType(row[0]), label=RiskLabel(row[1]), count=int(row[2]))
        for row in rows.all()
    ]


async def get_top_threats(db: AsyncSession, *, limit: int = 10) -> list[TopThreatItem]:
    rows = await db.execute(
        select(ContentItem, AnalysisResult)
        .join(AnalysisResult, AnalysisResult.content_id == ContentItem.id)
        .where(ContentItem.deleted_at.is_(None))
        .order_by(AnalysisResult.risk_score.desc(), AnalysisResult.analyzed_at.desc())
        .limit(limit)
    )

    threats: list[TopThreatItem] = []
    for content, analysis in rows.all():
        text = content.raw_text or ""
        threats.append(
            TopThreatItem(
                content_id=content.id,
                source=content.source,
                author_handle=content.author_handle,
                raw_text_preview=text[:240],
                risk_score=analysis.risk_score,
                risk_label=analysis.risk_label,
                analyzed_at=analysis.analyzed_at,
            )
        )
    return threats
