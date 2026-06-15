# Monitoring & Alerting

OsuRender API exports comprehensive Prometheus metrics and ships with pre-configured alert rules.

## Metrics Inventory

### Queue Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `queue_depth` | Gauge | `status` | Current jobs in each state (queued, rendering, downloading) |
| `outbox_pending_events` | Gauge | — | Pending events awaiting dispatch |
| `outbox_dispatched_events` | Gauge | — | Events dispatched, awaiting worker confirmation |
| `outbox_failed_events` | Gauge | — | Failed events (Dead Letter Queue) |

### Render Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `render_duration_seconds` | Histogram | — | End-to-end render time. Buckets: 30s, 60s, 120s, 180s, 300s, 600s |
| `render_failures_total` | Counter | `reason` | Failures by phase (init, download, osu_api, render) |
| `active_render_workers` | Gauge | — | Currently active workers |
| `jobs_completed_total` | Counter | — | Successfully completed jobs |
| `jobs_failed_total` | Counter | — | Failed jobs |
| `zombie_jobs_reaped_total` | Counter | — | Jobs recovered by zombie reaper |

### Dispatch Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `outbox_dispatch_total` | Counter | — | Events dispatched to Celery |
| `dispatch_latency_seconds` | Histogram | — | Time from event creation to dispatch |
| `listener_reconnects_total` | Counter | `reason` | Dispatcher reconnections |
| `stuck_processing_events_total` | Counter | — | Events rescued by sweeper |

### API Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `job_submit_total` | Counter | — | Jobs accepted by the API |
| `webhook_failures_total` | Counter | `reason` | Webhook auth failures |
| `rate_limit_violations_total` | Counter | — | Rate limit hits |
| `upload_validation_failures_total` | Counter | `type` | Upload validation failures |

### Storage Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `storage_operation_duration_seconds` | Histogram | `operation` | Storage operation latency |
| `storage_failures_total` | Counter | `operation` | Storage operation failures |

### HTTP Metrics (auto-instrumented)

The `prometheus-fastapi-instrumentator` automatically exports standard HTTP metrics:
- `http_requests_total`
- `http_request_duration_seconds`
- `http_request_size_bytes`
- `http_response_size_bytes`

## Alert Rules

Alerts are defined in `monitoring/alerts.yml`:

### Critical Alerts

| Alert | Condition | Duration |
|-------|-----------|----------|
| `QueueDepthCritical` | Queued jobs > 90 | 2 min |
| `NoActiveWorkers` | No workers + queue > 0 | 5 min |
| `SLOApiAvailabilityBreach` | API availability < 99.9% | 15 min |

### Warning Alerts

| Alert | Condition | Duration |
|-------|-----------|----------|
| `QueueDepthHigh` | Queued jobs > 50 | 5 min |
| `OutboxPendingHigh` | Pending events > 10 | 5 min |
| `HighRenderFailureRate` | Failures > 0.5/sec | 5 min |
| `RenderDurationHigh` | P95 > 300s | 10 min |
| `HighErrorRate` | 5xx rate > 5% | 5 min |
| `HighLatency` | P95 latency > 5s | 5 min |
| `StorageFailures` | Any storage failures | 5 min |
| `DeadLetterQueueGrowing` | Failed events > 0 | 15 min |

## Accessing Metrics

```bash
# Raw Prometheus endpoint
curl http://localhost:8727/metrics

# Prometheus UI
open http://localhost:9090

# Grafana dashboards
open http://localhost:3727  # Default: admin/admin
```

## SLO Recording Rules

```yaml
# API availability (target: 99.9%)
osurender:api_availability:ratio_5m

# Render success rate
osurender:render_success_rate:ratio_5m
```

## Live Dashboard

Since browser security policies prevent embedding the live dashboard directly in the documentation, you can view the real-time production metrics by opening the public dashboard directly:

<a href="https://rdrdash.azaken.com/public-dashboards/ea15b651606646389888597c6605e7c8" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; justify-content: center; gap: 10px; background: linear-gradient(135deg, var(--vp-c-brand-1) 0%, var(--vp-c-brand-3) 100%); color: white; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 1.5rem 0; box-shadow: 0 4px 14px rgba(255, 43, 133, 0.3); transition: transform 0.2s ease;">
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><polyline points="224 208 32 208 32 48" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="200 72 128 144 96 112 32 176" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><polyline points="200 112 200 72 160 72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
  Open Live Grafana Dashboard ↗
</a>
