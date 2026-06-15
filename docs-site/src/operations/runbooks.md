---
title: "Incident Runbooks"
description: "Operational runbooks for common OsuRender incidents — stuck jobs, worker failures, database issues, and storage problems."
---

# Incident Runbooks

Operational procedures for common failure scenarios.

---

## PostgreSQL Failure

### Symptoms
- `Dispatcher connection lost` errors in logs
- `listener_reconnects_total{reason="postgres"}` metric spike
- API returning 500 errors

### Actions
1. **Check DB Status**: `docker ps` to verify `osurender-postgres` is running
2. **View Logs**: `docker logs --tail 100 osurender-postgres` — look for OOM kills, corruptions, or max connections
3. **Connections**: If max connections reached, restart API instances to flush pools, or increase `max_connections` in `docker-compose.yml` (default: 200)
4. **Recovery**: The Dispatcher automatically reconnects using exponential backoff with jitter (3-10s). No manual restart required.

---

## Worker Failure (Celery/Modal)

### Symptoms
- `active_render_workers` drops to 0 while `queue_depth > 0`
- `NoActiveWorkers` alert triggers
- `zombie_jobs_reaped_total` increasing

### Actions
1. **Check Celery**: `docker logs --tail 100 osurender-worker`
2. **Check Modal**: Log into [Modal dashboard](https://modal.com) → verify `osurender-gpu-worker` status
3. **Queue Health**: If tasks queued but not processing, check Redis. Flush Celery queues if corrupted: `docker-compose exec redis redis-cli FLUSHALL`
4. **Recovery**: Failed jobs are automatically recovered by `reap_zombie_jobs` (runs every 60s) and retried up to 3 times.

---

## Storage Failure (R2/MinIO)

### Symptoms
- `StorageFailures` alert triggers
- `storage_failures_total` spikes
- API 500 errors on job submission
- Workers aborting during download phase

### Actions
1. **Credentials**: Verify `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY` in `.env`
2. **Network**: Ensure worker containers can resolve `STORAGE_ENDPOINT`
3. **Provider Status**: Check [Cloudflare Status](https://www.cloudflarestatus.com/) for R2 issues
4. **Recovery**: Jobs that fail to download are marked FAILED. Replay using the DLQ script once storage is restored.

---

## Queue Saturation

### Symptoms
- `QueueDepthHigh` or `QueueDepthCritical` alerts
- API returning 503 Service Unavailable

### Actions
1. **Scale Workers**: Increase Celery concurrency: `-c 4` in `docker-compose.yml`, or `docker-compose up -d --scale worker=3`
2. **Modal Limits**: Check if your Modal account hit concurrent invocation limits
3. **Abuse Detection**: Check Grafana for submission spikes from a single IP. May need Cloudflare WAF rules.
4. **Increase Capacity**: Raise `MAX_QUEUED` in configuration if infrastructure can handle it.

---

## Cloudflare Failure / IP Spoofing

### Symptoms
- Unusually high traffic bypassing rate limits
- Valid requests getting rate limited because `CF-Connecting-IP` is missing

### Actions
1. **Origin Shield**: Verify firewall only allows traffic from [Cloudflare IP ranges](https://www.cloudflare.com/ips/)
2. **Headers**: Ensure `CF-Connecting-IP` is trusted. If bypassed, attacker is hitting origin directly.

---

## Dead Letter Queue Growing

### Symptoms
- `DeadLetterQueueGrowing` alert
- Events stuck in `FAILED` status

### Actions
1. **Inspect**: Query PostgreSQL for failed events:
   ```sql
   SELECT id, event_type, last_error, created_at 
   FROM outbox_events WHERE status = 'FAILED';
   ```
2. **Replay**: Run `python scripts/replay_dead_letters.py` to reset failed events to PENDING
3. **Root Cause**: Check `last_error` for patterns — usually Redis connectivity or Celery task failures
