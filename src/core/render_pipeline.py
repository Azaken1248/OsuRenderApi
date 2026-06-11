import os
import shutil
import tempfile
import time
import asyncio
import re

async def _upload_log_and_fail(s3, bucket_name: str, job_id: str, log_path: str, error: str) -> dict:
    """Upload the log to R2 even on failure, so we can debug."""
    try:
        with open(log_path, "a") as f:
            f.write(f"\nFATAL ERROR: {error}\n")
    except:
        pass
        
    log_key = f"logs/{job_id}.log"
    try:
        if s3 is not None and os.path.exists(log_path):
            await s3.upload_file(log_path, bucket_name, log_key, ExtraArgs={"ContentType": "text/plain"})
    except:
        pass
    return {"success": False, "error": error, "log_key": log_key}

async def execute_render_pipeline(
    job_id: str,
    set_id: str,
    replay_key: str,
    skin: str,
    patch: str,
    target_name: str,
    bucket_name: str,
    songs_dir: str,
    skins_dir: str,
    danser_bin: str,
    s3_endpoint: str,
    s3_access_key: str,
    s3_secret_key: str,
    assets_commit_fn=None
) -> dict:
    import aioboto3
    from botocore.client import Config

    shared_log_path = f"/tmp/osurender_{job_id}.log"
    with open(shared_log_path, "w") as f:
        f.write(f"=== GPU Render Task Started: {time.ctime()} ===\n")

    def log(msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        print(line, end="")
        with open(shared_log_path, "a") as f:
            f.write(line)

    session = aioboto3.Session()
    
    try:
        async with session.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
            config=Config(signature_version="s3v4", s3={'addressing_style': 'path'})
        ) as s3:

            log("Setting up osu! directory structure...")
            os.makedirs(songs_dir, exist_ok=True)
            os.makedirs(skins_dir, exist_ok=True)
            os.makedirs(os.path.expanduser("~/.osu"), exist_ok=True)
            
            osu_songs = os.path.expanduser("~/.osu/Songs")
            if os.path.exists(osu_songs) and not os.path.islink(osu_songs):
                shutil.rmtree(osu_songs)
            if not os.path.exists(osu_songs):
                os.symlink(songs_dir, osu_songs)
                
            osu_skins = os.path.expanduser("~/.osu/Skins")
            if os.path.exists(osu_skins) and not os.path.islink(osu_skins):
                shutil.rmtree(osu_skins)
            if not os.path.exists(osu_skins):
                os.symlink(skins_dir, osu_skins)

            with tempfile.TemporaryDirectory() as tmpdir:
                osr_path = os.path.join(tmpdir, "replay.osr")
                log(f"Downloading replay: {replay_key}")
                await s3.download_file(bucket_name, replay_key, osr_path)
                log(f"Replay downloaded: {os.path.getsize(osr_path)} bytes")

                osz_path = os.path.join(songs_dir, f"{set_id}.osz")
                beatmap_s3_key = f"beatmaps/{set_id}.osz"

                if not os.path.exists(osz_path):
                    try:
                        log(f"Checking S3 cache for beatmap {set_id}...")
                        await s3.head_object(Bucket=bucket_name, Key=beatmap_s3_key)
                        log("Found in S3! Downloading...")
                        await s3.download_file(bucket_name, beatmap_s3_key, osz_path)
                        if assets_commit_fn: assets_commit_fn()
                    except Exception:
                        log(f"Downloading beatmap set {set_id} from mirrors...")
                        import httpx
                        mirrors = [
                            f"https://api.nerinyan.moe/d/{set_id}",
                            f"https://osu.direct/api/d/{set_id}",
                            f"https://catboy.best/d/{set_id}",
                        ]
                        downloaded = False
                        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                            for url in mirrors:
                                try:
                                    log(f"  Trying: {url}")
                                    dl = await client.get(url)
                                    if dl.status_code == 200 and len(dl.content) > 100:
                                        with open(osz_path, "wb") as f:
                                            f.write(dl.content)
                                        log(f"  Downloaded {len(dl.content)} bytes from {url}")
                                        downloaded = True
                                        
                                        try:
                                            log("  Caching beatmap to S3...")
                                            await s3.upload_file(osz_path, bucket_name, beatmap_s3_key)
                                        except Exception as s3_err:
                                            log(f"  Failed to cache to S3: {s3_err}")
                                            
                                        if assets_commit_fn: assets_commit_fn()
                                        break
                                    else:
                                        log(f"  Failed: status {dl.status_code}, size {len(dl.content)}")
                                except Exception as e:
                                    log(f"  Error: {e}")
                                    continue
                        if not downloaded:
                            return await _upload_log_and_fail(s3, bucket_name, job_id, shared_log_path, "Failed to download beatmap from all mirrors.")
                else:
                    log(f"Beatmap already cached locally: {osz_path}")

                if skin and skin.lower() != "default":
                    skin_folder = os.path.join(skins_dir, skin)
                    if not os.path.exists(os.path.join(skin_folder, "skin.ini")):
                        log(f"Downloading skin '{skin}' from R2...")
                        skin_tmp_path = os.path.join(tmpdir, "skin.osk")
                        try:
                            await s3.download_file(bucket_name, f"skins/{skin}.osk", skin_tmp_path)
                            log("  Skin downloaded, extracting...")
                            import zipfile
                            os.makedirs(skin_folder, exist_ok=True)
                            with zipfile.ZipFile(skin_tmp_path, 'r') as z:
                                skin_folder_abs = os.path.abspath(skin_folder)
                                for member in z.namelist():
                                    member_path = os.path.abspath(os.path.join(skin_folder_abs, member))
                                    if os.path.commonpath([skin_folder_abs, member_path]) != skin_folder_abs:
                                        raise Exception(f"Attempted Zip Slip: {member}")
                                    z.extract(member, skin_folder)
                            log("  Skin extracted successfully.")
                            if assets_commit_fn: assets_commit_fn()
                        except Exception as e:
                            log(f"  Failed to download/extract skin: {e}")
                            skin = "Default"
                    else:
                        log(f"Skin already cached: {skin}")

                log("Starting danser render...")
                env = os.environ.copy()
                env.update({
                    "DISPLAY": ":99",
                    "NVIDIA_DRIVER_CAPABILITIES": "all",
                    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                    "__NV_PRIME_RENDER_OFFLOAD": "1"
                })

                cmd = [
                    "xvfb-run", "-a", "-s",
                    "-screen 0 1920x1080x24 +extension GLX +render -noreset",
                    danser_bin,
                    f"-replay={osr_path}",
                    f"-skin={skin}",
                    f"-sPatch={patch}",
                    f"-out={target_name}",
                    "-record"
                ]
                log(f"Command: {' '.join(cmd)}")

                stop_event = asyncio.Event()
                
                async def upload_log_worker():
                    while not stop_event.is_set():
                        if os.path.exists(shared_log_path):
                            try:
                                await s3.upload_file(shared_log_path, bucket_name, f"logs/{job_id}.log", ExtraArgs={"ContentType": "text/plain"})
                            except: pass
                        try:
                            await asyncio.wait_for(stop_event.wait(), timeout=3.0)
                        except asyncio.TimeoutError:
                            pass
                
                log_task = asyncio.create_task(upload_log_worker())

                try:
                    with open(shared_log_path, "a") as danser_log:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd, env=env, stdout=danser_log, stderr=asyncio.subprocess.STDOUT
                        )
                        try:
                            await asyncio.wait_for(proc.wait(), timeout=600.0)
                        except asyncio.TimeoutError:
                            proc.kill()
                            await proc.wait()
                finally:
                    stop_event.set()
                    await asyncio.wait_for(log_task, timeout=2.0)
                
                with open(shared_log_path, "r") as f: danser_output = f.read()
                log(f"Danser exit code: {proc.returncode}")
                log(f"Danser output ({len(danser_output)} chars):\n{danser_output[-2000:]}")

                pp_gained = 0.0
                try:
                    match = re.search(r'\|\s*1\s*\|(?:[^|]*\|){11}\s*([\d.]+)\s*\|', danser_output)
                    if match:
                        pp_gained = float(match.group(1))
                        log(f"Parsed PP: {pp_gained}")
                except Exception as e:
                    log(f"Failed to parse PP from output: {e}")

                if "Beatmap not found" in danser_output:
                    return await _upload_log_and_fail(s3, bucket_name, job_id, shared_log_path, "Beatmap not found! The replay requires a beatmap that is unranked or not available on the osu! API.")
                if proc.returncode != 0:
                    return await _upload_log_and_fail(s3, bucket_name, job_id, shared_log_path, f"Danser failed with exit code {proc.returncode}")

                danser_dir = os.path.dirname(danser_bin)
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

                if not video_path:
                    return await _upload_log_and_fail(s3, bucket_name, job_id, shared_log_path, "Output video not found in any expected location.")

                log(f"Found video: {video_path} ({os.path.getsize(video_path)} bytes)")

                thumb_path = os.path.join(tmpdir, "thumb.jpg")
                thumb_proc = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-y", "-ss", "00:00:15", "-i", video_path, "-vframes", "1", "-q:v", "2", thumb_path,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                )
                try:
                    await asyncio.wait_for(thumb_proc.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    thumb_proc.kill()
                    await thumb_proc.wait()

                video_key = f"videos/{job_id}.mp4"
                thumb_key = f"thumbnails/{job_id}.jpg"
                log_key = f"logs/{job_id}.log"

                log(f"Uploading video to {video_key}...")
                await s3.upload_file(video_path, bucket_name, video_key, ExtraArgs={"ContentType": "video/mp4"})
                
                if os.path.exists(thumb_path):
                    log(f"Uploading thumbnail to {thumb_key}...")
                    await s3.upload_file(thumb_path, bucket_name, thumb_key, ExtraArgs={"ContentType": "image/jpeg"})

                if os.path.exists(shared_log_path):
                    await s3.upload_file(shared_log_path, bucket_name, log_key, ExtraArgs={"ContentType": "text/plain"})

                log("Done!")
                return {
                    "success": True,
                    "video_key": video_key,
                    "thumb_key": thumb_key,
                    "log_key": log_key,
                    "pp": pp_gained
                }

    except Exception as e:
        try:
            # We don't have the s3 context here if it failed outside the block, 
            # but log_path might exist.
            pass
        except: pass
        return {"success": False, "error": str(e)}
