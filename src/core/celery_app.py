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

from celery.signals import worker_ready

@worker_ready.connect
def start_metrics_server(**kwargs):
    from prometheus_client import start_http_server
    import os
    if os.environ.get("WORKER_TYPE") == "celery":
        start_http_server(8729)
celery_app.conf.beat_schedule = {
    'reap-zombie-jobs-every-minute': {
        'task': 'reap_zombie_jobs',
        'schedule': 60.0,
    },
}


from celery.signals import worker_process_init

@worker_process_init.connect
def init_worker_db_pool(**kwargs):
    """
    Called when a Celery worker process starts.
    We need to dispose of the global SQLAlchemy engine's connections
    so that the fork doesn't inherit dirty/shared DB connections.
    """
    from src.db.session import get_engine
    get_engine().sync_engine.dispose()
