import asyncio
import subprocess
import uuid
import json
import pytest
import asyncpg
from datetime import datetime, timezone

DB_URL = "postgresql://osurender:osurender@localhost:5434/osurender"

async def get_db():
    return await asyncpg.connect(DB_URL)

def run_docker(command: str):
    subprocess.run(f"docker {command}", shell=True, check=True)

@pytest.fixture(autouse=True)
async def cleanup():
    # Make sure all containers are running
    run_docker("start osurender-dispatcher osurender-redis osurender-worker")
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
    # 1. Disable the trigger temporarily
    conn = await get_db()
    await conn.execute("ALTER TABLE outbox_events DISABLE TRIGGER outbox_notify_trigger")
    
    # 2. Insert row directly without NOTIFY
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES ($1, $2, $3, $4, $5, 0)",
        event_id, "render_job_created", json.dumps({"job_id": job_id}), "PENDING", datetime.now(timezone.utc)
    )
    
    # 3. Wait 65 seconds for safety poll
    await asyncio.sleep(65)
    
    # 4. Verify PROCESSED
    status = await conn.fetchval("SELECT status FROM outbox_events WHERE id = $1", event_id)
    assert status == "PROCESSED", "Failsafe polling failed to process event"
    
    # Restore trigger
    await conn.execute("ALTER TABLE outbox_events ENABLE TRIGGER outbox_notify_trigger")
    await conn.close()

@pytest.mark.asyncio
async def test_a2_dispatcher_crash_recovery():
    """Prove: dispatcher is stateless"""
    # Create 50 pending events
    conn = await get_db()
    
    run_docker("stop osurender-dispatcher")
    
    for _ in range(50):
        job_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES ($1, $2, $3, $4, $5, 0)",
            event_id, "render_job_created", json.dumps({"job_id": job_id}), "PENDING", datetime.now(timezone.utc)
        )
        
    # Wait a bit
    await asyncio.sleep(2)
    
    # Restart
    run_docker("start osurender-dispatcher")
    
    # Wait for drain
    await asyncio.sleep(10)
    
    # Verify all 50 processed
    pending_count = await conn.fetchval("SELECT COUNT(*) FROM outbox_events WHERE status = 'PENDING'")
    assert pending_count == 0, "Not all events recovered after dispatcher restart"
    await conn.close()

@pytest.mark.asyncio
async def test_a3_notification_storm():
    """Prove: Event aggregation works"""
    # Insert 1000 outbox rows in one burst
    conn = await get_db()
    
    for i in range(10): # 10 chunks of 100
        values = []
        for _ in range(100):
            job_id = str(uuid.uuid4())
            event_id = str(uuid.uuid4())
            values.append(f"('{event_id}', 'render_job_created', '{json.dumps({'job_id': job_id})}', 'PENDING', NOW(), 0)")
        
        query = f"INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES {','.join(values)}"
        await conn.execute(query)
        
    await asyncio.sleep(10)
    
    pending_count = await conn.fetchval("SELECT COUNT(*) FROM outbox_events WHERE status = 'PENDING'")
    assert pending_count == 0, "Storm failed to process all events"
    await conn.close()


# --- TEST GROUP C: Broker Failure ---

@pytest.mark.asyncio
async def test_c1_redis_down_during_dispatch():
    """Prove: Redis failure gracefully increments retry and sets to PENDING"""
    run_docker("stop osurender-redis")
    
    conn = await get_db()
    
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES ($1, $2, $3, $4, $5, 0)",
        event_id, "render_job_created", json.dumps({"job_id": job_id}), "PENDING", datetime.now(timezone.utc)
    )
    
    # Wait for dispatcher to try dispatching
    await asyncio.sleep(5)
    
    # Check that it got rolled back to PENDING and retry_count went up
    row = await conn.fetchrow("SELECT status, retry_count FROM outbox_events WHERE id = $1", event_id)
    assert row["status"] == "PENDING"
    assert row["retry_count"] == 1
    
    run_docker("start osurender-redis")
    await conn.close()
    
@pytest.mark.asyncio
async def test_c3_retry_exhaustion():
    """Prove: Retries eventually hit FAILED state"""
    run_docker("stop osurender-redis")
    
    conn = await get_db()
    job_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    
    # Insert with retry count 3
    await conn.execute(
        "INSERT INTO outbox_events (id, event_type, payload, status, created_at, retry_count) VALUES ($1, $2, $3, $4, $5, 3)",
        event_id, "render_job_created", json.dumps({"job_id": job_id}), "PENDING", datetime.now(timezone.utc)
    )
    
    # Dispatcher will try, fail, and increment to > 3
    await asyncio.sleep(5)
    
    row = await conn.fetchrow("SELECT status FROM outbox_events WHERE id = $1", event_id)
    assert row["status"] == "FAILED"
    
    run_docker("start osurender-redis")
    await conn.close()
    

# --- TEST GROUP D: Queue Protection ---

@pytest.mark.asyncio
async def test_d1_max_queued():
    """Prove MAX_QUEUED returns 503"""
    import httpx
    # Need to simulate 100 queued jobs
    conn = await get_db()
    for _ in range(100):
        job_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO jobs (id, status, replay_storage_key, config, client_ip) VALUES ($1, $2, $3, $4, $5)",
            job_id, "queued", "test", "{}", "127.0.0.1"
        )
        
    # Now try to hit the API
    async with httpx.AsyncClient() as client:
        files = {"replay": ("test_replay.osr", b"dummy replay data", "application/octet-stream")}
        post_resp = await client.post("http://localhost:8000/v1/render", data={"skin": "Default"}, files=files)
        assert post_resp.status_code == 503
        
    await conn.close()
