from prometheus_client import Gauge, Histogram, Counter

queue_depth = Gauge(
    "queue_depth", "Current number of jobs in a specific state", ["status"]
)

outbox_pending_events = Gauge(
    "outbox_pending_events", "Number of pending events in the outbox queue"
)
outbox_dispatched_events = Gauge(
    "outbox_dispatched_events",
    "Number of dispatched events awaiting worker confirmation",
)
outbox_failed_events = Gauge(
    "outbox_failed_events", "Number of failed events in the outbox (dead letters)"
)

render_duration_seconds = Histogram(
    "render_duration_seconds",
    "Time taken to render a job in seconds",
    buckets=[30, 60, 120, 180, 300, 600],
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

dispatch_latency_seconds = Histogram(
    "dispatch_latency_seconds",
    "Time between outbox event creation and dispatch",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

webhook_failures_total = Counter(
    "webhook_failures_total",
    "Total number of webhook verification failures",
    ["reason"],
)

rate_limit_violations_total = Counter(
    "rate_limit_violations_total",
    "Total number of rate limit violations",
)

upload_validation_failures_total = Counter(
    "upload_validation_failures_total",
    "Total number of upload validation failures",
    ["type"],
)

storage_operation_duration_seconds = Histogram(
    "storage_operation_duration_seconds",
    "Duration of storage operations",
    ["operation"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

storage_failures_total = Counter(
    "storage_failures_total",
    "Total number of storage operation failures",
    ["operation"],
)

dead_letter_replayed_total = Counter(
    "dead_letter_replayed_total",
    "Total number of dead letter events replayed",
)

zombie_jobs_reaped_total = Counter(
    "zombie_jobs_reaped_total",
    "Total number of zombie jobs reaped by the sweeper",
)

analytics_requests_total = Counter(
    "analytics_requests_total",
    "Total analytics endpoint calls",
    ["outcome"],  # hit, miss, pending, error
)
