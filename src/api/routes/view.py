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
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OsuRender API</title>
    <style>
        body {
            background-color: #111111;
            color: #eeeeee;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }
        h1 {
            color: #ff66aa;
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }
        p {
            font-size: 1.2rem;
            color: #888888;
            margin-bottom: 2rem;
        }
        .nav-links {
            display: flex;
            gap: 1.5rem;
        }
        a {
            background-color: #ff66aa;
            color: #ffffff;
            text-decoration: none;
            padding: 0.75rem 1.5rem;
            border-radius: 6px;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        a:hover {
            background-color: #ff4499;
        }
        .secondary {
            background-color: #222222;
        }
        .secondary:hover {
            background-color: #333333;
        }
    </style>
</head>
<body>
    <h1>OsuRender API</h1>
    <p>High-quality osu! replay rendering service</p>
    <div class="nav-links">
        <a href="/api/docs">Swagger UI</a>
        <a href="/api/redoc" class="secondary">ReDoc</a>
    </div>
</body>
</html>"""
    return HTMLResponse(html)

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
        return HTMLResponse(
            """<html><body style="background:#111;color:#ff66aa;font-family:sans-serif;text-align:center;padding:50px;">
            <h1>404 - Job not found</h1></body></html>""", 
            status_code=404
        )
        
    is_complete = job.status.value == "completed"
    show = "inline-block" if is_complete else "none"
    
    video_url = f"/v1/artifacts/{job.video_storage_key}" if job.video_storage_key else ""
    thumb_url = f"/v1/artifacts/{job.thumb_storage_key}" if job.thumb_storage_key else ""
    
    video_src_html = f'<source src="{video_url}" type="video/mp4">' if is_complete else ''
    
    map_title = job.map_title or job.id.hex
    
    html = f"""<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
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
        
        <style>
            body {{
                background-color: #111111;
                color: #eeeeee;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 2rem;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .container {{
                max-width: 1000px;
                width: 100%;
                background-color: #1a1a1a;
                border-radius: 12px;
                padding: 2rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                text-align: center;
            }}
            h1 {{
                color: #ff66aa;
                margin-top: 0;
                margin-bottom: 0.5rem;
            }}
            .subtitle {{
                color: #888888;
                font-size: 1.1rem;
                margin-bottom: 1.5rem;
            }}
            #status-badge {{
                display: inline-block;
                background-color: #222222;
                color: #eeeeee;
                padding: 0.5rem 1rem;
                border-radius: 8px;
                font-weight: 600;
                margin-bottom: 2rem;
            }}
            video {{
                width: 100%;
                border-radius: 8px;
                background-color: #000000;
                display: {show};
                box-shadow: 0 8px 16px rgba(0,0,0,0.5);
                margin-bottom: 1.5rem;
            }}
            .btn {{
                background-color: #ff66aa;
                color: white;
                padding: 0.75rem 2rem;
                text-decoration: none;
                border-radius: 6px;
                font-weight: bold;
                display: {show};
                transition: background-color 0.2s;
            }}
            .btn:hover {{
                background-color: #ff4499;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{map_title}</h1>
            <div class="subtitle">Job ID: {job.id.hex}</div>
            <div id="status-badge">Status: {job.status.value} ({job.progress}%)</div>
            
            <video id="v" controls poster="{thumb_url}">{video_src_html}</video><br>
            <a id="d" href="{video_url}" class="btn" download>Download Video</a>
        </div>
        
        <script>
        async function check() {{
            let r = await fetch('/v1/jobs/{job.id.hex}');
            if (!r.ok) return;
            let d = await r.json();
            document.getElementById('status-badge').innerText = 'Status: ' + d.status + ' (' + d.progress + '%)';
            
            if (d.status === 'completed') {{
                let v = document.getElementById('v');
                if (!v.getAttribute('src') && v.innerHTML.trim() === '') {{
                    v.setAttribute('src', d.artifacts.video_url);
                    document.getElementById('d').href = d.artifacts.video_url;
                }}
                v.style.display = 'inline-block';
                document.getElementById('d').style.display = 'inline-block';
            }} else if (d.status !== 'failed') {{
                setTimeout(check, 3000);
            }}
        }};
        if ("{job.status.value}" !== "completed") check();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)
