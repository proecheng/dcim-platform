#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

stanza=${PGBACKREST_STANZA:-dcim}
target_type=${RESTORE_TARGET_TYPE:-latest}
target_value=${RESTORE_TARGET_VALUE:-}
expected_postgres_major=${EXPECTED_POSTGRES_MAJOR:-16}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
PGDATA=${PGDATA:-/var/lib/postgresql/data}
lock_dir="$status_dir/restore-operation.lock"
run_id="$(date -u +%Y%m%dT%H%M%S%N)-$$"
current_step=target_validation
failure_code=""
lock_acquired=0
completed=0

mkdir -p "$status_dir" "$status_dir/restore-runs" "$status_dir/staged/restore"

failure_code_for_step() {
    case "$current_step" in
        repository_info) printf '%s\n' "repository_info_failed" ;;
        repository_verify) printf '%s\n' "repository_verify_failed" ;;
        repository_wal_continuity) printf '%s\n' "wal_gap_detected" ;;
        repository_version) printf '%s\n' "repository_version_mismatch" ;;
        cluster_restore) printf '%s\n' "cluster_restore_failed" ;;
        *) printf '%s\n' "${current_step}_failed" ;;
    esac
}

write_state() {
    local state=$1
    local exit_code=$2
    local code=$3
    local finished_at
    local latest_tmp
    local run_tmp

    finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    run_tmp=$(mktemp "$status_dir/restore-runs/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","status":"%s","step":"%s","target_type":"%s","target_value":"%s","exit_code":%s,"failure_code":"%s","finished_at_utc":"%s"}\n' \
        "$run_id" "$state" "$current_step" "$target_type" "$target_value" "$exit_code" "$code" "$finished_at" >"$run_tmp"
    mv -f "$run_tmp" "$status_dir/restore-runs/${run_id}.json"

    latest_tmp=$(mktemp "$status_dir/.restore-last-run.XXXXXX")
    printf '{"run_id":"%s","status":"%s","step":"%s","target_type":"%s","target_value":"%s","exit_code":%s,"failure_code":"%s","finished_at_utc":"%s"}\n' \
        "$run_id" "$state" "$current_step" "$target_type" "$target_value" "$exit_code" "$code" "$finished_at" >"$latest_tmp"
    mv -f "$latest_tmp" "$status_dir/restore-last-run.json"
}

write_staged_marker() {
    local staged_file="$status_dir/staged/restore/${run_id}.json"
    local staged_tmp

    staged_tmp=$(mktemp "$status_dir/staged/restore/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","target_type":"%s","target_value":"%s","restore_staged":true,"validated":false,"published_at_utc":"%s"}\n' \
        "$run_id" "$target_type" "$target_value" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$staged_tmp"
    mv -f "$staged_tmp" "$staged_file"
}

fail_before_lock() {
    local code=$1
    local exit_code=$2

    failure_code=$code
    write_state "failed" "$exit_code" "$failure_code"
    echo "$failure_code" >&2
    exit "$exit_code"
}

cleanup() {
    local exit_code=$?

    trap - EXIT
    if [[ $completed -eq 0 && $lock_acquired -eq 1 ]]; then
        failure_code=${failure_code:-$(failure_code_for_step)}
        write_state "failed" "$exit_code" "$failure_code" || true
    fi
    if [[ $lock_acquired -eq 1 ]]; then
        rm -f "$lock_dir/owner"
        rmdir "$lock_dir" 2>/dev/null || true
    fi
    exit "$exit_code"
}

run_step() {
    current_step=$1
    shift
    "$@"
}

case "$target_type" in
    latest)
        if [[ -n "$target_value" ]]; then
            target_value="invalid"
            fail_before_lock "invalid_restore_target_value" 64
        fi
        ;;
    time)
        if [[ ! "$target_value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] \
           || [[ "$(date -u -d "$target_value" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)" != "$target_value" ]]; then
            target_value="invalid"
            fail_before_lock "invalid_restore_target_value" 64
        fi
        ;;
    lsn)
        if [[ ! "$target_value" =~ ^[0-9A-Fa-f]+/[0-9A-Fa-f]+$ ]]; then
            target_value="invalid"
            fail_before_lock "invalid_restore_target_value" 64
        fi
        ;;
    name)
        if [[ ! "$target_value" =~ ^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$ ]]; then
            target_value="invalid"
            fail_before_lock "invalid_restore_target_value" 64
        fi
        ;;
    *)
        target_type="invalid"
        target_value="invalid"
        fail_before_lock "invalid_restore_target_type" 64
        ;;
