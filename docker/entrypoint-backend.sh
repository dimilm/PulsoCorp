#!/bin/sh
# Runs as root inside the container so we can normalize the bind-mounted
# /data directory (which on Docker Desktop / WSL2 comes in as nobody:nobody
# with mode bits the unprivileged "app" user cannot write to) before dropping
# privileges to the unprivileged user that runs uvicorn.
set -e

mkdir -p /data /data/backups
chown -R app:app /data 2>/dev/null || true
chmod 0775 /data /data/backups 2>/dev/null || true

exec gosu app:app "$@"
