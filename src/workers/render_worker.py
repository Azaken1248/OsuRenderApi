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
                    from src.core.render_pipeline import execute_render_pipeline
                    
                    endpoint = os.environ.get("STORAGE_ENDPOINT", "minio:9000")
                    # Make sure it's a valid url
                    if not endpoint.startswith("http"):
                        use_ssl = os.environ.get("STORAGE_USE_SSL", "false").lower() == "true"
                        scheme = "https" if use_ssl else "http"
                        endpoint = f"{scheme}://{endpoint}"

                    access_key = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
                    secret_key = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
                    
                    result_dict = await asyncio.to_thread(
                        execute_render_pipeline,
                        job_id=job_id,
                        set_id=set_id,
                        replay_key=job.replay_storage_key,
                        skin=job.config.get("skin", "Default"),
                        patch=patch,
                        target_name=target_name,
                        bucket_name=storage_client.bucket,
                        songs_dir=SONGS_DIR,
                        skins_dir=os.environ.get("SKINS_DIR", "/tmp/osu_data/Skins"),
                        danser_bin=DANSER_BIN,
                        s3_endpoint=endpoint,
                        s3_access_key=access_key,
                        s3_secret_key=secret_key,
                        assets_commit_fn=None
                    )
                    
                    if not result_dict.get("success"):
                        raise Exception(result_dict.get("error", "Local execution pipeline failed"))
                        
                    video_key = result_dict.get("video_key")
                    thumb_key = result_dict.get("thumb_key")
                    
                    if "pp" in result_dict and float(result_dict["pp"]) > 0:
                        c_dict = dict(job.config)
                        if "replay_stats" in c_dict:
                            c_dict["replay_stats"]["pp"] = float(result_dict["pp"])
                        job.config = c_dict

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
