#!/usr/bin/env bash
set -Eeuo pipefail

stanza=${PGBACKREST_STANZA:-dcim}
wal_segment_size_bytes=${WAL_SEGMENT_SIZE_BYTES:-16777216}

if [[ ! "$wal_segment_size_bytes" =~ ^[0-9]+$ ]] \
   || (( wal_segment_size_bytes < 1048576 || wal_segment_size_bytes > 1073741824 )) \
   || (( 4294967296 % wal_segment_size_bytes != 0 )); then
    echo "invalid_wal_segment_size" >&2
    exit 64
fi

segments_per_xlog_id=$((4294967296 / wal_segment_size_bytes))
listing_file=$(mktemp)
trap 'rm -f "$listing_file"' EXIT

/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" repo-ls "archive/$stanza" \
    --recurse --output=text >"$listing_file"

mapfile -t segments < <(
    sed -nE 's#^.*/([0-9A-Fa-f]{24})-[^/]+$#\1#p' "$listing_file" \
        | tr '[:lower:]' '[:upper:]' \
        | sort -u
)

if (( ${#segments[@]} == 0 )); then
    echo "wal_archive_empty" >&2
    exit 65
fi

previous_timeline=""
previous_ordinal=0
previous_segment=""

for segment in "${segments[@]}"; do
    timeline=${segment:0:8}
    log_value=$((16#${segment:8:8}))
    segment_value=$((16#${segment:16:8}))
    if (( segment_value >= segments_per_xlog_id )); then
        echo "invalid_wal_segment_name segment=$segment" >&2
        exit 65
    fi
    ordinal=$((log_value * segments_per_xlog_id + segment_value))

    if [[ "$timeline" == "$previous_timeline" ]] && (( ordinal != previous_ordinal + 1 )); then
        echo "wal_gap_detected previous=$previous_segment current=$segment" >&2
        exit 65
    fi

    previous_timeline=$timeline
    previous_ordinal=$ordinal
    previous_segment=$segment
done

printf '{"status":"ok","segment_count":%d,"first_segment":"%s","last_segment":"%s"}\n' \
    "${#segments[@]}" "${segments[0]}" "$previous_segment"
