from fastapi import APIRouter
from src.core.config import get_settings
router = APIRouter()
@router.get("/", summary="API Root")
async def root():
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "online",
        "docs": "/api/docs",
    }
@router.get("/health", summary="Health Check")
async def health_check():
    return {"status": "healthy"}