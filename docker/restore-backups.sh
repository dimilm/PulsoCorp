#!/usr/bin/env bash
# Copies SQLite backups out of the `app_data` Docker volume onto the host.
#
# Since /data lives in a named Docker volume (not a host bind mount), the
# rotating backup files written by the `backup` service are not directly
# visible from the host filesystem. Run this script to materialise them under
# `../data/backups/` (or a custom destination) whenever you want a host copy.
#
# Usage:
#   ./restore-backups.sh                    # -> ../data/backups
#   ./restore-backups.sh /tmp/snapshots     # -> /tmp/snapshots
#
# Behaviour:
#   - Prefers `docker cp` from the running `docker-backend-1` container
#     (fresh, zero spin-up cost).
#   - Falls back to mounting the `docker_app_data` volume into a throwaway
#     alpine container if the backend isn't running.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

destination="${1:-$repo_root/data/backups}"
mkdir -p "$destination"
echo "Destination: $destination"

container="$(docker ps --filter "name=docker-backend-1" --format "{{.Names}}" | head -n1)"

if [[ -n "$container" ]]; then
  echo "Copying /data/backups from container '$container'..."
  docker cp "${container}:/data/backups/." "$destination"
else
  echo "Backend container not running; mounting volume 'docker_app_data' via temporary alpine..."
  docker run --rm \
    -v "docker_app_data:/data:ro" \
    -v "${destination}:/out" \
    alpine:3.20 sh -c 'cp -r /data/backups/. /out/ 2>/dev/null || true'
fi

count="$(find "$destination" -maxdepth 1 -type f -name 'sqlite-*.db' | wc -l | tr -d ' ')"
echo "Done. ${count} backup file(s) now under $destination"
