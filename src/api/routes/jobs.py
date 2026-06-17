import uuid
import hmac
import hashlib
import json
import time
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from src.api.schemas import (
    ArtifactLinks,
    JobListResponse,
    JobStatusResponse,
    AnalyticsResponse,
    ReplayIdentity,
    HitCounts,
    PerformanceData,
    LifeBarEntry,
)
from src.db.models import Job, JobStatus
from src.db.session import get_db
from src.api.utils import serialize_error
from src.core.config import get_settings
from src.core.limiter import limiter
from src.core.storage import storage_client
from src.core.metrics import analytics_requests_total

router = APIRouter()
logger = logging.getLogger("osurender.api")


def _job_to_response(job: Job) -> JobStatusResponse:
    stats = (job.config or {}).get("replay_stats", {})
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        map_title=job.map_title,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=serialize_error(job.error_message),
        config=job.config or {},
        has_analytics=bool(
            getattr(job, "analytics_storage_key", None) or stats.get("frames_key")
        ),
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
            analytics_url=f"/v1/jobs/{job.id}/analytics",
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


class WebhookPayload(BaseModel):
    success: bool
    video_key: str = ""
    thumb_key: str = ""
    log_key: str = ""
    error: str = ""
    pp: float = 0.0
    timestamp: int = 0
    nonce: str = ""


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
    from src.core.metrics import webhook_failures_total

    settings = get_settings()
    body = await request.body()
    if not settings.webhook_secret:
        webhook_failures_total.labels(reason="missing_secret_config").inc()
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: WEBHOOK_SECRET is not set",
        )

    signature = request.headers.get("X-Signature")
    if not signature:
        webhook_failures_total.labels(reason="missing_signature").inc()
        raise HTTPException(status_code=401, detail="Missing signature")

    expected_sig = hmac.new(
        settings.webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        webhook_failures_total.labels(reason="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        payload_dict = json.loads(body)
        payload = WebhookPayload(**payload_dict)
    except Exception:
        webhook_failures_total.labels(reason="invalid_body").inc()
        raise HTTPException(status_code=422, detail="Invalid JSON body")

    if payload.timestamp and abs(time.time() - payload.timestamp) > 300:
        webhook_failures_total.labels(reason="expired").inc()
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
        logger.warning(f"Webhook reported failure for job {job_id}: {payload.error}")
    else:
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.video_storage_key = payload.video_key
        job.thumb_storage_key = payload.thumb_key
        logger.info(f"Webhook confirmed completion for job {job_id}")

        if payload.pp > 0:
            c_dict = dict(job.config)
            if "replay_stats" not in c_dict:
                c_dict["replay_stats"] = {}
            c_dict["replay_stats"]["pp"] = payload.pp
            job.config = c_dict

    await db.execute(
        text(
            "UPDATE outbox_events SET status='PROCESSED', processed_at=NOW() WHERE payload->>'job_id' = :job_id"
        ),
        {"job_id": str(job_id)},
    )
    await db.commit()
    return {"status": "ok"}


@router.get(
    "/jobs/{job_id}/analytics",
    response_model=AnalyticsResponse,
    summary="Get Replay Analytics",
    description="Returns structured replay analytics data with a presigned URL for cursor frames.",
    responses={202: {"description": "Analytics not yet available"}},
)
@limiter.limit("30/minute")
async def get_replay_analytics(
    request: Request,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stats = (job.config or {}).get("replay_stats", {})
    frames_key = getattr(job, "analytics_storage_key", None) or stats.get("frames_key")

    # Return 202 if analytics data isn't ready yet
    if not frames_key and job.status.value not in ("completed", "failed"):
        analytics_requests_total.labels(outcome="pending").inc()
        return JSONResponse(
            status_code=202,
            content={
                "status": "pending",
                "message": "Analytics not yet available",
                "job_id": str(job_id),
            },
        )

    # Generate presigned URL with 1-hour TTL
    frames_url = None
    if frames_key:
        try:
            frames_url = storage_client.get_presigned_url(
                frames_key, expires=timedelta(hours=1)
            )
            # Apply host rewrite for local dev (same pattern as artifacts.py)
            if (
                frames_url
                and "minio:9000" in frames_url
                and "minio:9000" not in str(request.base_url)
            ):
                external_host = request.url.hostname
                frames_url = frames_url.replace("minio:9000", f"{external_host}:9000")
            analytics_requests_total.labels(outcome="hit").inc()
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for {frames_key}: {e}")
            analytics_requests_total.labels(outcome="error").inc()
    else:
        analytics_requests_total.labels(outcome="miss").inc()

    # Life bar is stored in config (not inside replay_stats) to avoid duplication
    life_bar_raw = (job.config or {}).get("life_bar", [])

    return AnalyticsResponse(
        job_id=str(job_id),
        status=job.status.value,
        has_analytics=frames_key is not None,
        identity=ReplayIdentity(
            username=stats.get("username"),
            beatmap_hash=stats.get("beatmap_hash"),
            game_mode=stats.get("game_mode"),
            mods=stats.get("mods", []),
            mods_int=stats.get("mods_int"),
            score=stats.get("score"),
            timestamp=stats.get("timestamp"),
        ),
        hit_counts=HitCounts(
            **{
                "300s": stats.get("300s", 0),
                "100s": stats.get("100s", 0),
                "50s": stats.get("50s", 0),
                "misses": stats.get("misses", 0),
                "gekis": stats.get("gekis", 0),
                "katus": stats.get("katus", 0),
                "max_combo": stats.get("max_combo", 0),
            }
        ),
        performance=PerformanceData(
            pp=stats.get("pp", 0),
            star_rating=(
                float(stats["star_rating"]) if stats.get("star_rating") else None
            ),
        ),
        life_bar=[LifeBarEntry(**e) for e in life_bar_raw],
        frames_url=frames_url,
        frame_count=stats.get("frame_count", 0),
    )
