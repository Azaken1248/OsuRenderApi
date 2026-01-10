import os
import uuid
import json
import asyncio
import shutil
import re
from typing import Dict

import httpx
from osrparse import Replay

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# ================== PATHS ==================

DANSER_DIR = "/home/aza/danser"
DANSER_BIN = "/home/aza/danser/danser-cli"
SONGS_DIR = "/home/aza/danser/osu_data/Songs"
SKINS_DIR = "/home/aza/danser/osu_data/Skins"

DOWNLOADS_DIR = "/home/aza/OsuRender/downloads"
JOBS_DIR = "/home/aza/OsuRender/jobs"
CONFIG_DIR = "/home/aza/danser/settings/jobs"

OSU_API_KEY = os.getenv("OSU_API_KEY")

for d in [DOWNLOADS_DIR, JOBS_DIR, CONFIG_DIR]:
    os.makedirs(d, exist_ok=True)

# ================== APP ==================

app = FastAPI(title="danser render API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================== STATE ==================

jobs: Dict[str, Dict] = {}
render_queue: asyncio.Queue = asyncio.Queue()
worker_started = False

# ================== UTILS ==================

def sanitize(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._ -]", "", s)

# ================== BEATMAP HANDLING ==================

async def ensure_beatmap(osr_path: str) -> bool:
    try:
        replay = Replay.from_path(osr_path)
        h = replay.beatmap_hash

        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                "https://osu.ppy.sh/api/get_beatmaps",
                params={"k": OSU_API_KEY, "h": h},
            )

            if not r.json():
                return False

            set_id = r.json()[0]["beatmapset_id"]
            osz = f"{SONGS_DIR}/{set_id}.osz"

            if os.path.exists(osz):
                return True

            dl = await c.get(
                f"https://api.nerinyan.moe/d/{set_id}",
                follow_redirects=True,
            )

            if dl.status_code != 200:
                return False

            with open(osz, "wb") as f:
                f.write(dl.content)

            return True
    except Exception:
        return False

# ================== WORKER ==================

async def render_worker():
    while True:
        job_id, data = await render_queue.get()
        log_file = f"{JOBS_DIR}/{job_id}.log"
        try:
            jobs[job_id]["status"] = "downloading"
            jobs[job_id]["percent"] = 10
            jobs[job_id]["error"] = None

            if not await ensure_beatmap(data["replay"]):
                jobs[job_id]["status"] = "error: beatmap"
                jobs[job_id]["error"] = "Failed to download beatmap"
                continue

            jobs[job_id]["status"] = "rendering"
            jobs[job_id]["percent"] = 25

            # Build settings patch JSON
            settings_patch = json.dumps({
                "Playfield": {
                    "Background": {
                        "Dim": {"Normal": data["bg_dim"]}
                    }
                }
            })

            env = os.environ.copy()
            env.update({
                "DRI_PRIME": "1",
                "MESA_LOADER_DRIVER_OVERRIDE": "radeonsi",
            })

            # Use xvfb-run for headless rendering
            cmd = [
                "xvfb-run",
                "-a",  # Auto-select display number
                "-s", "-screen 0 1920x1080x24",  # Virtual screen config
                DANSER_BIN,
                f"-replay={data['replay']}",
                f"-skin={data['skin']}",
                f"-sPatch={settings_patch}",
                f"-out=render_{job_id}",
                "-record",
            ]

            with open(log_file, "w") as log:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=DANSER_DIR,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                async def read_output():
                    if proc.stdout:
                        async for line in proc.stdout:
                            line_str = line.decode(errors="ignore")
                            log.write(line_str)
                            log.flush()
                            if "Progress" in line_str:
                                try:
                                    p = float(line_str.split(":")[1].replace("%", "").strip())
                                    jobs[job_id]["percent"] = 25 + (p * 0.75)
                                except Exception:
                                    pass

                async def read_errors():
                    if proc.stderr:
                        async for line in proc.stderr:
                            line_str = line.decode(errors="ignore")
                            log.write(f"[STDERR] {line_str}")
                            log.flush()

                # Read both stdout and stderr concurrently
                await asyncio.gather(
                    read_output(),
                    read_errors(),
                )

                try:
                    await asyncio.wait_for(proc.wait(), timeout=600)  # 10 min timeout
                except asyncio.TimeoutError:
                    proc.kill()
                    jobs[job_id]["status"] = "error: timeout"
                    jobs[job_id]["error"] = "Render timeout (10 minutes)"
                    continue

            out = f"{DOWNLOADS_DIR}/render_{job_id}.mp4"
            if os.path.exists(out):
                jobs[job_id]["status"] = "complete"
                jobs[job_id]["percent"] = 100
            else:
                jobs[job_id]["status"] = "error: no output"
                jobs[job_id]["error"] = "Danser did not produce output file. Check logs."
                # Keep last 20 lines of log for error context
                try:
                    with open(log_file, "r") as f:
                        lines = f.readlines()
                        jobs[job_id]["log_tail"] = "".join(lines[-20:])
                except Exception:
                    pass

        except Exception as e:
            jobs[job_id]["status"] = "error: exception"
            jobs[job_id]["error"] = str(e)
        finally:
            render_queue.task_done()

# ================== STARTUP ==================

@app.on_event("startup")
async def startup():
    global worker_started
    if not worker_started:
        asyncio.create_task(render_worker())
        worker_started = True

# ================== ROUTES ==================

@app.get("/")
def root():
    return {"status": "danser api online"}

@app.get("/skins")
def list_skins():
    if not os.path.exists(SKINS_DIR):
        return []
    return sorted([
        d for d in os.listdir(SKINS_DIR)
        if os.path.isdir(os.path.join(SKINS_DIR, d))
    ])

@app.get("/jobs")
def get_jobs():
    return {
        job_id: {
            "status": job["status"],
            "percent": job.get("percent", 0),
            "error": job.get("error"),
        }
        for job_id, job in jobs.items()
    }

@app.post("/render")
async def render(
    replay: UploadFile = File(...),
    skin: str = Form("Default"),
    bg_dim: float = Form(0.95),
):
    job_id = uuid.uuid4().hex[:8]
    osr_path = f"{JOBS_DIR}/{job_id}.osr"

    with open(osr_path, "wb") as f:
        f.write(await replay.read())

    jobs[job_id] = {
        "status": "queued",
        "percent": 0,
        "replay": osr_path,
        "skin": sanitize(skin),
        "bg_dim": bg_dim,
    }

    await render_queue.put((job_id, jobs[job_id]))

    return {
        "job_id": job_id,
        "logs": f"/logs/{job_id}",
        "download": f"/download/{job_id}",
    }

@app.get("/logs/{job_id}")
def logs(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404)
    result = jobs[job_id].copy()
    # Add full log file if available
    log_file = f"{JOBS_DIR}/{job_id}.log"
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                result["full_log"] = f.read()
        except Exception:
            pass
    return result

@app.get("/download/{job_id}")
def download(job_id: str):
    path = f"{DOWNLOADS_DIR}/render_{job_id}.mp4"
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path)
