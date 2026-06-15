---
title: "Testing Guide"
description: "Testing strategy for OsuRender API — unit tests, integration tests, chaos engineering scenarios, and CI test automation."
---

# Testing Guide

OsuRender API includes a comprehensive test suite covering unit tests, integration tests, and chaos engineering scenarios.

## Running Tests

```bash
# Run all tests (with danser mocked)
MOCK_DANSER=1 pytest -W default

# Run with verbose output
MOCK_DANSER=1 pytest -v

# Run with coverage
MOCK_DANSER=1 pytest --cov=src --cov-report=term-missing

# Run a specific test file
MOCK_DANSER=1 pytest tests/test_render.py -v

# Run a specific test
MOCK_DANSER=1 pytest tests/test_chaos.py::test_a5_outbox_claim_race -v
```

## Test Suite Overview

| File | Tests | Category | Description |
|------|-------|----------|-------------|
| `test_health.py` | 1 | Unit | Health endpoint returns healthy |
| `test_render.py` | 3 | Integration | Render submission, validation, rejection |
| `test_skins.py` | 3 | Integration | Skin listing, upload, validation |
| `test_storage.py` | 4 | Unit | Storage client operations |
| `test_legacy.py` | 4 | Integration | Legacy endpoint compatibility |
| `test_chaos.py` | 10 | Chaos | Architecture reliability guarantees |

## Chaos Engineering Tests

The chaos test suite (`test_chaos.py`) proves critical reliability properties:

### Phase 1 — Outbox Reliability

| Test | ID | Guarantee |
|------|-----|-----------|
| Lost Notification Recovery | A1 | LISTEN/NOTIFY not required for correctness; safety poll recovers |
| Dispatcher Crash Recovery | A2 | No job loss after mid-drain SIGKILL; 500 events all reach terminal state |
| Notification Storm | A3 | 1000 events batched into < 50 drain calls |
| Stuck Processing Sweeper | A4 | 5-minute-old PROCESSING events reset to PENDING |
| Outbox Claim Race | A5 | `FOR UPDATE SKIP LOCKED` prevents duplicate claims across 3 concurrent dispatchers |

### Phase 2 — Operational Hardening

| Test | ID | Guarantee |
|------|-----|-----------|
| Duplicate Worker Execution | B1 | Atomic `UPDATE WHERE status=QUEUED` prevents double-processing |
| Redis Failure Recovery | C1 | Dispatch failure increments retry and reverts to PENDING |
| Retry Exhaustion | C3 | Events marked FAILED after 3 retries (not retried forever) |
| Queue Circuit Breaker | D1 | `MAX_QUEUED` enforced — API returns 503 when full |
| Advisory Lock Race | E1 | 50 concurrent submissions from same IP yield ≤ 2 successes |

## Prerequisites for Chaos Tests

The chaos tests require a running infrastructure stack:

```bash
docker-compose up -d postgres redis
```

Some tests (A2, A5) interact directly with PostgreSQL via `asyncpg`.

## Writing New Tests

```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import create_app

@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_my_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```
