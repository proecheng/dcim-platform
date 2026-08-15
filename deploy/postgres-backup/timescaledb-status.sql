\set ON_ERROR_STOP on

DO $dcim_timescale$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        RAISE EXCEPTION 'timescaledb extension is missing';
    END IF;
    IF to_regclass('timescaledb_information.hypertables') IS NULL
       OR to_regclass('timescaledb_information.chunks') IS NULL
       OR to_regclass('timescaledb_information.jobs') IS NULL
       OR to_regclass('timescaledb_information.compression_settings') IS NULL THEN
        RAISE EXCEPTION 'required timescaledb information views are missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.hypertables
        WHERE hypertable_schema = 'public'
          AND hypertable_name = 'point_history'
    ) THEN
        RAISE EXCEPTION 'point_history hypertable is missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.jobs
        WHERE hypertable_schema = 'public'
          AND hypertable_name = 'point_history'
          AND proc_name = 'policy_compression'
    ) THEN
        RAISE EXCEPTION 'point_history compression policy is missing';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.jobs
        WHERE hypertable_schema = 'public'
          AND hypertable_name = 'point_history'
          AND proc_name = 'policy_retention'
    ) THEN
        RAISE EXCEPTION 'point_history retention policy is missing';
    END IF;
END
$dcim_timescale$;

SELECT json_build_object(
    'captured_at_utc', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'extension_version', (
        SELECT extversion
        FROM pg_extension
        WHERE extname = 'timescaledb'
    ),
    'hypertables', (
        SELECT coalesce(json_agg(row_to_json(hypertable_record)), '[]'::json)
        FROM (
            SELECT *
            FROM timescaledb_information.hypertables
            ORDER BY hypertable_schema, hypertable_name
        ) AS hypertable_record
    ),
    'chunks', (
        SELECT coalesce(json_agg(row_to_json(chunk_record)), '[]'::json)
        FROM (
            SELECT *
            FROM timescaledb_information.chunks
            ORDER BY hypertable_schema, hypertable_name, chunk_schema, chunk_name
        ) AS chunk_record
    ),
    'jobs', (
        SELECT coalesce(json_agg(row_to_json(job_record)), '[]'::json)
        FROM (
            SELECT *
            FROM timescaledb_information.jobs
            ORDER BY job_id
        ) AS job_record
    ),
    'compression_settings', (
        SELECT coalesce(json_agg(row_to_json(compression_record)), '[]'::json)
        FROM (
            SELECT *
            FROM timescaledb_information.compression_settings
            ORDER BY hypertable_schema, hypertable_name
        ) AS compression_record
    )
);
