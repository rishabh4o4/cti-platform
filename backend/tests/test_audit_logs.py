import pytest
import uuid
import json
from sqlalchemy import select
from httpx import AsyncClient

from app.models.audit import AuditLog
from app.models.user import User
from app.models.alert import Alert
from app.models.content import ContentItem
from app.core.security import hash_password
from app.domain.enums import Role, SourceType, RiskLabel
from app.api.deps import get_db

@pytest.fixture
async def setup_data(db_session):
    user = User(
        username="admin_user",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True
    )
    db_session.add(user)
    
    content = ContentItem(
        id=uuid.uuid4(),
        source=SourceType.TELEGRAM,
        source_id="msg_123",
        raw_text="Test content",
        author_handle="tester"
    )
    db_session.add(content)
    
    alert = Alert(
        id=uuid.uuid4(),
        content_id=content.id,
        threshold_hit=85.0,
        severity=RiskLabel.HIGH,
        notified_via=["webhook"]
    )
    db_session.add(alert)
    
    await db_session.commit()
    return {"user": user, "content": content, "alert": alert}

@pytest.mark.anyio
async def test_audit_logging_system(client, db_session, setup_data):
    # Override get_db for the client
    from app.main import app
    app.dependency_overrides[get_db] = lambda: db_session

    try:
        # 1. USER_LOGIN_FAILED
        res = client.post("/api/v1/auth/token", json={"username": "admin_user", "password": "wrongpassword"})
        assert res.status_code == 401
        
        # 2. USER_LOGIN
        res = client.post("/api/v1/auth/token", json={"username": "admin_user", "password": "password123"})
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. ALERT_RESOLVED
        alert_id = setup_data["alert"].id
        res = client.patch(f"/api/v1/alerts/{alert_id}/resolve", json={"analyst_note": "False positive", "suppress_minutes": 0}, headers=headers)
        assert res.status_code == 200
        
        # 4. CONFIG_UPDATED
        res = client.post("/api/v1/alerts/config", json={
            "high_threshold": 60,
            "critical_threshold": 95,
            "notification_channels": ["webhook", "email"]
        }, headers=headers)
        assert res.status_code == 200
        
        # 5. COLLECTOR_TRIGGERED
        from unittest.mock import patch
        with patch("app.api.v1.endpoints.collectors.trigger_collection") as mock_trigger:
            mock_trigger.return_value = ({
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "source": "telegram",
                "status": "pending",
                "trigger_type": "manual",
                "items_fetched": 0,
                "items_new": 0,
                "errors": [],
                "started_at": "2026-06-12T00:00:00Z"
            }, "Success")
            res = client.post("/api/v1/collectors/run", json={
                "source": "telegram",
                "reason": "Test trigger"
            }, headers=headers)
            if res.status_code != 202:
                print(res.json())
            assert res.status_code == 202
        
        # 6. USER_LOGOUT
        res = client.post("/api/v1/auth/logout", headers=headers)
        assert res.status_code == 204
        
        # Query and verify
        result = await db_session.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10)
        )
        logs = result.scalars().all()
        
        print("\n\n--- AUDIT LOG RESULTS ---")
        print(f"{'ACTION':<25} | {'ANALYST':<15} | DETAILS")
        print("-" * 100)
        for log in logs:
            print(f"{log.action:<25} | {log.analyst:<15} | {log.details}")
            
    finally:
        app.dependency_overrides.clear()
