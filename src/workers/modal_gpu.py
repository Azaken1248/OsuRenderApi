import asyncio
import os
import httpx
import tempfile
from pathlib import Path

async def run_danser_on_gpu(job_id: str, set_id: str, replay_key: str, skin: str, patch: str, target_name: str, bucket_name: str) -> dict:
    import boto3
    from botocore.client import Config
    
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
            
            log_path = os.path.join(tmpdir, "render.log")
            log_file = open(log_path, "w")
            
            async def read_stream(stream):
                if stream:
                    async for line in stream:
                        line_str = line.decode(errors="ignore")
                        log_file.write(line_str)
                        log_file.flush()
                        
            await asyncio.gather(
                read_stream(proc.stdout),
                read_stream(proc.stderr)
            )
            log_file.close()
            
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
            log_key = f"logs/{job_id}.log"
            
            s3.upload_file(video_path, bucket_name, video_key, ExtraArgs={"ContentType": "video/mp4"})
            if os.path.exists(thumb_path):
                s3.upload_file(thumb_path, bucket_name, thumb_key, ExtraArgs={"ContentType": "image/jpeg"})
            if os.path.exists(log_path):
                s3.upload_file(log_path, bucket_name, log_key, ExtraArgs={"ContentType": "text/plain"})
                
            return {
                "success": True,
                "video_key": video_key,
                "thumb_key": thumb_key,
                "log_key": log_key
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
