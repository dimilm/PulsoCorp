#!/bin/sh
set -eu

# On Docker Desktop / WSL2, host bind-mounts often appear as nobody:nobody
# with restrictive mode bits which prevent even container-root from writing
# into a pre-existing /data/backups directory. Normalize once at startup.
mkdir -p /data/backups
chmod 0777 /data/backups 2>/dev/null || true

while true
do
  if [ -f /data/sqlite.db ]; then
    cp /data/sqlite.db "/data/backups/sqlite-$(date +%Y%m%d-%H%M%S).db"
    ls -1t /data/backups/sqlite-*.db | awk 'NR>14' | xargs -r rm -f
  fi
  sleep 86400
done