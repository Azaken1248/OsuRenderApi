import os, shutil, uuid, zipfile, json, asyncio, httpx, re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from osrparse import Replay

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="osu! Render Manager v4.4")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
    return _rate_limit_exceeded_handler(request, exc)

OSU_API_KEY = os.getenv("OSU_API_KEY")
DANSER_DIR = os.getenv("DANSER_DIR", "/home/aza/danser")
DANSER_BIN = os.getenv("DANSER_BIN", "/home/aza/danser/danser-cli")
SONGS_DIR = os.getenv("SONGS_DIR", "/home/aza/danser/osu_data/Songs")
SKINS_DIR = os.getenv("SKINS_DIR", "/home/aza/danser/osu_data/Skins")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/home/aza/OsuRender/downloads")
JOBS_DIR = os.getenv("JOBS_DIR", "/home/aza/OsuRender/jobs")

for folder in [SONGS_DIR, SKINS_DIR, OUTPUT_DIR, JOBS_DIR]:
    os.makedirs(folder, exist_ok=True)

progress_tracker = {}
render_queue = asyncio.Queue()

def sanitize(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._ ]', '', name)

async def download_map_strict(replay_path: str, job_id: str):
    try:
        replay = Replay.from_path(replay_path)
        b_hash = replay.beatmap_hash
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"https://osu.ppy.sh/api/get_beatmaps?k={OSU_API_KEY}&h={b_hash}"
            r = await client.get(url)
            if r.status_code != 200 or not r.json(): return False
            set_id = r.json()[0]['beatmapset_id']
            dl = await client.get(f"https://api.nerinyan.moe/d/{set_id}", follow_redirects=True)
            if dl.status_code == 200:
                with open(os.path.join(SONGS_DIR, f"{set_id}.osz"), "wb") as f:
                    f.write(dl.content)
                return True
    except Exception: return False
    return False

async def worker():
    while True:
        job = await render_queue.get()
        replay_path, skin_name, bg_dim, job_id = job
        try:
            if not await download_map_strict(replay_path, job_id):
                progress_tracker[job_id]["status"] = "Error: Map Retrieval Failed"
                continue

            progress_tracker[job_id]["status"] = "Rendering"
            patch = {
                "Playfield": {"Background": {"Dim": {"Normal": bg_dim}}},
                "Skin": {"UseSkinCursor": True, "UseColorsFromSkin": True},
                "Cursor": {"ScaleToCS": True, "EnableRainbow": False},
                "Objects": {"Colors": {"UseSkinComboColors": True, "Color": {"EnableRainbow": False}}}
            }
            
            env = os.environ.copy()
            env["DRI_PRIME"] = "1"
            
            args = [
                DANSER_BIN, f"-replay={replay_path}", f"-skin={skin_name}",
                f"-sPatch={json.dumps(patch)}", f"-out=render_{job_id}", "-record"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *args, cwd=DANSER_DIR, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )

            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line: break
                    text = line.decode().strip()
                    if "Progress" in text:
                        try: 
                            p_val = text.split(":")[1].split("%")[0].strip()
                            progress_tracker[job_id]["percent"] = float(p_val)
                        except Exception: pass
            
            await process.wait()
            progress_tracker[job_id].update({"status": "Complete", "percent": 100.0})
        finally:
            if os.path.exists(replay_path): os.remove(replay_path)
            render_queue.task_done()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(worker())

@app.get("/skins")
@limiter.limit("60/minute")
async def list_skins(request: Request):
    return {"skins": [f for f in os.listdir(SKINS_DIR) if os.path.isdir(os.path.join(SKINS_DIR, f))]}

@app.post("/skins/upload")
@limiter.limit("10/minute")
async def upload_skin(request: Request, file: UploadFile = File(...)):
    raw_filename = file.filename
    if raw_filename is None:
        raise HTTPException(status_code=400, detail="Filename missing")
    
    name = sanitize(raw_filename)
    temp = os.path.join(SKINS_DIR, name)
    with open(temp, "wb") as f: f.write(await file.read())
    
    folder = name.replace(".osk", "").replace(".zip", "")
    target = os.path.abspath(os.path.join(SKINS_DIR, folder))

    if not target.startswith(os.path.abspath(SKINS_DIR)):
        os.remove(temp)
        raise HTTPException(status_code=400, detail="Invalid path")

    try:
        os.makedirs(target, exist_ok=True)
        with zipfile.ZipFile(temp, 'r') as z:
            for m in z.namelist():
                if os.path.abspath(os.path.join(target, m)).startswith(target):
                    z.extract(m, target)
        os.remove(temp)
        
        content = os.listdir(target)
        if len(content) == 1 and os.path.isdir(os.path.join(target, content[0])):
            sub = os.path.join(target, content[0])
            for i in os.listdir(sub): shutil.move(os.path.join(sub, i), target)
            os.rmdir(sub)
        return {"status": "Skin installed", "name": folder}
    except Exception:
        if os.path.exists(temp): os.remove(temp)
        raise HTTPException(status_code=500, detail="Processing error")

@app.post("/render")
@limiter.limit("15/minute")
async def queue_render(
    request: Request, 
    replay: UploadFile = File(...), 
    skin: str = Form("owc Skin Remake"), 
    bg_dim: float = Form(0.95)
):
    job_id = str(uuid.uuid4())[:8]
    r_path = os.path.abspath(os.path.join(JOBS_DIR, f"job_{job_id}.osr"))
    with open(r_path, "wb") as f: f.write(await replay.read())
    
    progress_tracker[job_id] = {"percent": 0.0, "status": "Queued"}
    await render_queue.put((r_path, sanitize(skin), bg_dim, job_id))
    return {"job_id": job_id, "status_url": f"/logs/{job_id}"}

@app.get("/logs/{job_id}")
@limiter.limit("120/minute")
async def get_logs(request: Request, job_id: str):
    return progress_tracker.get(sanitize(job_id), {"status": "Not Found"})

@app.get("/download/{job_id}")
@limiter.limit("30/minute")
async def download_video(request: Request, job_id: str):
    safe_id = sanitize(job_id)
    path = os.path.join(OUTPUT_DIR, f"render_{safe_id}.mp4")
    if os.path.exists(path): return FileResponse(path)
    raise HTTPException(status_code=404)