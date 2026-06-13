import re
import io
import zipfile
import logging
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from src.core.config import get_settings
from src.core.storage import storage_client
from src.core.limiter import limiter
from src.core.metrics import upload_validation_failures_total

router = APIRouter()
logger = logging.getLogger("osurender.api")

MAX_ZIP_ENTRIES = 10000
MAX_COMPRESSION_RATIO = 100
MAX_NESTING_DEPTH = 3


def validate_zip_structure(data: bytes, max_size_mb: int) -> list[str]:
    errors = []
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as z:
            if len(z.namelist()) > MAX_ZIP_ENTRIES:
                errors.append(
                    f"Archive contains too many entries ({len(z.namelist())} > {MAX_ZIP_ENTRIES})"
                )

            total_uncompressed = sum(info.file_size for info in z.infolist())
            if total_uncompressed > max_size_mb * 1024 * 1024 * 10:
                errors.append(
                    f"Total uncompressed size too large ({total_uncompressed} bytes)"
                )

            if len(data) > 0:
                ratio = total_uncompressed / len(data)
                if ratio > MAX_COMPRESSION_RATIO:
                    errors.append(
                        f"Suspicious compression ratio ({ratio:.1f}x > {MAX_COMPRESSION_RATIO}x)"
                    )

            for info in z.infolist():
                depth = info.filename.count("/")
                if depth > MAX_NESTING_DEPTH:
                    errors.append(f"Excessive nesting depth in {info.filename}")
                    break
                if info.filename.endswith(".zip") or info.filename.endswith(".osk"):
                    errors.append(f"Nested archive detected: {info.filename}")
                    break

            bad = z.testzip()
            if bad:
                errors.append(f"Corrupted entry detected: {bad}")

    except zipfile.BadZipFile:
        errors.append("File is not a valid ZIP archive")
    return errors


@router.get(
    "/skins",
    summary="List available skins",
    description="Returns a list of all available osu! skins for rendering.",
)
async def list_skins():
    try:
        objects = storage_client.list_objects(prefix="skins/")
        skins = []
        for obj in objects:
            if obj.object_name and obj.object_name.endswith(".osk"):
                skin_name = obj.object_name.split("/")[-1][:-4]
                skins.append(skin_name)
        return {"skins": skins}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list skins: {str(e)}")


@router.post(
    "/skins/upload",
    summary="Upload a custom skin",
    description="Upload a .osk skin file to make it available for rendering.",
)
@limiter.limit("2/minute")
async def upload_skin(request: Request, skin: UploadFile = File(...)):
    settings = get_settings()
    if not skin.filename or not skin.filename.lower().endswith(".osk"):
        upload_validation_failures_total.labels(type="skin_extension").inc()
        raise HTTPException(
            status_code=400,
            detail="File must be an osu! skin (.osk) file.",
        )
    max_bytes = settings.max_skin_size_mb * 1024 * 1024
    file_size = skin.size or 0

    if file_size > max_bytes:
        upload_validation_failures_total.labels(type="skin_size").inc()
        raise HTTPException(
            status_code=413,
            detail=f"Skin file exceeds maximum size of {settings.max_skin_size_mb}MB.",
        )

    skin_data = await skin.read()

    if not skin_data[:2] == b"PK":
        upload_validation_failures_total.labels(type="skin_invalid_zip").inc()
        raise HTTPException(
            status_code=415,
            detail="Invalid skin file. The payload is not a valid ZIP/OSK archive.",
        )

    zip_errors = validate_zip_structure(skin_data, settings.max_skin_size_mb)
    if zip_errors:
        upload_validation_failures_total.labels(type="skin_zip_structure").inc()
        logger.warning(f"Skin upload rejected: {zip_errors}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid skin archive: {'; '.join(zip_errors)}",
        )

    skin_name = skin.filename[:-4]
    if not re.match(r"^[a-zA-Z0-9_ -]+$", skin_name):
        upload_validation_failures_total.labels(type="skin_filename").inc()
        raise HTTPException(
            status_code=422,
            detail="Invalid skin filename. Only alphanumeric characters, underscores, hyphens, and spaces are allowed.",
        )
    skin_key = f"skins/{skin_name}.osk"

    storage_client.upload_file(
        object_name=skin_key,
        data=io.BytesIO(skin_data),
        length=len(skin_data),
        content_type=skin.content_type or "application/octet-stream",
    )

    logger.info(f"Skin '{skin_name}' uploaded successfully ({len(skin_data)} bytes)")

    return {
        "success": True,
        "skin_name": skin_name,
        "message": f"Skin '{skin_name}' uploaded successfully.",
    }
