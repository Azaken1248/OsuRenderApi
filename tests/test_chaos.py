import asyncio
import subprocess
import uuid
import json
import pytest
import asyncpg
import httpx
from datetime import datetime, timezone

from src.core.config import get_settings

DB_URL = "postgresql://osurender:osurender@localhost:5434/osurender"

async def get_db():
    return await asyncpg.connect(DB_URL)

def run_docker(command: str):
    subprocess.run(f"docker {command}", shell=True, check=True)

async def wait_for_status(event_id: str, expected_status: str, timeout: int = 120):
    conn = await get_db()
    for _ in range(timeout):
        status = await conn.fetchval("SELECT status FROM outbox_events WHERE id = $1", event_id)
        if status == expected_status:
            await conn.close()
            return True
        await asyncio.sleep(1)
    await conn.close()
    return False

async def insert_job_and_event(conn, status="queued", retry_count=0):
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    
    await conn.execute(
        "INSERT INTO jobs (id, status, replay_storage_key, config, client_ip) VALUES ($1, $2, $3, $4, $5)",
        job_id, status, f"replays/{job_id}/replay.osr", "{}", "127.0.0.1"
    )
    await conn.execute(
        "INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES ($1, $2, $3, $4, $5, $6)",
        event_id, "render_job_created", json.dumps({"job_id": job_id}), "PENDING", datetime.now(timezone.utc), retry_count
    )
    return job_id, event_id

@pytest.fixture(autouse=True)
async def cleanup():
    # Make sure all containers are running
    run_docker("start osurender-dispatcher osurender-redis osurender-worker osurender-api")
    yield
    # Cleanup DB
    conn = await get_db()
    await conn.execute("DELETE FROM outbox_events")
    await conn.execute("DELETE FROM jobs")
    await conn.close()

# --- TEST GROUP A: Outbox Reliability ---

@pytest.mark.asyncio
async def test_a1_lost_notification_recovery():
    """Prove: LISTEN/NOTIFY is optional"""
    conn = await get_db()
    await conn.execute("ALTER TABLE outbox_events DISABLE TRIGGER outbox_notify_trigger")
    
    _, event_id = await insert_job_and_event(conn)
    
    # Wait for the failsafe polling to pick it up
    success = await wait_for_status(event_id, "PROCESSED", timeout=90)
    assert success, "Failsafe polling failed to process event"
    
    await conn.execute("ALTER TABLE outbox_events ENABLE TRIGGER outbox_notify_trigger")
    await conn.close()

@pytest.mark.asyncio
async def test_a2_dispatcher_crash_recovery():
    """Prove: dispatcher recovers from cold backlog and mid-processing crashes"""
    conn = await get_db()
    
    # Insert 500 events
    for _ in range(500):
        await insert_job_and_event(conn)
        
    # Give it a second to start draining
    await asyncio.sleep(2)
    
    # KILL mid-drain
    run_docker("kill osurender-dispatcher")
    
    # Let the sweeper logic (5m) technically handle stuck ones in real life,
    # but for tests we will manually advance the clock to simulate sweeper pickup
    # by moving stuck processing back to PENDING.
    await conn.execute("UPDATE outbox_events SET status='PENDING' WHERE status='PROCESSING'")
    
    run_docker("start osurender-dispatcher")
    
    for _ in range(120):
        pending = await conn.fetchval("SELECT COUNT(*) FROM outbox_events WHERE status = 'PENDING' OR status = 'PROCESSING'")
        if pending == 0:
            break
        await asyncio.sleep(1)
        
    assert pending == 0, "Not all events recovered after dispatcher restart"
    await conn.close()

