import modal
import os, uuid, json, asyncio, httpx, shutil, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from osrparse import Replay

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

assets_vol = modal.Volume.from_name("osu-assets", create_if_missing=True)
jobs_vol = modal.Volume.from_name("osu-jobs", create_if_missing=True)

DANSER_BIN = "/root/danser/danser-cli"
SONGS_DIR = "/mnt/assets/Songs"
SKINS_DIR = "/mnt/assets/Skins"
JOBS_DIR = "/mnt/jobs"
METADATA_DIR = "/mnt/jobs/metadata"

web_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@web_app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>OsuRender Cloud</title>
        <style>
            body { background: #0f0f0f; color: #ff66aa; font-family: 'Segoe UI', sans-serif; text-align: center; padding: 50px; }
            h1 { font-size: 3rem; margin-bottom: 10px; }
            p { font-size: 1.2rem; color: #c0c0c0; }
            a { color: #ff66aa; text-decoration: none; font-weight: bold; }
            a:hover { color: #ff4488; text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🎮 OsuRender Cloud API</h1>
        <p>GPU-accelerated osu! replay rendering service</p>
        <p><a href="/docs">📖 View API Documentation</a></p>
    </body>
    </html>
    """

@web_app.get("/docs", response_class=HTMLResponse)
async def docs():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OsuRender Cloud API Documentation</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #0d0d0d 0%, #1a1a1a 100%);
                color: #e0e0e0;
                line-height: 1.6;
            }
            .header {
                background: linear-gradient(90deg, #ff66aa 0%, #ff4488 100%);
                padding: 30px 20px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(255, 102, 170, 0.3);
            }
            .header h1 {
                color: white;
                font-size: 2.5rem;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .header p {
                color: #ffe0ee;
                font-size: 1.1rem;
                margin-top: 10px;
            }
            .badge-cloud {
                background: #4caf50;
                color: white;
                padding: 5px 15px;
                border-radius: 15px;
                font-size: 0.9rem;
                display: inline-block;
                margin-top: 10px;
            }
            .container {
                max-width: 1200px;
                margin: 40px auto;
                padding: 0 20px;
            }
            .section {
                background: #242424;
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 30px;
                border: 1px solid #333;
                box-shadow: 0 8px 25px rgba(0,0,0,0.4);
            }
            .section h2 {
                color: #ff66aa;
                font-size: 1.8rem;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 2px solid #ff66aa;
            }
            .section h3 {
                color: #ff88bb;
                font-size: 1.4rem;
                margin: 20px 0 10px 0;
            }
            .endpoint {
                background: #1a1a1a;
                border-left: 4px solid #ff66aa;
                padding: 20px;
                margin: 15px 0;
                border-radius: 8px;
            }
            .method {
                display: inline-block;
                padding: 5px 12px;
                border-radius: 5px;
                font-weight: bold;
                margin-right: 10px;
                font-size: 0.9rem;
            }
            .get { background: #4caf50; color: white; }
            .post { background: #ff9800; color: white; }
            .path {
                font-family: 'Courier New', monospace;
                color: #ff66aa;
                font-size: 1.1rem;
                font-weight: bold;
            }
            .description {
                margin: 15px 0;
                color: #c0c0c0;
            }
            code {
                background: #1a1a1a;
                padding: 2px 8px;
                border-radius: 4px;
                color: #ff88bb;
                font-family: 'Courier New', monospace;
            }
            pre {
                background: #0d0d0d;
                padding: 15px;
                border-radius: 8px;
                overflow-x: auto;
                margin: 10px 0;
                border: 1px solid #333;
            }
            pre code {
                background: none;
                padding: 0;
                color: #66ff99;
            }
            .params {
                margin: 15px 0;
            }
            .param {
                background: #0d0d0d;
                padding: 10px;
                margin: 8px 0;
                border-radius: 6px;
                border-left: 3px solid #ff66aa;
            }
            .param-name {
                color: #ff88bb;
                font-weight: bold;
                font-family: 'Courier New', monospace;
            }
            .param-type {
                color: #66ddff;
                font-size: 0.9rem;
                font-style: italic;
            }
            .response {
                background: #0d0d0d;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
            }
            .response-title {
                color: #66ff99;
                font-weight: bold;
                margin-bottom: 10px;
            }
            ul {
                margin-left: 20px;
                color: #c0c0c0;
            }
            li {
                margin: 8px 0;
            }
            a {
                color: #ff66aa;
                text-decoration: none;
                transition: color 0.3s;
            }
            a:hover {
                color: #ff4488;
                text-decoration: underline;
            }
            .badge {
                display: inline-block;
                background: #333;
                color: #ff66aa;
                padding: 3px 10px;
                border-radius: 12px;
                font-size: 0.85rem;
                margin-left: 10px;
            }
            .highlight {
                background: #ff66aa22;
                border: 1px solid #ff66aa;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚀 OsuRender Cloud API</h1>
            <p>GPU-accelerated osu! replay rendering service powered by Modal + Danser-Go</p>
            <span class="badge-cloud">☁️ Cloud Deployment</span>
        </div>

        <div class="container">
            <div class="section">
                <h2>📖 Overview</h2>
                <p>Welcome to the OsuRender Cloud API! This is the <strong>serverless cloud version</strong> running on Modal with GPU acceleration. It provides high-quality osu! replay rendering with automatic scaling, persistent storage, and an interactive web player.</p>
                
                <div class="highlight">
                    <h3>🌟 Key Features:</h3>
                    <ul>
                        <li><strong>GPU Acceleration:</strong> NVIDIA T4 GPU for faster rendering</li>
                        <li><strong>High Quality:</strong> Support for 1080p and 4K (ultra) rendering</li>
                        <li><strong>Motion Blur:</strong> Cinematic motion blur effects</li>
                        <li><strong>Interactive Player:</strong> Built-in web player for viewing renders</li>
                        <li><strong>Persistent Storage:</strong> All renders saved to Modal Volumes</li>
                        <li><strong>Auto-scaling:</strong> Scales from 0 to 2 concurrent renders</li>
                    </ul>
                </div>
            </div>

            <div class="section">
                <h2>🚀 Endpoints</h2>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/skins</span>
                    <div class="description">List all available osu! skins that can be used for rendering.</div>
                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>["Default", "Rafis HDDT", "WhiteCat 1.0", "Seoul v9", ...]</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span class="path">/skins/upload</span>
                    <span class="badge">multipart/form-data</span>
                    <div class="description">Upload a .osk file to add a new skin to the cloud rendering service.</div>
                    
                    <div class="params">
                        <h3>Parameters:</h3>
                        <div class="param">
                            <span class="param-name">skin</span> <span class="param-type">(file, required)</span>
                            <p>The .osk skin file to upload</p>
                        </div>
                    </div>

                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>{
  "success": true,
  "skin_name": "MyCustomSkin",
  "message": "Skin 'MyCustomSkin' uploaded successfully"
}</code></pre>
                    </div>

                    <div class="response">
                        <div class="response-title">Example cURL:</div>
                        <pre><code>curl -X POST https://your-modal-app.modal.run/skins/upload \\
  -F "skin=@MyCustomSkin.osk"</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method post">POST</span>
                    <span class="path">/render</span>
                    <span class="badge">multipart/form-data</span>
                    <div class="description">Submit a new replay for cloud rendering with GPU acceleration.</div>
                    
                    <div class="params">
                        <h3>Parameters:</h3>
                        <div class="param">
                            <span class="param-name">replay</span> <span class="param-type">(file, required)</span>
                            <p>The .osr replay file to render</p>
                        </div>
                        <div class="param">
                            <span class="param-name">skin</span> <span class="param-type">(string, optional)</span>
                            <p>Skin name to use. Default: <code>"Default"</code></p>
                        </div>
                        <div class="param">
                            <span class="param-name">bg_dim</span> <span class="param-type">(float, optional)</span>
                            <p>Background dim (0.0-1.0). Default: <code>0.95</code></p>
                        </div>
                        <div class="param">
                            <span class="param-name">quality</span> <span class="param-type">(string, optional)</span>
                            <p>Render quality: <code>"standard"</code> (1080p) or <code>"ultra"</code> (4K). Default: <code>"standard"</code></p>
                        </div>
                        <div class="param">
                            <span class="param-name">motion_blur</span> <span class="param-type">(boolean, optional)</span>
                            <p>Enable motion blur effect. Default: <code>true</code></p>
                        </div>
                    </div>

                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>{
  "job_id": "abc123de",
  "view_url": "/view/abc123de"
}</code></pre>
                    </div>

                    <div class="response">
                        <div class="response-title">Example cURL:</div>
                        <pre><code>curl -X POST https://your-modal-app.modal.run/render \\
  -F "replay=@myreplay.osr" \\
  -F "skin=Default" \\
  -F "bg_dim=0.85" \\
  -F "quality=ultra" \\
  -F "motion_blur=true"</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/view/{job_id}</span>
                    <div class="description">View an interactive HTML player for your render. Auto-updates during rendering.</div>
                    
                    <div class="params">
                        <h3>Parameters:</h3>
                        <div class="param">
                            <span class="param-name">job_id</span> <span class="param-type">(path parameter)</span>
                            <p>The unique job identifier returned from <code>/render</code></p>
                        </div>
                    </div>

                    <div class="response">
                        <div class="response-title">Features:</div>
                        <ul>
                            <li>Real-time progress updates</li>
                            <li>Embedded video player when complete</li>
                            <li>Direct link to beatmap</li>
                            <li>Download button for high-quality MP4</li>
                            <li>osu!-themed aesthetic design</li>
                        </ul>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/status/{job_id}</span>
                    <div class="description">Get detailed JSON status for a specific job.</div>
                    
                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>{
  "job_id": "abc123de",
  "status": "rendering",
  "percent": 67,
  "skin": "Default",
  "map_link": "https://osu.ppy.sh/beatmapsets/123456",
  "map_title": "Artist - Song Title",
  "video_path": "/mnt/jobs/render_abc123de.mp4",
  "created_at": 1705161234.567,
  "last_updated": 1705161345.678
}</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/jobs</span>
                    <div class="description">List all render jobs, sorted by creation time (newest first).</div>
                    
                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>[
  {
    "job_id": "abc123de",
    "status": "complete",
    "percent": 100,
    "created_at": 1705161234.567,
    ...
  },
  {
    "job_id": "def456gh",
    "status": "rendering",
    "percent": 45,
    "created_at": 1705161123.456,
    ...
  }
]</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/logs/{job_id}</span>
                    <div class="description">Get Danser rendering logs for debugging.</div>
                    
                    <div class="response">
                        <div class="response-title">Response:</div>
                        <pre><code>{
  "log": "... full danser output ..."
}</code></pre>
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method get">GET</span>
                    <span class="path">/video/{job_id}</span>
                    <div class="description">Download or stream the rendered video file.</div>
                    
                    <div class="response">
                        <div class="response-title">Response:</div>
                        <p>Returns the video file as <code>video/mp4</code></p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>📊 Job Status Values</h2>
                <ul>
                    <li><strong>queued</strong> - Job submitted, waiting for GPU container</li>
                    <li><strong>downloading</strong> - Downloading beatmap from osu! servers</li>
                    <li><strong>rendering</strong> - GPU is actively rendering the video</li>
                    <li><strong>complete</strong> - Render finished, video ready!</li>
                    <li><strong>error</strong> - Something went wrong (check error field)</li>
                </ul>
            </div>

            <div class="section">
                <h2>⚡ Quick Start</h2>
                <pre><code>1. POST /render with your .osr file
   → Get job_id and view_url

2. Open the view_url in your browser
   → Watch live progress updates

3. When complete, video plays automatically
   → Click download for high-quality MP4

Alternative: Poll /status/{job_id} for JSON updates</code></pre>
            </div>

            <div class="section">
                <h2>⚙️ Technical Specifications</h2>
                <ul>
                    <li><strong>GPU:</strong> NVIDIA T4 (16GB VRAM)</li>
                    <li><strong>Encoder:</strong> h264_nvenc (hardware acceleration)</li>
                    <li><strong>Resolution:</strong> 1920x1080 (standard) or 3840x2160 (ultra)</li>
                    <li><strong>Max Concurrent Renders:</strong> 2</li>
                    <li><strong>Timeout:</strong> 20 minutes per render</li>
                    <li><strong>Storage:</strong> Persistent Modal Volumes</li>
                    <li><strong>Framework:</strong> FastAPI + Modal</li>
                    <li><strong>Render Engine:</strong> Danser-Go 0.11.0</li>
                </ul>
            </div>

            <div class="section">
                <h2>🎨 Quality Settings</h2>
                <h3>Standard (1080p):</h3>
                <ul>
                    <li>Resolution: 1920x1080</li>
                    <li>Bitrate: ~8-12 Mbps</li>
                    <li>Best for: Quick previews, web sharing</li>
                </ul>
                
                <h3>Ultra (4K):</h3>
                <ul>
                    <li>Resolution: 3840x2160</li>
                    <li>Bitrate: ~20-30 Mbps</li>
                    <li>Best for: YouTube uploads, archival</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """


def update_job_metadata(job_id, updates):
    """Saves job state to a persistent JSON file on the volume"""
    os.makedirs(METADATA_DIR, exist_ok=True)
    meta_path = f"{METADATA_DIR}/{job_id}.json"
    
    current_meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            current_meta = json.load(f)
    
    current_meta.update(updates)
    current_meta["last_updated"] = time.time()
    
    with open(meta_path, "w") as f:
        json.dump(current_meta, f)
    jobs_vol.commit()

async def ensure_beatmap(osr_path: str, api_key: str, job_id: str) -> bool:
    """Downloads map and updates job metadata with the osu! link"""
    try:
        replay = Replay.from_path(osr_path)
        h = replay.beatmap_hash
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get("https://osu.ppy.sh/api/get_beatmaps", params={"k": api_key, "h": h})
            data = r.json()
            if not data: return False
            
            set_id = data[0]["beatmapset_id"]
            map_link = f"https://osu.ppy.sh/beatmapsets/{set_id}"
            update_job_metadata(job_id, {"map_link": map_link, "map_title": data[0]["title"]})
            
            osz_path = f"{SONGS_DIR}/{set_id}.osz"
            if os.path.exists(osz_path): return True
            
            os.makedirs(SONGS_DIR, exist_ok=True)
            dl = await c.get(f"https://api.nerinyan.moe/d/{set_id}", follow_redirects=True)
            with open(osz_path, "wb") as f: f.write(dl.content)
            return True
    except Exception: return False

@app.function(
    image=image, gpu="T4",
    volumes={"/mnt/assets": assets_vol, "/mnt/jobs": jobs_vol},
    secrets=[modal.Secret.from_name("osu-api")], 
    timeout=1200, max_containers=2 
)
async def cloud_render_task(job_id: str, data: dict):
    log_file = f"{JOBS_DIR}/{job_id}.log"
    
    try:
        os.makedirs("/root/.osu", exist_ok=True)
        for d in ["Songs", "Skins"]:
            link = f"/root/.osu/{d}"
            target = SONGS_DIR if d == "Songs" else SKINS_DIR
            if not os.path.exists(link): os.symlink(target, link)

        update_job_metadata(job_id, {"status": "downloading", "percent": 10})
        api_key = os.environ.get("OSU_API_KEY")
        if not api_key or not await ensure_beatmap(data["replay"], api_key, job_id):
            update_job_metadata(job_id, {"status": "error", "error": "Map download failed"})
            return

        update_job_metadata(job_id, {"status": "rendering", "percent": 25})
        settings_patch = json.dumps({
            "Graphics": {"Width": data["res_w"], "Height": data["res_h"]},
            "Skin": {"CurrentSkin": data["skin"], "UseColorsFromSkin": True, "UseBeatmapColors": False,
                     "Cursor": {"UseSkinCursor": True, "Scale": 0.6}},
            "Objects": {"Sliders": {"ForceSliderBallTexture": True}},
            "Playfield": {"Background": {"Dim": {"Normal": data["bg_dim"]}},
                          "Skins": {"UseSkinCursor": True, "UseSkinColors": True, "UseSliderSkin": True}},
            "Recording": {"MotionBlur": {"Enabled": data["motion_blur"], "Samples": 24},
                          "Encoder": "h264_nvenc", "EncoderOptions": "-rc vbr -cq 23 -preset p4"}
        })

        env = os.environ.copy()
        env.update({"DISPLAY": ":99", "NVIDIA_VISIBLE_DEVICES": "all", "NVIDIA_DRIVER_CAPABILITIES": "all,graphics,utility,video,display",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__NV_PRIME_RENDER_OFFLOAD": "1", "MESA_LOADER_DRIVER_OVERRIDE": "nvidia"})

        target_name = f"render_{job_id}"
        final_mp4_path = f"{JOBS_DIR}/{target_name}.mp4"
        
        cmd = ["xvfb-run", "-a", "-s", f"-screen 0 {data['res_w']}x{data['res_h']}x24 +extension GLX +render -noreset",
               DANSER_BIN, "-nodbcheck", f"-replay={data['replay']}", f"-skin={data['skin']}",
               f"-sPatch={settings_patch}", f"-out={JOBS_DIR}/{target_name}", "-record"]

        with open(log_file, "w") as log:
            proc = await asyncio.create_subprocess_exec(*cmd, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            async def stream_output(stream):
                async for line in stream:
                    line_str = line.decode(errors="ignore")
                    log.write(line_str); log.flush()
                    if "Progress" in line_str:
                        try:
                            p = float(line_str.split("Progress:")[1].split("%")[0].strip())
                            update_job_metadata(job_id, {"percent": int(25 + (p * 0.75))})
                        except: pass
            await asyncio.gather(stream_output(proc.stdout), stream_output(proc.stderr))
            await proc.wait()

        found_path = None
        for p in [final_mp4_path, f"{final_mp4_path}.mp4", f"/root/danser/videos{JOBS_DIR}/{target_name}.mp4", f"/root/danser/videos{JOBS_DIR}/{target_name}.mp4.mp4"]:
            if os.path.exists(p):
                if p != final_mp4_path: shutil.move(p, final_mp4_path)
                found_path = final_mp4_path; break
        
        if found_path: update_job_metadata(job_id, {"status": "complete", "percent": 100, "video_path": final_mp4_path})
        else: update_job_metadata(job_id, {"status": "error", "error": "MP4 not found"})

    except Exception as e: update_job_metadata(job_id, {"status": "error", "error": str(e)})
    finally: jobs_vol.commit()


@web_app.get("/skins")
async def list_skins():
    """List all available skins in the assets volume"""
    assets_vol.reload()
    if not os.path.exists(SKINS_DIR):
        return []
    return sorted([
        d for d in os.listdir(SKINS_DIR)
        if os.path.isdir(os.path.join(SKINS_DIR, d))
    ])

@web_app.post("/skins/upload")
async def upload_skin(skin: UploadFile = File(...)):
    """Upload a .osk file and extract it as a new skin"""
    import zipfile
    import tempfile
    
    if not skin.filename or not skin.filename.endswith('.osk'):
        raise HTTPException(400, "File must be a .osk file")
    
    # Get skin name from filename (remove .osk extension)
    skin_name = skin.filename[:-4]
    skin_path = os.path.join(SKINS_DIR, skin_name)
    
    assets_vol.reload()
    
    # Check if skin already exists
    if os.path.exists(skin_path):
        raise HTTPException(409, f"Skin '{skin_name}' already exists")
    
    try:
        # Create temporary file to save the .osk
        with tempfile.NamedTemporaryFile(delete=False, suffix='.osk') as tmp:
            content = await skin.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Extract the .osk file (which is a zip file)
        os.makedirs(SKINS_DIR, exist_ok=True)
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            zip_ref.extractall(skin_path)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Commit changes to volume
        assets_vol.commit()
        
        return {
            "success": True,
            "skin_name": skin_name,
            "message": f"Skin '{skin_name}' uploaded successfully"
        }
    
    except zipfile.BadZipFile:
        raise HTTPException(400, "Invalid .osk file (not a valid zip archive)")
    except Exception as e:
        # Clean up on error
        if os.path.exists(skin_path):
            shutil.rmtree(skin_path)
        raise HTTPException(500, f"Failed to upload skin: {str(e)}")

@web_app.post("/render")
async def render(replay: UploadFile = File(...), skin: str = Form("Default"), bg_dim: float = Form(0.95), quality: str = Form("standard"), motion_blur: bool = Form(True)):
    job_id = uuid.uuid4().hex[:8]
    os.makedirs(f"{JOBS_DIR}/replays", exist_ok=True)
    osr_path = f"{JOBS_DIR}/replays/{job_id}.osr"
    with open(osr_path, "wb") as f: f.write(await replay.read())
    
    update_job_metadata(job_id, {
        "job_id": job_id, "status": "queued", "percent": 0, "skin": skin, 
        "replay_path": osr_path, "created_at": time.time(), "video_path": None
    })

    res_w, res_h = (3840, 2160) if quality == "ultra" else (1920, 1080)
    cloud_render_task.spawn(job_id, {"replay": osr_path, "skin": skin, "bg_dim": bg_dim, "quality": quality, "motion_blur": motion_blur, "res_w": res_w, "res_h": res_h})
    return {"job_id": job_id, "view_url": f"/view/{job_id}"}

@web_app.get("/status/{job_id}")
async def get_status(job_id: str):
    jobs_vol.reload()
    meta_path = f"{METADATA_DIR}/{job_id}.json"
    if not os.path.exists(meta_path): raise HTTPException(404)
    with open(meta_path, "r") as f: return json.load(f)

@web_app.get("/logs/{job_id}")
async def get_logs(job_id: str):
    jobs_vol.reload(); path = f"{JOBS_DIR}/{job_id}.log"
    if not os.path.exists(path): return {"status": "no logs"}
    with open(path, "r") as f: return {"log": f.read()}

@web_app.get("/jobs")
async def list_jobs():
    """Returns all jobs stored in the volume"""
    jobs_vol.reload()
    if not os.path.exists(METADATA_DIR): return []
    all_jobs = []
    for f in os.listdir(METADATA_DIR):
        with open(f"{METADATA_DIR}/{f}", "r") as j: all_jobs.append(json.load(j))
    return sorted(all_jobs, key=lambda x: x["created_at"], reverse=True)

@web_app.get("/view/{job_id}", response_class=HTMLResponse)
async def view_player(job_id: str):
    jobs_vol.reload()
    meta_path = f"{METADATA_DIR}/{job_id}.json"
    initial_data = {"status": "loading", "percent": 0}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            initial_data = json.load(f)

    show_player = "inline" if initial_data.get("status") == "complete" else "none"
    
    return f"""
    <html>
        <head>
            <title>Job {job_id}</title>
            <style>
                body {{ background: #0f0f0f; color: #ff66aa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; padding: 40px; }}
                .container {{ max-width: 900px; margin: auto; background: #1a1a1a; padding: 30px; border-radius: 15px; border: 1px solid #333; }}
                video {{ width: 100%; border-radius: 10px; border: 2px solid #ff66aa; margin-top: 20px; box-shadow: 0 0 20px rgba(255, 102, 170, 0.3); }}
                .status-box {{ font-size: 1.2rem; margin: 20px 0; padding: 10px; background: #222; border-radius: 8px; }}
                .btn {{ background: #ff66aa; color: white; padding: 12px 25px; text-decoration: none; border-radius: 8px; display: inline-block; margin-top: 20px; font-weight: bold; transition: 0.3s; }}
                .btn:hover {{ background: #ff4488; transform: scale(1.05); }}
                h1 {{ color: #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Render Job: {job_id}</h1>
                <p>Map: <a href="{initial_data.get('map_link', '#')}" target="_blank" style="color:#ff66aa;">{initial_data.get('map_title', 'Unknown Map')}</a></p>
                
                <div class="status-box" id="status">
                    Status: {initial_data.get('status')} ({initial_data.get('percent')}%)
                </div>

                <video id="player" controls style="display:{show_player};">
                    <source src="/video/{job_id}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <br>
                <a id="dl" href="/video/{job_id}" class="btn" style="display:{show_player};" download="render_{job_id}.mp4">Download High-Quality MP4</a>
            </div>

            <script>
                // FIXED: Use 'async function' instead of 'async def'
                async function checkStatus() {{
                    try {{
                        let response = await fetch('/status/{job_id}');
                        if (!response.ok) return;
                        
                        let data = await response.json();
                        document.getElementById('status').innerText = 'Status: ' + data.status + ' (' + data.percent + '%)';
                        
                        if (data.status === 'complete') {{ 
                            document.getElementById('player').style.display = 'inline'; 
                            document.getElementById('dl').style.display = 'inline-block';
                            // Reload video source to ensure it loads the finished file
                            document.getElementById('player').load();
                        }} else if (data.status !== 'error') {{ 
                            setTimeout(checkStatus, 3000); 
                        }}
                    }} catch (err) {{
                        console.error("Polling error:", err);
                    }}
                }}

                // Start polling only if not already complete
                if ("{initial_data.get('status')}" !== "complete") {{
                    checkStatus();
                }}
            </script>
        </body>
    </html>
    """

@web_app.get("/video/{job_id}")
async def stream_video(job_id: str):
    jobs_vol.reload()
    path = f"{JOBS_DIR}/render_{job_id}.mp4"
    if not os.path.exists(path): raise HTTPException(404)
    return FileResponse(path, media_type="video/mp4")

@app.function(image=image, volumes={"/mnt/assets": assets_vol, "/mnt/jobs": jobs_vol})
@modal.asgi_app()
def fastapi_app(): return web_app