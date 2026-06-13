from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Job
from src.db.session import get_db
import uuid

router = APIRouter()
templates = Jinja2Templates(directory="src/api/templates")


@router.get(
    "/",
    response_class=HTMLResponse,
    summary="Home",
    description="Returns the root level home HTML for backwards compatibility.",
)
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html")


@router.get(
    "/view/{job_id}",
    response_class=HTMLResponse,
    summary="View Player",
    description="Returns an HTML player with OpenGraph and Twitter card meta tags for Discord/social embedding.",
)
async def view_player(
    request: Request, job_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        return HTMLResponse(
            """<html><body style="background:#111;color:#ff66aa;font-family:sans-serif;text-align:center;padding:50px;">
            <h1>404 - Job not found</h1></body></html>""",
            status_code=404,
        )

    is_complete = job.status.value == "completed"

    video_url = (
        f"/v1/artifacts/{job.video_storage_key}" if job.video_storage_key else ""
    )
    thumb_url = (
        f"/v1/artifacts/{job.thumb_storage_key}" if job.thumb_storage_key else ""
    )

    video_src_html = (
        f'<source src="{video_url}" type="video/mp4">' if is_complete else ""
    )

    map_title = job.map_title or job.id.hex

    return templates.TemplateResponse(
        request,
        "view_player.html",
        {
            "map_title": map_title,
            "job_id": job.id.hex,
            "status": job.status.value,
            "progress": job.progress,
            "thumb_url": thumb_url,
            "video_url": video_url,
            "video_src_html": video_src_html,
            "base_url": "https://api.render.azaken.com",
        },
    )
