import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.schemas import ArtifactLinks, JobListResponse, JobStatusResponse
from src.db.models import Job
from src.db.session import get_db
router = APIRouter()
def _job_to_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        map_title=job.map_title,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
        config=job.config or {},
        artifacts=ArtifactLinks(
            video_url=f"/v1/artifacts/{job.video_storage_key}" if job.video_storage_key else None,
            thumbnail_url=f"/v1/artifacts/{job.thumb_storage_key}" if job.thumb_storage_key else None,
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