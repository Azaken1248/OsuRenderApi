# OsuRender Architecture Certification

This document is the permanent evidence trail for the OsuRender infrastructure.
Each phase records what was proven, when, and at which commit.

Run `./test.sh` to re-certify at any time.

---

## Phase 1 Certification — Outbox Reliability

**Date:** 2026-06-12  
**Commit:** `b787005bccfcacedc5a5b78e67fcae9df1542417`  
**Test file:** `tests/test_chaos.py`

| # | Test | Guarantee | How it's proven |
|---|------|-----------|-----------------|
| A1 | Lost Notification Recovery | `LISTEN/NOTIFY` is **not required** for correctness | Disables the Postgres trigger, inserts an event, verifies the 60-second safety poll picks it up and processes it to `PROCESSED`. |
| A2 | Dispatcher Crash Recovery | No job loss after a mid-drain dispatcher crash | Inserts 500 events, kills the dispatcher mid-drain with `SIGKILL`, resets stuck `PROCESSING` events to `PENDING`, restarts dispatcher, verifies all 500 reach terminal state. |
| A3 | Notification Storm | Event aggregation prevents O(n) drain calls | Inserts 1000 events across 10 bulk INSERTs, verifies the dispatcher batches them into fewer than 50 `Claimed` log lines (batch size = 100). |
| A4 | Stuck Processing Sweeper | The sweeper SQL correctly resets 5-minute-old `PROCESSING` events | Inserts an event with `PROCESSING` status and `processing_started_at` 10 minutes in the past, runs `sweep_stuck_events()` directly, verifies it reverts to `PENDING`. |
| A5 | Outbox Claim Race | `FOR UPDATE SKIP LOCKED` prevents duplicate batch claims | Stops the containerized dispatcher. Inserts 1000 `PENDING` events. Runs 3 local `OutboxDispatcher` instances concurrently, draining in parallel. Verifies `total_claimed == 1000` exactly — no duplicates, no missed events. |

---

## Phase 2 Certification — Operational Hardening

**Date:** 2026-06-12  
**Commit:** `b787005bccfcacedc5a5b78e67fcae9df1542417`  
**Test file:** `tests/test_chaos.py`

| # | Test | Guarantee | How it's proven |
|---|------|-----------|-----------------|
| B1 | Duplicate Worker Execution | Worker idempotency via atomic `UPDATE ... WHERE status = QUEUED` | Dispatches `_process_render_job(job_id)` twice concurrently via `asyncio.gather`. The first worker atomically transitions `QUEUED → DOWNLOADING` (rowcount=1). The second sees rowcount=0 and returns `"aborted"`. Asserts exactly one abort. |
| C1 | Redis Failure Recovery | Dispatcher retries on broker failure instead of losing events | Simulates the dispatcher's exact error-handling SQL path: claims an event (`PENDING → PROCESSING`), simulates a `ConnectionError` from Redis, verifies the dispatcher increments `retry_count` and reverts the event to `PENDING`. |
| C3 | Retry Exhaustion | Poison-pill events are terminated after max retries | Inserts an event with `retry_count=3`. Executes the dispatcher's retry logic (`new_retry = 4 > 3`). Verifies the event is marked `FAILED` — not retried forever. |
| D1 | Queue Circuit Breaker | `MAX_QUEUED` limit cannot be bypassed | Inserts `max_queued + 50` jobs directly into Postgres. Submits a real HTTP `POST /v1/render` with a valid `.osr` replay. Asserts the API returns `503 Service Unavailable`. |
| E1 | Advisory Lock Race | `pg_advisory_xact_lock` serializes per-IP concurrency | Fires 50 concurrent `POST /v1/render` requests from the same `X-Forwarded-For` IP. Asserts `success_count <= 2` (the per-IP active job limit). The advisory lock ensures no race condition bypasses the count. |

---

## Admission Control Hierarchy (verified by D1 + E1)

```
Request
  │
  ├─ 1. File size / extension check          → 400
  ├─ 2. osrparse structural validation       → 415
  ├─ 3. SlowApi rate limit (5/min per IP)    → 429
  ├─ 4. Queue depth circuit breaker          → 503
  ├─ 5. pg_advisory_xact_lock (per-IP)       → 429
  ├─ 6. Active job count per IP (≤ 2)        → 429
  ├─ 7. DB insert + outbox event (atomic)
  └─ 8. S3 upload (post-commit, fail-safe)   → 500 + job marked FAILED
```

---

## Infrastructure Under Test

| Component | Version | Role |
|-----------|---------|------|
| PostgreSQL | 16 | Jobs, outbox, advisory locks |
| Redis | 7-alpine | Celery broker, SlowApi rate limiting |
| MinIO | latest | S3-compatible replay/video storage |
| FastAPI | 0.115+ | API gateway |
| Celery | 5.x | Async render worker |
| Custom Dispatcher | — | Outbox → Celery bridge via `LISTEN/NOTIFY` + safety poll |

---

## How to Re-Certify

```bash
./test.sh
```

All 10 tests must pass. If any fail, the architecture guarantee they represent is broken.

---

## Future Phases

### Phase 3 — Observability (planned)
- [ ] Prometheus metrics (`prometheus-fastapi-instrumentator`)
- [ ] Custom counter: `stuck_events_recovered`
- [ ] Deterministic builds via `pip-compile`
- [ ] `reap_zombie_jobs` Celery Beat task certification
