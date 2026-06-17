import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from src.api.app import create_app
from src.db.session import get_session_factory

import pytest_asyncio

app = create_app()


@pytest_asyncio.fixture(loop_scope="session")
async def setup_db_job():
    job_id = uuid.uuid4()
    factory = get_session_factory()
    async with factory() as session:
        # Create a pending job
        await session.execute(
            text("""
                INSERT INTO jobs (id, status, map_title, progress, config, replay_storage_key)
                VALUES (:id, 'rendering', 'Test Map', 0.5, '{}', 'dummy')
            """),
            {"id": job_id},
        )

        # Create a completed job with analytics
        job_id_done = uuid.uuid4()
        config_data = """{
            "replay_stats": {
                "300s": 100, "100s": 20, "50s": 5, "misses": 1,
                "pp": 150.5, "star_rating": 5.2,
                "username": "TestUser", "beatmap_hash": "abc123hash",
                "game_mode": 0, "mods": ["HD", "HR"], "mods_int": 24,
                "score": 1000000, "max_combo": 500, "gekis": 10, "katus": 5,
                "frames_key": "analytics/test_frames.json.gz",
                "frame_count": 5000
            },
            "life_bar": [
                {"t": 0, "hp": 1.0},
                {"t": 1000, "hp": 0.8}
            ]
        }"""
        await session.execute(
            text("""
                INSERT INTO jobs (id, status, map_title, progress, config, analytics_storage_key, replay_storage_key)
                VALUES (:id, 'completed', 'Test Map Done', 1.0, :config, 'analytics/test_frames.json.gz', 'dummy')
            """),
            {"id": job_id_done, "config": config_data},
        )
        await session.commit()

    yield {"pending": str(job_id), "completed": str(job_id_done)}

    # Cleanup
    async with factory() as session:
        await session.execute(
            text("DELETE FROM jobs WHERE id IN (:id1, :id2)"),
            {"id1": job_id, "id2": job_id_done},
        )
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_analytics_pending(setup_db_job):
    job_id = setup_db_job["pending"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/jobs/{job_id}/analytics")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        assert data["message"] == "Analytics not yet available"


@pytest.mark.asyncio(loop_scope="session")
async def test_analytics_completed(setup_db_job):
    job_id = setup_db_job["completed"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/v1/jobs/{job_id}/analytics")
        assert resp.status_code == 200
        data = resp.json()

        # Check basic fields
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["has_analytics"] is True

        # Check identity
        assert data["identity"]["username"] == "TestUser"
        assert data["identity"]["game_mode"] == 0
        assert data["identity"]["mods"] == ["HD", "HR"]

        # Check hit counts
        assert data["hit_counts"]["300s"] == 100
        assert data["hit_counts"]["misses"] == 1

        # Check performance
        assert data["performance"]["pp"] == 150.5
        assert data["performance"]["star_rating"] == 5.2

        # Check life bar
        assert len(data["life_bar"]) == 2
        assert data["life_bar"][0]["hp"] == 1.0

        # Check frames URL
        assert data["frames_url"] is not None
        assert "X-Amz-Signature" in data["frames_url"]
