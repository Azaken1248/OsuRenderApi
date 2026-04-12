# OsuRender

High-quality osu! replay rendering service powered by Danser-Go, with two deployment modes:

- `app.py`: local FastAPI deployment (CPU/GPU depending on host setup)
- `modal_app.py`: cloud deployment on Modal with GPU workers

## Features

- Render `.osr` replays to MP4 video
- Select and upload custom skins (`.osk`)
- Track render progress and logs
- Replay job history endpoints
- Cloud deployment with auto-scaling GPU containers
- Built-in cloud viewer page for finished renders

## Important Notes

- Local mode should be run with Uvicorn (`uvicorn app:app ...`).
- In local mode, `GET /docs` is a custom HTML docs page, not the default Swagger UI.
- In cloud mode, the video endpoint is `GET /video/{job_id}.mp4` (includes `.mp4` in the route).
- Current local code uses hardcoded path constants in `app.py` (`DANSER_BIN`, `SONGS_DIR`, etc.). Older docs that reference only `DANSER_PATH` are outdated for this revision.
- Current local uploads are stored in `jobs/` (not a separate `uploads/` directory).

## Prerequisites

### Common

- Python 3.10+ (3.11 recommended)
- pip
- git
- osu! API key (v1): https://osu.ppy.sh/p/api

### Local mode (`app.py`)

- Danser-Go binary: https://github.com/Wieku/danser-go/releases
- `ffmpeg`
- `xvfb` on Linux (or equivalent virtual display)

### Cloud mode (`modal_app.py`)

- Modal account: https://modal.com
- Modal CLI (`pip install modal`)

## Local Deployment (`app.py`)

### 1. Install Python dependencies

Linux/macOS:

```bash
cd /path/to/OsuRenderApi
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd C:\path\to\OsuRenderApi
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows CMD:

```cmd
cd C:\path\to\OsuRenderApi
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Install Danser-Go

Download a release from:

- https://github.com/Wieku/danser-go/releases

Example Linux setup:

```bash
mkdir -p /home/aza/danser
cd /home/aza/danser
wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip
unzip danser-0.11.0-linux.zip
chmod +x danser-cli
```

Windows:

- Download the Windows release.
- Extract it (for example to `C:\danser`).
- Update `DANSER_BIN` in `app.py` to point to the executable path.

### 3. Configure environment and paths

Required environment variable:

- `OSU_API_KEY`

Linux/macOS:

```bash
export OSU_API_KEY="your_api_key_here"
```

Windows PowerShell:

```powershell
$env:OSU_API_KEY = "your_api_key_here"
```

Current local path configuration is in `app.py`:

```python
DANSER_DIR = "/home/aza/danser"
DANSER_BIN = "/home/aza/danser/danser-cli"
SONGS_DIR = "/home/aza/danser/osu_data/Songs"
SKINS_DIR = "/home/aza/danser/osu_data/Skins"
DOWNLOADS_DIR = "/home/aza/OsuRender/downloads"
JOBS_DIR = "/home/aza/OsuRender/jobs"
CONFIG_DIR = "/home/aza/danser/settings/jobs"
```

Adjust these for your environment.

### 4. Run local API

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Access local API

- API root: http://localhost:8000/
- Docs page: http://localhost:8000/docs

## Optional: PM2 (Local)

Install PM2:

```bash
npm install -g pm2
```

Example `ecosystem.config.js`:

```js
module.exports = {
  apps: [
    {
      name: "osurender",
      script: "venv/bin/uvicorn",
      args: "app:app --host 0.0.0.0 --port 8000",
      cwd: "/home/aza/OsuRenderApi",
      env: {
        OSU_API_KEY: "your_api_key_here"
      }
    }
  ]
}
```

Start/inspect logs:

```bash
pm2 start ecosystem.config.js
pm2 status
pm2 logs osurender
```

Stop/remove:

```bash
pm2 stop osurender
pm2 delete osurender
```

## Cloud Deployment (`modal_app.py`)

### 1. Install Modal CLI

```bash
pip install modal
```

### 2. Authenticate

```bash
modal setup
```

### 3. Create secret for osu! API key

The cloud worker expects a secret named `osu-api` containing `OSU_API_KEY`:

```bash
modal secret create osu-api OSU_API_KEY="your_api_key_here"
```

### 4. Deploy

Development (live reload):

```bash
modal serve modal_app.py
```

Production:

```bash
modal deploy modal_app.py
```

### 5. Access cloud app

Modal returns a URL like:

- `https://your-username--aza-render-cloud-fastapi-app.modal.run`

Useful paths:

- `/docs`
- `/view/{job_id}`
- `/video/{job_id}.mp4`

## API Reference

### Local API (`app.py`)

Base URL: `http://localhost:8000`

- `GET /` - API status
- `GET /docs` - custom HTML docs page
- `GET /skins` - list available skins
- `POST /skins/upload` - upload `.osk` skin
- `GET /jobs` - list in-memory job statuses
- `POST /render` - queue replay render
- `GET /logs/{job_id}` - job status + full log (if available)
- `GET /download/{job_id}` - download rendered MP4

Local render request fields (`multipart/form-data`):

- `replay` (file, required)
- `skin` (string, optional, default `Default`)
- `bg_dim` (float, optional, default `0.95`)

