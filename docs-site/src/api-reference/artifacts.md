# Artifacts API

<span class="custom-badge badge-get">GET</span> `/v1/artifacts/{key}`

Download or stream a render artifact (video, thumbnail, log, replay, or skin) from object storage.

## How It Works

The artifacts endpoint acts as a proxy to object storage. Depending on the artifact type:

- **Logs** (`logs/`): Content is fetched and returned inline as `text/plain`
- **All others** (`videos/`, `thumbnails/`, `replays/`, `skins/`): Returns a `302 Redirect` to a pre-signed S3/R2 URL

## Valid Prefixes

| Prefix | Content Type | Behavior |
|--------|-------------|----------|
| `logs/` | `text/plain` | Inline content response |
| `videos/` | `video/mp4` | Redirect to pre-signed URL |
| `thumbnails/` | `image/jpeg` | Redirect to pre-signed URL |
| `replays/` | `application/octet-stream` | Redirect to pre-signed URL |
| `skins/` | `application/octet-stream` | Redirect to pre-signed URL |

## Examples

```bash
# Stream render logs
curl http://localhost:8727/v1/artifacts/logs/550e8400-e29b-41d4-a716-446655440000.log

# Download video (follows redirect)
curl -L http://localhost:8727/v1/artifacts/videos/550e8400-e29b-41d4-a716-446655440000.mp4 \
  -o output.mp4

# Download thumbnail
curl -L http://localhost:8727/v1/artifacts/thumbnails/550e8400-e29b-41d4-a716-446655440000.jpg \
  -o thumb.jpg
```

## Error Responses

| Status | Condition |
|--------|-----------|
| `403` | Invalid artifact prefix (path traversal attempt) |
| `404` | Artifact not found in storage |

::: info Log Availability
Logs are available as soon as the render starts — they are uploaded periodically (every 3 seconds) during the render process. You can use this to monitor render progress in real-time.
:::
