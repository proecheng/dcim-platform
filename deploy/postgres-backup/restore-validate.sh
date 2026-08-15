#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

stanza=${PGBACKREST_STANZA:-dcim}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
postgres_user=${POSTGRES_USER:-dcim}
postgres_db=${POSTGRES_DB:-dcim}
postgres_socket=${POSTGRES_SOCKET_DIR:-/var/run/postgresql}
password_file=${POSTGRES_PASSWORD_FILE:?POSTGRES_PASSWORD_FILE is required}
expected_alembic_head=${EXPECTED_ALEMBIC_HEAD:?EXPECTED_ALEMBIC_HEAD is required}
recovery_timeout=${RESTORE_RECOVERY_TIMEOUT_SECONDS:-14400}
consistency_sql=${DATABASE_CONSISTENCY_SQL:-/usr/local/share/dcim-dr/database-consistency.sql}
timescale_sql=${TIMESCALEDB_STATUS_SQL:-/usr/local/share/dcim-dr/timescaledb-status.sql}
required_schema_file=${EXPECTED_SCHEMA_TABLES_FILE:-/usr/local/share/dcim-dr/expected-schema-tables.txt}
lock_dir="$status_dir/restore-validation.lock"
run_id="$(date -u +%Y%m%dT%H%M%S%N)-$$"
current_step=initializing
failure_code=""
lock_acquired=0
completed=0

if [[ ! "$recovery_timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "RESTORE_RECOVERY_TIMEOUT_SECONDS must be a positive integer" >&2
    exit 64
fi

mkdir -p "$status_dir" "$status_dir/validation-runs" "$status_dir/success/validation"
/usr/local/bin/validate-secrets.sh "$password_file" postgres_password 16

failure_code_for_step() {
    case "$current_step" in
        recovery_target) printf '%s\n' "recovery_target_not_reached" ;;
        repository_verify) printf '%s\n' "repository_verify_failed" ;;
        required_schema) printf '%s\n' "required_schema_missing" ;;
        pg_amcheck) printf '%s\n' "pg_amcheck_failed" ;;
        alembic_head) printf '%s\n' "alembic_head_mismatch" ;;
        database_consistency) printf '%s\n' "database_consistency_failed" ;;
        timescaledb_validation) printf '%s\n' "timescaledb_validation_failed" ;;
        *) printf '%s\n' "${current_step}_failed" ;;
    esac
}

write_state() {
    local state=$1
    local exit_code=$2
    local code=$3
    local captured_at
    local latest_tmp
    local run_tmp
    local validation_tmp

    captured_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    run_tmp=$(mktemp "$status_dir/validation-runs/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","status":"%s","step":"%s","exit_code":%s,"failure_code":"%s","captured_at_utc":"%s"}\n' \
        "$run_id" "$state" "$current_step" "$exit_code" "$code" "$captured_at" >"$run_tmp"
    mv -f "$run_tmp" "$status_dir/validation-runs/${run_id}.json"

    latest_tmp=$(mktemp "$status_dir/.restore-validation-last-run.XXXXXX")
    printf '{"run_id":"%s","status":"%s","step":"%s","exit_code":%s,"failure_code":"%s","captured_at_utc":"%s"}\n' \
        "$run_id" "$state" "$current_step" "$exit_code" "$code" "$captured_at" >"$latest_tmp"
    mv -f "$latest_tmp" "$status_dir/restore-validation-last-run.json"

    validation_tmp=$(mktemp "$status_dir/.restore-validation.XXXXXX")
    printf '{"run_id":"%s","status":"%s","step":"%s","exit_code":%s,"failure_code":"%s","captured_at_utc":"%s"}\n' \
        "$run_id" "$state" "$current_step" "$exit_code" "$code" "$captured_at" >"$validation_tmp"
    mv -f "$validation_tmp" "$status_dir/restore-validation.json"
}

write_success_marker() {
    local success_file="$status_dir/success/validation/${run_id}.json"
    local success_tmp

    success_tmp=$(mktemp "$status_dir/success/validation/.${run_id}.XXXXXX")
    printf '{"run_id":"%s","validated":true,"published_at_utc":"%s"}\n' \
        "$run_id" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$success_tmp"
    mv -f "$success_tmp" "$success_file"
}

