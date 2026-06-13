import asyncio
import os
import json
import uuid
import httpx
import tempfile
import logging
import time

from osrparse import Replay
from sqlalchemy import select, update

from src.core.celery_app import celery_app
from src.core.storage import storage_client
from src.core.config import get_settings
from src.core.logging import job_id_var, worker_id_var
from src.db.models import Job, JobStatus
from src.db.session import get_session_factory, reset_session_factory
from src.core.metrics import (
    active_render_workers,
    render_duration_seconds,
    render_failures_total,
    jobs_completed_total,
    jobs_failed_total,
    storage_operation_duration_seconds,
    storage_failures_total,
)

settings = get_settings()
logger = logging.getLogger("osurender.worker")

DANSER_BIN = os.environ.get("DANSER_BIN", "danser-cli")
SONGS_DIR = os.environ.get("SONGS_DIR", "/tmp/osu_data/Songs")


async def fetch_beatmap_with_backoff(
    client: httpx.AsyncClient, h: str, max_retries: int = 3
):
    for attempt in range(max_retries):
        try:
            r = await client.get(
                "https://osu.ppy.sh/api/get_beatmaps",
                params={"k": settings.osu_api_key, "h": h},
                timeout=30.0,
            )
            r.raise_for_status()
            data = r.json()
            if data:
                return data[0]
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2**attempt)
    return None


