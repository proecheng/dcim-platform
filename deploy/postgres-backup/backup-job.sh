#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

operation=${1:-}
case "$operation" in
    stanza|full|diff|incr|check|verify|expire|status)
        ;;
    *)
        echo "unsupported backup operation" >&2
        exit 64
        ;;
esac

stanza=${PGBACKREST_STANZA:-dcim}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
lock_file="$status_dir/backup-operation.lock"
run_id="$(date -u +%Y%m%dT%H%M%S%N)-$$"
current_step=initializing
failure_code=""
lock_acquired=0
completed=0
preserve_failed_last_run=${BACKUP_PRESERVE_FAILED_LAST_RUN:-false}

case "$preserve_failed_last_run" in
    true|false)
        ;;
    *)
        echo "BACKUP_PRESERVE_FAILED_LAST_RUN must be true or false" >&2
        exit 64
        ;;
esac

mkdir -p "$status_dir" "$status_dir/runs" "$status_dir/success"

write_state() {
    local state=$1
    local exit_code=$2
    local code=$3
    local finished_at
    local run_tmp
    local state_tmp

    finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    run_tmp=$(mktemp "$status_dir/runs/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","operation":"%s","status":"%s","step":"%s","exit_code":%s,"failure_code":"%s","finished_at_utc":"%s"}\n' \
        "$run_id" "$operation" "$state" "$current_step" "$exit_code" "$code" "$finished_at" >"$run_tmp"
    mv -f "$run_tmp" "$status_dir/runs/${run_id}.json"

    if [[ "$state" != "success" || "$preserve_failed_last_run" != "true" || ! -f "$status_dir/last-run.json" ]] \
        || ! grep -q '"status":"failed"' "$status_dir/last-run.json"; then
        state_tmp=$(mktemp "$status_dir/.last-run.XXXXXX")
        printf '{"run_id":"%s","operation":"%s","status":"%s","step":"%s","exit_code":%s,"failure_code":"%s","finished_at_utc":"%s"}\n' \
            "$run_id" "$operation" "$state" "$current_step" "$exit_code" "$code" "$finished_at" >"$state_tmp"
        mv -f "$state_tmp" "$status_dir/last-run.json"
    fi
}

write_success_marker() {
    local success_file="$status_dir/success/${run_id}.json"
    local success_tmp

    success_tmp=$(mktemp "$status_dir/success/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","operation":"%s","verified":true,"published_at_utc":"%s"}\n' \
        "$run_id" "$operation" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$success_tmp"
    mv -f "$success_tmp" "$success_file"
}

cleanup() {
    local exit_code=$?

    trap - EXIT
    if [[ $completed -eq 0 && $lock_acquired -eq 1 ]]; then
        failure_code=${failure_code:-${current_step}_failed}
        write_state "failed" "$exit_code" "$failure_code" || true
    fi
    if [[ $lock_acquired -eq 1 ]]; then
        flock -u 9 || true
    fi
    exit "$exit_code"
}

run_step() {
    current_step=$1
    shift
    "$@"
}

verify_repository() {
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.pgbackrest-verify.XXXXXX")
    set +e
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" verify --output=text >"$temporary" 2>&1
    operation_exit=$?
    set -e
    mv -f "$temporary" "$status_dir/pgbackrest-verify.txt"
    [[ $operation_exit -eq 0 ]] || return "$operation_exit"
    ! grep -Eq '^[[:space:]]*status:[[:space:]]+error[[:space:]]*$' "$status_dir/pgbackrest-verify.txt"
}

exec 9>>"$lock_file"
if ! flock -n 9; then
    current_step=lock
    failure_code=concurrent_operation
    write_state "failed" 75 "$failure_code"
    echo "concurrent_operation" >&2
    exit 75
fi
lock_acquired=1
touch "$lock_file"
trap cleanup EXIT

case "$operation" in
    "stanza")
        run_step "stanza_create" /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" stanza-create
        run_step "repository_check" /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" check
        ;;
    "full"|"diff"|"incr")
        run_step "repository_check" /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" check
        run_step "backup_${operation}" /usr/local/bin/pgbackrest-wrapper \
            --stanza="$stanza" backup --type="$operation" --no-expire-auto
        run_step "repository_verify" verify_repository
        run_step "wal_continuity" /usr/local/bin/wal-continuity-check.sh
        run_step "status_snapshot" /usr/local/bin/status-snapshot.sh
        ;;
    "check")
        run_step "repository_check" /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" check
        ;;
    "verify")
        run_step "repository_verify" verify_repository
        run_step "wal_continuity" /usr/local/bin/wal-continuity-check.sh
        ;;
    "expire")
        run_step "retention_before" /usr/local/bin/retention-guard.sh "before"
        run_step "expire" /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" expire
        run_step "retention_after" /usr/local/bin/retention-guard.sh "after"
        run_step "repository_verify" verify_repository
        run_step "wal_continuity" /usr/local/bin/wal-continuity-check.sh
        run_step "status_snapshot" /usr/local/bin/status-snapshot.sh
        ;;
    "status")
        run_step "status_snapshot" /usr/local/bin/status-snapshot.sh
        ;;
esac

current_step=complete
write_state "success" 0 ""
write_success_marker
completed=1
