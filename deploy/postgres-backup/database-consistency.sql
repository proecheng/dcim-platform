\set ON_ERROR_STOP on

BEGIN;

CREATE TEMP TABLE dcim_restore_write_probe (
    probe_id bigint PRIMARY KEY,
    probe_value text NOT NULL
);
INSERT INTO dcim_restore_write_probe (probe_id, probe_value) VALUES (1, 'restore-write-ok');

CREATE TEMP TABLE dcim_restore_table_inventory (
    table_name text PRIMARY KEY,
    row_count bigint NOT NULL,
    content_digest text NOT NULL
);

DO $dcim_consistency$
DECLARE
    inventory_record record;
    inventory_count bigint;
    inventory_digest text;
    sequence_record record;
    sequence_last_value numeric;
    sequence_is_called boolean;
    table_max_value numeric;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint AS constraint_record
        JOIN pg_namespace AS namespace_record
          ON namespace_record.oid = constraint_record.connamespace
        WHERE namespace_record.nspname = 'public'
          AND NOT constraint_record.convalidated
    ) THEN
        RAISE EXCEPTION 'public schema contains unvalidated constraints';
    END IF;

    FOR inventory_record IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    LOOP
        EXECUTE format(
            'SELECT count(*), '
            'md5(count(*)::text || '':'' || coalesce(sum(row_hash::numeric), 0)::text || '':'' || '
            'coalesce(bit_xor(row_hash), 0)::text) '
            'FROM (SELECT hashtextextended(row_to_json(source_row)::text, 0) AS row_hash '
            'FROM %I.%I AS source_row) AS hashed_rows',
            inventory_record.schemaname,
            inventory_record.tablename
        )
        INTO inventory_count, inventory_digest;

        INSERT INTO dcim_restore_table_inventory (table_name, row_count, content_digest)
        VALUES (
            format('%I.%I', inventory_record.schemaname, inventory_record.tablename),
            inventory_count,
            inventory_digest
        );
    END LOOP;

    FOR sequence_record IN
        SELECT sequence_namespace.nspname AS sequence_schema,
               sequence_class.relname AS sequence_name,
               table_namespace.nspname AS table_schema,
               table_class.relname AS table_name,
               table_attribute.attname AS column_name
        FROM pg_class AS sequence_class
        JOIN pg_namespace AS sequence_namespace
          ON sequence_namespace.oid = sequence_class.relnamespace
        JOIN pg_depend AS sequence_dependency
          ON sequence_dependency.objid = sequence_class.oid
         AND sequence_dependency.deptype IN ('a', 'i')
        JOIN pg_class AS table_class
          ON table_class.oid = sequence_dependency.refobjid
        JOIN pg_namespace AS table_namespace
          ON table_namespace.oid = table_class.relnamespace
        JOIN pg_attribute AS table_attribute
          ON table_attribute.attrelid = table_class.oid
         AND table_attribute.attnum = sequence_dependency.refobjsubid
        WHERE sequence_class.relkind = 'S'
          AND table_namespace.nspname = 'public'
    LOOP
        EXECUTE format(
            'SELECT last_value::numeric, is_called FROM %I.%I',
            sequence_record.sequence_schema,
            sequence_record.sequence_name
        )
        INTO sequence_last_value, sequence_is_called;

        EXECUTE format(
            'SELECT max(%I)::numeric FROM %I.%I',
            sequence_record.column_name,
            sequence_record.table_schema,
            sequence_record.table_name
        )
        INTO table_max_value;

        IF table_max_value IS NOT NULL
           AND (NOT sequence_is_called OR sequence_last_value < table_max_value) THEN
            RAISE EXCEPTION 'sequence %.% is behind %.%',
                sequence_record.sequence_schema,
                sequence_record.sequence_name,
                sequence_record.table_schema,
                sequence_record.table_name;
        END IF;
    END LOOP;
END
$dcim_consistency$;

SELECT json_build_object(
    'captured_at_utc', to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'alembic_version', (SELECT version_num FROM alembic_version LIMIT 1),
    'roles', (
        SELECT coalesce(
            json_agg(
                json_build_object(
                    'role_name', role_record.rolname,
                    'can_login', role_record.rolcanlogin,
                    'is_superuser', role_record.rolsuper
                )
                ORDER BY role_record.rolname
            ),
            '[]'::json
        )
        FROM pg_roles AS role_record
    ),
    'databases', (
        SELECT coalesce(json_agg(database_record.datname ORDER BY database_record.datname), '[]'::json)
        FROM pg_database AS database_record
        WHERE database_record.datallowconn
    ),
    'extensions', (
        SELECT coalesce(
            json_agg(
                json_build_object('name', extension_record.extname, 'version', extension_record.extversion)
                ORDER BY extension_record.extname
            ),
            '[]'::json
        )
        FROM pg_extension AS extension_record
    ),
    'tables', (
        SELECT coalesce(
            json_agg(
                json_build_object(
                    'table_name', inventory_record.table_name,
                    'row_count', inventory_record.row_count,
                    'content_digest', inventory_record.content_digest
                )
                ORDER BY inventory_record.table_name
            ),
            '[]'::json
        )
        FROM dcim_restore_table_inventory AS inventory_record
    ),
    'constraints', json_build_object(
        'unvalidated_count', (
            SELECT count(*)
            FROM pg_constraint AS constraint_record
            JOIN pg_namespace AS namespace_record
              ON namespace_record.oid = constraint_record.connamespace
            WHERE namespace_record.nspname = 'public'
              AND NOT constraint_record.convalidated
        )
    ),
    'sequences', (
        SELECT coalesce(
            json_agg(
                json_build_object(
                    'sequence_name', format('%I.%I', sequence_record.schemaname, sequence_record.sequencename),
                    'last_value', sequence_record.last_value,
                    'start_value', sequence_record.start_value,
                    'increment_by', sequence_record.increment_by
                )
                ORDER BY sequence_record.schemaname, sequence_record.sequencename
            ),
            '[]'::json
        )
        FROM pg_sequences AS sequence_record
        WHERE sequence_record.schemaname = 'public'
    ),
    'write_probe', (
        SELECT json_build_object(
            'row_count', count(*),
            'value', min(probe_record.probe_value)
        )
        FROM dcim_restore_write_probe AS probe_record
    )
);

ROLLBACK;
