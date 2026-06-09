from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from src.core.storage import storage_client

router = APIRouter()

@router.get(
    "/{key:path}",
    summary="Download or Stream Artifact",
    description="Returns a pre-signed URL to download or stream the artifact from object storage.",
)
async def get_artifact(key: str):
    try:
        url = storage_client.client.presigned_get_object(
            bucket_name=storage_client.bucket,
            object_name=key,
        )
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Artifact not found or storage error: {str(e)}")
