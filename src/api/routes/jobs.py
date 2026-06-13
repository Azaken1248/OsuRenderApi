import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas import ArtifactLinks, JobListResponse, JobStatusResponse
from src.db.models import Job
from src.db.session import get_db

router = APIRouter()
from src.api.utils import serialize_error


def _job_to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        map_title=job.map_title,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=serialize_error(job.error_message),
        config=job.config or {},
        artifacts=ArtifactLinks(
            video_url=(
                f"/v1/artifacts/{job.video_storage_key}"
                if job.video_storage_key
                else None
            ),
            thumbnail_url=(
                f"/v1/artifacts/{job.thumb_storage_key}"
                if job.thumb_storage_key
                else None
            ),
            logs_url=f"/v1/artifacts/logs/{job.id}.log",
        ),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Retrieve the current status, progress, and metadata for a specific render job.",
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )
    return _job_to_response(job)


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="List all jobs",
    description="Retrieve a paginated list of all render jobs, ordered by creation time (newest first).",
)
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100, description="Max jobs to return."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    status: str | None = Query(default=None, description="Filter by job status."),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).order_by(Job.created_at.desc())
    count_query = select(func.count(Job.id))
    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    jobs = result.scalars().all()
    return JobListResponse(
        total=total,
        jobs=[_job_to_response(j) for j in jobs],
    )


from pydantic import BaseModel
from src.db.models import JobStatus


class WebhookPayload(BaseModel):
    success: bool
    video_key: str = ""
    thumb_key: str = ""
    log_key: str = ""
    error: str = ""
    pp: float = 0.0
    timestamp: int = 0
    nonce: str = ""


import hmac
import hashlib
from fastapi import Request
from src.core.config import get_settings


import json


@router.post(
    "/jobs/{job_id}/webhook",
    summary="Modal Webhook Callback",
    description="Endpoint for Modal to push completion results natively.",
)
async def job_webhook(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    body = await request.body()
    if settings.webhook_secret:
        signature = request.headers.get("X-Signature")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing signature")

        expected_sig = hmac.new(
            settings.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid signature")

    import time

    try:
        payload_dict = json.loads(body)
        payload = WebhookPayload(**payload_dict)
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid JSON body")

    if payload.timestamp and abs(time.time() - payload.timestamp) > 300:
        raise HTTPException(
            status_code=400, detail="Webhook payload expired (replay protection)"
        )

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not payload.success:
        job.status = JobStatus.FAILED
        job.error_message = payload.error
    else:
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.video_storage_key = payload.video_key
        job.thumb_storage_key = payload.thumb_key

        if payload.pp > 0:
            c_dict = dict(job.config)
            if "replay_stats" not in c_dict:
                c_dict["replay_stats"] = {}
            c_dict["replay_stats"]["pp"] = payload.pp
            job.config = c_dict

    from sqlalchemy import text

    await db.execute(
        text(
            "UPDATE outbox_events SET status='PROCESSED', processed_at=NOW() WHERE payload->>'job_id' = :job_id"
        ),
        {"job_id": str(job_id)},
    )
    await db.commit()
    return {"status": "ok"}
