from prometheus_client import Gauge, Histogram, Counter

queue_depth = Gauge(
    "queue_depth", "Current number of jobs in a specific state", ["status"]
)


outbox_pending_events = Gauge(
    "outbox_pending_events", "Number of pending events in the outbox queue"
)


render_duration_seconds = Histogram(
    "render_duration_seconds", "Time taken to render a job in seconds"
)


render_failures_total = Counter(
    "render_failures_total",
    "Total number of failed render pipeline executions",
    ["reason"],
)


job_submit_total = Counter(
    "job_submit_total", "Total number of jobs successfully accepted by the API"
)

jobs_completed_total = Counter(
    "jobs_completed_total", "Total number of jobs that successfully completed rendering"
)

jobs_failed_total = Counter(
    "jobs_failed_total", "Total number of jobs that failed and were marked as failed"
)


outbox_dispatch_total = Counter(
    "outbox_dispatch_total",
    "Total number of outbox events dispatched to celery successfully",
)


listener_reconnects_total = Counter(
    "listener_reconnects_total",
    "Total number of times the dispatcher had to reconnect to postgres or redis",
    ["reason"],
)


stuck_processing_events_total = Counter(
    "stuck_processing_events_total",
    "Total number of stuck outbox events rescued by the sweeper",
)


active_render_workers = Gauge(
    "active_render_workers",
    "Current number of active render workers",
    multiprocess_mode="livesum",
)
