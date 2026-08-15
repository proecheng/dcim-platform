#!/usr/bin/env bash
set -Eeuo pipefail

umask 077

PGDATA=${PGDATA:-/var/lib/postgresql/data}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
start_timeout=${RESTORE_START_TIMEOUT_SECONDS:-600}
postgres_user=${POSTGRES_USER:-dcim}
postgres_config=${POSTGRES_RESTORE_CONFIG:-/etc/postgresql/postgresql-restore.conf}

if [[ ! "$start_timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "RESTORE_START_TIMEOUT_SECONDS must be a positive integer" >&2
    exit 64
fi

mkdir -p "$PGDATA" "$status_dir" /var/run/postgresql
chown postgres:postgres "$PGDATA" "$status_dir" /var/run/postgresql

write_server_state() {
    local state=$1
    local failure_code=$2
    local temporary

    temporary=$(mktemp "$status_dir/.restore-server-status.XXXXXX")
    printf '{"status":"%s","failure_code":"%s","captured_at_utc":"%s"}\n' \
        "$state" "$failure_code" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$temporary"
    mv -f "$temporary" "$status_dir/restore-server-status.json"
}

gosu postgres /usr/local/bin/restore-job.sh

/usr/local/bin/docker-entrypoint.sh postgres -c "config_file=$postgres_config" &
postgres_pid=$!

# shellcheck disable=SC2329
shutdown_postgres() {
    if kill -0 "$postgres_pid" 2>/dev/null; then
        kill -TERM "$postgres_pid" 2>/dev/null || true
        wait "$postgres_pid" 2>/dev/null || true
    fi
    exit 143
}
trap shutdown_postgres TERM INT

deadline=$((SECONDS + start_timeout))
while true; do
    if ! kill -0 "$postgres_pid" 2>/dev/null; then
        set +e
        wait "$postgres_pid"
        postgres_exit=$?
        set -e
        write_server_state "failed" "recovery_start_failed"
        if [[ $postgres_exit -eq 0 ]]; then
            postgres_exit=70
        fi
        exit "$postgres_exit"
    fi
    if pg_isready --host=/var/run/postgresql --username="$postgres_user" >/dev/null 2>&1; then
        write_server_state "ready" ""
        break
    fi
    if [[ $SECONDS -ge $deadline ]]; then
        write_server_state "failed" "recovery_start_failed"
        kill -TERM "$postgres_pid" 2>/dev/null || true
        wait "$postgres_pid" 2>/dev/null || true
        exit 70
    fi
    sleep 1
done

set +e
wait "$postgres_pid"
postgres_exit=$?
set -e
if [[ $postgres_exit -ne 0 ]]; then
    write_server_state "failed" "recovery_server_stopped"
fi
exit "$postgres_exit"
