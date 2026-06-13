import uuid

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RiskLabel
from app.models.analysis import AnalysisResult
from app.models.content import ContentItem
from app.schemas.analysis import ScoreBucket


async def get_latest_analysis(db: AsyncSession, content_id: uuid.UUID) -> AnalysisResult | None:
    result = await db.execute(
        select(AnalysisResult)
        .where(AnalysisResult.content_id == content_id)
        .order_by(AnalysisResult.analyzed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_analysis_result(
    db: AsyncSession,
    *,
    content_id: uuid.UUID,
    risk_score: float,
    risk_label: RiskLabel,
    nlp_flags: dict,
    vision_flags: dict,
    score_breakdown: dict,
    model_version: str,
    engine_version: str | None = None,
    weights_snapshot: dict | None = None,
    data_confidence: str | None = None,
) -> AnalysisResult:
    analysis = AnalysisResult(
        content_id=content_id,
        risk_score=risk_score,
        risk_label=risk_label,
        nlp_flags=nlp_flags,
        vision_flags=vision_flags,
        score_breakdown=score_breakdown,
        model_version=model_version,
        engine_version=engine_version,
        weights_snapshot=weights_snapshot,
        data_confidence=data_confidence,
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis


async def enqueue_reanalysis(db: AsyncSession, content_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(ContentItem.id).where(ContentItem.id == content_id, ContentItem.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        return False

    from app.tasks.workflow import enqueue_analysis_workflow

    enqueue_analysis_workflow(content_id)
    return True


async def get_analysis_stats(
    db: AsyncSession,
) -> tuple[int, list[tuple[RiskLabel, int]], list, list[ScoreBucket]]:
    total_result = await db.execute(select(func.count()).select_from(AnalysisResult))
    total = int(total_result.scalar_one())

    label_result = await db.execute(
        select(AnalysisResult.risk_label, func.count())
        .group_by(AnalysisResult.risk_label)
        .order_by(AnalysisResult.risk_label)
    )
    label_counts = [(row[0], int(row[1])) for row in label_result.all()]

    source_result = await db.execute(
        select(ContentItem.source, func.count())
        .join(AnalysisResult, AnalysisResult.content_id == ContentItem.id)
        .group_by(ContentItem.source)
    )
    source_breakdown = [(row[0], int(row[1])) for row in source_result.all()]

    # Bucketing is done in SQL to avoid fetching all scores into Python memory.
    bucket_expr = case(
        (AnalysisResult.risk_score < 25, "0-24"),
        (AnalysisResult.risk_score < 50, "25-49"),
        (AnalysisResult.risk_score < 65, "50-64"),
        (AnalysisResult.risk_score < 85, "65-84"),
        else_="85-100",
    )
    bucket_result = await db.execute(
        select(bucket_expr, func.count()).group_by(bucket_expr)
    )
    bucket_map: dict[str, int] = {row[0]: int(row[1]) for row in bucket_result.all()}
    ordered_buckets = ["0-24", "25-49", "50-64", "65-84", "85-100"]
    distribution = [
        ScoreBucket(bucket=b, count=bucket_map.get(b, 0)) for b in ordered_buckets
    ]

    return total, label_counts, source_breakdown, distribution