esac

if [[ "$expected_postgres_major" != "16" ]]; then
    current_step=repository_version
    fail_before_lock "repository_version_mismatch" 65
fi

if [[ "${RESTORE_ISOLATION_ID:-}" != "dcim-story-39-3-restore" ]]; then
    current_step=isolation_guard
    fail_before_lock "restore_isolation_guard_failed" 78
fi
if [[ -L "$PGDATA" ]]; then
    current_step=target_validation
    fail_before_lock "restore_target_symlink" 65
fi
if [[ ! -d "$PGDATA" ]]; then
    current_step=target_validation
    fail_before_lock "restore_target_missing" 65
fi
if [[ -n "$(find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    current_step=target_validation
    fail_before_lock "non_empty_restore_target" 65
fi

if ! mkdir "$lock_dir"; then
    current_step=lock
    fail_before_lock "concurrent_restore" 75
fi
lock_acquired=1
printf '%s\n' "$run_id" >"$lock_dir/owner"
trap cleanup EXIT

capture_repository_info() {
    local error_temporary
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.pgbackrest-info.before-restore.XXXXXX")
    error_temporary=$(mktemp "$status_dir/.pgbackrest-info.before-restore.error.XXXXXX")
    set +e
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" info --output=json \
        >"$temporary" 2>"$error_temporary"
    operation_exit=$?
    set -e
    mv -f "$error_temporary" "$status_dir/pgbackrest-info.before-restore.error.txt"
    if [[ $operation_exit -eq 0 ]]; then
        mv -f "$temporary" "$status_dir/pgbackrest-info.before-restore.json"
    else
        mv -f "$temporary" "$status_dir/pgbackrest-info.before-restore.partial.json"
    fi
    return "$operation_exit"
}

capture_repository_verify() {
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.pgbackrest-verify.before-restore.XXXXXX")
    set +e
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" verify --output=text >"$temporary" 2>&1
    operation_exit=$?
    set -e
    mv -f "$temporary" "$status_dir/pgbackrest-verify.before-restore.txt"
    [[ $operation_exit -eq 0 ]] || return "$operation_exit"
    ! grep -Eq '^[[:space:]]*status:[[:space:]]+error[[:space:]]*$' \
        "$status_dir/pgbackrest-verify.before-restore.txt"
}

restore_cluster() {
    local operation_exit
    local pgbackrest_target=$target_value
    local restore_args=(
        --stanza="$stanza"
        restore
        --cmd=/usr/local/bin/pgbackrest-wrapper
    )
    local temporary

    if [[ "$target_type" == "time" ]]; then
        pgbackrest_target=$(date -u -d "$target_value" '+%Y-%m-%d %H:%M:%S+00')
    fi
    if [[ "$target_type" == "latest" ]]; then
        restore_args+=(
            --type=default
            --target-timeline=latest
        )
    else
        restore_args+=(
            --type="$target_type"
            --target="$pgbackrest_target"
            --target-action=promote
            --target-timeline=latest
        )
    fi
    temporary=$(mktemp "$status_dir/.pgbackrest-restore.XXXXXX")
    set +e
    /usr/local/bin/pgbackrest-wrapper "${restore_args[@]}" >"$temporary" 2>&1
    operation_exit=$?
    set -e
    mv -f "$temporary" "$status_dir/pgbackrest-restore.txt"
    return "$operation_exit"
}

run_step "repository_info" capture_repository_info
repository_info=$(tr -d '\r\n\t ' <"$status_dir/pgbackrest-info.before-restore.json")
if grep -q '"error":true' <<<"$repository_info" || ! grep -q '"label":"' <<<"$repository_info"; then
    false
fi

current_step=repository_version
if [[ "$(postgres --version)" != *" ${expected_postgres_major}."* ]] \
   || ! grep -q "\"version\":\"${expected_postgres_major}\"" <<<"$repository_info"; then
    false
fi

run_step "repository_verify" capture_repository_verify
run_step "repository_wal_continuity" /usr/local/bin/wal-continuity-check.sh
run_step "cluster_restore" restore_cluster

current_step=repository_version
if [[ ! -f "$PGDATA/PG_VERSION" || "$(<"$PGDATA/PG_VERSION")" != "$expected_postgres_major" ]]; then
    false
fi

current_step=complete
write_state "success" 0 ""
write_staged_marker
completed=1
