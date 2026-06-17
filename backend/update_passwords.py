import asyncio
from app.db.session import async_session_maker
from app.models.user import User
from sqlalchemy import select
from app.core.security import hash_password
from app.core.config import settings

async def update_passwords():
    async with async_session_maker() as db:
        admin_res = await db.execute(select(User).where(User.username == settings.admin_username))
        admin = admin_res.scalar_one_or_none()
        if admin:
            admin.hashed_password = hash_password(settings.admin_password)
            print(f"Updated {settings.admin_username}")
        
        analyst_res = await db.execute(select(User).where(User.username == settings.analyst_username))
        analyst = analyst_res.scalar_one_or_none()
        if analyst:
            analyst.hashed_password = hash_password(settings.analyst_password)
            print(f"Updated {settings.analyst_username}")
            
        await db.commit()
        print("Updated passwords")

asyncio.run(update_passwords())
