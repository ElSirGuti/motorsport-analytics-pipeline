#!/bin/sh
# Container entrypoint. Optional DB migrations, then uvicorn (workers via UVICORN_WORKERS).
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ] && [ -f alembic.ini ]; then
    echo "[entrypoint] alembic upgrade head"
    alembic upgrade head
fi

if [ "${1:-uvicorn}" = "uvicorn" ]; then
    exec uvicorn main:app \
        --host 0.0.0.0 \
        --port "${API_PORT:-8000}" \
        --workers "${UVICORN_WORKERS:-1}" \
        --proxy-headers --forwarded-allow-ips="*" \
        --no-server-header
fi

exec "$@"
