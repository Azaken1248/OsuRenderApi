from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import get_settings
from src.api.routes import health, jobs, render, skins
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
    app.include_router(health.router, tags=["Health"])
    app.include_router(render.router, prefix="/v1", tags=["Rendering"])
    app.include_router(jobs.router, prefix="/v1", tags=["Jobs"])
    app.include_router(skins.router, prefix="/v1", tags=["Skins"])
    return app