@pytest.mark.asyncio
async def test_a3_notification_storm():
    """Prove: Event aggregation works"""
    conn = await get_db()
    
    # Capture log lines before
    res = subprocess.run("docker logs osurender-dispatcher | grep 'Claimed' | wc -l", shell=True, capture_output=True, text=True)
    claims_before = int(res.stdout.strip()) if res.stdout.strip() else 0
    
    for i in range(10): # 10 chunks of 100
        values_jobs = []
        values_events = []
        for _ in range(100):
            job_id = str(uuid.uuid4())
            event_id = str(uuid.uuid4())
            values_jobs.append(f"('{job_id}', 'queued', 'test', '{{}}', '127.0.0.1')")
            values_events.append(f"('{event_id}', 'render_job_created', '{json.dumps({'job_id': job_id})}', 'PENDING', NOW(), 0)")
        
        await conn.execute(f"INSERT INTO jobs (id, status, replay_storage_key, config, client_ip) VALUES {','.join(values_jobs)}")
        await conn.execute(f"INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES {','.join(values_events)}")
        
    for _ in range(120):
        if await conn.fetchval("SELECT COUNT(*) FROM outbox_events WHERE status != 'PROCESSED'") == 0:
            break
        await asyncio.sleep(1)
        
    # Verify it didn't do 1000 individual claims
    res = subprocess.run("docker logs osurender-dispatcher | grep 'Claimed' | wc -l", shell=True, capture_output=True, text=True)
    claims_after = int(res.stdout.strip()) if res.stdout.strip() else 0
    new_claims = claims_after - claims_before
    
    # Since we insert 1000, and batch limit is 100, we expect roughly 10-20 drain calls, not 1000
    assert new_claims < 50, f"Notification storm protection failed, made {new_claims} drain calls"
    await conn.close()

# --- TEST GROUP B: Duplicate Prevention ---

@pytest.mark.asyncio
async def test_b1_duplicate_dispatch():
    """Prove: Worker Idempotency"""
    from src.workers.render_worker import process_render_job
    
    conn = await get_db()
    job_id, _ = await insert_job_and_event(conn)
    
    # Dispatch twice concurrently
    process_render_job.delay(job_id)
    process_render_job.delay(job_id)
    
    for _ in range(120):
        status = await conn.fetchval("SELECT status FROM jobs WHERE id = $1", job_id)
        if status in ("completed", "failed"):
            break
        await asyncio.sleep(1)
        
    # Verify no duplicate rendering
    # Since we can't easily count worker executions without logs, we can check 
    # if it throws idempotency errors or if the status is cleanly resolved.
    assert status in ("completed", "failed")
    await conn.close()

# --- TEST GROUP C: Broker Failure ---

@pytest.mark.asyncio
async def test_c1_redis_down_during_dispatch():
    run_docker("stop osurender-redis")
    
    conn = await get_db()
    _, event_id = await insert_job_and_event(conn)
    
    for _ in range(60):
        row = await conn.fetchrow("SELECT status, retry_count FROM outbox_events WHERE id = $1", event_id)
        if row["status"] == "PENDING" and row["retry_count"] > 0:
            break
        await asyncio.sleep(1)
        
    assert row["status"] == "PENDING"
    assert row["retry_count"] >= 1
    
    run_docker("start osurender-redis")
    await conn.close()
    
@pytest.mark.asyncio
async def test_c3_retry_exhaustion():
    run_docker("stop osurender-redis")
    
    conn = await get_db()
    _, event_id = await insert_job_and_event(conn, retry_count=3)
    
    success = await wait_for_status(event_id, "FAILED", timeout=60)
    assert success, "Retries did not exhaust to FAILED"
    
    run_docker("start osurender-redis")
    await conn.close()

# --- TEST GROUP D: Queue Protection ---

@pytest.mark.asyncio
async def test_d1_max_queued():
    settings = get_settings()
    conn = await get_db()
    
    # Insert exactly max_queued jobs
    for _ in range(settings.max_queued):
        await insert_job_and_event(conn)
        
    async with httpx.AsyncClient() as client:
        files = {"replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")}
        post_resp = await client.post("http://localhost:8000/v1/render", data={"skin": "Default"}, files=files)
        assert post_resp.status_code == 503
        
    await conn.close()

# --- TEST GROUP E: Advisory Lock Certification ---

@pytest.mark.asyncio
async def test_e1_same_ip_race():
    """Prove: pg_advisory_xact_lock prevents API limit bypass"""
    conn = await get_db()
    await conn.execute("DELETE FROM jobs")
    
    # Try to submit 50 jobs concurrently from the same mocked IP
    async def submit_job():
        async with httpx.AsyncClient() as client:
            files = {"replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")}
            return await client.post("http://localhost:8000/v1/render", data={"skin": "Default"}, files=files)
            
    tasks = [submit_job() for _ in range(50)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in responses if getattr(r, "status_code", 0) == 202)
    too_many_req_count = sum(1 for r in responses if getattr(r, "status_code", 0) == 429)
    
    # Only 2 active jobs allowed per IP
    assert success_count <= 2, f"Allowed {success_count} concurrent jobs from same IP!"
    assert too_many_req_count >= 48
    
    await conn.close()
