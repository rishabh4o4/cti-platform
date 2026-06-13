import pytest
from httpx import AsyncClient
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.user import User
from app.domain.enums import Role
from app.core.security import hash_password, create_access_token
from app.main import app
from app.api.deps import get_db

from httpx import AsyncClient, ASGITransport

@pytest.fixture(autouse=True)
def override_dependency(db_session):
    async def _override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def setup_users(db_session: AsyncSession):
    users = []
    for r in [Role.ADMIN, Role.ANALYST, Role.VIEWER]:
        u = User(id=uuid.uuid4(), username=r.value, hashed_password="pw", role=r, is_active=True)
        db_session.add(u)
        users.append(u)
    
    inactive_u = User(id=uuid.uuid4(), username="inactive", hashed_password="pw", role=Role.ADMIN, is_active=False)
    db_session.add(inactive_u)
    users.append(inactive_u)
    
    await db_session.commit()
    
    tokens = {}
    for u in users:
        tokens[u.username] = create_access_token(subject=u.username, role=u.role, user_id=str(u.id))
        
    return tokens

@pytest.mark.asyncio
async def test_rbac_viewer(async_client: AsyncClient, setup_users):
    headers = {"Authorization": f"Bearer {setup_users['viewer']}"}
    
    # GET should work (mocked dependencies or 404 is fine, we just want to avoid 401/403)
    # Actually wait, /api/v1/health is public or requires role.
    # We test POST /api/v1/cases
    response = await async_client.post("/api/v1/cases", json={"title": "Test case"}, headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_rbac_analyst(async_client: AsyncClient, setup_users):
    headers = {"Authorization": f"Bearer {setup_users['analyst']}"}
    
    # Analyst can POST cases
    # We might get a 500 or validation error if the mock isn't complete, but 403 is what we check for.
    response = await async_client.post("/api/v1/cases", json={"title": "Test case"}, headers=headers)
    assert response.status_code != 403

    # Analyst cannot POST config
    response = await async_client.post("/api/v1/alerts/config", json={"high_threshold": 60, "critical_threshold": 80}, headers=headers)
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_rbac_admin(async_client: AsyncClient, setup_users):
    headers = {"Authorization": f"Bearer {setup_users['admin']}"}
    
    # Admin can POST config
    response = await async_client.post("/api/v1/alerts/config", json={"high_threshold": 60, "critical_threshold": 80}, headers=headers)
    assert response.status_code != 403

@pytest.mark.asyncio
async def test_rbac_inactive(async_client: AsyncClient, setup_users):
    headers = {"Authorization": f"Bearer {setup_users['inactive']}"}
    
    response = await async_client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 403
