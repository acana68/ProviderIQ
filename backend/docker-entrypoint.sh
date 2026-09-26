#!/bin/sh
# Container entrypoint: migrate, optionally seed an empty database, then serve.
# Must keep LF line endings (.gitattributes enforces it); a CRLF shebang won't run.
set -eu

cd /app/backend

echo "Applying database migrations..."
alembic upgrade head

if [ "${SEED_IF_EMPTY:-false}" = "true" ]; then
    # Only loads data/ when the providers table is empty, so restarts never wipe data.
    python -m scripts.seed_db --if-empty
fi

# --proxy-headers makes uvicorn take the client IP and scheme from X-Forwarded-For /
# X-Forwarded-Proto, but only on requests from the addresses in FORWARDED_ALLOW_IPS.
# The default, 127.0.0.1, trusts no other host, so a client can't spoof its IP to dodge
# the per-IP rate limits. Stage 14 sets it to the load balancer / reverse proxy.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
