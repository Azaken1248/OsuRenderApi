import modal
import os, uuid, json, asyncio, httpx, shutil, time, zipfile, tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from osrparse import Replay

# --- 1. ENVIRONMENT & IMAGE ---
image = (
    modal.Image.debian_slim()
    .apt_install(
        "wget", "unzip", "ffmpeg", "xvfb", "libnss3", "libgl1-mesa-glx", 
        "libgl1-mesa-dri", "libgbm1", "libgtk-3-0", "libasound2",
        "libxrender1", "libxtst6", "libxi6", "libxrandr2", "libxcursor1", "libxinerama1"
    )
    .pip_install("fastapi[standard]", "httpx", "osrparse")
    .run_commands(
        "wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip",
        "unzip danser-0.11.0-linux.zip -d /root/danser",
        "chmod +x /root/danser/danser-cli"
    )
)

app = modal.App("aza-render-cloud")
web_app = FastAPI(title="danser render API - Cloud")

# --- 2. STORAGE & VOLUMES ---
assets_vol = modal.Volume.from_name("osu-assets", create_if_missing=True)
jobs_vol = modal.Volume.from_name("osu-jobs", create_if_missing=True)

DANSER_BIN = "/root/danser/danser-cli"
SONGS_DIR = "/mnt/assets/Songs"
SKINS_DIR = "/mnt/assets/Skins"
JOBS_DIR = "/mnt/jobs"
METADATA_DIR = "/mnt/jobs/metadata"

web_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- 3. CORE LOGIC HELPERS ---

def update_job_metadata(job_id: str, updates: dict):
    os.makedirs(METADATA_DIR, exist_ok=True)
    path = f"{METADATA_DIR}/{job_id}.json"
    current_meta = {}
    if os.path.exists(path):
        try:
            with open(path, "r") as f: current_meta = json.load(f)
        except: pass
    current_meta.update(updates)
    current_meta["last_updated"] = time.time()
    with open(path, "w") as f: json.dump(current_meta, f)
    jobs_vol.commit()

async def ensure_beatmap(osr_path: str, api_key: str, job_id: str) -> dict:
    try:
        replay = Replay.from_path(osr_path)
        h = replay.beatmap_hash
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.get("https://osu.ppy.sh/api/get_beatmaps", params={"k": api_key, "h": h})
            data = r.json()
            if not data: return {"success": False, "error": f"Map Hash {h[:8]} not found on API."}

            b_id, s_id = data[0]["beatmap_id"], data[0]["beatmapset_id"]
            title = f"{data[0].get('artist')} - {data[0].get('title')}"
            update_job_metadata(job_id, {"map_link": f"https://osu.ppy.sh/beatmapsets/{s_id}", "map_title": title, "beatmap_id": b_id})

            osz_path = f"{SONGS_DIR}/{s_id}.osz"
            if not os.path.exists(osz_path):
                os.makedirs(SONGS_DIR, exist_ok=True)
                for url in [f"https://api.nerinyan.moe/d/{s_id}", f"https://osu.direct/api/d/{s_id}"]:
                    try:
                        dl = await c.get(url, follow_redirects=True)
                        if dl.status_code == 200:
                            with open(osz_path, "wb") as f: f.write(dl.content)
                            assets_vol.commit(); break
                    except: continue
            return {"success": os.path.exists(osz_path), "beatmap_id": b_id, "error": "Download failed"}
    except Exception as e: return {"success": False, "error": str(e)}

# --- 4. GPU WORKER ---

