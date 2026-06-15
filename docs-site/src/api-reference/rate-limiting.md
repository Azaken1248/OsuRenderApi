---
title: "Rate Limiting"
description: "Rate limiting policies, per-endpoint quotas, burst allowances, and strategies for handling 429 responses in OsuRender API."
---

# Rate Limiting

OsuRender API implements a multi-layered rate limiting and admission control strategy to prevent abuse and ensure fair resource allocation.

## Rate Limit Tiers

### Per-Endpoint Limits (SlowApi)

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /v1/render` | 5 requests | per minute |
| `POST /v1/skins/upload` | 2 requests | per minute |
| `POST /skins/upload` (legacy) | 5 requests | per minute |

Rate limits are enforced by [SlowApi](https://github.com/laurentS/slowapi) backed by Redis.

### Per-IP Concurrency Limits

Each IP address is limited to **2 active jobs** (in `queued`, `downloading`, or `rendering` status) at any time.

This limit is enforced using **PostgreSQL advisory locks** (`pg_advisory_xact_lock`) to prevent race conditions under concurrent submissions:

```python
# Hash the IP to a 64-bit lock ID
ip_lock_id = int.from_bytes(
    hashlib.sha256(client_ip.encode()).digest()[:8], "little", signed=True
)
await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": ip_lock_id})

# Now safely count active jobs for this IP
active_count = await db.scalar(
    select(func.count()).where(
        Job.client_ip == client_ip,
        Job.status.in_([JobStatus.QUEUED, JobStatus.RENDERING, JobStatus.DOWNLOADING]),
    )
)
```

### Global Capacity Limits

| Limit | Default | Description |
|-------|---------|-------------|
| `MAX_QUEUED` | 100 | Maximum jobs in `queued` state |
| `MAX_RENDERING` | 20 | Maximum jobs in `rendering`/`downloading` state |

When either limit is reached, the API returns `503 Service Unavailable` — acting as a circuit breaker.

## IP Detection

The API uses the following priority for client IP detection:

1. `CF-Connecting-IP` header (Cloudflare)
2. Direct `request.client.host`

```python
def get_real_ip(request):
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    return get_remote_address(request)
```

::: warning
If Cloudflare is bypassed, an attacker can hit the origin directly and `CF-Connecting-IP` won't be set. Ensure your origin server firewall only allows Cloudflare IP ranges.
:::

## Response Headers

When rate limited, the response includes:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1717848060
```

## Admission Control Hierarchy

Requests pass through validation checks in this order:

```
1. File extension / size check         → 400 / 413
2. osrparse structural validation      → 415
3. Skin name regex validation          → 422
4. SlowApi rate limit (5/min per IP)   → 429
5. Global queue depth circuit breaker  → 503
6. Global rendering capacity check     → 503
7. pg_advisory_xact_lock (per-IP)      → serialized
8. Per-IP active job count (≤ 2)       → 429
9. Job creation + outbox event         → atomic
10. S3 replay upload                   → 500 on failure
```
