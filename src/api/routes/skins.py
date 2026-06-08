from fastapi import APIRouter, File, HTTPException, UploadFile
from src.core.config import get_settings
router = APIRouter()
@router.get(
    "/skins",
    summary="List available skins",
    description="Returns a list of all available osu! skins for rendering.",
)
async def list_skins():
    return []
@router.post(
    "/skins/upload",
    summary="Upload a custom skin",
    description="Upload a .osk skin file to make it available for rendering.",
)
async def upload_skin(skin: UploadFile = File(...)):
    settings = get_settings()
    if not skin.filename or not skin.filename.lower().endswith(".osk"):
        raise HTTPException(
            status_code=400,
            detail="File must be an osu! skin (.osk) file.",
        )
    content = await skin.read()
    max_bytes = settings.max_skin_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Skin file exceeds maximum size of {settings.max_skin_size_mb}MB.",
        )
    skin_name = skin.filename[:-4]
    return {
        "success": True,
        "skin_name": skin_name,
        "message": f"Skin '{skin_name}' validated successfully. "
                   f"Storage upload will be enabled in Phase 2.",
    }