@app.function(
    image=image, gpu="T4",
    volumes={"/mnt/assets": assets_vol, "/mnt/jobs": jobs_vol},
    secrets=[modal.Secret.from_name("osu-api")], 
    timeout=1200, max_containers=2 
)
async def cloud_render_task(job_id: str, data: dict):
    log_file = f"{JOBS_DIR}/{job_id}.log"
    with open(log_file, "w") as f: f.write(f"Job started: {time.ctime()}\n"); f.flush()
    jobs_vol.commit()

    try:
        os.makedirs("/root/.osu", exist_ok=True)
        if not os.path.exists("/root/.osu/Songs"): os.symlink(SONGS_DIR, "/root/.osu/Songs")
        if not os.path.exists("/root/.osu/Skins"): os.symlink(SKINS_DIR, "/root/.osu/Skins")

        update_job_metadata(job_id, {"status": "downloading", "percent": 10})
        
        api_key = os.environ.get("OSU_API_KEY")
        if not api_key:
            update_job_metadata(job_id, {"status": "error", "error": "OSU_API_KEY is missing from Modal Secrets"})
            return

        map_result = await ensure_beatmap(data["replay"], api_key, job_id)
        if not map_result["success"]:
            update_job_metadata(job_id, {"status": "error", "error": map_result.get("error")})
            return

        update_job_metadata(job_id, {"status": "rendering", "percent": 25})
        
        patch = json.dumps({
            "Graphics": {"Width": data["res_w"], "Height": data["res_h"]},
            "Gameplay": {
                "HitErrorMeter": {"Show": data["hit_error_meter"]},
                "KeyOverlay": {"Show": data["key_overlay"]}
            },
            "Skin": {
                "CurrentSkin": data["skin"], "UseColorsFromSkin": True, 
                "UseBeatmapColors": False, "Cursor": {"UseSkinCursor": True, "Scale": 0.6}
            },
            "Objects": {
                "Sliders": {
                    "ForceSliderBallTexture": True,
                    "Snaking": {
                        "In": data["snaking_in"],
                        "Out": data["snaking_out"]
                    }
                }
            },
            "Playfield": {
                "Background": {
                    "Dim": {"Normal": data["bg_dim"]},
                    "LoadStoryboards": data["storyboard"],
                    "LoadVideos": data["video"]
                }, 
                "Skins": {"UseSkinCursor": True, "UseSliderSkin": True}
            },
            "Recording": {"MotionBlur": {"Enabled": data["motion_blur"]}, "Encoder": "h264_nvenc"}
        })

        env = os.environ.copy()
        env.update({"DISPLAY": ":99", "NVIDIA_DRIVER_CAPABILITIES": "all", "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__NV_PRIME_RENDER_OFFLOAD": "1"})

        target_name = f"render_{job_id}"
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {data['res_w']}x{data['res_h']}x24 +extension GLX +render -noreset",
               DANSER_BIN, "-nodbcheck", f"-id={map_result['beatmap_id']}", f"-replay={data['replay']}", 
               f"-skin={data['skin']}", f"-sPatch={patch}", f"-out={JOBS_DIR}/{target_name}", "-record"]

        with open(log_file, "a") as log:
            proc = await asyncio.create_subprocess_exec(*cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            async def stream_output(stream):
                if stream:
                    async for line in stream:
                        line_str = line.decode(errors="ignore"); log.write(line_str); log.flush()
                        if "Progress" in line_str:
                            try:
                                p = float(line_str.split("Progress:")[1].split("%")[0].strip())
                                update_job_metadata(job_id, {"percent": int(25 + (p * 0.75))})
                            except: pass
            await asyncio.gather(stream_output(proc.stdout), stream_output(proc.stderr)); await proc.wait()

        final_mp4 = f"{JOBS_DIR}/{target_name}.mp4"
        thumb_path = f"{JOBS_DIR}/thumb_{job_id}.jpg"
        found = False
        
        for p in [final_mp4, f"{final_mp4}.mp4", f"/root/danser/videos{JOBS_DIR}/{target_name}.mp4", f"/root/danser/videos{JOBS_DIR}/{target_name}.mp4.mp4"]:
            if os.path.exists(p):
                if p != final_mp4: shutil.move(p, final_mp4)
                found = True; break
        
        # FIX: Generate a thumbnail automatically 15 seconds into the video
        if found:
            thumb_proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", "00:00:15", "-i", final_mp4, "-vframes", "1", "-q:v", "2", thumb_path
            )
            await thumb_proc.wait()

        update_job_metadata(job_id, {"status": "complete" if found else "error", "percent": 100 if found else 25})
    except Exception as e: update_job_metadata(job_id, {"status": "error", "error": str(e)})
    finally: jobs_vol.commit()

# --- 5. ROUTES ---

