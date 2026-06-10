from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from src.core.storage import storage_client

router = APIRouter()
@router.get(
    "/{key:path}",
    summary="Download or Stream Artifact",
    description="Returns a pre-signed URL to download or stream the artifact from object storage.",
)
async def get_artifact(request: Request, key: str):
    try:
        url = storage_client.client.presigned_get_object(
            bucket_name=storage_client.bucket,
            object_name=key,
        )
        if "minio:9000" in url and "minio:9000" not in str(request.base_url):
            # Replace internal Docker DNS with the external host DNS
            external_host = request.url.hostname
            url = url.replace("minio:9000", f"{external_host}:9000")
            
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Artifact not found or storage error: {str(e)}")
