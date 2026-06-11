from celery import Celery
from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "osurender_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.render_worker"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
celery_app.conf.beat_schedule = {
    'poll-modal-jobs-every-10-seconds': {
        'task': 'poll_modal_status',
        'schedule': 10.0,
    },
}
