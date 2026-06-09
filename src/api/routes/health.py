from fastapi import APIRouter
from src.core.config import get_settings
router = APIRouter()
@router.get("/health", summary="Health Check")
async def health_check():
    return {"status": "healthy"}