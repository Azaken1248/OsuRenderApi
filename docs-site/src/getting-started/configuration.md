---
title: "Configuration"
description: "Complete configuration reference for OsuRender API — environment variables, rendering presets, storage backends, and worker tuning."
---

# Configuration Reference

OsuRender API is configured entirely through environment variables, managed by [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). Copy `.env.example` to `.env` and customize as needed.

## Application Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | `str` | `OsuRender API` | Application display name |
| `APP_HOST` | `str` | `0.0.0.0` | Server bind address |
| `APP_PORT` | `int` | `8000` | Server port |
| `DEBUG` | `bool` | `false` | Enable debug mode (verbose SQL, full error messages) |
| `CORS_ORIGINS` | `list[str]` | `["*"]` | Allowed CORS origins |
| `API_BASE_URL` | `str` | `http://localhost:8000` | Public-facing base URL for webhook callbacks |

## Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | `str` | `postgresql+asyncpg://osurender:osurender@localhost:5433/osurender` | Async PostgreSQL connection string (used by API + Dispatcher) |
| `DATABASE_URL_SYNC` | `str` | `postgresql+psycopg2://osurender:osurender@localhost:5433/osurender` | Sync PostgreSQL connection string (used by Alembic) |

## Redis

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `REDIS_URL` | `str` | `redis://localhost:6379/0` | Redis connection URL (Celery broker + rate limiter backend) |

## Object Storage (S3-compatible)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STORAGE_ENDPOINT` | `str` | `localhost:9000` | S3-compatible endpoint (MinIO locally, R2 in production) |
| `STORAGE_ACCESS_KEY` | `str` | `minioadmin` | S3 access key |
| `STORAGE_SECRET_KEY` | `str` | `minioadmin` | S3 secret key |
| `STORAGE_BUCKET_NAME` | `str` | `osurender` | Bucket name for all artifacts |
| `STORAGE_USE_SSL` | `bool` | `false` | Enable HTTPS for storage connections |

## Modal GPU

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `USE_MODAL_GPU` | `str` | `0` | Set to `1` to offload rendering to Modal GPU instances |
| `MODAL_TOKEN_ID` | `str` | *(empty)* | Modal API token ID |
| `MODAL_TOKEN_SECRET` | `str` | *(empty)* | Modal API token secret |
| `WEBHOOK_SECRET` | `str` | *(empty)* | HMAC-SHA256 secret for webhook verification |

## osu! API

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OSU_API_KEY` | `str` | *(empty)* | osu! API v1 key for beatmap resolution (required) |

## Rendering Defaults

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_SKIN` | `str` | `Default` | Default skin if none specified |
| `DEFAULT_BG_DIM` | `float` | `0.95` | Default background dim (0.0 – 1.0) |
| `DEFAULT_RESOLUTION` | `str` | `1080p` | Default resolution (`1080p` or `4k`) |
| `RENDER_TIMEOUT_SECONDS` | `int` | `600` | Hard timeout for render jobs (10 minutes) |

## Upload Limits

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_REPLAY_SIZE_MB` | `int` | `50` | Maximum `.osr` file upload size |
| `MAX_SKIN_SIZE_MB` | `int` | `200` | Maximum `.osk` file upload size |

## Capacity Limits

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_QUEUED` | `int` | `100` | Maximum number of jobs in `queued` state (circuit breaker) |
| `MAX_RENDERING` | `int` | `20` | Maximum number of jobs in `rendering`/`downloading` state |

## Worker Types

The `WORKER_TYPE` environment variable controls which process starts in the Docker container:

| Value | Process | Description |
|-------|---------|-------------|
| `api` | Uvicorn + FastAPI | HTTP API gateway |
| `dispatcher` | OutboxDispatcher | PostgreSQL → Celery bridge |
| `celery` | Celery Worker | Render job processor |
| `beat` | Celery Beat | Scheduled task scheduler (zombie reaper) |

::: tip
In Docker Compose, each service sets `WORKER_TYPE` in its environment. The `scripts/start.sh` entrypoint routes to the correct process.
:::
