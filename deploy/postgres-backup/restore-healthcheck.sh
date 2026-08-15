#!/usr/bin/env bash
set -euo pipefail

status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
postgres_user=${POSTGRES_USER:-dcim}

[[ -f "$status_dir/restore-server-status.json" ]]
grep -q '"status":"ready"' "$status_dir/restore-server-status.json"
pg_isready --host=/var/run/postgresql --username="$postgres_user" >/dev/null 2>&1
