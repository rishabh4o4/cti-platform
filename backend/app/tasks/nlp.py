import uuid

from asgiref.sync import async_to_sync

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.nlp.run_nlp_analysis", bind=True)
def run_nlp_analysis(self, content_id: str) -> dict:
    return async_to_sync(_run_nlp_analysis)(content_id)


async def _run_nlp_analysis(content_id: str) -> dict:
    """Fetch the content's raw text and run the Intelligence Layer.

    The returned dict is consumed by ``run_scoring`` via the Celery chord.
    ``flags`` is written directly to ``analysis_results.nlp_flags`` and
    ``model_version`` is written to ``analysis_results.model_version``.
    """
    import structlog
    from sqlalchemy import select

    from app.db.session import async_session_maker
    from app.models.content import ContentItem
    from app.services.intelligence import MODEL_NAME, analyze_text

    logger = structlog.get_logger()

    # --- Fetch raw text from the database ---
    async with async_session_maker() as db:
        result = await db.execute(
            select(ContentItem.raw_text).where(
                ContentItem.id == uuid.UUID(content_id)
            )
        )
        raw_text = result.scalar_one_or_none()

    if raw_text is None:
        logger.error("Content not found for NLP analysis", content_id=content_id)
        return {
            "stage": "nlp",
            "content_id": content_id,
            "model_version": None,
            "flags": {
                "status": "error",
                "note": f"Content {content_id} not found.",
            },
        }

    # --- Run the Intelligence Layer ---
    intel = analyze_text(raw_text)

    return {
        "stage": "nlp",
        "content_id": content_id,
        "model_version": MODEL_NAME,
        "flags": {
            "status": "completed",
            "category": intel["category"],
            "confidence": intel["confidence"],
            "entities": intel["entities"],
            "pii_risk": intel["pii_risk"],
        },
    }

@celery_app.task(name="app.tasks.nlp.ping_nlp", bind=True)
def ping_nlp(self) -> str:
    from app.services.intelligence import MODEL_NAME
    return MODEL_NAME
