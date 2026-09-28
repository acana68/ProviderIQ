# syntax=docker/dockerfile:1
# Backend API image. Build context is the repo root, so data/ (the seed CSVs) can be copied:
#   docker build -f backend/Dockerfile .
# Inside the image the repo layout is kept (/app/backend, /app/data), so config.py's
# REPO_ROOT and the seed script's data path work unchanged.

# Base images are pinned by digest (what's actually pulled), with the tag kept for
# Dependabot, which updates both. python:3.12-slim at this digest is Python 3.12.14.

# --- Build stage: install the runtime requirements into a virtualenv --------------------
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Runtime dependencies only: requirements-dev.txt (pytest, ruff, faker...) never gets in.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# --- Final stage -------------------------------------------------------------------------
# Python 3.12.14: the same digest as the build stage.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --from=builder /opt/venv /opt/venv
# Owned by root and read-only to the app user: the running process can't modify its code.
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY --chmod=755 backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

WORKDIR /app/backend
USER app

EXPOSE 8000

# No curl in the slim image, so ask with Python. /health/ready is 503 when the database is
# down, which makes urlopen raise, which fails the check.
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=4)"]

ENTRYPOINT ["docker-entrypoint.sh"]
