# Data Flow & Job Lifecycle

This page details the complete lifecycle of a render job from submission to video delivery.

## End-to-End Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API Gateway
    participant DB as PostgreSQL
    participant S3 as Object Storage
    participant D as Dispatcher
    participant R as Redis
    participant W as Celery Worker
    participant G as Modal GPU

    C->>A: POST /v1/render (.osr + config)
    A->>A: Validate file, rate limits, capacity
    A->>S3: Upload .osr replay
    A->>DB: BEGIN TRANSACTION
    A->>DB: INSERT jobs (status=queued)
    A->>DB: INSERT outbox_events (status=PENDING)
    A->>DB: COMMIT
    A-->>C: 202 Accepted {job_id}

    DB-->>D: LISTEN/NOTIFY new_outbox_event
    D->>DB: SELECT ... FOR UPDATE SKIP LOCKED
    D->>DB: SET status=PROCESSING
    D->>R: celery.delay(process_render_job, job_id)
    D->>DB: SET status=DISPATCHED

    R-->>W: Dequeue task
    W->>DB: UPDATE SET status=downloading (WHERE status=queued)
    W->>S3: Download .osr replay
    W->>W: Parse replay (osrparse)
    W->>W: Fetch beatmap metadata (osu! API)
    W->>DB: UPDATE map_title, beatmap_id, config

    W->>DB: UPDATE SET status=rendering
    W->>G: gpu_render_task.spawn(...)
    G->>S3: Download replay + beatmap + skin
    G->>G: xvfb-run danser-cli (render video)
    G->>S3: Upload .mp4, .jpg thumbnail, .log
    G->>A: POST /v1/jobs/{id}/webhook (HMAC signed)

    A->>DB: UPDATE SET status=completed, artifacts
    A->>DB: UPDATE outbox SET status=PROCESSED

    C->>A: GET /v1/jobs/{job_id}
    A->>DB: SELECT job
    A-->>C: 200 OK {status: completed, artifacts: {...}}
    C->>S3: Download video via presigned URL
```

## Job State Machine

```mermaid
stateDiagram-v2
    [*] --> queued: POST /v1/render
    
    queued --> downloading: Worker claims job<br/>(atomic UPDATE WHERE status=queued)
    downloading --> rendering: Assets resolved,<br/>danser-go starting
    rendering --> completed: Video uploaded,<br/>webhook received
    
    queued --> failed: Dispatch failure<br/>(3 retries exhausted)
    downloading --> failed: Beatmap not found,<br/>download error
    rendering --> failed: Render timeout,<br/>danser error
    
    note right of queued: Zombie reaper checks<br/>every 60s for stuck jobs
    note right of completed: Artifacts available<br/>via /v1/artifacts/
```

## Atomic State Transitions

Job status transitions use **atomic SQL updates** to prevent race conditions:

```python
# Only one worker can claim a job
update_stmt = (
    update(Job)
    .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
    .values(status=JobStatus.DOWNLOADING)
)
result = await db.execute(update_stmt)
if result.rowcount == 0:
    # Another worker already claimed this job
    return "aborted"
```

This ensures that even if duplicate Celery tasks are dispatched for the same job, only one worker will successfully claim it.

## Data Stored Per Job

| Phase | Data Created | Storage |
|-------|-------------|---------|
| **Submission** | Job record, outbox event, `.osr` replay | PostgreSQL, S3 |
| **Downloading** | Beatmap metadata, map title, replay stats | PostgreSQL |
| **Rendering** | Live render logs, progress updates | S3 (periodic), PostgreSQL |
| **Completion** | `.mp4` video, `.jpg` thumbnail, final log | S3 |
| **Failure** | Error message, partial logs | PostgreSQL, S3 |

## Zombie Job Recovery

The `reap_zombie_jobs` Celery Beat task runs every 60 seconds:

1. **Stuck rendering/downloading** (> 15 min): Checks Modal for results, marks as failed if unrecoverable
2. **Stuck queued** (> 5 min): Increments retry counter
3. **Retry exhausted** (> 3 retries): Marks as permanently failed
