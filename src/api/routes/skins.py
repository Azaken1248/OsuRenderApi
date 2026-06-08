from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from src.core.config import get_settings
from src.core.storage import storage_client
from src.core.limiter import limiter
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
@limiter.limit("2/minute")
async def upload_skin(request: Request, skin: UploadFile = File(...)):
    settings = get_settings()
    if not skin.filename or not skin.filename.lower().endswith(".osk"):
        raise HTTPException(
            status_code=400,
            detail="File must be an osu! skin (.osk) file.",
        )
    max_bytes = settings.max_skin_size_mb * 1024 * 1024
    file_size = skin.size or 0
    
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Skin file exceeds maximum size of {settings.max_skin_size_mb}MB.",
        )
    skin_name = skin.filename[:-4]
    skin_key = f"skins/{skin.filename}"
    
    storage_client.upload_file(
        object_name=skin_key,
        data=skin.file,
        length=file_size,
        content_type=skin.content_type or "application/octet-stream"
    )

    return {
        "success": True,
        "skin_name": skin_name,
        "message": f"Skin '{skin_name}' uploaded successfully.",
    }