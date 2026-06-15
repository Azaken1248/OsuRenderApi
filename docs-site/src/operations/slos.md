---
title: "SLOs & SLIs"
description: "Service Level Objectives and Indicators for OsuRender API — availability targets, latency budgets, and error rate thresholds."
---

# SLOs & SLIs

Service Level Objectives define the reliability targets for OsuRender API.

## Service Level Indicators

| SLI | Metric | Calculation |
|-----|--------|-------------|
| **API Availability** | `osurender:api_availability:ratio_5m` | `1 - (5xx rate / total rate)` |
| **Render Success Rate** | `osurender:render_success_rate:ratio_5m` | `completed / (completed + failed)` |
| **Dispatch Latency** | `dispatch_latency_seconds` | P99 of event creation → Celery dispatch |
| **Render Duration** | `render_duration_seconds` | P95 end-to-end render time |

## Service Level Objectives

| SLO | Target | Alert Threshold | Alert Duration |
|-----|--------|-----------------|----------------|
| **API Availability** | 99.9% | < 99.9% | 15 min |
| **Queue Dispatch** | 99% within 60s | P99 > 60s | 10 min |
| **Render Start** | 95% within 5 min | — | Monitored |
| **Render Completion** | 95% within 15 min | P95 > 300s | 10 min |
| **Data Durability** | 99.99% | — | No lost jobs |

## Prometheus Recording Rules

```yaml
# API availability ratio (5-minute window)
- record: osurender:api_availability:ratio_5m
  expr: >
    1 - (
      rate(http_requests_total{status=~"5.."}[5m]) /
      rate(http_requests_total[5m])
    )

# Render success rate (5-minute window)
- record: osurender:render_success_rate:ratio_5m
  expr: >
    rate(jobs_completed_total[5m]) / (
      rate(jobs_completed_total[5m]) +
      rate(jobs_failed_total[5m])
    )
```

## Error Budget

With a 99.9% API availability SLO:
- **Monthly budget**: 43.8 minutes of downtime
- **Weekly budget**: 10.1 minutes of downtime

When the error budget is exhausted, prioritize reliability work over features.

## Key Dashboards

Monitor these Grafana panels to track SLO compliance:

1. **API Availability** — 5-minute rolling availability ratio
2. **Queue Depth Over Time** — Trend of queued/rendering/downloading jobs
3. **Dispatch Latency** — P50/P95/P99 histograms
4. **Render Duration** — P50/P95 with SLO target line
5. **Error Rate** — 5xx responses per second
