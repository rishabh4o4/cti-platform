from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.alerts.dispatch_alert_notification", bind=True)
def dispatch_alert_notification(self, alert_id: str) -> dict[str, str]:
    return {
        "alert_id": alert_id,
        "status": "not_implemented",
        "note": "Notification dispatch is intentionally deferred until channels are configured.",
    }
