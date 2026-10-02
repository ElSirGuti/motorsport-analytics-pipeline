# syntax=docker/dockerfile:1
# ── Backend image: FastAPI + pandas/xgboost/reportlab ────────────────────────
# Stage 1 builds wheels into a virtualenv; stage 2 copies only the venv + code
# (no compilers, no pip cache) and runs as an unprivileged user.

FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Only needed if a dependency has no wheel for the platform (e.g. arm64 edge cases).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3.11-slim AS runtime

# libgomp1: OpenMP runtime required by xgboost / scikit-learn wheels.
# libpq5: harmless when psycopg[binary] is used, required if plain psycopg is.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    TEMP_DIR=/tmp/motorsport-analytics \
    STORAGE_DIR=/app/data/storage \
    LOG_LEVEL=INFO \
    MAX_UPLOAD_MB=2048 \
    API_PORT=8000 \
    UVICORN_WORKERS=1 \
    RUN_MIGRATIONS=0

WORKDIR /app
# .dockerignore keeps data/, tmp/, CSVs, tests, node_modules and .git out of the image.
COPY --chown=app:app . .
RUN chmod 0755 docker/entrypoint.sh \
    && mkdir -p /app/data/storage /tmp/motorsport-analytics \
    && chown -R app:app /app/data /tmp/motorsport-analytics

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('API_PORT','8000'), timeout=4); sys.exit(0)" || exit 1

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["uvicorn"]
