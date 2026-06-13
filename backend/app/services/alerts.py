import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.domain.enums import RiskLabel, SourceType
from app.models.alert import Alert
from app.models.analysis import AnalysisResult
from app.models.content import ContentItem
from app.schemas.alert import AlertConfigRequest, AlertConfigResponse
from app.services.cache import delete_key, get_json, set_json, get_redis
from app.services.pubsub import publish_alert_to_redis
from app.utils.datetime import utcnow

ALERT_CONFIG_KEY = "alert:config"
DASHBOARD_SUMMARY_KEY = "dashboard:summary"


async def _is_author_on_cooldown(source: str, author: str, severity: str, ttl: int) -> bool:
    redis = get_redis()
    key = f"alert_cooldown:{severity}:{source}:{author or 'unknown'}"
    result = await redis.set(key, "1", ex=ttl, nx=True)
    return result is None


async def list_alerts(
    db: AsyncSession,
    *,
    severity: RiskLabel | None = None,
    source: SourceType | None = None,
    resolved: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Alert]:
    filters = []
    if resolved is not None:
        filters.append(Alert.resolved == resolved)
    if source:
        filters.append(ContentItem.source == source)

    stmt = (
        select(Alert)
        .join(ContentItem, ContentItem.id == Alert.content_id)
        .where(*filters)
    )

    if severity:
        stmt = stmt.where(Alert.severity == severity)

    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


from datetime import timedelta

async def resolve_alert(
    db: AsyncSession,
    *,
    alert_id: uuid.UUID,
    resolved_by: str,
    analyst_note: str | None,
    suppress_minutes: int = 0,
    commit: bool = True,
) -> Alert | None:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return None

    alert.resolved = True
    alert.resolved_by = resolved_by
    alert.analyst_note = analyst_note
    alert.resolved_at = utcnow()
    if suppress_minutes > 0:
        alert.suppress_until = utcnow() + timedelta(minutes=suppress_minutes)
    
    if commit:
        await db.commit()
        await db.refresh(alert)
    # Invalidate the dashboard cache so open alert counts stay accurate.
    await delete_key(DASHBOARD_SUMMARY_KEY)
    return alert

async def create_alert_if_needed(
    db: AsyncSession,
    *,
    content_id: uuid.UUID,
    risk_score: float,
    content_item: ContentItem | None = None,
    analysis_result: AnalysisResult | None = None,
) -> Alert | None:
    config = await get_alert_config()
    threshold = config.high_threshold
    if risk_score < threshold:
        return None

    # Check for active suppression
    now = utcnow()
    suppressed_result = await db.execute(
        select(Alert).where(
            Alert.content_id == content_id,
            Alert.suppress_until > now
        )
    )
    if suppressed_result.scalar_one_or_none():
        logger.info("Alert suppressed by analyst (suppress_until) for content_id=%s", content_id)
        return None

    # Fetch additional context early for cooldown and severity
    if content_item is None:
        content_item_req = await db.execute(select(ContentItem).where(ContentItem.id == content_id))
        content_item = content_item_req.scalar_one_or_none()
    
    if analysis_result is None:
        analysis_result_req = await db.execute(select(AnalysisResult).where(AnalysisResult.content_id == content_id))
        analysis_result = analysis_result_req.scalar_one_or_none()

    severity = RiskLabel.CRITICAL if risk_score >= config.critical_threshold else RiskLabel.HIGH

    if content_item and content_item.source:
        ttl = settings.alert_cooldown_seconds_critical if severity == RiskLabel.CRITICAL else settings.alert_cooldown_seconds_high
        if await _is_author_on_cooldown(content_item.source, content_item.author_handle, severity.value, ttl):
            logger.info("Author %s on source %s is on cooldown, suppressing alert.", content_item.author_handle, content_item.source)
            return None

    notified_via = config.notification_channels or ["none:notification-not-configured"]
    alert = Alert(
        content_id=content_id,
        threshold_hit=threshold,
        notified_via=notified_via,
        severity=severity,
    )
    try:
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
    except IntegrityError:
        await db.rollback()
        # Escalate existing alert if needed
        existing = await db.execute(select(Alert).where(Alert.content_id == content_id, Alert.resolved.is_(False)))
        existing_alert = existing.scalar_one_or_none()
        if existing_alert and severity == RiskLabel.CRITICAL and existing_alert.severity != RiskLabel.CRITICAL:
            existing_alert.severity = severity
            existing_alert.threshold_hit = risk_score
            existing_alert.escalated_at = utcnow()
            await db.commit()
            await db.refresh(existing_alert)
            alert = existing_alert
            logger.info("Escalated existing alert to CRITICAL for content_id=%s", content_id)
        else:
            logger.info("Duplicate alert suppressed for content_id=%s", content_id)
            return None
    
    if content_item and analysis_result:
        payload = {
            "id": str(alert.id),
            "content_id": str(content_item.id),
            "severity": severity.value,
            "risk_score": risk_score,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "source": content_item.source.value if hasattr(content_item.source, "value") else str(content_item.source),
            "author_handle": content_item.author_handle,
            "raw_text": content_item.raw_text[:200] if content_item.raw_text else "",
            "top_factors": analysis_result.score_breakdown.get("top_factors", []) if analysis_result.score_breakdown else [],
            "data_confidence": analysis_result.score_breakdown.get("nlp_threat_confidence", 0.0) if analysis_result.score_breakdown else 0.0
        }
        await publish_alert_to_redis(payload)

    # Invalidate the dashboard cache so open alert counts stay accurate.
    await delete_key(DASHBOARD_SUMMARY_KEY)
    return alert


_config_cache: AlertConfigResponse | None = None
_config_cache_expires: float = 0.0

async def get_alert_config() -> AlertConfigResponse:
    global _config_cache, _config_cache_expires
    import time
    now = time.monotonic()
    if _config_cache and now < _config_cache_expires:
        return _config_cache

    cached = await get_json(ALERT_CONFIG_KEY)
    if cached:
        config = AlertConfigResponse.model_validate(cached)
    else:
        channels = ["webhook"] if settings.alert_webhook_url else []
        config = AlertConfigResponse(
            high_threshold=settings.risk_threshold_high,
            critical_threshold=settings.risk_threshold_critical,
            notification_channels=channels,
            source="environment",
        )
        
    _config_cache = config
    _config_cache_expires = now + 60
    return config

async def set_alert_config(payload: AlertConfigRequest) -> AlertConfigResponse:
    global _config_cache_expires
    config = AlertConfigResponse(**payload.model_dump(), source="redis")
    await set_json(ALERT_CONFIG_KEY, config.model_dump(mode="json"), ttl_seconds=60 * 60 * 24 * 365)
    _config_cache_expires = 0.0  # Invalidate local cache
    return config
