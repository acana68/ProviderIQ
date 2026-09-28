#!/bin/sh
# Container entrypoint: migrate, optionally seed an empty database, then serve.
# Must keep LF line endings (.gitattributes enforces it); a CRLF shebang won't run.
set -eu

cd /app/backend

# Migrations, the runtime role's password and the seed run as the owner role
# (MIGRATION_DATABASE_URL); the API itself connects as the runtime role (DATABASE_URL).
echo "Applying database migrations..."
alembic upgrade head
python -m scripts.app_db_role

if [ "${SEED_IF_EMPTY:-false}" = "true" ]; then
    # Only loads data/ when the providers table is empty, so restarts never wipe data.
    python -m scripts.seed_db --if-empty
fi

# The API process never needs the owner's credentials, so it doesn't get them.
unset MIGRATION_DATABASE_URL TEST_DATABASE_URL POSTGRES_PASSWORD

# --proxy-headers makes uvicorn take the client IP and scheme from X-Forwarded-For /
# X-Forwarded-Proto, but only on requests from the addresses in FORWARDED_ALLOW_IPS.
# The default, 127.0.0.1, trusts no other host, so a client can't spoof its IP to dodge
# the per-IP rate limits. docker-compose.yml sets it to the nginx container's fixed IP.
# nginx appends its peer to X-Forwarded-For, and uvicorn takes the rightmost entry that
# isn't trusted: that peer, never an address the client wrote into the header itself.
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
