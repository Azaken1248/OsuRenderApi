import os
import modal

image = (
    modal.Image.debian_slim()
    .apt_install(
        "wget", "unzip", "ffmpeg", "xvfb", "libnss3", "libgl1-mesa-glx", 
        "libgl1-mesa-dri", "libgbm1", "libgtk-3-0", "libasound2",
        "libxrender1", "libxtst6", "libxi6", "libxrandr2", "libxcursor1", "libxinerama1"
    )
    .pip_install_from_requirements("requirements.txt")
    .run_commands(
        "wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip",
        "unzip danser-0.11.0-linux.zip -d /usr/local/bin/danser",
        "chmod +x /usr/local/bin/danser/danser-cli"
    )
    .env({
        "DANSER_BIN": "/usr/local/bin/danser/danser-cli",
        "SONGS_DIR": "/mnt/osu_data/Songs"
    })
)

app = modal.App("osurender-gpu-worker")

assets_vol = modal.Volume.from_name("osu-assets", create_if_missing=True)

@app.function(
    image=image, 
    gpu="T4",
    volumes={"/mnt/osu_data": assets_vol},
    timeout=660,
    secrets=[modal.Secret.from_name("osurender-secrets")]
)
def gpu_render_task(job_id: str, osr_path: str, skin: str, patch: str, target_name: str, resolution: str) -> dict:
    import asyncio
    import os
    from src.workers.modal_gpu import run_danser_on_gpu
    
    return asyncio.run(run_danser_on_gpu(
        job_id=job_id,
        osr_path=osr_path,
        skin=skin,
        patch=patch,
        target_name=target_name,
        resolution=resolution
    ))
