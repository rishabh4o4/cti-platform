import asyncio
import os
import uuid
import json
from datetime import datetime
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from app.core.config import settings

async def verify():
    # 1. Check details->>'report_ref'
    from app.db.session import get_engine
    engine = get_engine()
    async with AsyncSession(engine) as session:
        # Insert a dummy REPORT_EXPORTED just to have data
        await session.execute(text("""
            INSERT INTO audit_logs (id, analyst, action, details, timestamp)
            VALUES (:id, 'test_user', 'REPORT_EXPORTED', '{"report_ref": "REF-12345"}', NOW())
        """), {"id": str(uuid.uuid4())})
        await session.commit()
        
        result = await session.execute(text("""
            SELECT details->>'report_ref' FROM audit_logs WHERE action = 'REPORT_EXPORTED' LIMIT 1
        """))
        print(f"1. REPORT_EXPORTED report_ref: {result.scalar()}")

        # 3. Check DELETE permissions
        try:
            await session.execute(text("DELETE FROM audit_logs WHERE action = 'REPORT_EXPORTED'"))
            await session.commit()
            print("3. DELETE SUCCESS (This is bad if we are running as the user that had it revoked!)")
        except Exception as e:
            print(f"3. DELETE FAILED (Expected): {e}")

    # Now let's test the API using TestClient
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_db

    # Create a fresh session for the client
    async with AsyncSession(engine) as db_session:
        app.dependency_overrides[get_db] = lambda: db_session
        client = TestClient(app)
        
        # Create an admin user first using DB
        from app.models.user import User
        from app.core.security import hash_password
        admin_username = f"admin_{uuid.uuid4().hex[:8]}"
        admin_user = User(
            username=admin_username,
            hashed_password=hash_password("password123"),
            role="admin",
            is_active=True
        )
        db_session.add(admin_user)
        await db_session.commit()
        
        # Now login
        res = client.post("/api/v1/auth/token", json={"username": admin_username, "password": "password123"})
        if res.status_code != 200:
            print(f"Failed to get token: {res.json()}")
            return
        
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create user -> USER_CREATED with analyst_id
        new_username = f"test_user_{uuid.uuid4().hex[:8]}"
        res = client.post("/api/v1/users", json={"username": new_username, "password": "password", "role": "viewer", "is_active": True}, headers=headers)
        print(f"2. Create User status: {res.status_code}")
        
        # Verify USER_CREATED in DB
        result = await db_session.execute(text("SELECT analyst_id, details->>'username' FROM audit_logs WHERE action = 'USER_CREATED' ORDER BY timestamp DESC LIMIT 1"))
        row = result.fetchone()
        print(f"2. USER_CREATED log: analyst_id={row[0]}, username_in_details={row[1]}")

        # 4. GET /audit-logs filtering
        res = client.get("/api/v1/audit-logs?action=USER_LOGIN_FAILED&from_timestamp=2026-01-01T00:00:00Z&limit=5", headers=headers)
        print(f"4. GET /audit-logs status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"4. GET /audit-logs count: {len(data)}")
            if len(data) > 0:
                print(f"   First item details: {data[0].get('details')}")

if __name__ == "__main__":
    asyncio.run(verify())
