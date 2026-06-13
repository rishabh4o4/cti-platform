import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.auth import Principal
from app.domain.enums import Role

def test_root_health_removed() -> None:
    from app.main import app
    with TestClient(app) as c:
        response = c.get("/health")
    assert response.status_code == 404

def test_v1_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("app.api.v1.endpoints.health.async_session_maker")
@patch("app.api.v1.endpoints.health.get_redis")
@patch("app.api.v1.endpoints.health._ping_celery")
@patch("app.api.v1.endpoints.health.settings")
@patch("app.api.v1.endpoints.health._get_latest_run", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.health.celery_app.signature")
@patch("app.api.v1.endpoints.health._check_neo4j")
def test_system_health_healthy(
    mock_check_neo4j,
    mock_signature,
    mock_get_latest_run,
    mock_settings,
    mock_ping_celery,
    mock_get_redis,
    mock_async_session_maker,
    client: TestClient
) -> None:
    from app.main import app
    from app.api.deps import require_dashboard_principal, get_db
    from app.domain.enums import PrincipalType
    import uuid
    
    # Mock authentication
    app.dependency_overrides[require_dashboard_principal] = lambda: Principal(subject="user", email="test@test.com", role=Role.ANALYST, user_id=uuid.uuid4(), principal_type=PrincipalType.DASHBOARD)
    
    # Mock DB dependency for role_checker
    mock_db = AsyncMock()
    mock_db.get.return_value = MagicMock(is_active=True)
    async def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db

    # Mock DB for the endpoint
    mock_db_session = AsyncMock()
    mock_async_session_maker.return_value.__aenter__.return_value = mock_db_session
    
    # Mock Redis
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis
    
    # Mock Celery Ping
    mock_ping_celery.return_value = {"worker1@local": {"ok": "pong"}}
    
    # Mock Telegram Settings
    mock_settings.telegram_session_string = "valid_session"
    
    # Mock CollectionRuns
    mock_run_telegram = MagicMock()
    mock_run_telegram.status = "completed"
    mock_run_telegram.ended_at = "2024-01-01T00:00:00Z"
    
    mock_run_reddit = MagicMock()
    mock_run_reddit.metadata_ = {}
    mock_run_reddit.ended_at = "2024-01-01T00:00:00Z"
    
    mock_run_x = MagicMock()
    mock_run_x.metadata_ = {}
    mock_run_x.ended_at = "2024-01-01T00:00:00Z"

    mock_get_latest_run.side_effect = [mock_run_telegram, mock_run_reddit, mock_run_x]
    
    # Mock NLP Celery signature
    mock_async_result = MagicMock()
    mock_async_result.get.return_value = "deberta-test"
    mock_signature.return_value.apply_async.return_value = mock_async_result
    
    # Mock Neo4j
    mock_check_neo4j.return_value = 100

    response = client.get("/api/v1/health/system")
        
    assert response.status_code == 200
    data = response.json()
    assert data["overall"] == "HEALTHY"
    assert len(data["components"]) == 8

    app.dependency_overrides.clear()

@patch("app.api.v1.endpoints.health.async_session_maker")
@patch("app.api.v1.endpoints.health.get_redis")
@patch("app.api.v1.endpoints.health._ping_celery")
@patch("app.api.v1.endpoints.health.settings")
@patch("app.api.v1.endpoints.health._get_latest_run", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.health.celery_app.signature")
@patch("app.api.v1.endpoints.health._check_neo4j")
def test_system_health_db_error(
    mock_check_neo4j,
    mock_signature,
    mock_get_latest_run,
    mock_settings,
    mock_ping_celery,
    mock_get_redis,
    mock_async_session_maker,
    client: TestClient
) -> None:
    from app.main import app
    from app.api.deps import require_dashboard_principal, get_db
    from app.domain.enums import PrincipalType
    import uuid

    # Mock authentication
    app.dependency_overrides[require_dashboard_principal] = lambda: Principal(subject="user", email="test@test.com", role=Role.ANALYST, user_id=uuid.uuid4(), principal_type=PrincipalType.DASHBOARD)
    
    # Mock DB dependency for role_checker
    mock_db = AsyncMock()
    mock_db.get.return_value = MagicMock(is_active=True)
    async def override_get_db():
        yield mock_db
    app.dependency_overrides[get_db] = override_get_db

    # Mock DB - raise error on SELECT 1
    mock_db_session = AsyncMock()
    mock_db_session.execute.side_effect = Exception("DB Down")
    mock_async_session_maker.return_value.__aenter__.return_value = mock_db_session
    
    # Mock Redis
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis
    
    # Mock Celery Ping
    mock_ping_celery.return_value = {"worker1@local": {"ok": "pong"}}
    
    # Mock Telegram Settings
    mock_settings.telegram_session_string = "valid_session"
    
    # Mock CollectionRuns
    mock_run_telegram = MagicMock()
    mock_run_telegram.status = "completed"
    mock_run_telegram.ended_at = "2024-01-01T00:00:00Z"
    
    mock_run_reddit = MagicMock()
    mock_run_reddit.metadata_ = {}
    mock_run_reddit.ended_at = "2024-01-01T00:00:00Z"
    
    mock_run_x = MagicMock()
    mock_run_x.metadata_ = {}
    mock_run_x.ended_at = "2024-01-01T00:00:00Z"

    mock_get_latest_run.side_effect = [mock_run_telegram, mock_run_reddit, mock_run_x]
    
    # Mock NLP Celery signature
    mock_async_result = MagicMock()
    mock_async_result.get.return_value = "deberta-test"
    mock_signature.return_value.apply_async.return_value = mock_async_result
    
    # Mock Neo4j
    mock_check_neo4j.return_value = 100

    response = client.get("/api/v1/health/system")

    assert response.status_code == 200
    data = response.json()
    assert data["overall"] == "CRITICAL"
    db_component = next(c for c in data["components"] if c["name"] == "Database")
    assert db_component["status"] == "ERROR"

    app.dependency_overrides.clear()
