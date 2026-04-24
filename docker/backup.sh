#!/bin/sh
# /data is a Docker named volume (see docker-compose.yml). The backend's
# entrypoint creates and chowns /data/backups, but provision it again here in
# case the backup container starts before the backend has run.
set -eu

mkdir -p /data/backups

while true
do
  if [ -f /data/sqlite.db ]; then
    cp /data/sqlite.db "/data/backups/sqlite-$(date +%Y%m%d-%H%M%S).db"
    ls -1t /data/backups/sqlite-*.db | awk 'NR>14' | xargs -r rm -f
  fi
  sleep 86400
done
