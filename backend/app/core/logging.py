import logging
import sys

import structlog

def add_celery_task_info(logger, method_name, event_dict):
    try:
        from celery import current_task
        if current_task and current_task.request and current_task.request.id:
            event_dict["task_id"] = current_task.request.id
            event_dict["task_name"] = current_task.name
    except ImportError:
        pass
    return event_dict

def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_celery_task_info,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
