# Dead Letter Queue Management

Events that fail dispatch after 3 retries are moved to `FAILED` status in the `outbox_events` table, forming the Dead Letter Queue (DLQ).

## What Triggers DLQ Entries

| Cause | Typical Error |
|-------|--------------|
| Redis/Celery unavailable | `ConnectionError: Error while reading from socket` |
| Worker task registration failure | `NotRegistered: process_render_job` |
| Database constraint violation | `IntegrityError: duplicate key` |
| Stuck in PROCESSING > 5 min (3x) | `Stuck in PROCESSING state too many times` |

## Inspecting the DLQ

```sql
-- Count failed events
SELECT COUNT(*) FROM outbox_events WHERE status = 'FAILED';

-- View details
SELECT id, event_type, payload, last_error, retry_count, created_at
FROM outbox_events 
WHERE status = 'FAILED'
ORDER BY created_at DESC;

-- Check which jobs are affected
SELECT oe.id, oe.payload->>'job_id' as job_id, j.status as job_status, oe.last_error
FROM outbox_events oe
LEFT JOIN jobs j ON j.id = (oe.payload->>'job_id')::uuid
WHERE oe.status = 'FAILED';
```

## Replaying Failed Events

Use the provided script to reset failed events back to `PENDING`:

```bash
python scripts/replay_dead_letters.py
```

The script will:
1. List all `FAILED` events with their errors
2. Ask for confirmation
3. Reset `status` to `PENDING`, `retry_count` to 0, and clear `last_error`
4. The Dispatcher will automatically pick them up on the next drain cycle

### Manual Replay

```sql
-- Replay all failed events
UPDATE outbox_events 
SET status = 'PENDING', retry_count = 0, last_error = NULL 
WHERE status = 'FAILED';

-- Replay a specific event
UPDATE outbox_events 
SET status = 'PENDING', retry_count = 0, last_error = NULL 
WHERE id = 'event-uuid-here';
```

## Monitoring

The `outbox_failed_events` Prometheus gauge tracks the DLQ size. The `DeadLetterQueueGrowing` alert fires if any failed events exist for more than 15 minutes.

## Prevention

- Ensure Redis is healthy and accessible
- Monitor `listener_reconnects_total` for early warning signs
- Keep Celery workers registered and running