### Cloud API (`modal_app.py`)

Base URL: your Modal deployment URL

- `GET /` - landing page
- `GET /docs` - FastAPI interactive docs
- `GET /skins` - list available skins
- `POST /skins/upload` - upload `.osk` skin
- `POST /render` - submit cloud render
- `GET /status/{job_id}` - metadata/status JSON
- `GET /jobs` - list metadata history
- `GET /logs/{job_id}` - renderer logs
- `GET /view/{job_id}` - HTML player/status page
- `GET /video/{job_id}.mp4` - stream/download MP4

Cloud render request fields (`multipart/form-data`):

- `replay` (file, required)
- `skin` (string, default `Default`)
- `bg_dim` (float, default `0.95`, values above `1.0` are interpreted as percentages)
- `quality` (`standard` or `ultra`, default `standard`)
- `motion_blur` (bool, default `true`)
- `storyboard` (bool, default `true`)
- `video` (bool, default `false`)
- `snaking_in` (bool, default `true`)
- `snaking_out` (bool, default `true`)
- `hit_error_meter` (bool, default `true`)
- `key_overlay` (bool, default `true`)

## Example Requests

Local render:

```bash
curl -X POST http://localhost:8000/render \
  -F "replay=@myreplay.osr" \
  -F "skin=Default" \
  -F "bg_dim=0.85"
```

Cloud render:

```bash
curl -X POST https://your-modal-app.modal.run/render \
  -F "replay=@myreplay.osr" \
  -F "skin=Default" \
  -F "quality=ultra" \
  -F "motion_blur=true" \
  -F "storyboard=true" \
  -F "video=false" \
  -F "bg_dim=0.85"
```

## Danser Configuration

Edit Danser settings (example path used by current setup):

- `/home/aza/danser/settings/default.json`

Example:

```json
{
  "Recording": {
    "OutputDir": "/home/aza/OsuRender/downloads",
    "Encoder": "h264_nvenc",
    "EncoderOptions": "-rc vbr -cq 23 -preset p4"
  }
}
```

## Cloud Runtime Configuration

Current `modal_app.py` highlights:

```python
gpu="T4"          # Change to A10G/A100 if needed
timeout=1200       # 20 minutes
max_containers=2   # Concurrent cloud render workers

assets_vol = modal.Volume.from_name("osu-assets", create_if_missing=True)
jobs_vol = modal.Volume.from_name("osu-jobs", create_if_missing=True)
```

## Project Structure (Current Workspace)

```text
OsuRenderApi/
|- app.py
|- modal_app.py
|- README.md
|- requirements.txt
|- downloads/
|- jobs/
|- venv/              (local, optional)
`- __pycache__/       (generated)
```

## Dependencies

Install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

Current pinned dependencies:

```text
annotated-doc==0.0.4
annotated-types==0.7.0
anyio==4.12.1
certifi==2026.1.4
charset-normalizer==3.4.4
click==8.3.1
Deprecated==1.3.1
fastapi==0.128.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.11
limits==5.6.0
osrparse==7.0.1
packaging==25.0
pydantic==2.12.5
pydantic_core==2.41.5
python-multipart==0.0.21
requests==2.32.5
slowapi==0.1.9
starlette==0.50.0
typing-inspection==0.4.2
typing_extensions==4.15.0
urllib3==2.6.3
uvicorn==0.40.0
wrapt==2.0.1
```

Cloud-only dependency:

- `modal` (install separately for cloud deployment)

## Workflow Examples

### Local workflow

1. Start API with Uvicorn.
2. Submit `POST /render`.
3. Track `GET /logs/{job_id}`.
4. Download `GET /download/{job_id}` when complete.

### Cloud workflow

1. Deploy with `modal deploy modal_app.py`.
2. Submit `POST /render`.
3. Poll `GET /status/{job_id}` or open `GET /view/{job_id}`.
4. Watch/download from `GET /video/{job_id}.mp4`.

## Troubleshooting

### Local

- Danser not found: verify `DANSER_BIN` path and executable permissions.
- `xvfb` issues on Linux: install with `sudo apt-get install xvfb`.
- No output video: inspect `jobs/{job_id}.log`, verify Danser `Recording.OutputDir`, and check disk space.
- osu! API failures: confirm `OSU_API_KEY` is set and valid.

### Cloud

- Modal auth issues: run `modal token new` and `modal setup`.
- Missing secret: run `modal secret list` and recreate `osu-api` if needed.
- Timeout during render: increase `timeout` in `@app.function(...)`.
- Volume issues: inspect with `modal volume list`.

## Performance Tips

### Local

- Use GPU encoder (`h264_nvenc`) when available.
- Keep `downloads/` and Danser assets on SSD.
- Limit concurrent workload per host to avoid IO contention.

### Cloud

- Use `quality=standard` for faster jobs.
- `T4` is a good cost/performance default.
- Move to `A10G` or `A100` for heavier maps or higher throughput.

## Support Links

- Danser-Go: https://github.com/Wieku/danser-go
- osu! API docs: https://github.com/ppy/osu-api/wiki
- Modal docs: https://modal.com/docs
- FastAPI docs: https://fastapi.tiangolo.com

## License

Provided as-is for educational and personal use. Please respect osu! community guidelines.
