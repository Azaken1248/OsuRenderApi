---
title: "Project Structure"
description: "OsuRender API codebase organization — package layout, module responsibilities, and dependency architecture."
---

# Project Structure

Annotated directory tree of the OsuRender API codebase.

```
OsuRenderApi/
├── src/                          # Application source code
│   ├── __init__.py
│   ├── api/                      # FastAPI application layer
│   │   ├── app.py                # App factory, middleware, lifespan, metrics polling
│   │   ├── schemas.py            # Pydantic request/response models
│   │   ├── utils.py              # Error serialization helpers
│   │   ├── routes/               # Endpoint handlers
│   │   │   ├── render.py         # POST /v1/render — job submission
│   │   │   ├── jobs.py           # GET /v1/jobs, webhook callback
│   │   │   ├── skins.py          # GET/POST /v1/skins
│   │   │   ├── artifacts.py      # GET /v1/artifacts/{key}
│   │   │   ├── health.py         # GET /health
│   │   │   ├── view.py           # HTML player + home page
│   │   │   └── legacy.py         # Backward-compatible endpoints
│   │   └── templates/            # Jinja2 HTML templates (player, home)
│   │
│   ├── core/                     # Shared infrastructure & utilities
│   │   ├── config.py             # Pydantic settings (all env vars)
│   │   ├── celery_app.py         # Celery instance, beat schedule, signals
│   │   ├── storage.py            # MinIO/S3 storage client wrapper
│   │   ├── metrics.py            # All Prometheus metric definitions
│   │   ├── logging.py            # JSON structured logging, context vars
│   │   ├── limiter.py            # SlowApi rate limiter setup
│   │   └── render_pipeline.py    # Core danser rendering logic (shared)
│   │
│   ├── db/                       # Database layer
│   │   ├── base.py               # SQLAlchemy declarative base
│   │   ├── models.py             # ORM models (Job, OutboxEvent)
│   │   └── session.py            # Engine factory, session management
│   │
│   ├── workers/                  # Background processors
│   │   ├── dispatcher.py         # Outbox → Celery dispatcher (asyncpg)
│   │   └── render_worker.py      # Celery task, job orchestration, zombie reaper
│   │
│   └── modal_deploy.py           # Modal GPU worker definition
│
├── alembic/                      # Database migration framework
│   ├── env.py                    # Migration environment config
│   ├── script.py.mako            # Migration template
│   └── versions/                 # Migration scripts
│
├── monitoring/                   # Observability configuration
│   ├── alerts.yml                # Prometheus alert rules (20+ alerts)
│   └── grafana_dashboard.json    # Pre-built Grafana dashboard
│
├── scripts/                      # Operational scripts
│   ├── start.sh                  # Docker entrypoint (routes by WORKER_TYPE)
│   ├── replay_dead_letters.py    # DLQ replay utility
│   └── load_test.py              # Basic load testing script
│
├── tests/                        # Test suite
│   ├── test_health.py            # Health endpoint tests
│   ├── test_render.py            # Render submission tests
│   ├── test_skins.py             # Skin upload tests
│   ├── test_storage.py           # Storage client tests
│   ├── test_legacy.py            # Legacy endpoint tests
│   └── test_chaos.py             # Chaos engineering tests (10 scenarios)
│
├── .github/
│   ├── workflows/ci.yml          # CI/CD pipeline (lint, scan, test, SBOM)
│   └── dependabot.yml            # Automated dependency updates
│
├── docs/                         # Architecture documents (reference)
│
├── docker-compose.yml            # Full stack deployment
├── Dockerfile                    # Application container image
├── main.py                       # Direct uvicorn entry point
├── requirements.in               # Direct dependencies
├── requirements.lock             # Pinned dependency lock file
├── alembic.ini                   # Alembic configuration
├── prometheus.yml                # Prometheus scrape config
├── pytest.ini                    # Pytest configuration
├── pyrightconfig.json            # Type checker config
└── .env.example                  # Environment variable template
```

## Key Files

| File | Purpose |
|------|---------|
| `src/api/app.py` | Application factory — creates FastAPI app, wires middleware, registers routes |
| `src/core/render_pipeline.py` | The shared rendering logic used by both Modal and local execution |
| `src/workers/dispatcher.py` | The heart of reliable dispatch — PostgreSQL outbox → Celery bridge |
| `src/workers/render_worker.py` | Job orchestration — asset resolution, rendering, cleanup |
| `src/db/models.py` | SQLAlchemy ORM models defining the database schema |
| `scripts/start.sh` | Docker entrypoint that routes to the correct process based on `WORKER_TYPE` |
