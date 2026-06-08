# OsuRender API - Implementation Phase Plan

## Overview
This document outlines a structured, phased approach to refactoring the OsuRender API from its current monolithic state into a production-ready, highly scalable, and decoupled architecture. This plan aligns with the Requirements, System Architecture, and Implementation Use Cases documents.

---

## Phase 1: Local Infrastructure & Project Foundation (Estimated: 1-2 Days)
**Goal:** Establish a robust local development environment and core abstractions before moving business logic.

1. **Repository Structure Refactoring**:
   - Organize the monolithic codebase into a standard Python project layout (e.g., `src/api/`, `src/workers/`, `src/core/`, `src/db/`).
2. **Containerization (Docker Compose)**:
   - Create a `docker-compose.yml` to spin up local instances of **PostgreSQL** (Database) and **Redis** (Message Broker).
   - Set up an S3-compatible local bucket (e.g., **MinIO**) to mock Object Storage.
3. **Database Setup**:
   - Install an ORM (e.g., SQLAlchemy or SQLModel) and Alembic for database migrations.
   - Implement the `jobs` schema defined in the Implementation Document.
4. **Configuration Management**:
   - Implement environment-based settings (using `pydantic-settings`) to manage secrets (DB URIs, Redis URLs, API Keys).

---

## Phase 2: API Gateway & Storage Abstraction (Estimated: 2-3 Days)
**Goal:** Build the stateless FastAPI frontend and decouple file operations from the local disk.

1. **Storage Interface**:
   - Implement an abstract `StorageClient` with a local implementation (for testing) and an S3/Cloudflare R2 implementation.
   - Refactor file uploads (`.osr`, `.osk`) to stream directly to this storage interface instead of `DOWNLOADS_DIR` or `JOBS_DIR`.
2. **REST API Implementation**:
   - Implement strict Pydantic validation schemas for endpoints (`/v1/render`, `/v1/jobs/{job_id}`).
   - Build CRUD operations interacting with PostgreSQL for job metadata creation and status tracking.
   - Implement the `POST /v1/render` endpoint so it uploads the replay to storage, creates a DB record, and returns the `job_id`.
3. **Error Handling & Rate Limiting**:
   - Add global exception handlers and basic IP/User-based rate limiting (using Redis).

---

## Phase 3: Message Queue & GPU Worker Decoupling (Estimated: 3-4 Days)
**Goal:** Move the heavy `danser-go` rendering logic into background workers that communicate via Redis.

1. **Task Queue Setup**:
   - Integrate a task queue library (e.g., **Celery** or **RQ**).
   - Configure the API to push a rendering task payload to Redis immediately after job creation.
2. **Worker Logic Refactoring**:
   - Create the Worker executable (`src/workers/render_worker.py`).
   - The worker must:
     1. Dequeue tasks from Redis.
     2. Update the DB status to `downloading`.
     3. Fetch the `.osr` from Object Storage and download the `.osz` beatmap.
     4. Update the DB status to `rendering`.
     5. Execute the `danser-go` command (headless via `xvfb-run`).
3. **Telemetry & Artifact Uploads**:
   - Parse `danser-go` stdout to update progress in the database periodically.
   - Once complete, upload the `.mp4` and generated thumbnails to Object Storage.
   - Update the DB status to `completed` and save artifact URLs.
4. **Fault Tolerance**:
   - Implement exponential backoff for osu! API calls.
   - Set strict task timeouts and failure callbacks to mark jobs as `failed`.

---

## Phase 4: Production Environment & Modal Deployment (Estimated: 2 Days)
**Goal:** Deploy the scalable architecture to the cloud securely.

1. **Cloud Infrastructure Provisioning**:
   - Provision production PostgreSQL and Redis databases (e.g., Supabase, AWS RDS/ElastiCache, or Render).
   - Provision an S3/R2 bucket for production assets.
2. **Modal GPU Worker Deployment**:
   - Adapt the worker code into a Modal app (`@app.function(gpu="T4")`).
   - Configure Modal Volumes for beatmap/skin caching (to avoid downloading identical assets multiple times).
   - Securely mount Modal Secrets for API keys and DB/Storage credentials.
3. **API Gateway Deployment**:
   - Deploy the FastAPI application (e.g., via Modal web endpoint, or AWS ECS / Render.com).

---

## Phase 5: Testing, Security & Optimization (Estimated: 2 Days)
**Goal:** Ensure the system is robust, secure, and production-ready.

1. **Testing**:
   - Write unit tests for API endpoints and storage abstractions using `pytest` and `httpx`.
   - Write integration tests validating the end-to-end flow from queue to database state updates.
2. **Security Audit**:
   - Verify that malicious `.osr` payloads cannot execute arbitrary code.
   - Ensure the API requires authentication (if applicable to the business model) and honors rate limits.
3. **Load Testing**:
   - Simulate concurrent job submissions to ensure Redis effectively queues requests without API slowdowns.
   - Validate that Modal automatically spins up multiple GPU containers to process the backlog efficiently.
