import asyncio
import os
import json
import uuid
import httpx
import tempfile
from pathlib import Path

from osrparse import Replay
from sqlalchemy import select
from celery import shared_task

from src.core.celery_app import celery_app
from src.core.storage import storage_client
from src.core.config import get_settings
from src.db.models import Job, JobStatus

settings = get_settings()

DANSER_BIN = os.environ.get("DANSER_BIN", "danser-cli")
SONGS_DIR = os.environ.get("SONGS_DIR", "/tmp/osu_data/Songs")

async def fetch_beatmap_with_backoff(client: httpx.AsyncClient, h: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            r = await client.get(
                "https://osu.ppy.sh/api/get_beatmaps",
                params={"k": settings.osu_api_key, "h": h},
                timeout=30.0
            )
            r.raise_for_status()
            data = r.json()
            if data:
                return data[0]
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)
    return None

from src.db.session import async_session_factory

async def _process_render_job(job_id: str):
    async with async_session_factory() as db:
        result = await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job_result = result.scalar_one_or_none()
        if not job_result:
            return
            
        job: Job = job_result

        try:
            job.status = JobStatus.DOWNLOADING
            await db.commit()

            with tempfile.TemporaryDirectory() as tmpdir:
                osr_path = os.path.join(tmpdir, "replay.osr")
                storage_client.client.fget_object(
                    bucket_name=storage_client.bucket,
                    object_name=job.replay_storage_key,
                    file_path=osr_path
                )

                replay = None
                try:
                    replay = Replay.from_path(osr_path)
                    h = replay.beatmap_hash
                except Exception:
                    h = "unknown"

                async with httpx.AsyncClient() as client:
                    if settings.osu_api_key and h != "unknown" and replay is not None:
                        beatmap_data = await fetch_beatmap_with_backoff(client, h)
                        if not beatmap_data:
                            raise Exception("Beatmap not found on osu! API.")
                        set_id = beatmap_data["beatmapset_id"]
                        b_id = beatmap_data["beatmap_id"]
                        job.beatmap_id = int(b_id)
                        job.map_title = f"{beatmap_data.get('artist')} - {beatmap_data.get('title')}"
                        
                        # Fetch PP from osu API if possible
                        pp_val = 0.0
                        try:
                            username = getattr(replay, "username", "")
                            if username:
                                scores_resp = await client.get(f"https://osu.ppy.sh/api/get_scores?k={settings.osu_api_key}&b={b_id}&u={username}")
                                if scores_resp.status_code == 200:
                                    scores_data = scores_resp.json()
                                    for score in scores_data:
                                        if int(score.get("maxcombo", 0)) == replay.max_combo and int(score.get("count300", 0)) == replay.count_300:
                                            pp_val = float(score.get("pp") or 0)
                                            break
                                    if pp_val == 0 and len(scores_data) > 0:
                                        pp_val = float(scores_data[0].get("pp") or 0)
                        except Exception:
                            pass

                        # Store stats
                        c_dict = dict(job.config)
                        c_dict["replay_stats"] = {
                            "300s": replay.count_300,
                            "100s": replay.count_100,
                            "50s": replay.count_50,
                            "misses": replay.count_miss,
                            "max_combo": replay.max_combo,
                            "star_rating": beatmap_data.get("difficultyrating"),
                            "pp": pp_val 
                        }
                        job.config = c_dict
                        
                        await db.commit()
                    else:
                        raise Exception(f"Beatmap with hash {h} not found on osu! API (or API key missing). Unranked/unavailable maps cannot be rendered yet.")


                job.status = JobStatus.RENDERING
                await db.commit()

                target_name = f"render_{job_id}"
                
                patch = json.dumps({
                    "Graphics": {
                        "Width": 1920 if job.config.get("resolution") == "1080p" else 3840, 
                        "Height": 1080 if job.config.get("resolution") == "1080p" else 2160
                    },
                    "Gameplay": {
                        "HitErrorMeter": {"Show": job.config.get("hit_error_meter", True)},
                        "KeyOverlay": {"Show": job.config.get("key_overlay", True)}
                    },
                    "Skin": {
                        "CurrentSkin": job.config.get("skin", "Default"),
                        "UseColorsFromSkin": True,
                        "UseBeatmapColors": False,
                        "Cursor": {
                            "UseSkinCursor": True,
                            "Scale": 0.6
                        }
                    },
                    "Objects": {
                        "Colors": {"UseSkinColors": True, "UseBeatmapColors": False},
                        "Sliders": {
                            "ForceSliderBallTexture": True,
                            "Snaking": {
                                "In": job.config.get("snaking_in", True),
                                "Out": job.config.get("snaking_out", True)
                            }
                        }
                    },
                    "Playfield": {
                        "Background": {
                            "Dim": {"Normal": job.config.get("bg_dim", 0.95)},
                            "LoadStoryboards": job.config.get("storyboard", True),
                            "LoadVideos": job.config.get("video", False)
                        }
                    },
                    "Cursor": {"UseSkinCursor": True},
                    "Recording": {
                        "MotionBlur": {"Enabled": job.config.get("motion_blur", True)},
                        "Encoder": "libx264"
                    }
                })

                if os.environ.get("USE_MODAL_GPU") == "1":
                    import modal
                    
                    gpu_render_fn = modal.Function.from_name("osurender-gpu-worker", "gpu_render_task")  # type: ignore[attr-defined]
                    
                    function_call = gpu_render_fn.spawn(  # type: ignore
                        job_id=job_id,
                        set_id=set_id,
                        replay_key=job.replay_storage_key,
                        skin=job.config.get("skin", "Default"),
                        patch=patch,
                        target_name=target_name,
                        bucket_name=storage_client.bucket
                    )
                    
                    job.modal_call_id = function_call.object_id
                    await db.commit()
                    
                    return f"Dispatched to Modal: {function_call.object_id}"
                    
                else:
                    osz_path = os.path.join(SONGS_DIR, f"{set_id}.osz")
                    os.makedirs(SONGS_DIR, exist_ok=True)
                    if not os.path.exists(osz_path) and settings.osu_api_key:
                        async with httpx.AsyncClient() as client:
                            dl = await client.get(f"https://api.nerinyan.moe/d/{set_id}", follow_redirects=True, timeout=60.0)
                            if dl.status_code == 200:
                                with open(osz_path, "wb") as f:
                                    f.write(dl.content)
                            else:
                                raise Exception("Failed to download beatmap from mirror.")

                    log_path = ""
                    if os.environ.get("MOCK_DANSER"):
                        await asyncio.sleep(1)
                        video_path = os.path.join(tmpdir, f"{target_name}.mp4")
                        with open(video_path, "wb") as f:
                            f.write(b"mock video data")
                        thumb_path = os.path.join(tmpdir, "thumb.jpg")
                        with open(thumb_path, "wb") as f:
                            f.write(b"mock thumb data")
                        log_path = os.path.join(tmpdir, "mock.log")
                        with open(log_path, "wb") as f:
                            f.write(b"mock log data")
                    else:
                        cmd = [
                            "xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                            DANSER_BIN,
                            f"-replay={osr_path}",
                            f"-skin={job.config.get('skin', 'Default')}",
                            f"-sPatch={patch}",
                            f"-out={target_name}",
                            "-record"
                        ]

                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            cwd=tmpdir,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )

                        log_path = os.path.join(tmpdir, "render.log")
                        log_file = open(log_path, "w")

                        async def read_stdout():
                            if proc.stdout:
                                async for line in proc.stdout:
                                    line_str = line.decode(errors="ignore")
                                    log_file.write(line_str)
                                    log_file.flush()
                                    if "Progress" in line_str:
                                        try:
                                            p = float(line_str.split(":")[1].replace("%", "").strip())
                                            if job is not None:
                                                job.progress = p
                                                db.add(job)
                                                await db.commit()
                                        except Exception:
                                            pass

                        async def read_stderr():
                            if proc.stderr:
                                async for line in proc.stderr:
                                    line_str = line.decode(errors="ignore")
                                    log_file.write(line_str)
                                    log_file.flush()

                        await asyncio.gather(read_stdout(), read_stderr())
                        log_file.close()
                        try:
                            await asyncio.wait_for(proc.wait(), timeout=settings.render_timeout_seconds)
                        except asyncio.TimeoutError:
                            proc.kill()
                            raise Exception(f"Render timeout ({settings.render_timeout_seconds} seconds)")

                        if proc.returncode != 0:
                            raise Exception("Danser rendering failed.")

                        video_path = os.path.join(tmpdir, "videos", f"{target_name}.mp4")
                        if not os.path.exists(video_path):
                            video_path = os.path.join(tmpdir, f"{target_name}.mp4")
                            if not os.path.exists(video_path):
                                raise Exception("Output video not found.")

                        thumb_path = os.path.join(tmpdir, "thumb.jpg")
                        thumb_proc = await asyncio.create_subprocess_exec(
                            "ffmpeg", "-y", "-ss", "00:00:15", "-i", video_path, "-vframes", "1", "-q:v", "2", thumb_path,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        await thumb_proc.wait()

                    video_key = f"videos/{job_id}.mp4"
                    thumb_key = f"thumbnails/{job_id}.jpg"
                    log_key = f"logs/{job_id}.log"
                    
                    storage_client.client.fput_object(
                        bucket_name=storage_client.bucket,
                        object_name=video_key,
                        file_path=video_path,
                        content_type="video/mp4"
                    )
                    if os.path.exists(thumb_path):
                        storage_client.client.fput_object(
                            bucket_name=storage_client.bucket,
                            object_name=thumb_key,
                            file_path=thumb_path,
                            content_type="image/jpeg"
                        )
                    if os.path.exists(log_path):
                        storage_client.client.fput_object(
                            bucket_name=storage_client.bucket,
                            object_name=log_key,
                            file_path=log_path,
                            content_type="text/plain"
                        )

                if job is not None:
                    job.video_storage_key = video_key
                    job.thumb_storage_key = thumb_key
                    job.status = JobStatus.COMPLETED
                    job.progress = 100.0
                    await db.commit()

        except Exception as e:
            if 'job' in locals() and job is not None:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()

@celery_app.task(
    name="process_render_job", 
    bind=True, 
    max_retries=3,
    time_limit=660, 
    soft_time_limit=600
)
def process_render_job(self, job_id: str):
    asyncio.run(_process_render_job(job_id))

async def _poll_modal_status():
    from src.db.session import async_session_factory
    from src.db.models import Job, JobStatus
    from sqlalchemy import select
    import modal
    from modal.functions import FunctionCall

    async with async_session_factory() as db:
        query = select(Job).where(Job.status == JobStatus.RENDERING, Job.modal_call_id.isnot(None))
        result = await db.execute(query)
        active_jobs = result.scalars().all()

        for job in active_jobs:
            if not job.modal_call_id:
                continue
            try:
                call = FunctionCall.from_id(job.modal_call_id)
                try:
                    result_dict = call.get(timeout=0)
                    
                    if not isinstance(result_dict, dict):
                        result_dict = {"success": False, "error": "Modal returned unexpected result type"}
                    
                    if not result_dict.get("success"):
                        job.status = JobStatus.FAILED
                        job.error_message = result_dict.get("error", "Modal GPU render failed")
                    else:
                        job.video_storage_key = str(result_dict.get("video_key", ""))
                        job.thumb_storage_key = str(result_dict.get("thumb_key", ""))
                        
                        if "pp" in result_dict and float(result_dict["pp"]) > 0:
                            c_dict = dict(job.config)
                            if "replay_stats" in c_dict:
                                c_dict["replay_stats"]["pp"] = float(result_dict["pp"])
                            job.config = c_dict
                            
                        job.status = JobStatus.COMPLETED
                        job.progress = 100.0
                    
                    await db.commit()
                except TimeoutError:
                    continue
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()

@celery_app.task(name="poll_modal_status")
def poll_modal_status():
    if os.environ.get("USE_MODAL_GPU") == "1":
        asyncio.run(_poll_modal_status())
