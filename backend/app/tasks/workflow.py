import uuid

from celery import chord

from app.tasks.nlp import run_nlp_analysis
from app.tasks.scoring import run_scoring
from app.tasks.vision import run_vision_analysis


def enqueue_analysis_workflow(content_id: uuid.UUID | str) -> str:
    content_id_str = str(content_id)
    workflow = chord(
        [
            run_nlp_analysis.s(content_id_str).set(queue="nlp"),
            run_vision_analysis.s(content_id_str).set(queue="vision"),
        ],
        run_scoring.s(content_id_str).set(queue="scoring"),
    )
    result = workflow.apply_async()
    return result.id
