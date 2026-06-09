# OsuRender API

A production-grade, distributed osu! replay rendering service powered by [Danser-Go](https://github.com/Wieku/danser-go).

OsuRender has been re-architected from a monolith into a highly scalable, decoupled microservice system.

## 🏗️ Architecture

- **API Gateway (FastAPI)**: Stateless HTTP server that handles rate-limiting, job submission, and frontend views.
- **Database (PostgreSQL)**: Persists jobs, beatmap metadata, and statuses (via async SQLAlchemy).
- **Message Broker (Redis)**: Queues rendering jobs.
- **Task Workers (Celery)**: Consume jobs from Redis, download assets, and orchestrate rendering.
- **Cloud Execution (Modal GPU)**: Offloads the intensive rendering process to Modal's T4/A10G GPU instances for scalable video generation.
- **Object Storage (S3 / MinIO)**: Stores `.osr` replays, `.mp4` videos, thumbnails, and logs.

## 🚀 Deployment

The system is fully containerized and easily deployable via Docker Compose.

### Prerequisites
- Docker & Docker Compose
- A [Modal](https://modal.com) account (for GPU rendering)

### 1. Configure Secrets

Copy the example environment file and fill in your secrets:
```bash
cp .env.example .env
```
Ensure you provide a valid `OSU_API_KEY` (from https://osu.ppy.sh/p/api) and configure Modal properly.

### 2. Deploy Local Infrastructure & Application

The included `docker-compose.yml` spins up PostgreSQL, Redis, MinIO, the FastAPI gateway, and the Celery worker.

```bash
docker-compose up -d --build
```
*Note: Wait a few seconds for MinIO to initialize and the `minio-init` container to provision the storage buckets.*

### 3. Deploy Modal GPU Worker

If `USE_MODAL_GPU=1` is set in your `.env`, you must deploy the cloud GPU worker:

```bash
modal secret create osurender-secrets S3_ENDPOINT="http://your-ip:9000" S3_ACCESS_KEY="minioadmin" S3_SECRET_KEY="minioadmin"
modal deploy src.modal_deploy
```
*Note: Make sure your MinIO instance is accessible from the internet for Modal to push artifacts to it.*

## 💻 Local Development

If you prefer to develop locally without Docker:

1. Install Python 3.10+ dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Start Infrastructure:
```bash
docker-compose up -d postgres redis minio minio-init
```

3. Run Migrations:
```bash
alembic upgrade head
```

4. Start API Server:
```bash
uvicorn src.api.app:create_app --host 0.0.0.0 --port 8000 --reload
```

5. Start Celery Worker:
```bash
celery -A src.core.celery_app.celery_app worker --loglevel=info -c 2
```

## 🌐 API Reference

Access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

Legacy endpoints (`/render`, `/jobs`, `/status`) are strictly supported for backward compatibility with the old monolithic application.

## 🧪 Testing

The codebase includes a comprehensive `pytest` suite ensuring backward compatibility and infrastructure stability.

```bash
MOCK_DANSER=1 pytest -W default
```

## License
Provided as-is for educational and personal use. Please respect osu! community guidelines.
