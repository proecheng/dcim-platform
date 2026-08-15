#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
full_weekday=${BACKUP_FULL_WEEKDAY:-0}
daily_hour=${BACKUP_DAILY_HOUR:-2}
incremental_hours=${BACKUP_INCREMENTAL_HOURS:-8,14,20}
poll_seconds=${BACKUP_SCHEDULER_POLL_SECONDS:-60}
last_slot_file="$status_dir/scheduler-last-slot"

validate_hour() {
    local value=$1
    [[ "$value" =~ ^([0-9]|1[0-9]|2[0-3])$ ]]
}

if [[ ! "$full_weekday" =~ ^[0-6]$ ]]; then
    echo "BACKUP_FULL_WEEKDAY must be between 0 and 6" >&2
    exit 64
fi
if ! validate_hour "$daily_hour"; then
    echo "BACKUP_DAILY_HOUR must be between 0 and 23" >&2
    exit 64
fi
if [[ ! "$poll_seconds" =~ ^[1-9][0-9]*$ ]]; then
    echo "BACKUP_SCHEDULER_POLL_SECONDS must be a positive integer" >&2
    exit 64
fi

IFS=',' read -r -a incremental_hour_list <<<"$incremental_hours"
for configured_hour in "${incremental_hour_list[@]}"; do
    if ! validate_hour "$configured_hour"; then
        echo "BACKUP_INCREMENTAL_HOURS contains an invalid hour" >&2
        exit 64
    fi
done

mkdir -p "$status_dir"

write_atomic_value() {
    local destination=$1
    local value=$2
    local temporary

    temporary=$(mktemp "$status_dir/.scheduler.XXXXXX")
    printf '%s\n' "$value" >"$temporary"
    mv -f "$temporary" "$destination"
}

write_heartbeat() {
    write_atomic_value "$status_dir/scheduler-heartbeat" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

is_incremental_hour() {
    local current_hour=$1
    local candidate

    for candidate in "${incremental_hour_list[@]}"; do
        if [[ $current_hour -eq $candidate ]]; then
            return 0
        fi
    done
    return 1
}

run_scheduled_backup() {
    local operation=$1

    case "$operation" in
        full)
            /usr/local/bin/backup-job.sh "full"
            ;;
        diff)
            /usr/local/bin/backup-job.sh "diff"
            ;;
        incr)
            /usr/local/bin/backup-job.sh "incr"
            ;;
    esac
}

run_retention_if_ready() {
    local guard_exit

    if /usr/local/bin/retention-guard.sh "ready"; then
        /usr/local/bin/backup-job.sh "expire"
    else
        guard_exit=$?
        if [[ $guard_exit -gt 1 ]]; then
            return "$guard_exit"
        fi
        return 0
    fi
}

write_heartbeat
BACKUP_PRESERVE_FAILED_LAST_RUN=true /usr/local/bin/backup-job.sh "stanza"
BACKUP_PRESERVE_FAILED_LAST_RUN=true /usr/local/bin/backup-job.sh "status"
run_retention_if_ready

while true; do
    write_heartbeat
    current_date=$(date -u +%Y-%m-%d)
    current_weekday=$(date -u +%w)
    current_hour=$((10#$(date -u +%H)))
    operation=""

    if [[ $current_hour -eq $daily_hour ]]; then
        if [[ $current_weekday -eq $full_weekday ]]; then
            operation="full"
        else
            operation="diff"
        fi
    elif is_incremental_hour "$current_hour"; then
        operation="incr"
    fi

    if [[ -n "$operation" ]]; then
        schedule_slot="${current_date}-${current_hour}-${operation}"
        last_slot=""
        if [[ -f "$last_slot_file" ]]; then
            last_slot=$(<"$last_slot_file")
        fi
        if [[ "$last_slot" != "$schedule_slot" ]]; then
            run_scheduled_backup "$operation"
            write_atomic_value "$last_slot_file" "$schedule_slot"
            run_retention_if_ready
        fi
    fi

    sleep "$poll_seconds"
done