@web_app.get("/")
def home(): return HTMLResponse("<h1>🎮 OsuRender API Online</h1><p><a href='/jobs'>History</a> | <a href='/docs'>Docs</a></p>")

@web_app.get("/skins")
async def list_skins():
    assets_vol.reload()
    if not os.path.exists(SKINS_DIR): return []
    return sorted([d for d in os.listdir(SKINS_DIR) if os.path.isdir(os.path.join(SKINS_DIR, d))])

@web_app.post("/skins/upload")
async def upload_skin(skin: UploadFile = File(...)):
    orig_filename = skin.filename
    if not orig_filename or not orig_filename.endswith('.osk'): 
        raise HTTPException(400, "Must be a valid .osk file")
        
    skin_name = orig_filename[:-4]
    skin_path = os.path.join(SKINS_DIR, skin_name)
    
    assets_vol.reload()
    if os.path.exists(skin_path): raise HTTPException(409, "Skin already exists")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.osk') as tmp:
        tmp.write(await skin.read()); tmp_path = tmp.name
    try:
        os.makedirs(SKINS_DIR, exist_ok=True)
        with zipfile.ZipFile(tmp_path, 'r') as z: z.extractall(skin_path)
        os.unlink(tmp_path); assets_vol.commit()
        return {"success": True, "skin_name": skin_name}
    except: raise HTTPException(500, "Extraction failed")

@web_app.post("/render")
async def render(
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
    key_overlay: bool = Form(True)
):
    if bg_dim > 1.0:
        bg_dim = bg_dim / 100.0
    bg_dim = max(0.0, min(1.0, bg_dim))

    job_id = uuid.uuid4().hex[:8]
    os.makedirs(f"{JOBS_DIR}/replays", exist_ok=True)
    osr_path = f"{JOBS_DIR}/replays/{job_id}.osr"
    
    with open(osr_path, "wb") as f: 
        f.write(await replay.read())
        
    update_job_metadata(job_id, {
        "job_id": job_id, "status": "queued", "percent": 0, "skin": skin, 
        "created_at": time.time()
    })
    
    w, h = (3840, 2160) if quality == "ultra" else (1920, 1080)
    
    cloud_render_task.spawn(job_id, {
        "replay": osr_path, 
        "skin": skin, 
        "bg_dim": bg_dim, 
        "quality": quality, 
        "motion_blur": motion_blur, 
        "storyboard": storyboard,
        "video": video,
        "snaking_in": snaking_in,
        "snaking_out": snaking_out,
        "hit_error_meter": hit_error_meter,
        "key_overlay": key_overlay,
        "res_w": w, 
        "res_h": h
    })
    
    return {
        "job_id": job_id, 
        "view_url": f"/view/{job_id}",
        "video_url": f"/video/{job_id}.mp4" 
    }

@web_app.get("/status/{job_id}")
async def get_status(job_id: str):
    jobs_vol.reload(); path = f"{METADATA_DIR}/{job_id}.json"
    if not os.path.exists(path): raise HTTPException(404)
    with open(path, "r") as f: return json.load(f)

@web_app.get("/jobs")
async def list_history():
    jobs_vol.reload(); os.makedirs(METADATA_DIR, exist_ok=True)
    return [json.load(open(f"{METADATA_DIR}/{f}")) for f in os.listdir(METADATA_DIR) if f.endswith(".json")]

@web_app.get("/logs/{job_id}")
async def get_logs(job_id: str):
    jobs_vol.reload(); path = f"{JOBS_DIR}/{job_id}.log"
    return {"log": open(path).read()} if os.path.exists(path) else {"status": "no logs"}

