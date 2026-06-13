# OsuRenderApi — Big Tech Readiness Roadmap

## Executive Summary

OsuRenderApi already demonstrates architecture quality significantly above the average open-source backend:

* Event-driven architecture
* Transactional Outbox Pattern
* PostgreSQL as source of truth
* SKIP LOCKED queue draining
* Advisory locking
* Object storage abstraction
* Stateless API tier
* Worker separation
* HMAC authentication
* Zip bomb protection

The primary gap between OsuRenderApi and systems found at companies such as Stripe, Cloudflare, Google, or Meta is not architecture.

The primary gap is:

* Observability
* Operations
* Reliability guarantees
* Incident management
* Engineering process maturity

---

# Current Assessment

| Category             | Score |
| -------------------- | ----- |
| Architecture         | 9.0   |
| Reliability          | 8.0   |
| Security             | 8.5   |
| Observability        | 7.0   |
| Production Readiness | 8.4   |

---

# Phase 1 — Full Observability

## Goal

Every render should be traceable end-to-end.

---

## Implement Distributed Tracing

Adopt OpenTelemetry.

Instrument:

* FastAPI
* PostgreSQL
* Dispatcher
* Modal Worker
* R2/S3 Storage
* External API calls

### Required IDs

Every request must carry:

```text
request_id
trace_id
job_id
event_id
worker_id
modal_invocation_id
```

---

## Structured Logging

Replace free-form logs.

Format:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "trace_id": "...",
  "job_id": "...",
  "event_id": "...",
  "worker_id": "...",
  "component": "dispatcher",
  "message": "Job dispatched"
}
```

### Recommended

* structlog
* python-json-logger

---

## Grafana Dashboards

Create dashboards for:

### API

* Request Rate
* Error Rate
* Latency

### Queue

* Pending Events
* Processing Events
* Failed Events
* Queue Age

### Workers

* Active Workers
* Active Renders
* Worker Crashes

### Storage

* Upload Failures
* Download Failures
* Latency

---

## Success Criteria

Given only a job ID, an engineer can identify:

* Who submitted it
* Which event created it
* Which worker processed it
* Which storage operations occurred
* Why it failed

within 30 seconds.

---

# Phase 2 — Reliability Hardening

## Fix Outbox State Machine

Current:

```text
PENDING
↓
PROCESSING
↓
PROCESSED
```

Recommended:

```text
PENDING
↓
PROCESSING
↓
DISPATCHED
↓
STARTED
↓
COMPLETED
```

---

## Worker Acknowledgements

Worker must explicitly acknowledge:

```text
Job Received
Job Started
Job Completed
Job Failed
```

Dispatcher should not assume success after enqueue.

---

## Dead Letter Queue

Create:

```sql
dead_letter_events
```

Store:

```text
event_id
payload
error
retry_count
failed_at
```

---

## DLQ Operations

Engineers must be able to:

```text
Replay Event
Retry Event
Inspect Event
Archive Event
```

---

## Worker Heartbeats

Track:

```text
worker_id
last_seen
current_job
version
```

---

## Orphan Recovery

If worker disappears:

```text
heartbeat timeout
↓
job marked orphaned
↓
requeue
```

---

## Idempotency

All dispatch operations must be safely repeatable.

A duplicate dispatch should never corrupt state.

---

## Success Criteria

No job can be silently lost.

---

# Phase 3 — Security Maturity

## Supply Chain Security

Add:

### Dependabot

Dependency updates.

### Trivy

Container scanning.

### Secret Scanning

Detect:

```text
AWS Keys
R2 Keys
Tokens
Passwords
```

### SBOM

Generate:

```text
CycloneDX
or
SPDX
```

on every release.

---

## Artifact Integrity

Hash:

```text
Replay
Skin
Render Output
```

Store checksums.

---

## Cloudflare Hardening

Require:

* Cloudflare-only ingress
* Authenticated Origin Pulls
* Firewall rules allowing only Cloudflare IPs

Never trust CF-Connecting-IP unless origin is protected.

---

## ZIP Validation

Validate archive structure during upload.

Reject:

* Corrupted archives
* Deep nesting
* Suspicious compression ratios

before storage.

---

## Security Metrics

Track:

```text
Webhook Failures
Rate Limit Violations
Upload Validation Failures
Authentication Failures
```

---

# Phase 4 — SLO Program

## Define Service Objectives

### API Availability

```text
99.9%
```

---

### Queue Dispatch

```text
99% dispatched within 60s
```

---

### Render Start

```text
95% begin within 5 min
```

---

### Render Completion

```text
95% complete within 15 min
```

---

### Data Durability

```text
99.99%
```

No lost jobs.

---

## Alerting

Alert on:

### Queue

```text
Queue depth > threshold
```

### Workers

```text
No workers alive
```

### Database

```text
Connection failures
```

### Storage

```text
Upload failures
```

---

# Phase 5 — Chaos Engineering

## Automated Failure Injection

---

### Worker Death

Kill active worker.

Expected:

```text
Automatic recovery
```

---

### PostgreSQL Restart

Expected:

```text
Dispatcher reconnects
```

---

### Notification Loss

Disable LISTEN/NOTIFY.

Expected:

```text
Polling recovers queue
```

---

### Storage Failure

Simulate R2 outage.

Expected:

```text
Retries
Visibility
Recovery
```

---

## Success Criteria

Every critical dependency has:

* Recovery tests
* Recovery documentation
* Expected behavior

---

# Phase 6 — Internal Operations Platform

## Admin Dashboard

Required functionality:

### Job Management

```text
Search Job
View Job
Retry Job
Cancel Job
```

---

### Queue Management

```text
Pending
Processing
Failed
DLQ
```

---

### Worker Management

```text
View Workers
View Health
View Current Jobs
```

---

### Trace Explorer

Search by:

```text
job_id
trace_id
event_id
worker_id
```

---

## Success Criteria

Most incidents resolved without touching PostgreSQL directly.

---

# Phase 7 — Engineering Process

## CI/CD Gates

Every merge should run:

### Tests

```text
Unit
Integration
Chaos
```

---

### Security

```text
Dependency Audit
Container Scan
Secret Scan
```

---

### Quality

```text
Lint
Type Check
Coverage
```

---

## Architecture Decision Records

Create ADRs for:

### Outbox Pattern

Why chosen.

### PostgreSQL Queue

Why chosen over RabbitMQ.

### Modal

Why chosen over Kubernetes.

### Storage

Why R2 chosen.

### Security Model

Threat model and assumptions.

---

## Runbooks

Document:

### PostgreSQL Failure

### Worker Failure

### Storage Failure

### Queue Saturation

### Cloudflare Failure

### Modal Failure

---

## Incident Response

Standardized postmortem template:

```text
Timeline
Root Cause
Impact
Contributing Factors
Corrective Actions
Preventative Actions
```

---

# Things Not Worth Building Yet

Avoid:

* Kafka
* RabbitMQ
* Event Sourcing
* CQRS
* Service Mesh
* Kubernetes
* Multi-region complexity

None solve your current bottlenecks.

---

# Ideal End State

An engineer should be able to:

1. Trace any render end-to-end.
2. Recover from worker crashes automatically.
3. Replay failed events safely.
4. Diagnose incidents in minutes.
5. Pass a professional security review.
6. Operate the system with documented procedures.
7. Deploy changes confidently.

At that point, the repo would be much closer to what you'd see in a well-run SaaS engineering organization than a typical open-source project, while still remaining inexpensive to operate.
