#!/bin/bash
set -e

# Run database migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start the application based on the WORKER_TYPE environment variable
if [ "$WORKER_TYPE" = "celery" ]; then
    echo "Starting Celery worker..."
    celery -A src.core.celery_app.celery_app worker --loglevel=info -c 2
elif [ "$WORKER_TYPE" = "beat" ]; then
    echo "Starting Celery beat..."
    celery -A src.core.celery_app.celery_app beat --loglevel=info
elif [ "$WORKER_TYPE" = "dispatcher" ]; then
    echo "Starting Outbox Dispatcher..."
    exec python -m src.workers.dispatcher
else
    echo "Starting FastAPI server..."
    exec uvicorn src.api.app:create_app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8000} --factory --proxy-headers
fi
