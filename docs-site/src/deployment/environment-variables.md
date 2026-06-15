# Environment Variables

Complete reference of all environment variables. See [Configuration](/src/getting-started/configuration) for detailed descriptions.

## Quick Reference

```env
# ─── Application ───
APP_NAME=OsuRender API
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
CORS_ORIGINS=["*"]
API_BASE_URL=http://localhost:8000

# ─── Database ───
DATABASE_URL=postgresql+asyncpg://osurender:osurender@localhost:5433/osurender
DATABASE_URL_SYNC=postgresql+psycopg2://osurender:osurender@localhost:5433/osurender

# ─── Redis ───
REDIS_URL=redis://localhost:6379/0

# ─── Object Storage ───
STORAGE_ENDPOINT=localhost:9000
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin
STORAGE_BUCKET_NAME=osurender
STORAGE_USE_SSL=false

# ─── Modal GPU ───
USE_MODAL_GPU=0
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
WEBHOOK_SECRET=

# ─── osu! API ───
OSU_API_KEY=your_osu_api_key_here

# ─── Rendering Defaults ───
DEFAULT_SKIN=Default
DEFAULT_BG_DIM=0.95
DEFAULT_RESOLUTION=1080p
RENDER_TIMEOUT_SECONDS=600

# ─── Limits ───
MAX_REPLAY_SIZE_MB=50
MAX_SKIN_SIZE_MB=200
MAX_QUEUED=100
MAX_RENDERING=20

# ─── Docker-internal (set in docker-compose.yml) ───
WORKER_TYPE=api
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
```

## Per-Service Overrides

The Docker Compose file sets `WORKER_TYPE` differently for each service:

| Container | `WORKER_TYPE` |
|-----------|---------------|
| `osurender-api` | `api` |
| `osurender-dispatcher` | `dispatcher` |
| `osurender-worker` | `celery` |
| `osurender-worker-beat` | `beat` |
