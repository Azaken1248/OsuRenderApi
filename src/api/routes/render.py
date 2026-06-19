import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas import RenderConfig, JobCreatedResponse
from src.core.config import get_settings
from src.core.limiter import limiter
from src.core.storage import storage_client
from src.db.models import Job, JobStatus, OutboxEvent, OutboxStatus
from src.db.session import get_db
from src.core.metrics import job_submit_total
from sqlalchemy import select, func, text

router = APIRouter()


@router.post(
    "/render",
    response_model=JobCreatedResponse,
    status_code=202,
    summary="Submit a replay for rendering",
    description="Upload a .osr replay file with rendering parameters. "
    "Returns a job_id that can be used to track progress.",
)
@limiter.limit("5/minute")
async def submit_render(
    request: Request,
    replay: UploadFile = File(
        ...,
        description="The .osr replay file to render.",
    ),
    skin: str = Form("Default"),
    bg_dim: float = Form(0.95),
    resolution: str = Form("1080p"),
    motion_blur: bool = Form(True),
    storyboard: bool = Form(True),
    video: bool = Form(False),
    snaking_in: bool = Form(True),
    snaking_out: bool = Form(True),
    hit_error_meter: bool = Form(True),
    key_overlay: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not replay.filename or not replay.filename.lower().endswith(".osr"):
        raise HTTPException(
            status_code=400,
            detail="File must be an osu! replay (.osr) file.",
        )
    max_bytes = settings.max_replay_size_mb * 1024 * 1024
    file_size = replay.size or 0

    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Replay file exceeds maximum size of {settings.max_replay_size_mb}MB.",
        )
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded replay file is empty.",
        )

    from osrparse import Replay

    try:
        parsed_replay = Replay.from_file(replay.file)
        if parsed_replay.mode.value != 0:
            raise ValueError("Only osu!standard replays are supported.")
    except Exception:
        raise HTTPException(
            status_code=415,
            detail="Invalid replay file. The structure is corrupted or unsupported.",
        )
    finally:
        await replay.seek(0)

    import re

    if not re.match(r"^[a-zA-Z0-9_ -]+$", skin):
        raise HTTPException(
            status_code=422,
            detail="Invalid skin name. Only alphanumeric characters, underscores, hyphens, and spaces are allowed.",
        )

    global_queued_query = (
        select(func.count()).select_from(Job).where(Job.status == JobStatus.QUEUED)
    )
    global_rendering_query = (
        select(func.count())
        .select_from(Job)
        .where(Job.status.in_([JobStatus.RENDERING, JobStatus.DOWNLOADING]))
    )

    queued_count = await db.scalar(global_queued_query)
    rendering_count = await db.scalar(global_rendering_query)

    if queued_count and queued_count >= settings.max_queued:
        raise HTTPException(
            status_code=503,
            detail="The render queue is currently full. Please try again later.",
        )
    if rendering_count and rendering_count >= settings.max_rendering:
        raise HTTPException(
            status_code=503,
            detail="The render infrastructure is at maximum capacity. Please try again later.",
        )

    cf_ip = request.headers.get("CF-Connecting-IP")
    client_ip = (
        cf_ip if cf_ip else (request.client.host if request.client else "unknown")
    )
    import hashlib

    ip_lock_id = int.from_bytes(
        hashlib.sha256(client_ip.encode()).digest()[:8], "little", signed=True
    )
    await db.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": ip_lock_id})

    active_jobs_query = (
        select(func.count())
        .select_from(Job)
        .where(
            Job.client_ip == client_ip,
            Job.status.in_(
                [JobStatus.QUEUED, JobStatus.RENDERING, JobStatus.DOWNLOADING]
            ),
        )
    )
    active_jobs_count = await db.scalar(active_jobs_query)

    if active_jobs_count and active_jobs_count >= 2:
        raise HTTPException(
            status_code=429,
            detail="You already have 2 active render jobs. Please wait for them to finish before queueing more.",
        )

    try:
        config = RenderConfig(
            skin=skin,
            bg_dim=bg_dim,
            resolution=resolution,
            motion_blur=motion_blur,
            storyboard=storyboard,
            video=video,
            snaking_in=snaking_in,
            snaking_out=snaking_out,
            hit_error_meter=hit_error_meter,
            key_overlay=key_overlay,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    job_id = uuid.uuid4()
    replay_key = f"replays/{job_id}/replay.osr"

    import asyncio

    try:
        await asyncio.to_thread(
            storage_client.upload_file,
            object_name=replay_key,
            data=replay.file,
            length=file_size,
            content_type=replay.content_type or "application/octet-stream",
        )
    except Exception:
        import logging

        logger = logging.getLogger("osurender.api")
        logger.exception(f"Failed to upload replay file for job {job_id}")

        raise HTTPException(
            status_code=500,
            detail="An internal storage error occurred during upload. Please try again.",
        )

    job = Job(
        id=job_id,
        status=JobStatus.QUEUED,
        progress=0.0,
        replay_storage_key=replay_key,
        config=config.model_dump(),
        client_ip=client_ip,
    )

    db.add(job)
    outbox_event = OutboxEvent(
        event_type="render_job_created",
        payload={"job_id": str(job.id)},
        status=OutboxStatus.PENDING,
    )
    db.add(outbox_event)
    await db.commit()
    await db.refresh(job)
    job_submit_total.inc()

    return JobCreatedResponse(
        job_id=job.id,
        status=job.status.value,
        links={
            "status": f"/v1/jobs/{job.id}",
        },
    )
