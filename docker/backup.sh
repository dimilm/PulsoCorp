#!/bin/sh
# Crash-consistent SQLite backup loop.
#
# Why not `cp`?
#   The previous version copied /data/sqlite.db with `cp` while the backend
#   was potentially mid-transaction. With WAL enabled (or even rollback
#   journals), that yields a torn snapshot that may fail to open or be
#   silently inconsistent. `sqlite3 .backup` uses the online backup API
#   which takes a read lock per page and produces a verified, consistent
#   copy even under concurrent writes.
#
# Layout:
#   /data/sqlite.db                  -- live DB
#   /data/backups/sqlite-YYYYmmdd-HHMMSS.db   -- rotating snapshots
#
# Retention: 14 daily snapshots. Bump RETENTION below if you want more.
#
# Notes:
#   - Runs in `alpine:3.20` (see docker-compose.yml). `sqlite` package
#     provides the `sqlite3` CLI; install is idempotent on every start.
#   - We `sleep 86400` between runs. A container restart resets that timer,
#     so worst case you get an extra backup right after a redeploy. That is
#     by design (cheap, easier to reason about than a cron sidecar).

set -eu

RETENTION="${BACKUP_RETENTION:-14}"
BACKUP_DIR="/data/backups"
DB_PATH="/data/sqlite.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "[backup] installing sqlite CLI..."
  apk add --no-cache sqlite >/dev/null
fi

mkdir -p "$BACKUP_DIR"

while true; do
  if [ -f "$DB_PATH" ]; then
    ts="$(date +%Y%m%d-%H%M%S)"
    target="$BACKUP_DIR/sqlite-$ts.db"
    tmp="$target.partial"

    # Online backup: safe under concurrent writes. We write to a `.partial`
    # file first and rename on success so a half-finished backup never wins
    # the rotation step below.
    if sqlite3 "$DB_PATH" ".backup '$tmp'" 2>/tmp/backup.err; then
      # Verify the snapshot before we accept it. `integrity_check` returns
      # `ok` for a healthy DB; anything else means we keep the previous
      # snapshots and skip rotation this round.
      if [ "$(sqlite3 "$tmp" 'PRAGMA integrity_check;' 2>/dev/null)" = "ok" ]; then
        mv "$tmp" "$target"
        echo "[backup] wrote $target"
        # Rotate: keep only the newest $RETENTION snapshots.
        ls -1t "$BACKUP_DIR"/sqlite-*.db 2>/dev/null \
          | awk -v n="$RETENTION" 'NR>n' \
          | xargs -r rm -f
      else
        echo "[backup] integrity check FAILED for $tmp; discarding" >&2
        rm -f "$tmp"
      fi
    else
      echo "[backup] sqlite3 .backup failed:" >&2
      cat /tmp/backup.err >&2 || true
      rm -f "$tmp"
    fi
  else
    echo "[backup] $DB_PATH not present yet; skipping this cycle"
  fi

  sleep 86400
done
