# Quick Start

Get OsuRender API running and submit your first render in under 5 minutes.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)
- A [Modal](https://modal.com) account (only if using GPU rendering)
- An [osu! API key](https://osu.ppy.sh/p/api) for beatmap resolution

## 1. Clone & Configure

```bash
git clone https://github.com/Azaken1248/OsuRenderApi.git
cd OsuRenderApi
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
OSU_API_KEY=your_osu_api_key_here
USE_MODAL_GPU=0          # Set to 1 for GPU rendering
```

## 2. Start the Stack

```bash
docker-compose up -d --build
```

This brings up **7 services**:

| Service | Port | Description |
|---------|------|-------------|
| `osurender-api` | `8727` | FastAPI gateway |
| `osurender-dispatcher` | — | Outbox event dispatcher |
| `osurender-worker` | — | Celery render worker |
| `osurender-worker-beat` | — | Celery beat scheduler |
| `osurender-postgres` | `5432` | PostgreSQL database |
| `osurender-redis` | `6379` | Redis message broker |
| `osurender-prometheus` | `9090` | Prometheus metrics |
| `osurender-grafana` | `3727` | Grafana dashboards |

Wait ~10 seconds for all services to initialize.

## 3. Verify Health

```bash
curl http://localhost:8727/health
```

```json
{ "status": "healthy" }
```

## 4. Submit a Render

Upload a `.osr` replay file:

::: code-group

```bash [curl]
curl -X POST http://localhost:8727/v1/render \
  -F "replay=@my_replay.osr" \
  -F "skin=Default" \
  -F "resolution=1080p" \
  -F "bg_dim=0.95"
```

```python [Python]
import httpx

with open("my_replay.osr", "rb") as f:
    response = httpx.post(
        "http://localhost:8727/v1/render",
        files={"replay": ("replay.osr", f, "application/octet-stream")},
        data={
            "skin": "Default",
            "resolution": "1080p",
            "bg_dim": "0.95",
        },
    )

print(response.json())
```

```javascript [JavaScript]
const form = new FormData();
form.append("replay", fileInput.files[0]);
form.append("skin", "Default");
form.append("resolution", "1080p");
form.append("bg_dim", "0.95");

const res = await fetch("http://localhost:8727/v1/render", {
  method: "POST",
  body: form,
});

const data = await res.json();
console.log(data);
```

:::

**Response** (HTTP 202 Accepted):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "links": {
    "status": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## 5. Poll Job Status

```bash
curl http://localhost:8727/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "rendering",
  "progress": 45.5,
  "map_title": "Omoi - Teo [Expert]",
  "created_at": "2026-06-08T10:00:00Z",
  "updated_at": "2026-06-08T10:02:30Z",
  "error_message": null,
  "config": {
    "skin": "Default",
    "resolution": "1080p",
    "bg_dim": 0.95
  },
  "artifacts": {
    "video_url": null,
    "thumbnail_url": null,
    "logs_url": "/v1/artifacts/logs/550e8400-e29b-41d4-a716-446655440000.log"
  }
}
```

## 6. Download the Video

Once `status` is `"completed"`:

```bash
# The artifacts.video_url will contain the path
curl -L http://localhost:8727/v1/artifacts/videos/550e8400-e29b-41d4-a716-446655440000.mp4 \
  -o rendered_video.mp4
```

## Interactive API Docs

The API ships with interactive documentation:

- **Swagger UI**: [https://render.azaken.com/api/docs](https://render.azaken.com/api/docs)
- **ReDoc**: [https://render.azaken.com/api/redoc](https://render.azaken.com/api/redoc)

## What's Next?

- [Configuration Reference](/src/getting-started/configuration) — All environment variables explained
- [API Reference](/src/api-reference/overview) — Complete endpoint documentation
- [Architecture](/src/architecture/system-overview) — How it all works under the hood
