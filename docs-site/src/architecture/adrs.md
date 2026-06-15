---
title: "Architecture Decision Records"
description: "Key architectural decisions in OsuRender API — rationale for technology choices, trade-offs, and design alternatives considered."
---

# Architecture Decision Records

This page documents the key architectural decisions made during the design and implementation of OsuRender API.

---

## ADR-001: Transactional Outbox Pattern

**Status:** Accepted

### Context
The system needs to reliably dispatch render jobs from the API tier to GPU workers. Direct message broker enqueueing during the HTTP request creates a dual-write problem: if the database commit succeeds but the broker publish fails (or vice versa), the system enters an inconsistent state.

### Decision
Implement the Transactional Outbox pattern. When a render job is created, both the `Job` row and an `OutboxEvent` row are inserted in the same PostgreSQL transaction. A dedicated `OutboxDispatcher` process polls/listens for pending events and dispatches them to Celery workers.

### Consequences
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Guaranteed consistency between job creation and dispatch — no lost jobs
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Natural retry semantics via outbox event state machine
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Dispatcher can be horizontally scaled using `FOR UPDATE SKIP LOCKED`
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Adds latency between job creation and actual dispatch (typically < 1s)
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Requires a dedicated dispatcher process

---

## ADR-002: PostgreSQL as Queue Backend

**Status:** Accepted

### Context
Options considered: RabbitMQ, Amazon SQS, Redis Streams, PostgreSQL with `SKIP LOCKED`.

### Decision
Use PostgreSQL with `FOR UPDATE SKIP LOCKED` as the queue backend via the Outbox pattern.

### Consequences
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> No additional infrastructure dependency
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Transactional consistency with job data
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Sufficient throughput for 10K+ jobs/day
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Not suitable for millions of messages/second (not our scale)
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Queue operations add load to the primary database

---

## ADR-003: Modal for GPU Compute

**Status:** Accepted

### Context
Options considered: Self-managed Kubernetes with GPU nodes, AWS EC2 GPU instances, Modal serverless GPUs, RunPod.

### Decision
Use Modal's serverless GPU infrastructure for render execution.

### Consequences
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Zero GPU infrastructure management
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Pay-per-second billing eliminates idle costs
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Automatic scaling to demand
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Vendor dependency on Modal's platform
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Cold start latency on first invocation
- <img src="/icons/sync.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Mitigation: Local rendering fallback path exists via `USE_MODAL_GPU=0`

---

## ADR-004: Cloudflare R2 for Object Storage

**Status:** Accepted

### Context
Options considered: AWS S3, Cloudflare R2, Self-hosted MinIO.

### Decision
Use Cloudflare R2 for production, MinIO for local development. Both are S3-compatible.

### Consequences
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Zero egress fees (R2's primary advantage)
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> S3-compatible API means code works with MinIO locally
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Fewer regions than AWS S3
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Slightly less mature tooling ecosystem

---

## ADR-005: Defense-in-Depth Security Model

**Status:** Accepted

### Context
The API is publicly accessible via Cloudflare. Threat model includes: unauthenticated abuse, webhook spoofing, IP spoofing, zip bombs, and secret leakage.

### Decision
Implement defense-in-depth with seven layers:

1. **HMAC-SHA256** webhook verification with replay protection (timestamp + nonce)
2. **Cloudflare-only ingress** with `CF-Connecting-IP` extraction
3. **PostgreSQL advisory locks** for per-IP concurrency limits
4. **ZIP structure validation** on upload (ratio, nesting, corruption)
5. **Zip bomb protection** during extraction (physical byte counting)
6. **Subprocess environment allowlisting** — only whitelisted env vars passed to danser
7. **Global error masking** in production mode

### Consequences
- <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Comprehensive protection against known attack vectors
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> Requires Cloudflare infrastructure lockdown at the perimeter level
- <img src="/icons/warning.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> ZIP validation adds upload latency
