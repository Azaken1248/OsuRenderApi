# System Overview

OsuRender API is architected as a distributed, event-driven system with clear separation between the API tier, job orchestration, and compute-intensive rendering.

## High-Level Architecture

```mermaid
graph TD
    Client([Client / Bot]) -->|"1. Upload .osr"| API[API Gateway<br/>FastAPI :8727]
    API -->|"2. Atomic Insert"| DB[(PostgreSQL)]
    API -->|"3. Upload Replay"| S3[(Object Storage<br/>MinIO / R2)]
    
    DB -.->|"4. LISTEN/NOTIFY"| Dispatcher[Outbox Dispatcher]
    Dispatcher -->|"5. Celery Task"| Redis[(Redis<br/>Message Broker)]
    Redis -->|"6. Consume"| Worker[Celery Worker]
    
    Worker -->|"7a. USE_MODAL_GPU=1"| Modal[Modal T4/A10G GPU]
    Worker -->|"7b. USE_MODAL_GPU=0"| Local[Local danser-cli]
    
    Modal -->|"8. Webhook"| API
    Modal -->|"9. Upload .mp4"| S3
    Local -->|"9. Upload .mp4"| S3
    
    Worker -->|"10. Update Status"| DB
    Client -->|"11. Poll Status"| API
    Client -->|"12. Download Video"| S3

    API -.->|Metrics| Prom[Prometheus]
    Prom -.->|Dashboards| Grafana[Grafana :3727]
    
    Beat[Celery Beat] -->|"Zombie Reaper<br/>every 60s"| Worker
```

## Component Summary

| Component | Technology | Role | Stateless? |
|-----------|-----------|------|------------|
| **API Gateway** | FastAPI + Uvicorn | HTTP entry point, validation, job creation | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Database** | PostgreSQL 16 | Source of truth for jobs, outbox events | — |
| **Message Broker** | Redis 7 | Celery task queue, rate limiter backend | — |
| **Object Storage** | MinIO (dev) / R2 (prod) | Binary artifacts (replays, videos, skins, logs) | — |
| **Dispatcher** | Custom Python async | PostgreSQL outbox → Celery bridge | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Celery Worker** | Celery 5 | Job orchestration, asset resolution | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Celery Beat** | Celery Beat | Scheduled zombie job reaper (60s interval) | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **GPU Compute** | Modal / Local danser | Video rendering via danser-go | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Monitoring** | Prometheus + Grafana | Metrics collection and dashboards | — |

## Design Principles

### 1. Guaranteed Job Delivery
The **Transactional Outbox pattern** ensures that job creation and dispatch are atomic. A job is never created without a corresponding dispatch event in the same database transaction.

### 2. Stateless Everything
All processing components (API, Dispatcher, Workers) are stateless and can be horizontally scaled. State lives exclusively in PostgreSQL and Redis.

### 3. Defense-in-Depth
Security is implemented at every layer — from Cloudflare edge protection, through API-level validation and rate limiting, to subprocess environment sandboxing.

### 4. Fail-Safe Defaults
- Stuck jobs are automatically reaped after 15 minutes
- Failed dispatch events are retried up to 3 times before going to the Dead Letter Queue
- The Dispatcher reconnects with exponential backoff + jitter

### 5. Observability by Default
Every component emits Prometheus metrics. Structured JSON logging with correlation IDs (`request_id`, `job_id`, `event_id`, `worker_id`) enables end-to-end tracing.
