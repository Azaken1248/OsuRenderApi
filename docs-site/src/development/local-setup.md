# Local Development Setup

Set up OsuRender API for local development without running the full Docker stack.

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for infrastructure services)
- An osu! API key

## 1. Clone & Install

```bash
git clone https://github.com/Azaken1248/OsuRenderApi.git
cd OsuRenderApi

python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: .\venv\Scripts\activate  # Windows

pip install -r requirements.lock
pip install -r requirements-dev.txt  # pytest, etc.
```

## 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your local settings. For development, the defaults work with the Docker infrastructure.

## 3. Start Infrastructure Only

```bash
docker-compose up -d postgres redis
```

This starts only PostgreSQL and Redis, leaving the application processes for you to run locally.

## 4. Run Database Migrations

```bash
alembic upgrade head
```

## 5. Start the API Server

```bash
uvicorn src.api.app:create_app --host 0.0.0.0 --port 8727 --reload --factory
```

The `--reload` flag enables hot-reloading on file changes.

## 6. Start the Dispatcher

In a second terminal:

```bash
source venv/bin/activate
python -m src.workers.dispatcher
```

## 7. Start a Celery Worker

In a third terminal:

```bash
source venv/bin/activate
celery -A src.core.celery_app.celery_app worker --loglevel=info -c 2
```

## 8. (Optional) Start Celery Beat

For scheduled tasks like zombie job reaping:

```bash
celery -A src.core.celery_app.celery_app beat --loglevel=info
```

## Verify Setup

```bash
# Health check
curl http://localhost:8727/health

# Interactive docs
open http://localhost:8727/api/docs
```

## Development Tips

- **Hot reload**: The API server reloads automatically. The Dispatcher and Worker need manual restart.
- **Debug mode**: Set `DEBUG=true` in `.env` for verbose SQL logging and full error messages.
- **Local rendering**: Set `USE_MODAL_GPU=0` and install danser-go locally for testing renders without Modal.
- **Mock danser**: Run tests with `MOCK_DANSER=1` to skip actual rendering.
