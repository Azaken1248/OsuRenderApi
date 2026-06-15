# OsuRender API

<p align="center">
  A production-grade, distributed osu! replay rendering pipeline powered by Danser-Go.
</p>

---

OsuRender API is a highly scalable, decoupled microservice system designed to process, orchestrate, and render osu! replays concurrently using cloud GPU infrastructure.

## 📚 Official Documentation

**Comprehensive documentation, architectural ADRs, and deployment guides have been moved to our dedicated documentation portal.**

**👉 [View the full OsuRender Documentation](https://render.azaken.com/docs)** (or serve it locally from `/docs-site`)

The documentation portal covers:
- **Architecture**: In-depth explanations of the Outbox Pattern, Celery orchestration, and Modal cloud GPU execution.
- **API Reference**: Interactive Swagger playgrounds and detailed payload schemas.
- **Deployment**: Step-by-step CI/CD setup, production readiness checklists, and monitoring runbooks.
- **Contributing**: Development workflows, PR guidelines, and testing requirements.

---

## ⚡ Quick Start

The fastest way to get OsuRender running locally is via Docker Compose.

### 1. Configure Environment
```bash
cp .env.example .env
```
Ensure you provide a valid `OSU_API_KEY` and your Modal credentials inside `.env`.

### 2. Launch Infrastructure
```bash
docker-compose up -d --build
```
This automatically provisions PostgreSQL, Redis, MinIO, the FastAPI gateway, and the local Celery worker.

### 3. Deploy Cloud Worker (Optional)
If rendering on Modal (`USE_MODAL_GPU=1`), deploy the execution environment:
```bash
modal secret create osurender-secrets S3_ENDPOINT="http://your-ip:9000" S3_ACCESS_KEY="minioadmin" S3_SECRET_KEY="minioadmin"
modal deploy src.modal_deploy
```

## 🛠 Tech Stack

- **Gateway**: FastAPI, Uvicorn, Pydantic
- **Database**: PostgreSQL 16, async SQLAlchemy, Alembic
- **Orchestration**: Celery 5, Redis
- **Compute**: Modal (T4/A10G Cloud GPUs), Danser-Go
- **Storage**: MinIO / AWS S3
- **Monitoring**: Prometheus, Grafana

## 📄 License
Provided as-is for educational and personal use. Please respect osu! community guidelines.
