#!/usr/bin/env bash
set -euo pipefail

umask 077

mode=${1:-}
case "$mode" in
    before|after|ready)
        ;;
    *)
        echo "retention guard mode must be before, after, or ready" >&2
        exit 64
        ;;
esac

stanza=${PGBACKREST_STANZA:-dcim}
status_dir=${BACKUP_STATUS_DIR:-/var/lib/dcim-dr-status}
retention_days=35
minimum_full_count=5
if [[ -n "${BACKUP_RETENTION_DAYS:-}" ]]; then
    if [[ ! "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ || $BACKUP_RETENTION_DAYS -lt 35 ]]; then
        echo "BACKUP_RETENTION_DAYS cannot be lower than 35" >&2
        exit 64
    fi
    retention_days=$BACKUP_RETENTION_DAYS
fi
if [[ -n "${BACKUP_MINIMUM_FULL_COUNT:-}" ]]; then
    if [[ ! "$BACKUP_MINIMUM_FULL_COUNT" =~ ^[0-9]+$ || $BACKUP_MINIMUM_FULL_COUNT -lt 5 ]]; then
        echo "BACKUP_MINIMUM_FULL_COUNT cannot be lower than 5" >&2
        exit 64
    fi
    minimum_full_count=$BACKUP_MINIMUM_FULL_COUNT
fi
before_snapshot="$status_dir/pgbackrest-info.before-expire.json"
after_snapshot="$status_dir/pgbackrest-info.after-expire.json"
baseline_file="$status_dir/.retention-before.state"
retention_full_count=0
retention_window_full_count=0
latest_backup=""

mkdir -p "$status_dir"

capture_snapshot() {
    local destination=$1
    local temporary

    temporary=$(mktemp "$status_dir/.pgbackrest-info.XXXXXX")
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" info --output=json >"$temporary"
    mv -f "$temporary" "$destination"
}

parse_snapshot() {
    local snapshot=$1
    local compact
    local cutoff_epoch
    local full_label
    local full_label_epoch
    local full_labels
    local full_matches

    compact=$(tr -d '\r\n\t ' <"$snapshot")
    if grep -q '"error":true' <<<"$compact"; then
        echo "repository_info_error" >&2
        return 2
    fi

    full_matches=$(grep -o '"type":"full"' <<<"$compact" || true)
    if [[ -n "$full_matches" ]]; then
        retention_full_count=$(wc -l <<<"$full_matches" | tr -d ' ')
    else
        retention_full_count=0
    fi
    full_labels=$(
        grep -o '"label":"[0-9]\{8\}-[0-9]\{6\}F"' <<<"$compact" \
            | cut -d'"' -f4 \
            || true
    )
    if [[ -n "$full_labels" && $(wc -l <<<"$full_labels" | tr -d ' ') -ne $retention_full_count ]]; then
        echo "full_backup_label_count_mismatch" >&2
        return 2
    fi
    cutoff_epoch=$(($(date -u +%s) - retention_days * 86400))
    retention_window_full_count=0
    while IFS= read -r full_label; do
        [[ -n "$full_label" ]] || continue
        full_label_epoch=$(date -u -d \
            "${full_label:0:4}-${full_label:4:2}-${full_label:6:2} ${full_label:9:2}:${full_label:11:2}:${full_label:13:2}" \
            +%s) || {
                echo "invalid_full_backup_label" >&2
                return 2
            }
        if [[ $full_label_epoch -ge $cutoff_epoch ]]; then
            retention_window_full_count=$((retention_window_full_count + 1))
        fi
    done <<<"$full_labels"
    latest_backup=$(
        grep -o '"label":"[^"]*"' <<<"$compact" \
            | cut -d'"' -f4 \
            | LC_ALL=C sort \
            | tail -n 1 \
            || true
    )

    if [[ -z "$latest_backup" ]]; then
        if [[ "$mode" == "ready" ]]; then
            return 1
        fi
        echo "empty_backup_chain" >&2
        return 2
    fi
}

write_retention_status() {
    local phase=$1
    local temporary

    temporary=$(mktemp "$status_dir/.retention-status.XXXXXX")
    printf '{"phase":"%s","retention_full_count":%s,"retention_window_full_count":%s,"retention_days":%s,"minimum_full_count":%s,"latest_backup":"%s","captured_at_utc":"%s"}\n' \
        "$phase" "$retention_full_count" "$retention_window_full_count" "$retention_days" "$minimum_full_count" "$latest_backup" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$temporary"
    mv -f "$temporary" "$status_dir/retention-status.json"
}

if [[ "$mode" == "ready" ]]; then
    ready_snapshot=$(mktemp "$status_dir/.pgbackrest-ready.XXXXXX")
    trap 'rm -f "$ready_snapshot"' EXIT
    /usr/local/bin/pgbackrest-wrapper --stanza="$stanza" info --output=json >"$ready_snapshot"
    parse_exit=0
    parse_snapshot "$ready_snapshot" || parse_exit=$?
    if [[ $parse_exit -eq 1 ]]; then
        exit 1
    fi
    if [[ $parse_exit -ne 0 ]]; then
        exit "$parse_exit"
    fi
    if [[ $retention_full_count -lt $minimum_full_count || $retention_window_full_count -lt $minimum_full_count ]]; then
        exit 1
    fi
    exit 0
fi

if [[ "$mode" == "before" ]]; then
    capture_snapshot "$before_snapshot"
    parse_snapshot "$before_snapshot"
    if [[ $retention_full_count -lt $minimum_full_count || $retention_window_full_count -lt $minimum_full_count ]]; then
        echo "minimum_full_count_not_met" >&2
        exit 65
    fi

    baseline_tmp=$(mktemp "$status_dir/.retention-before.XXXXXX")
    printf '%s\n%s\n' "$latest_backup" "$retention_full_count" >"$baseline_tmp"
    mv -f "$baseline_tmp" "$baseline_file"
    write_retention_status "before"
    exit 0
fi

if [[ ! -f "$baseline_file" ]]; then
    echo "retention_baseline_missing" >&2
    exit 66
fi

before_latest=$(sed -n '1p' "$baseline_file")
capture_snapshot "$after_snapshot"
parse_snapshot "$after_snapshot"
if [[ $retention_full_count -lt $minimum_full_count || $retention_window_full_count -lt $minimum_full_count ]]; then
    echo "minimum_full_count_not_met_after_expire" >&2
    exit 65
fi
if [[ "$latest_backup" != "$before_latest" ]]; then
    echo "latest_backup_changed" >&2
    exit 65
fi
write_retention_status "after"
