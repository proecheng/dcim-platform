#!/usr/bin/env bash
set -euo pipefail

status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
heartbeat="$status_dir/scheduler-heartbeat"
lock_file="$status_dir/backup-operation.lock"
heartbeat_max_age=${BACKUP_HEARTBEAT_MAX_AGE_SECONDS:-180}
active_max_age=${BACKUP_ACTIVE_MAX_AGE_SECONDS:-14400}
now_epoch=$(date -u +%s)

file_age() {
    local path=$1
    local modified

    modified=$(stat -c %Y "$path")
    printf '%s\n' "$((now_epoch - modified))"
}

if [[ -f "$lock_file" ]]; then
    exec 9>>"$lock_file"
    if ! flock -n 9; then
        [[ $(file_age "$lock_file") -le $active_max_age ]]
        exit 0
    fi
    flock -u 9
fi

[[ -f "$heartbeat" ]]
[[ $(file_age "$heartbeat") -le $heartbeat_max_age ]]

if [[ -f "$status_dir/last-run.json" ]]; then
    if grep -q '"status":"failed"' "$status_dir/last-run.json"; then
        exit 1
    fi
fi
