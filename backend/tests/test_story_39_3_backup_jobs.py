"""Story 39.3 pgBackRest 备份、保留和状态生产端契约测试。"""

from pathlib import Path
import re

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def test_backup_scheduler_is_a_single_external_worker():
    dr = _yaml("deploy/dr/docker-compose.dr.yml")
    scheduler = dr["services"]["backup-scheduler"]

    assert scheduler["command"] == ["/usr/local/bin/backup-scheduler.sh"]
    assert scheduler["restart"] == "on-failure:3"
    assert scheduler["user"] == "postgres"
    assert "postgres-socket:/var/run/postgresql" in scheduler["volumes"]
    assert "dr-status:/var/lib/dcim-dr-status" in scheduler["volumes"]
    assert "postgres_password" in scheduler["secrets"]
    assert scheduler["healthcheck"]["test"] == ["CMD", "/usr/local/bin/backup-healthcheck.sh"]

    scheduler_script = _text("deploy/postgres-backup/backup-scheduler.sh")
    assert "BACKUP_FULL_WEEKDAY" in scheduler_script
    assert "BACKUP_DAILY_HOUR" in scheduler_script
    assert "BACKUP_INCREMENTAL_HOURS" in scheduler_script
    assert 'backup-job.sh "full"' in scheduler_script
    assert 'backup-job.sh "diff"' in scheduler_script
    assert 'backup-job.sh "incr"' in scheduler_script

    assert "backup-scheduler" not in _text("backend/app/main.py")


def test_backup_job_uses_atomic_lock_validation_and_markers():
    job = _text("deploy/postgres-backup/backup-job.sh")

    assert 'case "$operation" in' in job
    assert "stanza|full|diff|incr|check|verify|expire|status" in job
    assert 'exec 9>>"$lock_file"' in job
    assert "flock -n 9" in job
    assert 'mkdir "$lock_dir"' not in job
    assert "concurrent_operation" in job
    assert "exit 75" in job
    assert 'mktemp "$status_dir/.last-run.XXXXXX"' in job
    assert 'mv -f "$state_tmp" "$status_dir/last-run.json"' in job
    assert "success/${run_id}.json" in job
    assert "stanza-create" in job
    assert 'run_step "repository_check"' in job
    assert 'run_step "repository_verify"' in job
    assert 'run_step "wal_continuity" /usr/local/bin/wal-continuity-check.sh' in job
    assert "--output=text" in job
    assert "status:[[:space:]]+error" in job
    assert 'run_step "backup_${operation}"' in job
    assert 'run_step "expire"' in job

    dockerfile = _text("deploy/postgres-backup/Dockerfile")
    assert "util-linux" in dockerfile


def test_scheduler_bootstrap_preserves_failure_and_empty_repository_is_not_fatal():
    scheduler = _text("deploy/postgres-backup/backup-scheduler.sh")
    assert 'BACKUP_PRESERVE_FAILED_LAST_RUN=true /usr/local/bin/backup-job.sh "stanza"' in scheduler
    assert 'BACKUP_PRESERVE_FAILED_LAST_RUN=true /usr/local/bin/backup-job.sh "status"' in scheduler

    job = _text("deploy/postgres-backup/backup-job.sh")
    assert "preserve_failed_last_run=${BACKUP_PRESERVE_FAILED_LAST_RUN:-false}" in job
    assert 'grep -q \'"status":"failed"\'' in job

    guard = _text("deploy/postgres-backup/retention-guard.sh")
    empty_chain = guard.index('if [[ -z "$latest_backup" ]]')
    ready_skip = guard.index('if [[ "$mode" == "ready" ]]', empty_chain)
    nonfatal_return = guard.index("return 1", ready_skip)
    fatal_error = guard.index('echo "empty_backup_chain"', nonfatal_return)
    assert empty_chain < ready_skip < nonfatal_return < fatal_error


def test_retention_is_time_bounded_and_latest_chain_is_guarded():
    config = _text("deploy/postgres-backup/pgbackrest.conf")
    assert "repo1-retention-full-type=time" in config
    assert "repo1-retention-full=35" in config
    assert "repo1-retention-archive-type=full" in config
    archive_retention = re.search(r"^repo1-retention-archive=(\d+)$", config, re.MULTILINE)
    assert archive_retention is not None
    assert int(archive_retention.group(1)) >= 6
    assert "expire-auto=n" in config

    guard = _text("deploy/postgres-backup/retention-guard.sh")
    assert '"type":"full"' in guard
    assert "minimum_full_count=5" in guard
    assert "retention_full_count" in guard
    assert "retention_window_full_count" in guard
    assert "latest_backup_changed" in guard
    assert "pgbackrest-info.before-expire.json" in guard
    assert "pgbackrest-info.after-expire.json" in guard

    job = _text("deploy/postgres-backup/backup-job.sh")
    assert "--no-expire-auto" in job
    expire_block = job[job.index('"expire")') : job.index('"status")')]
    assert expire_block.index('retention-guard.sh "before"') < expire_block.index('run_step "expire"')
    assert expire_block.index('run_step "expire"') < expire_block.index('retention-guard.sh "after"')
    assert expire_block.index('retention-guard.sh "after"') < expire_block.index('run_step "repository_verify"')


def test_status_snapshot_exposes_required_machine_metrics():
    status = _text("deploy/postgres-backup/status-snapshot.sh")
    assert "pgbackrest-info.json" in status
    assert "postgres-status.json" in status
    assert "backup-status.json" in status
    assert "backup_age_seconds" in status
    assert "retention_full_count" in status
    assert "retention_window_full_count" in status
    assert "failure_code" in _text("deploy/postgres-backup/backup-job.sh")

    sql = _text("deploy/postgres-backup/postgres-status.sql")
    assert "archive_age_seconds" in sql
    assert "write_lag_seconds" in sql
    assert "flush_lag_seconds" in sql
    assert "replay_lag_seconds" in sql
    assert "retained_wal_bytes" in sql
    assert "slot_wal_limit_bytes" in sql
    assert "slot_wal_utilization_ratio" in sql


def test_runtime_image_installs_backup_workers_without_fastapi_scheduler():
    dockerfile = _text("deploy/postgres-backup/Dockerfile")
    for script in (
        "backup-job.sh",
        "backup-scheduler.sh",
        "backup-healthcheck.sh",
        "retention-guard.sh",
        "status-snapshot.sh",
        "wal-continuity-check.sh",
    ):
        assert f"COPY deploy/postgres-backup/{script} /usr/local/bin/{script}" in dockerfile
        assert f"/usr/local/bin/{script}" in dockerfile