async def _process_render_job(job_id: str):
    job_id_var.set(job_id)
    worker_id_var.set(f"celery-{os.getpid()}")
    active_render_workers.inc()
    start_time = time.monotonic()
    logger.info(f"Starting render job {job_id}")
    try:
        factory = get_session_factory()
        db = factory()

        update_stmt = (
            update(Job)
            .where(Job.id == uuid.UUID(job_id), Job.status == JobStatus.QUEUED)
            .values(status=JobStatus.DOWNLOADING)
        )
        res = await db.execute(update_stmt)
        if getattr(res, "rowcount", 0) == 0:
            logger.warning(f"Job {job_id} not in QUEUED state, aborting")
            await db.close()
            return "aborted"

        result = await db.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
        job: Job | None = result.scalar_one_or_none()
        if not job:
            logger.warning(f"Job {job_id} not found, aborting")
            await db.close()
            return "aborted"

        try:
            await db.commit()
            current_phase = "init"

            with tempfile.TemporaryDirectory() as tmpdir:
                current_phase = "download"
                osr_path = os.path.join(tmpdir, "replay.osr")
                dl_start = time.monotonic()
                try:
                    storage_client.client.fget_object(
                        bucket_name=storage_client.bucket,
                        object_name=job.replay_storage_key,
                        file_path=osr_path,
                    )
                    storage_operation_duration_seconds.labels(
                        operation="download_replay"
                    ).observe(time.monotonic() - dl_start)
                except Exception:
                    storage_failures_total.labels(operation="download_replay").inc()
                    raise

                replay = None
                try:
                    replay = Replay.from_path(osr_path)
                    h = replay.beatmap_hash
                except Exception:
                    h = "unknown"

                current_phase = "osu_api"
                async with httpx.AsyncClient() as client:
                    if settings.osu_api_key and h != "unknown" and replay is not None:
                        beatmap_data = await fetch_beatmap_with_backoff(client, h)
                        if not beatmap_data:
                            raise Exception("Beatmap not found on osu! API.")
                        set_id = beatmap_data["beatmapset_id"]
                        b_id = beatmap_data["beatmap_id"]
                        job.beatmap_id = int(b_id)
                        job.map_title = f"{beatmap_data.get('artist')} - {beatmap_data.get('title')}"

                        pp_val = 0.0
                        try:
                            username = getattr(replay, "username", "")
                            if username:
                                scores_resp = await client.get(
                                    f"https://osu.ppy.sh/api/get_scores?k={settings.osu_api_key}&b={b_id}&u={username}"
                                )
                                if scores_resp.status_code == 200:
                                    scores_data = scores_resp.json()
                                    for score in scores_data:
                                        if (
                                            int(score.get("maxcombo", 0))
                                            == replay.max_combo
                                            and int(score.get("count300", 0))
                                            == replay.count_300
                                        ):
                                            pp_val = float(score.get("pp") or 0)
                                            break
                                    if pp_val == 0 and len(scores_data) > 0:
                                        pp_val = float(scores_data[0].get("pp") or 0)
                        except Exception:
                            pass

                        c_dict = dict(job.config)
                        c_dict["replay_stats"] = {
                            "300s": replay.count_300,
                            "100s": replay.count_100,
                            "50s": replay.count_50,
                            "misses": replay.count_miss,
                            "max_combo": replay.max_combo,
                            "star_rating": beatmap_data.get("difficultyrating"),
                            "pp": pp_val,
                        }
                        job.config = c_dict

                        await db.commit()
                    else:
                        raise Exception(
                            f"Beatmap with hash {h} not found on osu! API (or API key missing). Unranked/unavailable maps cannot be rendered yet."
                        )

                job.status = JobStatus.RENDERING
                await db.commit()
                logger.info(f"Job {job_id} entering render phase")

                target_name = f"render_{job_id}"

                patch = json.dumps(
                    {
                        "Graphics": {
                            "Width": (
                                1920
                                if job.config.get("resolution") == "1080p"
                                else 3840
                            ),
                            "Height": (
                                1080
                                if job.config.get("resolution") == "1080p"
                                else 2160
                            ),
                        },
                        "Gameplay": {
                            "HitErrorMeter": {
                                "Show": job.config.get("hit_error_meter", True)
                            },
                            "KeyOverlay": {"Show": job.config.get("key_overlay", True)},
                        },
                        "Skin": {
                            "CurrentSkin": job.config.get("skin", "Default"),
                            "UseColorsFromSkin": True,
                            "UseBeatmapColors": False,
                            "Cursor": {"UseSkinCursor": True, "Scale": 0.6},
                        },
                        "Objects": {
                            "Colors": {
                                "UseSkinColors": True,
                                "UseBeatmapColors": False,
                            },
                            "Sliders": {
                                "ForceSliderBallTexture": True,
                                "Snaking": {
                                    "In": job.config.get("snaking_in", True),
                                    "Out": job.config.get("snaking_out", True),
                                },
                            },
                        },
                        "Playfield": {
                            "Background": {
                                "Dim": {"Normal": job.config.get("bg_dim", 0.95)},
                                "LoadStoryboards": job.config.get("storyboard", True),
                                "LoadVideos": job.config.get("video", False),
                            }
                        },
                        "Cursor": {"UseSkinCursor": True},
                        "Recording": {
                            "MotionBlur": {
                                "Enabled": job.config.get("motion_blur", True)
                            },
                            "Encoder": "libx264",
                        },
                    }
                )

                current_phase = "render"
                if os.environ.get("USE_MODAL_GPU") == "1":
                    import modal

                    gpu_render_fn = modal.Function.from_name(
                        "osurender-gpu-worker", "gpu_render_task"
                    )

                    function_call = gpu_render_fn.spawn(  # type: ignore
                        job_id=job_id,
                        set_id=set_id,
                        replay_key=job.replay_storage_key,
                        skin=job.config.get("skin", "Default"),
                        patch=patch,
                        target_name=target_name,
                        bucket_name=storage_client.bucket,
                        webhook_url=f"{settings.api_base_url}/v1/jobs/{job_id}/webhook",
                    )

                    job.modal_call_id = function_call.object_id
                    await db.commit()

                    logger.info(
                        f"Job {job_id} dispatched to Modal: {function_call.object_id}"
                    )
                    return f"Dispatched to Modal: {function_call.object_id}"

                else:
                    from src.core.render_pipeline import execute_render_pipeline

                    endpoint = os.environ.get("STORAGE_ENDPOINT", "minio:9000")

                    if not endpoint.startswith("http"):
                        use_ssl = (
                            os.environ.get("STORAGE_USE_SSL", "false").lower() == "true"
                        )
                        scheme = "https" if use_ssl else "http"
                        endpoint = f"{scheme}://{endpoint}"

                    access_key = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
                    secret_key = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")

                    result_dict = await execute_render_pipeline(
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
                        assets_commit_fn=None,
                    )

                    if not result_dict.get("success"):
                        raise Exception(
                            result_dict.get("error", "Local execution pipeline failed")
                        )

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
                    jobs_completed_total.inc()
                    logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            render_failures_total.labels(
                reason=locals().get("current_phase", "unknown")
            ).inc()
            if "job" in locals() and job is not None:
                logger.exception(f"Render failed for job {job_id}")

                job.status = JobStatus.FAILED
                job.error_message = str(e)
                await db.commit()
                jobs_failed_total.inc()
    finally:
        if "db" in locals():
            await db.close()
        active_render_workers.dec()
        duration = time.monotonic() - start_time
        render_duration_seconds.observe(duration)
        logger.info(f"Job {job_id} finished in {duration:.2f}s")
        job_id_var.set("")
        worker_id_var.set("")