cleanup() {
    local exit_code=$?

    trap - EXIT
    unset PGPASSWORD || true
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

if ! mkdir "$lock_dir"; then
    echo "concurrent_restore_validation" >&2
    exit 75
fi
lock_acquired=1
printf '%s\n' "$run_id" >"$lock_dir/owner"
trap cleanup EXIT

export PGPASSWORD
PGPASSWORD=$(<"$password_file")
psql_base=(
    psql
    --no-psqlrc
    --host="$postgres_socket"
    --username="$postgres_user"
    --dbname="$postgres_db"
    --set=ON_ERROR_STOP=1
    --tuples-only
    --no-align
    --quiet
)

wait_for_recovery_target() {
    local deadline=$((SECONDS + recovery_timeout))
    local recovery_state

    while [[ $SECONDS -lt $deadline ]]; do
        recovery_state=$("${psql_base[@]}" --command="SELECT pg_is_in_recovery()" 2>/dev/null || true)
        if [[ "$recovery_state" == "f" ]]; then
            return 0
        fi
        sleep 1
    done
    return 1
}

capture_repository_verify() {
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.pgbackrest-verify.after-restore.XXXXXX")
    set +e
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" verify --output=text >"$temporary" 2>&1
    operation_exit=$?
    set -e
    mv -f "$temporary" "$status_dir/pgbackrest-verify.after-restore.txt"
    [[ $operation_exit -eq 0 ]] || return "$operation_exit"
    ! grep -Eq '^[[:space:]]*status:[[:space:]]+error[[:space:]]*$' \
        "$status_dir/pgbackrest-verify.after-restore.txt"
}

validate_required_schema() {
    local error_temporary
    local expected_count=0
    local missing_temporary
    local operation_exit
    local query_values=""
    local table_name

    [[ -s "$required_schema_file" ]] || return 66
    while IFS= read -r table_name || [[ -n "$table_name" ]]; do
        [[ -z "$table_name" || "$table_name" == \#* ]] && continue
        [[ "$table_name" =~ ^[a-z][a-z0-9_]*$ ]] || return 64
        query_values+="('${table_name}'),"
        expected_count=$((expected_count + 1))
    done <"$required_schema_file"
    [[ $expected_count -gt 0 ]] || return 66
    query_values=${query_values%,}

    missing_temporary=$(mktemp "$status_dir/.required-schema-missing.XXXXXX")
    error_temporary=$(mktemp "$status_dir/.required-schema.error.XXXXXX")
    set +e
    "${psql_base[@]}" --command="WITH required(name) AS (VALUES ${query_values})
        SELECT name FROM required
        WHERE to_regclass('public.' || quote_ident(name)) IS NULL
        ORDER BY name" >"$missing_temporary" 2>"$error_temporary"
    operation_exit=$?
    set -e
    mv -f "$error_temporary" "$status_dir/required-schema.error.txt"
    mv -f "$missing_temporary" "$status_dir/required-schema-missing.txt"
    printf '%s\n' "$expected_count" >"$status_dir/required-schema-expected-count.txt"
    [[ $operation_exit -eq 0 ]] || return "$operation_exit"
    [[ ! -s "$status_dir/required-schema-missing.txt" ]]
}

capture_pg_amcheck() {
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.pg-amcheck.XXXXXX")
    set +e
    pg_amcheck --host="$postgres_socket" --username="$postgres_user" --all --install-missing --verbose \
        >"$temporary" 2>&1
    operation_exit=$?
    set -e
    mv -f "$temporary" "$status_dir/pg-amcheck.txt"
    return "$operation_exit"
}

validate_alembic_head() {
    local actual_head
    local error_temporary
    local operation_exit

    error_temporary=$(mktemp "$status_dir/.alembic-head.error.XXXXXX")
    set +e
    actual_head=$("${psql_base[@]}" --command="SELECT version_num FROM alembic_version" 2>"$error_temporary")
    operation_exit=$?
    set -e
    mv -f "$error_temporary" "$status_dir/alembic-head.error.txt"
    printf '%s\n' "$actual_head" >"$status_dir/alembic-head.txt"
    [[ $operation_exit -eq 0 ]] || return "$operation_exit"
    [[ "$actual_head" == "$expected_alembic_head" ]]
}

capture_database_consistency() {
    local error_temporary
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.database-consistency.XXXXXX")
    error_temporary=$(mktemp "$status_dir/.database-consistency.error.XXXXXX")
    set +e
    "${psql_base[@]}" --file="$consistency_sql" >"$temporary" 2>"$error_temporary"
    operation_exit=$?
    set -e
    mv -f "$error_temporary" "$status_dir/database-consistency.error.txt"
    if [[ $operation_exit -eq 0 && -s "$temporary" ]]; then
        mv -f "$temporary" "$status_dir/database-consistency.json"
        return 0
    fi
    mv -f "$temporary" "$status_dir/database-consistency.partial.json"
    [[ $operation_exit -ne 0 ]] && return "$operation_exit"
    return 1
}

capture_timescaledb_status() {
    local error_temporary
    local operation_exit
    local temporary

    temporary=$(mktemp "$status_dir/.timescaledb-status.XXXXXX")
    error_temporary=$(mktemp "$status_dir/.timescaledb-status.error.XXXXXX")
    set +e
    "${psql_base[@]}" --file="$timescale_sql" >"$temporary" 2>"$error_temporary"
    operation_exit=$?
    set -e
    mv -f "$error_temporary" "$status_dir/timescaledb-status.error.txt"
    if [[ $operation_exit -eq 0 && -s "$temporary" ]]; then
        mv -f "$temporary" "$status_dir/timescaledb-status.json"
        return 0
    fi
    mv -f "$temporary" "$status_dir/timescaledb-status.partial.json"
    [[ $operation_exit -ne 0 ]] && return "$operation_exit"
    return 1
}

run_step "recovery_target" wait_for_recovery_target
run_step "repository_verify" capture_repository_verify
run_step "required_schema" validate_required_schema
run_step "pg_amcheck" capture_pg_amcheck
run_step "alembic_head" validate_alembic_head
run_step "database_consistency" capture_database_consistency
run_step "timescaledb_validation" capture_timescaledb_status

current_step=complete
write_state "success" 0 ""
write_success_marker
completed=1
unset PGPASSWORD
