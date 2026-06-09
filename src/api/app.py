from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.core.config import get_settings
from src.core.limiter import limiter
from src.api.routes import health, jobs, render, skins, artifacts

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[startup] {settings.app_name} v{settings.app_version}")
    print(f"[startup] Debug mode: {settings.debug}")
    print(f"[startup] Database: {settings.database_url.split('@')[-1]}")
    print(f"[startup] Redis: {settings.redis_url}")
    print(f"[startup] Storage: {settings.storage_endpoint}/{settings.storage_bucket_name}")
    yield
    from src.db.session import engine
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
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import logging
        logging.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."},
        )

    app.include_router(health.router, tags=["Health"])
    app.include_router(render.router, prefix="/v1", tags=["Rendering"])
    app.include_router(jobs.router, prefix="/v1", tags=["Jobs"])
    app.include_router(skins.router, prefix="/v1", tags=["Skins"])
    app.include_router(artifacts.router, prefix="/v1/artifacts", tags=["Artifacts"])
    return app