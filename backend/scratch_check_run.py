import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.collection import CollectionRun
from app.domain.enums import SourceType

async def main():
    async with async_session_maker() as db:
        result = await db.execute(
            select(CollectionRun).where(CollectionRun.source == SourceType.TELEGRAM).order_by(CollectionRun.id.desc()).limit(1)
        )
        run = result.scalar_one_or_none()
        if run:
            print(f"Run ID: {run.id}")
            print(f"Status: {run.status}")
            print(f"Errors: {run.errors}")
        else:
            print("No run found")

if __name__ == "__main__":
    asyncio.run(main())
