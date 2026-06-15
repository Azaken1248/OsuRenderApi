# Legacy Endpoints

<span class="custom-badge badge-deprecated">Deprecated</span>

These endpoints exist for backward compatibility with the original monolithic OsuRender application. **New integrations should use the `/v1/` API.**

## Migration Guide

| Legacy Endpoint | v1 Equivalent | Notes |
|----------------|---------------|-------|
| `POST /render` | `POST /v1/render` | Response format differs |
| `GET /status/{job_id}` | `GET /v1/jobs/{job_id}` | Field names differ |
| `GET /jobs` | `GET /v1/jobs` | Response is array vs. paginated object |
| `GET /video/{job_id}.mp4` | `GET /v1/artifacts/videos/{job_id}.mp4` | Redirects to artifacts |
| `GET /thumbnail/{job_id}.jpg` | `GET /v1/artifacts/thumbnails/{job_id}.jpg` | Redirects to artifacts |
| `GET /logs/{job_id}` | `GET /v1/artifacts/logs/{job_id}.log` | Redirects to artifacts |
| `GET /skins` | `GET /v1/skins` | Same response format |
| `POST /skins/upload` | `POST /v1/skins/upload` | Same behavior |

## Key Differences

### POST /render (Legacy)

The legacy render endpoint returns a different response format:

```json
{
  "job_id": "550e8400e29b41d4a716446655440000",
  "view_url": "/view/550e8400e29b41d4a716446655440000",
  "video_url": "/video/550e8400e29b41d4a716446655440000.mp4"
}
```

Note: The legacy `job_id` uses hex format (no dashes) vs. the v1 API which uses standard UUID format with dashes.

The legacy `quality` parameter maps to v1 `resolution`: `"ultra"` → `"4k"`, everything else → `"1080p"`.

### GET /status/{job_id} (Legacy)

```json
{
  "job_id": "550e8400e29b41d4a716446655440000",
  "status": "complete",
  "percent": 100.0,
  "skin": "Default",
  "map_title": "Kano - Prima Stella [Caged]",
  "created_at": 1717848000.0,
  "last_updated": 1717848330.0,
  "error": null
}
```

Key differences:
- `status` uses `"complete"` instead of `"completed"`
- `percent` instead of `progress`
- Timestamps are Unix floats instead of ISO 8601
- No `artifacts` links object

### GET /jobs (Legacy)

Returns a flat array of the 50 most recent jobs (no pagination, no `total` count).

::: warning
Legacy endpoints delegate to their v1 counterparts internally. They share the same rate limits, validation, and capacity checks.
:::
