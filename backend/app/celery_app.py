from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lead_triage",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_routes={"app.tasks.*": {"queue": "lead-triage"}},
    task_default_queue="lead-triage",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=86400,
)
