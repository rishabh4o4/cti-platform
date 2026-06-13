from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.vision.run_vision_analysis", bind=True)
def run_vision_analysis(self, content_id: str) -> dict:
    return {
        "stage": "vision",
        "content_id": content_id,
        "flags": {
            "status": "not_implemented",
            "stored_media": [],
            "nsfw_score": None,
            "ocr_text": None,
            "detected_objects": [],
            "hash_blocklist_match": None,
            "note": "Vision model and media storage integration is intentionally deferred.",
        },
    }
