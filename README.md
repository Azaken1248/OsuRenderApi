# OsuRender

Comprehensive instructions to set up and run this repository locally. Includes virtual environment setup for Linux and Windows, Python dependencies, Danser Go download link, `ecosystem.config.js`/PM2 setup, and osu! API configuration.

## Project Overview

This project provides an API/service to render osu! replays using Danser (danser-go) and related tooling. The repository root contains `app.py`, a `requirements.txt`, an `ecosystem.config.js` (process manager configuration), and folders for `uploads`, `downloads`, and `jobs`.

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

