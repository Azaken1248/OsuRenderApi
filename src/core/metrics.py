from prometheus_client import Gauge, Histogram, Counter

# Queue Depth
queue_depth = Gauge(
    "queue_depth",
    "Current number of jobs in a specific state",
    ["status"]
)

# Render Duration
render_duration_seconds = Histogram(
    "render_duration_seconds",
    "Time taken to render a job in seconds"
)

# Render Failures
render_failures_total = Counter(
    "render_failures_total",
    "Total number of failed render jobs",
    ["reason"]
)

# Outbox Dispatch
outbox_dispatch_total = Counter(
    "outbox_dispatch_total",
    "Total number of outbox events dispatched to celery successfully"
)

# Dispatcher Reconnects
listener_reconnects_total = Counter(
    "listener_reconnects_total",
    "Total number of times the dispatcher had to reconnect to postgres or redis"
)

# Stuck Processing Recoveries
stuck_processing_events_total = Counter(
    "stuck_processing_events_total",
    "Total number of stuck outbox events rescued by the sweeper"
)

# Active Workers
active_render_workers = Gauge(
    "active_render_workers",
    "Current number of active render workers"
)
