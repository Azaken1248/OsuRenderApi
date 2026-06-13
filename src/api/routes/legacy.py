import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Job
from src.db.session import get_db

router = APIRouter()


@router.post("/render")
async def legacy_render(
    request: Request,
    replay: UploadFile = File(...),
    skin: str = Form("Default"),
    bg_dim: float = Form(0.95),
    quality: str = Form("standard"),
    motion_blur: bool = Form(True),
    storyboard: bool = Form(True),
    video: bool = Form(False),
    snaking_in: bool = Form(True),
    snaking_out: bool = Form(True),
    hit_error_meter: bool = Form(True),
    key_overlay: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    from src.api.routes.render import submit_render

    res = await submit_render(
        request=request,
        replay=replay,
        skin=skin,
        bg_dim=bg_dim,
        resolution="4k" if quality == "ultra" else "1080p",
        motion_blur=motion_blur,
        storyboard=storyboard,
        video=video,
        snaking_in=snaking_in,
        snaking_out=snaking_out,
        hit_error_meter=hit_error_meter,
        key_overlay=key_overlay,
        db=db,
    )
    return {
        "job_id": str(res.job_id).replace("-", ""),
        "view_url": f"/view/{res.job_id.hex}",
        "video_url": f"/video/{res.job_id.hex}.mp4",
    }


@router.get("/status/{job_id}")
async def legacy_status(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.id.hex,
        "status": "complete" if job.status.value == "completed" else job.status.value,
        "percent": job.progress,
        "skin": job.config.get("skin", "Default") if job.config else "Default",
        "map_title": job.map_title,
        "created_at": job.created_at.timestamp(),
        "last_updated": job.updated_at.timestamp(),
        "error": job.error_message,
    }


@router.get("/jobs")
async def legacy_list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).order_by(Job.created_at.desc()).limit(50))
    jobs = result.scalars().all()
    out = []
    for job in jobs:
        out.append(
            {
                "job_id": job.id.hex,
                "status": (
                    "complete" if job.status.value == "completed" else job.status.value
                ),
                "percent": job.progress,
                "skin": job.config.get("skin", "Default") if job.config else "Default",
                "map_title": job.map_title,
                "created_at": job.created_at.timestamp(),
                "last_updated": job.updated_at.timestamp(),
            }
        )
    return out


@router.get("/thumbnail/{job_id}.jpg")
async def legacy_thumbnail(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.thumb_storage_key:
        raise HTTPException(404, "Thumbnail not found")
    return RedirectResponse(f"/v1/artifacts/{job.thumb_storage_key}")


@router.get("/video/{job_id}.mp4")
async def legacy_video(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.video_storage_key:
        raise HTTPException(404, "Video not found")
    return RedirectResponse(f"/v1/artifacts/{job.video_storage_key}")


@router.get("/logs/{job_id}")
async def legacy_logs(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Logs not found")
    if job.status.value not in ("completed", "failed"):
        return {"status": "no logs"}
    return RedirectResponse(f"/v1/artifacts/logs/{job.id}.log")


@router.get("/skins")
async def legacy_list_skins():
    from src.api.routes.skins import list_skins

    return await list_skins()


@router.post("/skins/upload")
async def legacy_upload_skin(skin: UploadFile = File(...)):
    from src.api.routes.skins import upload_skin

    return await upload_skin(skin=skin)
