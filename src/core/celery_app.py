from celery import Celery
from celery.signals import celeryd_init, worker_process_init, worker_process_shutdown
from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "osurender_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.workers.render_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celeryd_init.connect
def start_metrics_server(**kwargs):
    import os

    if os.environ.get("WORKER_TYPE") == "celery":
        from prometheus_client import CollectorRegistry, start_http_server, multiprocess

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        start_http_server(8729, registry=registry)


celery_app.conf.beat_schedule = {
    "reap-zombie-jobs-every-minute": {
        "task": "reap_zombie_jobs",
        "schedule": 60.0,
    },
}


@worker_process_init.connect
def init_worker_db_pool(**kwargs):
    """
    Called when a Celery worker process starts.
    We need to dispose of the global SQLAlchemy engine's connections
    so that the fork doesn't inherit dirty/shared DB connections.
    """
    from src.db.session import get_engine

    get_engine().sync_engine.dispose()


@worker_process_shutdown.connect
def clean_up_multiprocess_metrics(pid, **kwargs):
    import os

    if (
        os.environ.get("WORKER_TYPE") == "celery"
        and "PROMETHEUS_MULTIPROC_DIR" in os.environ
    ):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(pid)
