import os
import modal

image = (
    modal.Image.debian_slim()
    .apt_install(
        "wget", "unzip", "ffmpeg", "xvfb", "libnss3", "libgl1",
        "libgl1-mesa-dri", "libgbm1", "libgtk-3-0", "libasound2",
        "libxrender1", "libxtst6", "libxi6", "libxrandr2", "libxcursor1", "libxinerama1"
    )
    .pip_install("boto3", "httpx")
    .run_commands(
        "wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip",
        "unzip danser-0.11.0-linux.zip -d /usr/local/bin/danser",
        "chmod +x /usr/local/bin/danser/danser-cli"
    )
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
def gpu_render_task(job_id: str, set_id: str, replay_key: str, skin: str, patch: str, target_name: str, bucket_name: str) -> dict:
    """
    Fully self-contained GPU render function.
    All logic is inlined here because this runs on Modal's cloud,
    where the local src/ package does not exist.
    """
    import asyncio
    import os
    import tempfile
    import httpx
    import boto3
    from botocore.client import Config

    endpoint = os.environ.get("S3_ENDPOINT")
    access_key = os.environ.get("S3_ACCESS_KEY")
    secret_key = os.environ.get("S3_SECRET_KEY")

    SONGS_DIR = "/mnt/osu_data/Songs"
    DANSER_BIN = "/usr/local/bin/danser/danser-cli"

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4")
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Download replay from R2
            osr_path = os.path.join(tmpdir, "replay.osr")
            s3.download_file(bucket_name, replay_key, osr_path)

            # 2. Download beatmap if needed
            osz_path = os.path.join(SONGS_DIR, f"{set_id}.osz")
            os.makedirs(SONGS_DIR, exist_ok=True)
            if not os.path.exists(osz_path):
                import httpx as hx
                with hx.Client(follow_redirects=True, timeout=60.0) as client:
                    dl = client.get(f"https://api.nerinyan.moe/d/{set_id}")
                    if dl.status_code == 200:
                        with open(osz_path, "wb") as f:
                            f.write(dl.content)
                    else:
                        return {"success": False, "error": "Failed to download beatmap from mirror."}

            # 3. Run danser
            import subprocess
            env = os.environ.copy()
            env.update({
                "DISPLAY": ":99",
                "NVIDIA_DRIVER_CAPABILITIES": "all",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                "__NV_PRIME_RENDER_OFFLOAD": "1"
            })

            cmd = [
                "xvfb-run", "-a", "-s", "-screen 0 1920x1080x24 +extension GLX +render -noreset",
                DANSER_BIN,
                "-nodbcheck",
                f"-replay={osr_path}",
                f"-skin={skin}",
                f"-sPatch={patch}",
                f"-out={tmpdir}/{target_name}",
                "-record"
            ]

            log_path = os.path.join(tmpdir, "render.log")
            with open(log_path, "w") as log_file:
                proc = subprocess.run(
                    cmd, env=env, cwd=tmpdir,
                    stdout=log_file, stderr=subprocess.STDOUT,
                    timeout=600
                )

            if proc.returncode != 0:
                log_content = ""
                try:
                    with open(log_path) as f:
                        log_content = f.read()[-500:]
                except:
                    pass
                return {"success": False, "error": f"Danser failed (rc={proc.returncode}). Last log: {log_content}"}

            # 4. Find video output
            video_path = os.path.join(tmpdir, f"{target_name}.mp4")
            if not os.path.exists(video_path):
                video_path = os.path.join(tmpdir, "videos", f"{target_name}.mp4")
                if not os.path.exists(video_path):
                    return {"success": False, "error": "Output video not found."}

            # 5. Generate thumbnail
            thumb_path = os.path.join(tmpdir, "thumb.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "00:00:15", "-i", video_path, "-vframes", "1", "-q:v", "2", thumb_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30
            )

            # 6. Upload results to R2
            video_key = f"videos/{job_id}.mp4"
            thumb_key = f"thumbnails/{job_id}.jpg"
            log_key = f"logs/{job_id}.log"

            s3.upload_file(video_path, bucket_name, video_key, ExtraArgs={"ContentType": "video/mp4"})
            if os.path.exists(thumb_path):
                s3.upload_file(thumb_path, bucket_name, thumb_key, ExtraArgs={"ContentType": "image/jpeg"})
            if os.path.exists(log_path):
                s3.upload_file(log_path, bucket_name, log_key, ExtraArgs={"ContentType": "text/plain"})

            # Commit volume so beatmap persists for next render
            assets_vol.commit()

            return {
                "success": True,
                "video_key": video_key,
                "thumb_key": thumb_key,
                "log_key": log_key
            }

    except Exception as e:
        return {"success": False, "error": str(e)}