@celery_app.task(
    name="process_render_job",
    bind=True,
    max_retries=3,
    time_limit=660,
    soft_time_limit=600,
)
def process_render_job(self, job_id: str):
    reset_session_factory()
    asyncio.run(_process_render_job(job_id))


async def _reap_zombie_jobs():
    from src.db.session import get_session_factory
    from src.db.models import Job, JobStatus
    from src.core.metrics import zombie_jobs_reaped_total
    from sqlalchemy import update
    from datetime import datetime, timezone, timedelta

    timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=15)
    queued_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)

    factory = get_session_factory()
    async with factory() as db:

        stuck_jobs_query = select(Job).where(
            Job.status.in_([JobStatus.RENDERING, JobStatus.DOWNLOADING]),
            Job.updated_at < timeout_threshold,
        )
        stuck_res = await db.execute(stuck_jobs_query)
        stuck_jobs = stuck_res.scalars().all()

        rowcount1 = 0
        for job in stuck_jobs:
            if job.modal_call_id:
                try:
                    import modal

                    fc = modal.FunctionCall.from_id(job.modal_call_id)
                    try:
                        res = fc.get(timeout=0)
                        if res and isinstance(res, dict) and res.get("success"):
                            job.status = JobStatus.COMPLETED
                            job.progress = 100.0
                            job.video_storage_key = res.get("video_key")
                            job.thumb_storage_key = res.get("thumb_key")
                            if res.get("pp") and float(res.get("pp")) > 0:
                                c_dict = dict(job.config)
                                if "replay_stats" not in c_dict:
                                    c_dict["replay_stats"] = {}
                                c_dict["replay_stats"]["pp"] = float(res.get("pp"))
                                job.config = c_dict
                            logger.info(
                                f"Modal polling fallback recovered completed job {job.id}"
                            )
                        else:
                            job.status = JobStatus.FAILED
                            job.error_message = (
                                res.get(
                                    "error",
                                    "Modal execution failed without error message.",
                                )
                                if isinstance(res, dict)
                                else "Unknown Modal failure"
                            )
                            logger.info(
                                f"Modal polling fallback recovered failed job {job.id}"
                            )
                    except TimeoutError:
                        job.status = JobStatus.FAILED
                        job.error_message = (
                            "Job timed out and was reaped by the system."
                        )
                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error_message = f"Modal polling failed: {str(e)}"
            else:
                job.status = JobStatus.FAILED
                job.error_message = "Job timed out and was reaped by the system."

            rowcount1 += 1

        if rowcount1 > 0:
            zombie_jobs_reaped_total.inc(rowcount1)
            logger.warning(f"Reaped {rowcount1} timed-out jobs")

        query2 = (
            update(Job)
            .where(
                Job.status == JobStatus.QUEUED,
                Job.created_at < queued_threshold,
                Job.retry_count <= 3,
            )
            .values(retry_count=Job.retry_count + 1)
        )
        await db.execute(query2)

        query3 = (
            update(Job)
            .where(Job.status == JobStatus.QUEUED, Job.retry_count > 3)
            .values(
                status=JobStatus.FAILED,
                error_message="Job failed to dispatch after 3 retries.",
            )
        )
        result3 = await db.execute(query3)
        rowcount3 = getattr(result3, "rowcount", 0)
        if rowcount3 > 0:
            zombie_jobs_reaped_total.inc(rowcount3)

        await db.commit()


@celery_app.task(name="reap_zombie_jobs")
def reap_zombie_jobs():
    reset_session_factory()
    asyncio.run(_reap_zombie_jobs())