@web_app.get("/view/{job_id}", response_class=HTMLResponse)
async def view_player(job_id: str):
    jobs_vol.reload(); path = f"{METADATA_DIR}/{job_id}.json"
    if not os.path.exists(path): return "Job not found"
    
    meta = json.load(open(path))
    is_complete = meta.get("status") == "complete"
    show = "inline" if is_complete else "none"
    
    video_src_html = f'<source src="/video/{job_id}.mp4" type="video/mp4">' if is_complete else ''
    
    # FIX: Comprehensive Meta Tags for Discord, Twitter, WhatsApp, and Facebook
    return f"""
    <html><head>
        <title>OsuRender: {meta.get('map_title', job_id)}</title>
        <meta name="description" content="Watch this osu! replay render powered by OsuRender Cloud API.">
        <meta name="theme-color" content="#ff66aa">
        
        <meta property="og:title" content="OsuRender Job: {meta.get('map_title', 'Loading...')}">
        <meta property="og:description" content="Click to watch this osu! replay render.">
        <meta property="og:type" content="video.other">
        <meta property="og:url" content="https://api.render.azaken.com/view/{job_id}">
        <meta property="og:image" content="https://api.render.azaken.com/thumbnail/{job_id}.jpg">
        <meta property="og:video" content="https://api.render.azaken.com/video/{job_id}.mp4">
        <meta property="og:video:secure_url" content="https://api.render.azaken.com/video/{job_id}.mp4">
        <meta property="og:video:type" content="video/mp4">
        <meta property="og:video:width" content="1920">
        <meta property="og:video:height" content="1080">

        <meta name="twitter:card" content="player">
        <meta name="twitter:title" content="OsuRender: {meta.get('map_title', 'Loading...')}">
        <meta name="twitter:description" content="Watch this osu! replay render.">
        <meta name="twitter:image" content="https://api.render.azaken.com/thumbnail/{job_id}.jpg">
        <meta name="twitter:player" content="https://api.render.azaken.com/view/{job_id}">
        <meta name="twitter:player:width" content="1920">
        <meta name="twitter:player:height" content="1080">
        <meta name="twitter:player:stream" content="https://api.render.azaken.com/video/{job_id}.mp4">
        <meta name="twitter:player:stream:content_type" content="video/mp4">
        
        <style>body{{background:#0f0f0f;color:#ff66aa;font-family:sans-serif;text-align:center;padding:40px;}} video{{width:80%;border:2px solid #ff66aa;display:{show};}} .btn{{background:#ff66aa;color:white;padding:12px 25px;text-decoration:none;border-radius:8px;display:{show};margin-top:20px;}}</style>
    </head>
    <body><h1>Job: {job_id}</h1><p>Map: {meta.get('map_title','Loading...')}</p>
    <div id="status">Status: {meta['status']} ({meta['percent']}%)</div>
    
    <video id="v" controls poster="/thumbnail/{job_id}.jpg">{video_src_html}</video><br>
    <a id="d" href="/video/{job_id}.mp4" class="btn" download>Download</a>
    
    <script>
    async function check() {{
        let r = await fetch('/status/{job_id}');
        let d = await r.json();
        document.getElementById('status').innerText = 'Status: ' + d.status + ' (' + d.percent + '%)';
        
        if (d.status === 'complete') {{
            let v = document.getElementById('v');
            if (!v.getAttribute('src') && v.innerHTML.trim() === '') {{
                v.setAttribute('src', '/video/{job_id}.mp4');
            }}
            v.style.display = 'inline';
            document.getElementById('d').style.display = 'inline-block';
        }} else if (d.status !== 'error') {{
            setTimeout(check, 3000);
        }}
    }};
    if ("{meta.get('status')}" !== "complete") check();
    </script></body></html>
    """
@web_app.get("/thumbnail/{job_id}.jpg")
async def stream_thumbnail(job_id: str):
    path = f"{JOBS_DIR}/thumb_{job_id}.jpg"
    for _ in range(10):
        jobs_vol.reload()
        if os.path.exists(path):
            return FileResponse(path, media_type="image/jpeg")
        await asyncio.sleep(0.5)
    raise HTTPException(404, "Thumbnail not found")

@web_app.get("/video/{job_id}.mp4")
async def stream_video(job_id: str):
    path = f"{JOBS_DIR}/render_{job_id}.mp4"
    for _ in range(10):
        jobs_vol.reload()
        if os.path.exists(path):
            return FileResponse(path, media_type="video/mp4", headers={"Content-Disposition": "inline"})
        await asyncio.sleep(0.5)
    raise HTTPException(404, "Video file not found or still syncing across cloud volume.")

@app.function(image=image, volumes={"/mnt/assets": assets_vol, "/mnt/jobs": jobs_vol})
@modal.asgi_app()
def fastapi_app(): return web_app