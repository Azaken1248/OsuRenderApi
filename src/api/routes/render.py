import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas import RenderConfig, JobCreatedResponse
from src.core.config import get_settings
from src.core.limiter import limiter
from src.core.storage import storage_client
from src.db.models import Job, JobStatus
from src.db.session import get_db
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
    content = await replay.read()
    max_bytes = settings.max_replay_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Replay file exceeds maximum size of {settings.max_replay_size_mb}MB.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded replay file is empty.",
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
    replay_key = f"replays/{job_id}/{replay.filename}"
    
    storage_client.upload_file(
        object_name=replay_key,
        data=content,
        content_type=replay.content_type or "application/octet-stream"
    )

    job = Job(
        id=job_id,
        status=JobStatus.QUEUED,
        progress=0.0,
        replay_storage_key=replay_key,
        config=config.model_dump(),
    )
    db.add(job)
    await db.flush() 
    await db.refresh(job)
    return JobCreatedResponse(
        job_id=job.id,
        status=job.status.value,
        links={
            "status": f"/v1/jobs/{job.id}",
        },
    )