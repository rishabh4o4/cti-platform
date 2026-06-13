import asyncio
import uuid
import pytest
import time
from sqlalchemy import select
from app.models.alert import Alert
from app.models.content import ContentItem
from app.models.analysis import AnalysisResult
from app.domain.enums import RiskLabel, SourceType
from app.services.alerts import create_alert_if_needed, list_alerts
from app.core.config import settings

@pytest.mark.asyncio
async def test_parallel_inserts(db_session):
    # Test 1A: Duplicate alert cannot be created by concurrent workers
    content_id = uuid.uuid4()
    content = ContentItem(id=content_id, source=SourceType.TELEGRAM, source_id="test_parallel", raw_text="test")
    db_session.add(content)
    await db_session.commit()

    # Run 5 concurrent inserts
    tasks = [
        create_alert_if_needed(db_session, content_id=content_id, risk_score=80.0, content_item=content)
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count alerts
    count = await db_session.execute(select(Alert).where(Alert.content_id == content_id))
    alerts = count.scalars().all()
    assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"

@pytest.mark.asyncio
async def test_critical_vs_high_cooldown(db_session):
    # Test 2A: CRITICAL alert fires within 60s cooldown even if HIGH fired recently
    author = f"actor_{uuid.uuid4()}"
    c1 = ContentItem(id=uuid.uuid4(), source=SourceType.TELEGRAM, source_id=str(uuid.uuid4()), author_handle=author, raw_text="high")
    c2 = ContentItem(id=uuid.uuid4(), source=SourceType.TELEGRAM, source_id=str(uuid.uuid4()), author_handle=author, raw_text="crit")
    db_session.add_all([c1, c2])
    await db_session.commit()

    # 1. Fire HIGH
    alert1 = await create_alert_if_needed(db_session, content_id=c1.id, risk_score=60.0, content_item=c1)
    assert alert1 is not None

    # 2. Fire CRITICAL (should NOT be suppressed)
    alert_crit = await create_alert_if_needed(db_session, content_id=c2.id, risk_score=90.0, content_item=c2)
    assert alert_crit is not None

@pytest.mark.asyncio
async def test_list_alerts_dedup(db_session):
    # Test 3E: list_alerts returns each alert exactly once even when content re-analysed 3 times
    content_id = uuid.uuid4()
    content = ContentItem(id=content_id, source=SourceType.TELEGRAM, source_id=str(uuid.uuid4()), raw_text="test")
    db_session.add(content)
    await db_session.commit()

    # Create 1 Alert
    alert = await create_alert_if_needed(db_session, content_id=content_id, risk_score=80.0, content_item=content)

    # Add 3 AnalysisResults for the same content_id
    for i in range(3):
        ar = AnalysisResult(content_id=content_id, risk_score=80.0+i, risk_label=RiskLabel.CRITICAL, model_version="v1")
        db_session.add(ar)
        # Sleep slightly to ensure different timestamps
        await asyncio.sleep(0.01)
    await db_session.commit()

    # Call list_alerts
    alerts = await list_alerts(db_session)
    # Check that this content_id appears exactly once
    matching = [a for a in alerts if a.content_id == content_id]
    assert len(matching) == 1
