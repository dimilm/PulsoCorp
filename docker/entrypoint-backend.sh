#!/bin/sh
# /data is a Docker named volume backed by ext4 inside the WSL2/Linux VM, so
# chown/chmod actually take effect here (unlike a Windows host bind mount,
# which is why we moved away from `../data:/data`). We still create the dirs
# defensively in case the volume was just provisioned empty, then drop privs
# to the unprivileged `app` user that runs uvicorn.
set -e

mkdir -p /data /data/backups
chown -R app:app /data
chmod 0775 /data /data/backups

exec gosu app:app "$@"
