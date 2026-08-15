"""Story 39.3 隔离恢复、PITR 和一致性检查契约测试。"""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_restore_and_validator_are_isolated_from_source_volumes():
    dr = _yaml("deploy/dr/docker-compose.dr.yml")
    restore = dr["services"]["postgres-restore"]
    validator = dr["services"]["restore-validator"]

    assert restore["entrypoint"] == ["/usr/local/bin/restore-entrypoint.sh"]
    assert restore["restart"] == "no"
    assert restore["healthcheck"]["test"] == ["CMD", "/usr/local/bin/restore-healthcheck.sh"]
    assert validator["command"] == ["/usr/local/bin/restore-validate.sh"]
    assert validator["user"] == "postgres"
    assert validator["depends_on"]["postgres-restore"]["condition"] == "service_healthy"

    restore_volumes = "\n".join(restore["volumes"])
    validator_volumes = "\n".join(validator["volumes"])
    for volumes in (restore_volumes, validator_volumes):
        assert "postgres-primary-data" not in volumes
        assert "postgres-standby-data" not in volumes
    assert "postgres-restore-data:/var/lib/postgresql/data" in restore_volumes
    assert "pgbackrest-repository:/var/lib/pgbackrest:ro" in restore_volumes
    assert "restore-socket:/var/run/postgresql" in restore_volumes
    assert "restore-socket:/var/run/postgresql" in validator_volumes
    assert "dr-status:/var/lib/dcim-dr-status" in validator_volumes
    assert restore["environment"]["EXPECTED_POSTGRES_MAJOR"] == "${EXPECTED_POSTGRES_MAJOR:-16}"
    assert validator["environment"]["EXPECTED_ALEMBIC_HEAD"] == "${EXPECTED_ALEMBIC_HEAD:-20260707_0100}"


def test_restore_job_validates_target_repository_version_and_empty_pgdata():
    job = _text("deploy/postgres-backup/restore-job.sh")

    for target_type in ("latest)", "time)", "lsn)", "name)"):
        assert target_type in job
    assert "invalid_restore_target_type" in job
    assert "invalid_restore_target_value" in job
    assert 'find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit' in job
    assert "non_empty_restore_target" in job
    assert 'run_step "repository_info"' in job
    assert 'run_step "repository_verify"' in job
    assert 'run_step "repository_wal_continuity" /usr/local/bin/wal-continuity-check.sh' in job
    assert "wal_gap_detected" in job
    assert "repository_version_mismatch" in job
    assert 'run_step "cluster_restore"' in job
    assert "--cmd=/usr/local/bin/pgbackrest-wrapper" in job
    assert "--type=default" in job
    assert '--type="$target_type"' in job
    assert "pgbackrest_target=$(date -u -d \"$target_value\" '+%Y-%m-%d %H:%M:%S+00')" in job
    assert '--target="$pgbackrest_target"' in job
    assert "restore-last-run.json" in job
    assert "staged/restore/${run_id}.json" in job
    assert "pgbackrest-info.before-restore.error.txt" in job
    assert "pgbackrest-verify.before-restore.txt" in job
    assert "status:[[:space:]]+error" in job
    assert "pgbackrest-restore.txt" in job
    assert "eval " not in job

    entrypoint = _text("deploy/postgres-backup/restore-entrypoint.sh")
    assert entrypoint.index("restore-job.sh") < entrypoint.index("docker-entrypoint.sh")
    assert "recovery_start_failed" in entrypoint
    assert "RESTORE_START_TIMEOUT_SECONDS" in entrypoint
    assert "postgres_exit=70" in entrypoint


