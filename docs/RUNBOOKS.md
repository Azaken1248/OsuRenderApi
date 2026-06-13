# Incident Runbooks

## PostgreSQL Failure

### Symptoms
- `Dispatcher connection lost` errors in logs.
- `Listener_reconnects_total{reason="postgres"}` metric spike.
- API returning 500 errors.

### Actions
1. **Check DB Status**: Run `docker ps` to verify the `osurender-postgres` container is running.
2. **View Logs**: `docker logs --tail 100 osurender-postgres`. Look for OOM kills, corruptions, or max connections reached.
3. **Connections**: If max connections reached, restart the API instances to flush connection pools, or increase `max_connections` in `docker-compose.yml`.
4. **Recovery**: The Dispatcher will automatically reconnect using exponential backoff with jitter once the database is available again. No manual dispatcher restart is required.

---

## Worker Failure (Celery/Modal)

### Symptoms
- `Active_render_workers` metric drops to 0 while queue depth > 0.
- `NoActiveWorkers` alert triggers.
- Zombie jobs reaped metric increases.

### Actions
1. **Check Celery**: View worker logs: `docker logs --tail 100 osurender-worker`.
2. **Check Modal**: Log into Modal dashboard and verify the `osurender-gpu-worker` app status.
3. **Queue Health**: If tasks are queued but not processing, check Redis (`osurender-redis`). Flush Celery queues if corrupted.
4. **Recovery**: Failed jobs will be automatically recovered by the `reap_zombie_jobs` Celery beat task and retried up to 3 times. If they fail completely, they are sent to the Dead Letter Queue.

---

## Storage Failure (R2/MinIO)

### Symptoms
- `StorageFailures` alert triggers.
- `storage_failures_total` metric spikes.
- API 500 errors on job submission (upload fails).
- Workers aborting during `download` phase.

### Actions
1. **Credentials**: Verify `STORAGE_ACCESS_KEY` and `STORAGE_SECRET_KEY` in environment.
2. **Network**: Ensure the worker containers can resolve `STORAGE_ENDPOINT`.
3. **Provider Status**: Check Cloudflare R2 Status page.
4. **Recovery**: Jobs that fail to download will be marked as FAILED. You can replay them using the DLQ script once storage is restored.

---

## Queue Saturation

### Symptoms
- `QueueDepthHigh` or `QueueDepthCritical` alerts.
- API returning 503 Service Unavailable (queue full).

### Actions
1. **Scale Workers**: If using Celery workers, increase concurrency `-c 4` in `docker-compose.yml`.
2. **Modal Limits**: If using Modal, check if your account hit concurrent invocation limits.
3. **Abuse**: Check Grafana for a spike in submissions from a single IP. Rate limiting should prevent this, but distributed attacks might require Cloudflare WAF rules.
4. **Capacity**: Increase `MAX_QUEUED` in configuration if infrastructure can handle the buffer.

---

## Cloudflare Failure / IP Spoofing

### Symptoms
- Unusually high traffic bypassing rate limits.
- Valid requests returning rate limit errors because `CF-Connecting-IP` is missing or spoofed.

### Actions
1. **Origin Shield**: Verify that your server firewall (iptables/UFW or AWS Security Group) is set to ONLY allow traffic from `https://www.cloudflare.com/ips/`.
2. **Headers**: Ensure `CF-Connecting-IP` is trusted. If bypassed, an attacker is hitting the origin directly.

---

## Managing Dead Letters

### Symptoms
- `DeadLetterQueueGrowing` alert.
- Events stuck in `FAILED` status.

### Actions
1. **Inspect**: Review the failed events and their stack traces in PostgreSQL `outbox_events` table.
2. **Replay**: Run `scripts/replay_dead_letters.py` to reset the failed events back to `PENDING` and restart dispatch.
