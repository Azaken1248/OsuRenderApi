# ADR-001: Transactional Outbox Pattern

## Status
Accepted

## Context
The system needs to reliably dispatch render jobs from the API tier to GPU workers. Direct message broker enqueueing (Redis/Celery) during the HTTP request creates a dual-write problem: if the database commit succeeds but the broker publish fails (or vice versa), the system enters an inconsistent state where either a job exists without a dispatch event, or a dispatch event exists without a job.

## Decision
We implement the Transactional Outbox pattern. When a render job is created, both the `Job` row and an `OutboxEvent` row are inserted in the same PostgreSQL transaction. A dedicated `OutboxDispatcher` process polls/listens for pending events and dispatches them to Celery workers.

## Consequences
- **Positive**: Guaranteed consistency between job creation and dispatch. No lost jobs.
- **Positive**: Natural retry semantics via outbox event state machine.
- **Positive**: Dispatcher can be horizontally scaled using `FOR UPDATE SKIP LOCKED`.
- **Negative**: Adds latency between job creation and actual dispatch (typically < 1s).
- **Negative**: Requires a dedicated dispatcher process.

---

# ADR-002: PostgreSQL as Queue Backend

## Status
Accepted

## Context
The system needed a reliable queue mechanism for job dispatch. Options considered:
- RabbitMQ
- Amazon SQS
- Redis Streams
- PostgreSQL with SKIP LOCKED

## Decision
Use PostgreSQL with `FOR UPDATE SKIP LOCKED` as the queue backend via the Outbox pattern.

## Consequences
- **Positive**: No additional infrastructure dependency.
- **Positive**: Transactional consistency with job data.
- **Positive**: Sufficient throughput for 10k+ jobs/day.
- **Negative**: Not suitable for millions of messages/second (not our scale).
- **Negative**: Queue operations add load to the primary database.

---

# ADR-003: Modal for GPU Compute

## Status
Accepted

## Context
Rendering requires GPU acceleration. Options considered:
- Self-managed Kubernetes with GPU nodes
- AWS EC2 GPU instances
- Modal serverless GPUs
- RunPod

## Decision
Use Modal's serverless GPU infrastructure for render execution.

## Consequences
- **Positive**: Zero GPU infrastructure management.
- **Positive**: Pay-per-second billing eliminates idle costs.
- **Positive**: Automatic scaling to demand.
- **Negative**: Vendor dependency on Modal's platform.
- **Negative**: Cold start latency on first invocation.
- **Mitigation**: Local rendering fallback path exists via `USE_MODAL_GPU=0`.

---

# ADR-004: Cloudflare R2 for Object Storage

## Status
Accepted

## Context
The system stores replays, rendered videos, thumbnails, and skins. Options:
- AWS S3
- Cloudflare R2
- Self-hosted MinIO

## Decision
Use Cloudflare R2 for production, MinIO for local development. Both are S3-compatible.

## Consequences
- **Positive**: Zero egress fees (R2's primary advantage).
- **Positive**: S3-compatible API means code works with MinIO locally.
- **Negative**: Fewer regions than AWS S3.
- **Negative**: Slightly less mature tooling ecosystem.

---

# ADR-005: Security Model

## Status
Accepted

## Context
The API is publicly accessible via Cloudflare. Threat model includes:
- Unauthenticated abuse (rate limiting, queue flooding)
- Webhook spoofing (fake job completions)
- IP spoofing (rate limit bypass)
- Zip bombs (storage/compute abuse)
- Secret leakage (env vars in subprocess)

## Decision
Implement defense-in-depth:
1. HMAC-SHA256 webhook verification with replay protection (timestamp + nonce).
2. Cloudflare-only ingress with `CF-Connecting-IP` extraction.
3. PostgreSQL advisory locks for per-IP concurrency limits.
4. ZIP structure validation on upload (ratio, nesting, corruption).
5. Zip bomb protection during extraction (physical byte counting).
6. Subprocess environment allowlisting.
7. Global error masking in production mode.

## Consequences
- **Positive**: Comprehensive protection against known attack vectors.
- **Negative**: Requires Cloudflare infrastructure lockdown at the perimeter level.
- **Negative**: ZIP validation adds upload latency.
