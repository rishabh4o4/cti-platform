import structlog
import asyncio
from sqlalchemy import text
from app.db.session import async_session_maker

logger = structlog.get_logger()

async def main():
    async with async_session_maker() as db:
        result = await db.execute(
            text("SELECT risk_score, risk_label, data_confidence, engine_version FROM analysis_results ORDER BY analyzed_at DESC LIMIT 5")
        )
        for row in result:
            logger.info("Analysis Result", risk_score=row[0], risk_label=row[1], data_confidence=row[2], engine_version=row[3])

if __name__ == "__main__":
    asyncio.run(main())