def test_restore_validator_checks_database_and_timescaledb_objects():
    validator = _text("deploy/postgres-backup/restore-validate.sh")
    assert 'run_step "repository_verify"' in validator
    assert 'run_step "required_schema"' in validator
    assert "required_schema_missing" in validator
    assert "expected-schema-tables.txt" in validator
    assert "to_regclass" in validator
    assert 'run_step "pg_amcheck"' in validator
    assert "--install-missing" in validator
    assert "pg_is_in_recovery" in validator
    assert "EXPECTED_ALEMBIC_HEAD" in validator
    assert "database-consistency.sql" in validator
    assert "timescaledb-status.sql" in validator
    assert "database-consistency.json" in validator
    assert "timescaledb-status.json" in validator
    assert "restore-validation.json" in validator
    assert "validation/${run_id}.json" in validator
    assert "pgbackrest-verify.after-restore.txt" in validator
    assert "status:[[:space:]]+error" in validator
    assert "database-consistency.error.txt" in validator
    assert "timescaledb-status.error.txt" in validator
    assert "RESTORE_RECOVERY_TIMEOUT_SECONDS:-14400" in validator

    consistency_sql = _text("deploy/postgres-backup/database-consistency.sql")
    for required in (
        "alembic_version",
        "pg_roles",
        "pg_database",
        "row_count",
        "content_digest",
        "convalidated",
        "pg_sequences",
        "last_value",
        "CREATE TEMP TABLE dcim_restore_write_probe",
    ):
        assert required in consistency_sql
    assert "hashtextextended" in consistency_sql
    assert "bit_xor" in consistency_sql
    assert "string_agg" not in consistency_sql

    timescale_sql = _text("deploy/postgres-backup/timescaledb-status.sql")
    for required in (
        "pg_extension",
        "timescaledb_information.hypertables",
        "timescaledb_information.chunks",
        "timescaledb_information.jobs",
        "timescaledb_information.compression_settings",
        "point_history",
        "policy_compression",
        "policy_retention",
    ):
        assert required in timescale_sql


def test_restore_negative_paths_fail_without_success_marker():
    job = _text("deploy/postgres-backup/restore-job.sh")
    entrypoint = _text("deploy/postgres-backup/restore-entrypoint.sh")
    validator = _text("deploy/postgres-backup/restore-validate.sh")

    assert "repository_info_failed" in job
    assert "repository_verify_failed" in job
    assert "cluster_restore_failed" in job
    assert "recovery_start_failed" in entrypoint
    assert "recovery_target_not_reached" in validator
    assert "database_consistency_failed" in validator
    assert "timescaledb_validation_failed" in validator
    assert job.rindex("write_staged_marker") > job.index('run_step "cluster_restore"')


def test_runtime_image_installs_restore_and_validation_tools():
    dockerfile = _text("deploy/postgres-backup/Dockerfile")
    for script in (
        "restore-job.sh",
        "restore-entrypoint.sh",
        "restore-healthcheck.sh",
        "restore-validate.sh",
    ):
        assert f"COPY deploy/postgres-backup/{script} /usr/local/bin/{script}" in dockerfile
        assert f"/usr/local/bin/{script}" in dockerfile

    for artifact in (
        "postgresql-restore.conf",
        "database-consistency.sql",
        "timescaledb-status.sql",
        "expected-schema-tables.txt",
    ):
        assert f"COPY deploy/postgres-backup/{artifact}" in dockerfile

    assert "COPY deploy/postgres-backup/wal-continuity-check.sh" in dockerfile
    assert "/usr/local/bin/wal-continuity-check.sh" in dockerfile


def test_restore_validator_requires_the_complete_release_schema():
    tables = {
        line.strip()
        for line in _text("deploy/postgres-backup/expected-schema-tables.txt").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert len(tables) == 188
    for required in (
        "users",
        "alarms",
        "operation_logs",
        "power_devices",
        "point_history",
        "linkage_policies",
        "maintenance_advices",
        "training_data_audits",
    ):
        assert required in tables


def test_wal_continuity_checker_rejects_missing_archive_segments():
    checker = _text("deploy/postgres-backup/wal-continuity-check.sh")
    assert "repo-ls" in checker
    assert "--recurse" in checker
    assert "segments_per_xlog_id" in checker
    assert "ordinal != previous_ordinal + 1" in checker
    assert "wal_gap_detected" in checker
