import asyncio
import os
import httpx
import tempfile
from pathlib import Path

async def run_danser_on_gpu(job_id: str, set_id: str, replay_key: str, skin: str, patch: str, target_name: str, bucket_name: str) -> dict:
    import boto3
    from botocore.client import Config
    
    # We must use boto3 or MinIO to download the .osr, since we don't have src.core.storage config
    # Modal secrets should provide S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY
    endpoint = os.environ.get("S3_ENDPOINT")
    access_key = os.environ.get("S3_ACCESS_KEY")
    secret_key = os.environ.get("S3_SECRET_KEY")
    
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4")
        )
        
        SONGS_DIR = "/mnt/osu_data/Songs"
        DANSER_BIN = "/usr/local/bin/danser/danser-cli"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            osr_path = os.path.join(tmpdir, "replay.osr")
            s3.download_file(bucket_name, replay_key, osr_path)
            
            # Download beatmap .osz if not cached
            osz_path = os.path.join(SONGS_DIR, f"{set_id}.osz")
            os.makedirs(SONGS_DIR, exist_ok=True)
            if not os.path.exists(osz_path):
                async with httpx.AsyncClient() as client:
                    dl = await client.get(f"https://api.nerinyan.moe/d/{set_id}", follow_redirects=True, timeout=60.0)
                    if dl.status_code == 200:
                        with open(osz_path, "wb") as f:
                            f.write(dl.content)
                    else:
                        return {"success": False, "error": "Failed to download beatmap from mirror."}
                        
            # Run danser
            cmd = [
                "xvfb-run", "-a", "-s", "-screen 0 1920x1080x24",
                DANSER_BIN,
                f"-replay={osr_path}",
                f"-skin={skin}",
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
            
            # We skip DB progress updates here because we are in the Modal GPU container and shouldn't hit the DB constantly.
            # Real-time progress updates are traded off for cost optimization. The celery worker waits for the full job.
            await proc.wait()
            
            if proc.returncode != 0:
                return {"success": False, "error": "Danser rendering failed."}
                
            video_path = os.path.join(tmpdir, "videos", f"{target_name}.mp4")
            if not os.path.exists(video_path):
                video_path = os.path.join(tmpdir, f"{target_name}.mp4")
                if not os.path.exists(video_path):
                    return {"success": False, "error": "Output video not found."}
                    
            thumb_path = os.path.join(tmpdir, "thumb.jpg")
            thumb_proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", "00:00:15", "-i", video_path, "-vframes", "1", "-q:v", "2", thumb_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await thumb_proc.wait()
            
            video_key = f"videos/{job_id}.mp4"
            thumb_key = f"thumbnails/{job_id}.jpg"
            
            # Upload artifacts
            s3.upload_file(video_path, bucket_name, video_key, ExtraArgs={"ContentType": "video/mp4"})
            if os.path.exists(thumb_path):
                s3.upload_file(thumb_path, bucket_name, thumb_key, ExtraArgs={"ContentType": "image/jpeg"})
                
            return {
                "success": True,
                "video_key": video_key,
                "thumb_key": thumb_key
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
