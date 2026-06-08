import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app

app = create_app()

@pytest.mark.asyncio
async def test_render_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Submit a render job
        files = {
            "replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")
        }
        data = {
            "skin": "Default",
            "bg_dim": "0.8",
            "resolution": "1080p",
        }
        
        post_resp = await client.post("/v1/render", data=data, files=files)
        assert post_resp.status_code == 202, f"Failed to submit render: {post_resp.text}"
        
        resp_data = post_resp.json()
        assert "job_id" in resp_data
        assert resp_data["status"] == "queued"
        
        job_id = resp_data["job_id"]
        
        # 2. Check the job status
        get_resp = await client.get(f"/v1/jobs/{job_id}")
        assert get_resp.status_code == 200
        
        job_data = get_resp.json()
        assert job_data["job_id"] == job_id
        assert job_data["status"] == "queued"
        assert job_data["progress"] == 0.0
