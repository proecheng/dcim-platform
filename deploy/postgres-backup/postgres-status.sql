SELECT json_build_object(
    'captured_at_utc', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'current_lsn', pg_current_wal_lsn(),
    'archiver', (
        SELECT row_to_json(a)
        FROM (
            SELECT archived_count,
                   failed_count,
                   last_archived_wal,
                   last_archived_time,
                   last_failed_wal,
                   last_failed_time,
                   CASE
                       WHEN last_archived_time IS NULL THEN NULL
                       ELSE extract(epoch FROM clock_timestamp() - last_archived_time)::bigint
                   END AS archive_age_seconds
            FROM pg_stat_archiver
        ) AS a
    ),
    'replication', (
        SELECT coalesce(json_agg(row_to_json(r)), '[]'::json)
        FROM (
            SELECT application_name, client_addr, state, sync_state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
                   pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
                   extract(epoch FROM write_lag) AS write_lag_seconds,
                   extract(epoch FROM flush_lag) AS flush_lag_seconds,
                   extract(epoch FROM replay_lag) AS replay_lag_seconds
            FROM pg_stat_replication
            ORDER BY application_name
        ) AS r
    ),
    'slots', (
        SELECT coalesce(json_agg(row_to_json(s)), '[]'::json)
        FROM (
            SELECT slot_name, slot_type, active, restart_lsn,
                   pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_wal_bytes,
                   pg_size_bytes(current_setting('max_slot_wal_keep_size')) AS slot_wal_limit_bytes,
                   round(
                       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
                       / nullif(pg_size_bytes(current_setting('max_slot_wal_keep_size')), 0),
                       6
                   ) AS slot_wal_utilization_ratio
            FROM pg_replication_slots
            ORDER BY slot_name
        ) AS s
    )
);
