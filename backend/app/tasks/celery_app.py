from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "threat_intel",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.tasks.ingest",
        "app.tasks.nlp",
        "app.tasks.vision",
        "app.tasks.scoring",
        "app.tasks.alerts",
        # DISABLED: real API access not available — uncomment when credentials are configured
        "app.tasks.reddit",
        "app.tasks.telegram",
        # DISABLED: real API access not available — uncomment when credentials are configured
        "app.tasks.x",
    ],
)

from celery.schedules import crontab

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.ingest.*": {"queue": "ingest"},
        "app.tasks.nlp.*": {"queue": "nlp"},
        "app.tasks.vision.*": {"queue": "vision"},
        "app.tasks.scoring.*": {"queue": "scoring"},
        "app.tasks.alerts.*": {"queue": "alerts"},
        "app.tasks.reddit.*": {"queue": "ingest"},
        "app.tasks.telegram.*": {"queue": "ingest"},
        "app.tasks.x.*": {"queue": "ingest"},
    },
    beat_schedule={
        # DISABLED: real API access not available — uncomment when credentials are configured
        "collect-reddit-data": {
            "task": "app.tasks.reddit.collect_reddit_data",
            "schedule": crontab(minute=f"*/{settings.reddit_poll_interval_minutes}"),
        },
        "collect-telegram-data": {
            "task": "app.tasks.telegram.collect_telegram_data",
            "schedule": crontab(minute=f"*/{settings.telegram_poll_interval_minutes}"),
        },
        # DISABLED: real API access not available — uncomment when credentials are configured
        "collect-x-data": {
            "task": "app.tasks.x.collect_x_data",
            "schedule": crontab(minute=f"*/{settings.x_poll_interval_minutes}"),
        },
        # Fix 5.1: watchdog — resets CollectionRun rows stuck in RUNNING status
        # (e.g. after a worker OOM / SIGKILL) so they don't pollute the dashboard.
        "reset-stale-runs": {
            "task": "app.tasks.ingest.reset_stale_collection_runs",
            "schedule": crontab(minute="*/5"),
        },
    },
)

from celery.signals import worker_init

@worker_init.connect
def configure_celery_logging(**kwargs):
    from app.core.logging import configure_logging
    from app.db.neo4j_session import initialize_schema
    configure_logging(settings.log_level)
    try:
        initialize_schema()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to initialize Neo4j schema in worker: {e}")
