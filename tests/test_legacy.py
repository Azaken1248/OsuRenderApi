import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app

app = create_app()

@pytest.mark.asyncio
async def test_legacy_render_response_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {
            "replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")
        }
        data = {
            "skin": "Default",
            "bg_dim": "0.8",
            "quality": "standard",
        }
        
        post_resp = await client.post("/render", data=data, files=files)
        assert post_resp.status_code == 200, f"Failed to submit legacy render: {post_resp.text}"
        
        resp_data = post_resp.json()
        assert "job_id" in resp_data
        assert "view_url" in resp_data
        assert "video_url" in resp_data
        assert "-" not in resp_data["job_id"]  # Hex format without dashes
        
        job_id = resp_data["job_id"]
        
        # Test legacy status
        # Since we use UUIDs internally, the legacy status endpoint needs a valid UUID.
        # However, the legacy job_id we get might just be a hex string.
        # Wait, our legacy endpoint takes uuid.UUID for job_id, so it accepts hex strings without dashes too!
        status_resp = await client.get(f"/status/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        assert "job_id" in status_data
        assert "status" in status_data
        assert "percent" in status_data
        assert "skin" in status_data
        assert "map_title" in status_data
        assert "created_at" in status_data
        assert "last_updated" in status_data
        assert "error" in status_data

@pytest.mark.asyncio
async def test_legacy_jobs_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/jobs")
        assert resp.status_code == 200
        
        jobs = resp.json()
        assert isinstance(jobs, list)
        
        if len(jobs) > 0:
            first_job = jobs[0]
            assert "job_id" in first_job
            assert "status" in first_job
            assert "percent" in first_job
