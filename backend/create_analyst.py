import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import bcrypt
import uuid
import os

from dotenv import load_dotenv
load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("NO DATABASE_URL")
    exit(1)

engine = create_async_engine(db_url)

async def insert():
    analyst_pass = os.environ.get("ANALYST_PASSWORD")
    if not analyst_pass:
        print("NO ANALYST_PASSWORD")
        return
    hashed = bcrypt.hashpw(analyst_pass.encode(), bcrypt.gensalt()).decode()
    uid = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(text(f"INSERT INTO users (id, username, hashed_password, role, is_active, created_at, updated_at) VALUES ('{uid}', 'analyst', '{hashed}', 'analyst', true, NOW(), NOW())"))
    print("Inserted successfully")
        
asyncio.run(insert())
