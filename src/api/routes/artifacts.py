from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from src.core.storage import storage_client

router = APIRouter()


@router.get(
    "/{key:path}",
    summary="Download or Stream Artifact",
    description="Returns a pre-signed URL to download or stream the artifact from object storage.",
)
async def get_artifact(request: Request, key: str):
    # analytics/ added as fallback for expired presigned URLs — frames are
    # primarily served via presigned URL from GET /v1/jobs/:id/analytics
    valid_prefixes = (
        "logs/",
        "videos/",
        "thumbnails/",
        "replays/",
        "skins/",
        "analytics/",
    )
    if not key.startswith(valid_prefixes):
        raise HTTPException(status_code=403, detail="Invalid artifact prefix")

    try:
        # For logs and analytics frames, proxy directly to avoid CORS/mixed-content on JS fetch()
        if key.startswith("logs/") or key.startswith("analytics/"):
            try:
                response = storage_client.client.get_object(
                    bucket_name=storage_client.bucket,
                    object_name=key,
                )
                with response:
                    c_type = "application/gzip" if key.endswith(".gz") else "text/plain"
                    return Response(content=response.read(), media_type=c_type)
            except Exception:
                return Response(content="", media_type="text/plain")

        url = storage_client.client.presigned_get_object(
            bucket_name=storage_client.bucket,
            object_name=key,
        )
        if "minio:9000" in url and "minio:9000" not in str(request.base_url):

            external_host = request.url.hostname
            url = url.replace("minio:9000", f"{external_host}:9000")

        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Artifact not found or storage error: {str(e)}"
        )
