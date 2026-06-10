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
    Closely follows the proven legacy_modal_app.py pattern.
    """
    import subprocess
    import shutil
    import tempfile
    import time
    import boto3
    from botocore.client import Config

    SONGS_DIR = "/mnt/osu_data/Songs"
    SKINS_DIR = "/mnt/osu_data/Skins"
    DANSER_BIN = "/usr/local/bin/danser/danser-cli"

    endpoint = os.environ.get("S3_ENDPOINT")
    access_key = os.environ.get("S3_ACCESS_KEY")
    secret_key = os.environ.get("S3_SECRET_KEY")

    log_lines = [f"=== GPU Render Task Started: {time.ctime()} ===\n"]

    def log(msg: str):
        log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

    s3 = None
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4")
        )

        # --- Setup osu! directory structure (exactly like legacy) ---
        log("Setting up osu! directory structure...")
        os.makedirs(SONGS_DIR, exist_ok=True)
        os.makedirs(SKINS_DIR, exist_ok=True)
        os.makedirs("/root/.osu", exist_ok=True)
        
        # Symlink Songs/Skins into where danser looks for them
        if os.path.exists("/root/.osu/Songs") and not os.path.islink("/root/.osu/Songs"):
            shutil.rmtree("/root/.osu/Songs")
        if not os.path.exists("/root/.osu/Songs"):
            os.symlink(SONGS_DIR, "/root/.osu/Songs")
            
        if os.path.exists("/root/.osu/Skins") and not os.path.islink("/root/.osu/Skins"):
            shutil.rmtree("/root/.osu/Skins")
        if not os.path.exists("/root/.osu/Skins"):
            os.symlink(SKINS_DIR, "/root/.osu/Skins")

        with tempfile.TemporaryDirectory() as tmpdir:
            # --- 1. Download replay from R2 ---
            osr_path = os.path.join(tmpdir, "replay.osr")
            log(f"Downloading replay: {replay_key}")
            s3.download_file(bucket_name, replay_key, osr_path)
            log(f"Replay downloaded: {os.path.getsize(osr_path)} bytes")

            # --- 2. Download beatmap .osz if needed ---
            osz_path = os.path.join(SONGS_DIR, f"{set_id}.osz")
            if not os.path.exists(osz_path):
                log(f"Downloading beatmap set {set_id}...")
                import httpx
                mirrors = [
                    f"https://api.nerinyan.moe/d/{set_id}",
                    f"https://osu.direct/api/d/{set_id}",
                    f"https://catboy.best/d/{set_id}",
                ]
                downloaded = False
                with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                    for url in mirrors:
                        try:
                            log(f"  Trying: {url}")
                            dl = client.get(url)
                            if dl.status_code == 200 and len(dl.content) > 100:
                                with open(osz_path, "wb") as f:
                                    f.write(dl.content)
                                log(f"  Downloaded {len(dl.content)} bytes from {url}")
                                downloaded = True
                                assets_vol.commit()
                                break
                            else:
                                log(f"  Failed: status {dl.status_code}, size {len(dl.content)}")
                        except Exception as e:
                            log(f"  Error: {e}")
                            continue
                if not downloaded:
                    return _upload_log_and_fail(s3, bucket_name, job_id, log_lines,
                                                "Failed to download beatmap from all mirrors.")
            else:
                log(f"Beatmap already cached: {osz_path}")

            # --- 3. Run danser ---
            log("Starting danser render...")
            env = os.environ.copy()
            env.update({
                "DISPLAY": ":99",
                "NVIDIA_DRIVER_CAPABILITIES": "all",
                "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                "__NV_PRIME_RENDER_OFFLOAD": "1"
            })

            # Output goes into danser's own videos directory
            cmd = [
                "xvfb-run", "-a", "-s",
                "-screen 0 1920x1080x24 +extension GLX +render -noreset",
                DANSER_BIN,
                f"-replay={osr_path}",
                f"-skin={skin}",
                f"-sPatch={patch}",
                f"-out={tmpdir}/{target_name}",
                "-record"
            ]
            log(f"Command: {' '.join(cmd)}")

            danser_log_path = os.path.join(tmpdir, "danser.log")
            with open(danser_log_path, "w") as danser_log:
                proc = subprocess.run(
                    cmd, env=env,
                    stdout=danser_log, stderr=subprocess.STDOUT,
                    timeout=600
                )
            
            # Read danser output
            with open(danser_log_path, "r") as f:
                danser_output = f.read()
            log(f"Danser exit code: {proc.returncode}")
            log(f"Danser output ({len(danser_output)} chars):\n{danser_output[-2000:]}")

            if "Beatmap not found" in danser_output:
                return _upload_log_and_fail(s3, bucket_name, job_id, log_lines,
                                            "Beatmap not found! The replay requires a beatmap that is unranked or not available on the osu! API.")

            if proc.returncode != 0:
                return _upload_log_and_fail(s3, bucket_name, job_id, log_lines,
                                            f"Danser failed with exit code {proc.returncode}")

            # --- 4. Find video output ---
            # danser outputs to various locations, check them all (legacy pattern)
            danser_dir = os.path.dirname(DANSER_BIN)
            search_paths = [
                os.path.join(tmpdir, f"{target_name}.mp4"),
                os.path.join(tmpdir, "videos", f"{target_name}.mp4"),
                os.path.join(danser_dir, "videos", f"{target_name}.mp4"),
                f"/usr/local/bin/danser/videos/{target_name}.mp4",
                os.path.join(tmpdir, f"{target_name}.mp4.mp4"),
            ]
            
            video_path = None
            log("Searching for output video...")
            for p in search_paths:
                log(f"  Checking: {p} -> exists={os.path.exists(p)}")
                if os.path.exists(p):
                    video_path = p
                    break

            # Also list danser directory contents for debugging
            for search_dir in [tmpdir, os.path.join(danser_dir, "videos"), danser_dir]:
                if os.path.exists(search_dir):
                    try:
                        contents = os.listdir(search_dir)
                        log(f"  Contents of {search_dir}: {contents}")
                    except:
                        pass

            if not video_path:
                return _upload_log_and_fail(s3, bucket_name, job_id, log_lines,
                                            "Output video not found in any expected location.")

            log(f"Found video: {video_path} ({os.path.getsize(video_path)} bytes)")

            # --- 5. Generate thumbnail ---
            thumb_path = os.path.join(tmpdir, "thumb.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "00:00:15", "-i", video_path,
                 "-vframes", "1", "-q:v", "2", thumb_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30
            )

            # --- 6. Upload results to R2 ---
            video_key = f"videos/{job_id}.mp4"
            thumb_key = f"thumbnails/{job_id}.jpg"
            log_key = f"logs/{job_id}.log"

            log(f"Uploading video to {video_key}...")
            s3.upload_file(video_path, bucket_name, video_key,
                           ExtraArgs={"ContentType": "video/mp4"})
            
            if os.path.exists(thumb_path):
                log(f"Uploading thumbnail to {thumb_key}...")
                s3.upload_file(thumb_path, bucket_name, thumb_key,
                               ExtraArgs={"ContentType": "image/jpeg"})

            # Upload full log
            full_log = "".join(log_lines)
            import io
            s3.upload_fileobj(
                io.BytesIO(full_log.encode()),
                bucket_name, log_key,
                ExtraArgs={"ContentType": "text/plain"}
            )

            log("Done!")
            return {
                "success": True,
                "video_key": video_key,
                "thumb_key": thumb_key,
                "log_key": log_key
            }

    except Exception as e:
        try:
            _upload_log_and_fail(s3, bucket_name, job_id, log_lines, str(e))
        except:
            pass
        return {"success": False, "error": str(e)}


def _upload_log_and_fail(s3, bucket_name: str, job_id: str, log_lines: list, error: str) -> dict:
    """Upload the log to R2 even on failure, so we can debug."""
    import io
    log_lines.append(f"FATAL ERROR: {error}\n")
    log_key = f"logs/{job_id}.log"
    try:
        if s3 is not None:
            full_log = "".join(log_lines)
            s3.upload_fileobj(
                io.BytesIO(full_log.encode()),
                bucket_name, log_key,
                ExtraArgs={"ContentType": "text/plain"}
            )
    except:
        pass
    return {"success": False, "error": error, "log_key": log_key}
