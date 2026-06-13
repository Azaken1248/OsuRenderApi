from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.core.config import get_settings
from src.core.limiter import limiter
from src.api.routes import health, jobs, render, skins, artifacts, view, legacy

import asyncio
from sqlalchemy import text
from src.core.metrics import queue_depth


async def metrics_poll_loop():
    from src.db.session import get_session_factory

    AsyncSessionLocal = get_session_factory()
    while True:
        try:
            async with AsyncSessionLocal() as db:
                queued = await db.scalar(
                    text("SELECT COUNT(*) FROM jobs WHERE status = 'queued'")
                )
                rendering = await db.scalar(
                    text("SELECT COUNT(*) FROM jobs WHERE status = 'rendering'")
                )
                downloading = await db.scalar(
                    text("SELECT COUNT(*) FROM jobs WHERE status = 'downloading'")
                )
                outbox_pending = await db.scalar(
                    text("SELECT COUNT(*) FROM outbox_events WHERE status = 'PENDING'")
                )

                if queued is not None:
                    queue_depth.labels(status="queued").set(queued)
                if rendering is not None:
                    queue_depth.labels(status="rendering").set(rendering)
                if downloading is not None:
                    queue_depth.labels(status="downloading").set(downloading)

                from src.core.metrics import outbox_pending_events

                if outbox_pending is not None:
                    outbox_pending_events.set(outbox_pending)
        except Exception as e:
            import logging

            logging.error(f"Error polling metrics: {e}")

        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[startup] {settings.app_name} v{settings.app_version}")
    print(f"[startup] Debug mode: {settings.debug}")
    print(f"[startup] Database: {settings.database_url.split('@')[-1]}")
    print(f"[startup] Redis: {settings.redis_url}")
    print(
        f"[startup] Storage: {settings.storage_endpoint}/{settings.storage_bucket_name}"
    )

    metrics_task = asyncio.create_task(metrics_poll_loop())

    yield
    metrics_task.cancel()
    from src.db.session import get_engine

    engine = get_engine()
    await engine.dispose()
    print("[shutdown] Database connections closed.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="High-quality osu! replay rendering service powered by danser-go.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import logging

        logging.exception("Unhandled exception in API route")
        settings = get_settings()
        detail = str(exc) if settings.debug else "An internal rendering error occurred."
        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )

    app.include_router(health.router, tags=["Health"])
    app.include_router(legacy.router, tags=["Legacy API"])
    app.include_router(view.router, tags=["Web Player"])
    app.include_router(render.router, prefix="/v1", tags=["Rendering"])
    app.include_router(jobs.router, prefix="/v1", tags=["Jobs"])
    app.include_router(skins.router, prefix="/v1", tags=["Skins"])
    app.include_router(artifacts.router, prefix="/v1/artifacts", tags=["Artifacts"])

    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app)

    return app
