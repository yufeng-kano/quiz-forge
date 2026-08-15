#!/bin/sh
# container 啟動流程：先跑 migration，再起 API server。
# BACKEND_HOST / BACKEND_PORT 由根目錄 .env 提供，這裡的預設值只是保底。
set -e

echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

echo "[entrypoint] starting uvicorn"
exec uvicorn backend.main:app \
    --host "${BACKEND_HOST:-0.0.0.0}" \
    --port "${BACKEND_PORT:-8000}"
