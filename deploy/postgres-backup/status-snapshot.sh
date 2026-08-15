#!/usr/bin/env bash
set -euo pipefail

umask 077

stanza=${PGBACKREST_STANZA:-dcim}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
postgres_status_sql=${POSTGRES_STATUS_SQL:-/usr/local/share/dcim-dr/postgres-status.sql}
postgres_user=${POSTGRES_USER:-dcim}
postgres_db=${POSTGRES_DB:-dcim}
postgres_socket=${POSTGRES_SOCKET_DIR:-/var/run/postgresql}
password_file=${POSTGRES_PASSWORD_FILE:?POSTGRES_PASSWORD_FILE is required}
retention_days=35

mkdir -p "$status_dir"
/usr/local/bin/validate-secrets.sh "$password_file" postgres_password 16

info_tmp=$(mktemp "$status_dir/.pgbackrest-info.XXXXXX")
postgres_tmp=$(mktemp "$status_dir/.postgres-status.XXXXXX")
summary_tmp=$(mktemp "$status_dir/.backup-status.XXXXXX")
trap 'rm -f "$info_tmp" "$postgres_tmp" "$summary_tmp"' EXIT

/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" info --output=json >"$info_tmp"

export PGPASSWORD
PGPASSWORD=$(<"$password_file")
psql --no-psqlrc --host="$postgres_socket" --username="$postgres_user" --dbname="$postgres_db" \
    --set=ON_ERROR_STOP=1 --tuples-only --no-align --file="$postgres_status_sql" >"$postgres_tmp"
unset PGPASSWORD

compact_info=$(tr -d '\r\n\t ' <"$info_tmp")
full_matches=$(grep -o '"type":"full"' <<<"$compact_info" || true)
if [[ -n "$full_matches" ]]; then
    retention_full_count=$(wc -l <<<"$full_matches" | tr -d ' ')
else
    retention_full_count=0
fi
full_labels=$(
    grep -o '"label":"[0-9]\{8\}-[0-9]\{6\}F"' <<<"$compact_info" \
        | cut -d'"' -f4 \
        || true
)
retention_cutoff_epoch=$(($(date -u +%s) - retention_days * 86400))
retention_window_full_count=0
while IFS= read -r full_label; do
    [[ -n "$full_label" ]] || continue
    full_label_epoch=$(date -u -d \
        "${full_label:0:4}-${full_label:4:2}-${full_label:6:2} ${full_label:9:2}:${full_label:11:2}:${full_label:13:2}" \
        +%s)
    if [[ $full_label_epoch -ge $retention_cutoff_epoch ]]; then
        retention_window_full_count=$((retention_window_full_count + 1))
    fi
done <<<"$full_labels"

timestamp_objects=$(grep -o '"timestamp":{[^}]*}' <<<"$compact_info" || true)
latest_backup_epoch=$(
    sed -n 's/.*"stop":\([0-9][0-9]*\).*/\1/p' <<<"$timestamp_objects" \
        | sort -n \
        | tail -n 1 \
        || true
)
if [[ -n "$latest_backup_epoch" ]]; then
    backup_age_seconds=$(($(date -u +%s) - latest_backup_epoch))
else
    backup_age_seconds=null
fi

failure_code=""
last_run_status="none"
if [[ -f "$status_dir/last-run.json" ]]; then
    failure_code=$(sed -n 's/.*"failure_code":"\([^"]*\)".*/\1/p' "$status_dir/last-run.json")
    last_run_status=$(sed -n 's/.*"status":"\([^"]*\)".*/\1/p' "$status_dir/last-run.json")
fi
if [[ -n "$failure_code" ]]; then
    failure_json="\"$failure_code\""
    health_status=failed
elif [[ "$backup_age_seconds" == "null" ]]; then
    failure_json=null
    health_status=initializing
else
    failure_json=null
    health_status=ok
fi

printf '{"captured_at_utc":"%s","status":"%s","backup_age_seconds":%s,"retention_full_count":%s,"retention_window_full_count":%s,"retention_days":%s,"last_run_status":"%s","failure_code":%s}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$health_status" "$backup_age_seconds" "$retention_full_count" \
    "$retention_window_full_count" "$retention_days" \
    "$last_run_status" "$failure_json" >"$summary_tmp"

mv -f "$info_tmp" "$status_dir/pgbackrest-info.json"
mv -f "$postgres_tmp" "$status_dir/postgres-status.json"
mv -f "$summary_tmp" "$status_dir/backup-status.json"
trap - EXIT
