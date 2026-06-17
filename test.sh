#!/bin/bash
set -e

echo "============================================="
echo "   OsuRender Chaos Engineering Test Suite   "
echo "============================================="

# Ensure virtual environment is used
if [ ! -d "venv" ]; then
    echo "Virtual environment 'venv' not found. Please create it first."
    exit 1
fi

echo "[1/2] Ensuring backend infrastructure is running..."
docker compose up -d

echo "[2/2] Running all resilience and concurrency tests..."
echo "This will test broker failures, dispatcher crashes, API limits, and queue overflow."

DATABASE_URL="postgresql+asyncpg://osurender:osurender@localhost:5434/osurender" \
DATABASE_URL_SYNC="postgresql+psycopg2://osurender:osurender@localhost:5434/osurender" \
REDIS_URL="redis://localhost:6380/0" \
venv/bin/pytest tests/test_chaos.py -v -W ignore::DeprecationWarning

echo "============================================="
echo "   All 10/10 Chaos Tests Completed!         "
echo "============================================="
