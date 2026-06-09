from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Job
from src.db.session import get_db
import uuid

router = APIRouter()

@router.get(
    "/",
    response_class=HTMLResponse,
    summary="Home",
    description="Returns the root level home HTML for backwards compatibility.",
)
async def home():
    return HTMLResponse(
        "<h1>🎮 OsuRender API Online</h1><p><a href='/api/docs'>Swagger API Docs</a> | <a href='/api/redoc'>Redoc</a></p>"
    )

@router.get(
    "/view/{job_id}",
    response_class=HTMLResponse,
    summary="View Player",
    description="Returns an HTML player with OpenGraph and Twitter card meta tags for Discord/social embedding.",
)
async def view_player(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        return HTMLResponse("<h1>Job not found</h1>", status_code=404)
        
    is_complete = job.status.value == "completed"
    show = "inline" if is_complete else "none"
    
    video_url = f"/v1/artifacts/{job.video_storage_key}" if job.video_storage_key else ""
    thumb_url = f"/v1/artifacts/{job.thumb_storage_key}" if job.thumb_storage_key else ""
    
    video_src_html = f'<source src="{video_url}" type="video/mp4">' if is_complete else ''
    
    map_title = job.map_title or job.id.hex
    
    html = f"""
    <html><head>
        <title>OsuRender: {map_title}</title>
        <meta name="description" content="Watch this osu! replay render powered by OsuRender Cloud API.">
        <meta name="theme-color" content="#ff66aa">
        
        <meta property="og:title" content="OsuRender Job: {map_title}">
        <meta property="og:description" content="Click to watch this osu! replay render.">
        <meta property="og:type" content="video.other">
        <meta property="og:url" content="https://api.render.azaken.com/view/{job.id.hex}">
        <meta property="og:image" content="https://api.render.azaken.com{thumb_url}">
        <meta property="og:video" content="https://api.render.azaken.com{video_url}">
        <meta property="og:video:secure_url" content="https://api.render.azaken.com{video_url}">
        <meta property="og:video:type" content="video/mp4">
        <meta property="og:video:width" content="1920">
        <meta property="og:video:height" content="1080">

        <meta name="twitter:card" content="player">
        <meta name="twitter:title" content="OsuRender: {map_title}">
        <meta name="twitter:description" content="Watch this osu! replay render.">
        <meta name="twitter:image" content="https://api.render.azaken.com{thumb_url}">
        <meta name="twitter:player" content="https://api.render.azaken.com/view/{job.id.hex}">
        <meta name="twitter:player:width" content="1920">
        <meta name="twitter:player:height" content="1080">
        <meta name="twitter:player:stream" content="https://api.render.azaken.com{video_url}">
        <meta name="twitter:player:stream:content_type" content="video/mp4">
        
        <style>body{{background:#0f0f0f;color:#ff66aa;font-family:sans-serif;text-align:center;padding:40px;}} video{{width:80%;border:2px solid #ff66aa;display:{show};}} .btn{{background:#ff66aa;color:white;padding:12px 25px;text-decoration:none;border-radius:8px;display:{show};margin-top:20px;}}</style>
    </head>
    <body><h1>Job: {job.id.hex}</h1><p>Map: {map_title}</p>
    <div id="status">Status: {job.status.value} ({job.progress}%)</div>
    
    <video id="v" controls poster="{thumb_url}">{video_src_html}</video><br>
    <a id="d" href="{video_url}" class="btn" download>Download</a>
    
    <script>
    async function check() {{
        let r = await fetch('/v1/jobs/{job.id.hex}');
        if (!r.ok) return;
        let d = await r.json();
        document.getElementById('status').innerText = 'Status: ' + d.status + ' (' + d.progress + '%)';
        
        if (d.status === 'completed') {{
            let v = document.getElementById('v');
            if (!v.getAttribute('src') && v.innerHTML.trim() === '') {{
                v.setAttribute('src', d.artifacts.video_url);
                document.getElementById('d').href = d.artifacts.video_url;
            }}
            v.style.display = 'inline';
            document.getElementById('d').style.display = 'inline-block';
        }} else if (d.status !== 'failed') {{
            setTimeout(check, 3000);
        }}
    }};
    if ("{job.status.value}" !== "completed") check();
    </script></body></html>
    """
    return HTMLResponse(html)
