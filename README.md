# OsuRender

High-quality osu! replay rendering service powered by Danser-Go. Available in two deployment modes:

- **`app.py`** - Local deployment with CPU/GPU rendering
- **`modal_app.py`** - Cloud deployment on Modal with automatic GPU scaling

## Features

- Render osu! replays to high-quality MP4 videos
- Customizable skins and visual settings
- Real-time progress tracking
- RESTful API with interactive documentation
- Cloud deployment option with GPU acceleration
- Built-in video player for cloud renders

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Deployment (app.py)](#local-deployment-apppy)
3. [Cloud Deployment (modal_app.py)](#cloud-deployment-modal_apppy)
4. [API Documentation](#api-documentation)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

### For Both Deployments

- Python 3.10+ (3.11 recommended)
- git
- An osu! API key - get one at https://osu.ppy.sh/p/api

### Local Deployment Only

- Danser-Go binary (https://github.com/Wieku/danser-go/releases)
- ffmpeg
- xvfb (Linux) or equivalent display server

### Cloud Deployment Only

- Modal account (https://modal.com)
- Modal CLI installed: `pip install modal`

## Local Deployment (app.py)

### 1. Download and Setup Danser-Go

Download the latest Danser-Go binary from https://github.com/Wieku/danser-go/releases

**Linux:**
```bash
mkdir -p /home/aza/danser
cd /home/aza/danser
wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip
unzip danser-0.11.0-linux.zip
chmod +x danser-cli
```

**Windows:**
Download the Windows release, extract to `C:\danser`, and ensure `danser.exe` is accessible.

### 2. Install Python Dependencies

**Linux/macOS:**
```bash
cd /home/aza/OsuRender
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
cd C:\path\to\OsuRender
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (CMD):**
```cmd
cd C:\path\to\OsuRender
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Set Environment Variables

**Linux/macOS:**
```bash
export OSU_API_KEY="your_api_key_here"
export DANSER_PATH="/home/aza/danser/danser-cli"
```

**Windows (PowerShell):**
```powershell
$env:OSU_API_KEY = "your_api_key_here"
$env:DANSER_PATH = "C:\danser\danser.exe"
```

### 4. Run the Application

**Direct execution:**
```bash
python app.py
```

**Or with Uvicorn:**
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Access the Application

- **API Root:** http://localhost:8000/
- **Documentation:** http://localhost:8000/docs
- **Swagger UI:** http://localhost:8000/docs (FastAPI auto-generated)

### Production Deployment with PM2 (Optional)

Install PM2:
```bash
npm install -g pm2
```

Configure `ecosystem.config.js`:
```js
module.exports = {
  apps: [
    {
      name: 'osurender',
      script: 'app.py',
      interpreter: '/home/aza/OsuRender/venv/bin/python',
      env: {
        OSU_API_KEY: 'your_api_key_here',
        DANSER_PATH: '/home/aza/danser/danser-cli',
        FLASK_ENV: 'production'
      }
    }
  ]
}
```

Start with PM2:
```bash
pm2 start ecosystem.config.js
pm2 status
pm2 logs osurender
```

Stop and remove:
```bash
pm2 stop osurender
pm2 delete osurender
```

## Cloud Deployment (modal_app.py)

### 1. Install Modal

```bash
pip install modal
```

### 2. Authenticate with Modal

```bash
modal setup
```

Follow the prompts to authenticate with your Modal account.

### 3. Set Up Modal Secret

Create a secret named `osu-api` in the Modal dashboard with your API key:

```bash
modal secret create osu-api OSU_API_KEY="your_api_key_here"
```

Or via the Modal web dashboard: https://modal.com/secrets

### 4. Deploy to Modal

**Development (live reload):**
```bash
modal serve modal_app.py
```

**Production deployment:**
```bash
modal deploy modal_app.py
```

### 5. Access Your Cloud App

After deployment, Modal will provide a URL like:
- `https://your-username--aza-render-cloud-fastapi-app.modal.run`

Visit this URL to access:
- **Home:** `/`
- **Documentation:** `/docs`
- **Interactive player:** `/view/{job_id}`

## API Documentation

Both deployments expose a `/docs` endpoint with beautiful osu!-themed documentation.

### Local API (app.py)

**Base URL:** `http://localhost:8000`

**Key Endpoints:**
- `GET /` - API status
- `GET /docs` - Interactive documentation
- `GET /skins` - List available skins
- `POST /render` - Submit replay for rendering
- `GET /jobs` - Get all job statuses
- `GET /logs/{job_id}` - Get job details and logs
- `GET /download/{job_id}` - Download rendered video

**Example render request:**
```bash
curl -X POST http://localhost:8000/render \
  -F "replay=@myreplay.osr" \
  -F "skin=Default" \
  -F "bg_dim=0.85"
```

### Cloud API (modal_app.py)

**Base URL:** `https://your-modal-app.modal.run`

**Key Endpoints:**
- `GET /` - Landing page
- `GET /docs` - Interactive documentation
- `POST /render` - Submit replay (with quality options)
- `GET /view/{job_id}` - Interactive web player
- `GET /status/{job_id}` - JSON status
- `GET /jobs` - List all jobs
- `GET /video/{job_id}` - Download/stream video

**Example render request:**
```bash
curl -X POST https://your-modal-app.modal.run/render \
  -F "replay=@myreplay.osr" \
  -F "skin=Default" \
  -F "quality=ultra" \
  -F "motion_blur=true" \
  -F "bg_dim=0.85"
```

**Quality options:**
- `standard` - 1080p (1920x1080)
- `ultra` - 4K (3840x2160)

## Configuration

### Danser Settings

Edit `/home/aza/danser/settings/default.json` to configure:
- Output directory
- Recording quality
- Video codec settings
- Playfield options

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

### App Configuration (app.py)

Edit paths in [app.py](app.py):
```python
DANSER_DIR = "/home/aza/danser"
DANSER_BIN = "/home/aza/danser/danser-cli"
SONGS_DIR = "/home/aza/danser/osu_data/Songs"
SKINS_DIR = "/home/aza/danser/osu_data/Skins"
DOWNLOADS_DIR = "/home/aza/OsuRender/downloads"
JOBS_DIR = "/home/aza/OsuRender/jobs"
```

### Cloud Configuration (modal_app.py)

Key settings in [modal_app.py](modal_app.py):
```python
# GPU selection (in @app.function decorator)
gpu="T4"  # Options: T4, A10G, A100

# Container limits
timeout=1200  # 20 minutes
max_containers=2  # Max concurrent renders

# Volume names
assets_vol = modal.Volume.from_name("osu-assets")
jobs_vol = modal.Volume.from_name("osu-jobs")
```

## Project Structure

```
OsuRender/
├── app.py              # Local FastAPI application
├── modal_app.py        # Cloud Modal application
├── requirements.txt    # Python dependencies
├── ecosystem.config.js # PM2 configuration (optional)
├── README.md          # This file
├── downloads/         # Rendered videos (local)
├── uploads/           # Upload staging
└── jobs/              # Job metadata and replay files
```

## Dependencies

From `requirements.txt`:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - HTTP client for API calls
- `osrparse` - osu! replay parser
- `python-multipart` - Form data handling

Cloud-only:
- `modal` - Serverless deployment platform

## Workflow Examples

### Local Workflow

1. Start the server: `python app.py`
2. Submit a replay: `POST /render`
3. Get job ID: `{"job_id": "abc123"}`
4. Poll status: `GET /logs/abc123`
5. Download: `GET /download/abc123`

### Cloud Workflow

1. Deploy: `modal deploy modal_app.py`
2. Submit replay: `POST /render`
3. Open view URL in browser: `/view/abc123`
4. Watch live progress
5. Video auto-plays when complete
6. Click download button

## Troubleshooting

### Local Deployment

**Danser not found:**
- Verify `DANSER_PATH` points to the correct binary
- Check execute permissions: `chmod +x /path/to/danser-cli`

**xvfb errors (Linux):**
```bash
sudo apt-get install xvfb
```

**No output video:**
- Check Danser logs in jobs folder
- Verify `Recording.OutputDir` in Danser settings
- Ensure sufficient disk space

**API key errors:**
- Confirm `OSU_API_KEY` is set correctly
- Test key at https://osu.ppy.sh/api/get_user

### Cloud Deployment

**Modal authentication:**
```bash
modal token new
```

**Secret not found:**
```bash
modal secret list
modal secret create osu-api OSU_API_KEY="key"
```

**GPU timeout:**
- Increase timeout in `@app.function(timeout=...)`
- Check render complexity

**Volume issues:**
```bash
modal volume list
modal volume delete osu-jobs  # If needed
```

## Performance Tips

### Local
- Use GPU encoding (`h264_nvenc`) if available
- Adjust worker count based on CPU cores
- Use SSD for downloads folder

### Cloud
- Use `quality="standard"` for faster renders
- T4 GPU is cost-effective for most replays
- A100 for ultra-high quality or complex maps

## Support and Links

- **Danser-Go:** https://github.com/Wieku/danser-go
- **osu! API:** https://github.com/ppy/osu-api/wiki
- **Modal Docs:** https://modal.com/docs
- **FastAPI Docs:** https://fastapi.tiangolo.com

## License

This project is provided as-is for educational and personal use. Please respect osu! community guidelines and don't abuse rendering services.

---

## Quick Reference

### Start Local Server
```bash
# Development
python app.py

# Production with Uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000

# With PM2
pm2 start ecosystem.config.js
```

### Deploy to Cloud
```bash
# Development (hot reload)
modal serve modal_app.py

# Production
modal deploy modal_app.py
```

### Common Commands
```bash
# Check job status
curl http://localhost:8000/logs/{job_id}

# List all jobs
curl http://localhost:8000/jobs

# List available skins (local only)
curl http://localhost:8000/skins

# Download video
curl http://localhost:8000/download/{job_id} -o render.mp4
```

Enjoy rendering!

## Prerequisites

- Python 3.10+ (3.11 recommended)
- pip
- git
- Node.js + npm (for PM2, optional)
- Danser Go (danser-go) binary — see download link below
- An osu! API key (see instructions below)

## Danser Go (danser-go)

Download the latest prebuilt binaries from the official repository releases:

- Releases: https://github.com/Wieku/danser-go/releases

Place the danser binary in a location accessible to this app. Two common options:

- Put the binary under `/home/aza/danser` (or any chosen folder) and ensure it is executable.
- Or keep it anywhere and set the `DANSER_PATH` environment variable to the full path of the danser binary.

Example (Linux):

```bash
# move binary to /home/aza/danser and make executable
mkdir -p /home/aza/danser
mv danser-go_linux_amd64 /home/aza/danser/danser
chmod +x /home/aza/danser/danser
```

The repository includes a Danser configuration file example at `/home/aza/danser/settings/default.json`. You can edit that file to configure recording output directories and other Danser options. For example, adjust `Recording.OutputDir` to match the `downloads` folder in this repo.

## Getting an osu! API Key

To use osu! services you will likely need an API key. For the classic osu! v1 API, request a key here:

- https://osu.ppy.sh/p/api

Follow the instructions on that page and note your API key value. This key will be used by the application to query osu! endpoints.

## Environment variables

This app accepts configuration via environment variables. Common variables to set:

- `OSU_API_KEY` — your osu! API key
- `DANSER_PATH` — full path to the danser binary (optional if in PATH)
- `FLASK_ENV` or `ENV` — optional, e.g., `development`/`production`

You can export these directly or wire them into `ecosystem.config.js` for PM2-managed deployment.

Example (Linux / bash):

```bash
export OSU_API_KEY="your_api_key_here"
export DANSER_PATH="/home/aza/danser/danser"
```

Example (Windows PowerShell):

```powershell
$env:OSU_API_KEY = "your_api_key_here"
$env:DANSER_PATH = "C:\path\to\danser.exe"
```

## ecosystem.config.js and PM2 (optional)

If you want to run the app as a background service, use PM2. Install PM2 globally:

```bash
npm install -g pm2
```

A simple `ecosystem.config.js` may look like this (adjust paths and env variables):

```js
module.exports = {
  apps: [
    {
      name: 'osurender',
      script: 'app.py',
      interpreter: '/usr/bin/python3', // or full path to your venv python
      env: {
        OSU_API_KEY: process.env.OSU_API_KEY || 'your_api_key_here',
        DANSER_PATH: process.env.DANSER_PATH || '/home/aza/danser/danser',
        FLASK_ENV: 'production'
      }
    }
  ]
}
```

Start with PM2:

```bash
pm2 start ecosystem.config.js
pm2 status
pm2 logs osurender
```

To stop and remove:

```bash
pm2 stop osurender
pm2 delete osurender
```

If you're using a Python virtual environment, change the `interpreter` path above to the venv python binary (e.g. `/home/aza/OsuRender/venv/bin/python`).

## Python virtual environment (venv)

Follow these steps to create and activate a virtual environment, then install dependencies from `requirements.txt`.

Linux / macOS (bash):

```bash
cd /home/aza/OsuRender
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd C:\path\to\OsuRender
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows CMD:

```cmd
cd C:\path\to\OsuRender
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Requirements

This project uses `requirements.txt` for Python dependencies. Current contents of `requirements.txt`:

```
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

Install them with:

```bash
pip install -r requirements.txt
```

## Running the application locally

With venv active:

```bash
python app.py
```

Or run via Uvicorn (if the app exposes an ASGI entrypoint):

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

(Adjust the module/path depending on how `app.py` defines the FastAPI/Flask app.)

## Files and folders of interest

- `app.py` — main Python application entrypoint.
- `requirements.txt` — Python dependencies.
- `ecosystem.config.js` — PM2 config for production usage.
- `downloads/` — default output directory for rendered videos (see Danser config).
- `uploads/` — upload point for beatmaps/replays.
- `jobs/` — rendered job artifacts.
- `/home/aza/danser/settings/default.json` — example Danser settings (already included in your attachments).

## Example workflow

1. Install Python deps in venv and export `OSU_API_KEY` and `DANSER_PATH`.
2. Ensure Danser Go binary is present and settings point `Recording.OutputDir` to `downloads/`.
3. Start the app locally (`python app.py`) or with PM2 (`pm2 start ecosystem.config.js`).
4. Use the web/API endpoints to submit render jobs (check `app.py` routes).

## Troubleshooting

- If Danser fails to run, verify `DANSER_PATH` is correct and the binary has execute permission.
- Check `downloads/` permissions — the service must be able to write files there.
- If requests to osu! API fail, confirm `OSU_API_KEY` is valid and not rate-limited.
- Use `pm2 logs` or the app console to inspect error traces.

