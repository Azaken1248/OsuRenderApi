import os
import modal

image = (
    modal.Image.debian_slim()
    .apt_install(
        "wget",
        "unzip",
        "ffmpeg",
        "xvfb",
        "libnss3",
        "libgl1",
        "libgl1-mesa-dri",
        "libgbm1",
        "libgtk-3-0",
        "libasound2",
        "libxrender1",
        "libxtst6",
        "libxi6",
        "libxrandr2",
        "libxcursor1",
        "libxinerama1",
    )
    .pip_install("boto3", "aioboto3", "httpx")
    .run_commands(
        "wget https://github.com/Wieku/danser-go/releases/download/0.11.0/danser-0.11.0-linux.zip",
        "unzip danser-0.11.0-linux.zip -d /usr/local/bin/danser",
        "chmod +x /usr/local/bin/danser/danser-cli",
    )
)

app = modal.App("osurender-gpu-worker")

assets_vol = modal.Volume.from_name("osu-assets", create_if_missing=True)


@app.function(
    image=image,
    gpu="T4",
    volumes={"/mnt/osu_data": assets_vol},
    timeout=660,
    secrets=[modal.Secret.from_name("osurender-secrets")],
)
async def gpu_render_task(
    job_id: str,
    set_id: str,
    replay_key: str,
    skin: str,
    patch: str,
    target_name: str,
    bucket_name: str,
    webhook_url: str | None = None,
) -> dict:
    """
    Fully self-contained GPU render function executing the DRY render pipeline.
    """
    from src.core.render_pipeline import execute_render_pipeline

    endpoint = os.environ.get("S3_ENDPOINT", "")
    access_key = os.environ.get("S3_ACCESS_KEY", "")
    secret_key = os.environ.get("S3_SECRET_KEY", "")

    def commit_assets():
        assets_vol.commit()

    result = await execute_render_pipeline(
        job_id=job_id,
        set_id=set_id,
        replay_key=replay_key,
        skin=skin,
        patch=patch,
        target_name=target_name,
        bucket_name=bucket_name,
        songs_dir="/mnt/osu_data/Songs",
        skins_dir="/mnt/osu_data/Skins",
        danser_bin="/usr/local/bin/danser/danser-cli",
        s3_endpoint=endpoint,
        s3_access_key=access_key,
        s3_secret_key=secret_key,
        assets_commit_fn=commit_assets,
    )

    if webhook_url:
        import httpx
        import hmac
        import hashlib
        import json

        try:
            payload = {
                "success": result.get("success", False),
                "video_key": result.get("video_key", ""),
                "thumb_key": result.get("thumb_key", ""),
                "log_key": result.get("log_key", ""),
                "error": result.get("error", ""),
                "pp": result.get("pp", 0.0),
            }
            body = json.dumps(payload).encode()
            headers = {}
            webhook_secret = os.environ.get("WEBHOOK_SECRET")
            if webhook_secret:
                headers["X-Signature"] = hmac.new(
                    webhook_secret.encode(), body, hashlib.sha256
                ).hexdigest()

            async with httpx.AsyncClient() as client:
                await client.post(
                    webhook_url, content=body, headers=headers, timeout=15.0
                )
        except Exception as e:
            print(f"Webhook error: {e}")

    return result
