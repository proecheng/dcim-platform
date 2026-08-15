#!/usr/bin/env python3
"""Run the Story 39.3 migration rollback contract in an isolated restore project."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPO_ROOT / "deploy" / "postgres-backup" / "migration-rollback-contract.yaml"
)
PROJECT_PATTERN = re.compile(r"^dcim-story-39-3-[a-z0-9][a-z0-9-]*$")
RESTORE_POINT_PATTERN = re.compile(r"^story_39_3_[a-z0-9_]{1,48}$")
IMAGE_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
FREEZE_TOKEN_PATTERN = re.compile(
    r"^frozen:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z:[0-9a-f]{8}-[0-9a-f-]{27}$"
)
MIGRATION_WRITE_FREEZE_TOKEN = "MIGRATION_WRITE_FREEZE_TOKEN"
MIGRATION_RESTORE_POINT = "MIGRATION_RESTORE_POINT"
CURRENT_APP_IMAGE = "CURRENT_APP_IMAGE"
PREVIOUS_APP_IMAGE = "PREVIOUS_APP_IMAGE"
FAULT_TREE_HMAC_KEY = "FAULT_TREE_HMAC_KEY"
ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
POSTGRES_SOCKET_DIR = "/var/run/postgresql"
MIGRATION_RTO_SECONDS_MAX = 3600.0


class DrillError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_value(value: str | None, code: str, name: str) -> str:
    if value is None or not value.strip():
        raise DrillError(code, f"{name} is required")
    return value.strip()


def load_secret_file(
    path: Path, code: str, name: str, *, environment_name: str | None = None
) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DrillError(code, f"cannot read {name}") from exc
    if environment_name is None:
        value = content.strip()
    else:
        prefix = f"{environment_name}="
        value = ""
        for line in content.splitlines():
            candidate = line.strip()
            if candidate.startswith(prefix):
                value = candidate[len(prefix) :].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                break
    return require_value(value, code, name)


def parse_json_output(output: str, code: str, name: str) -> Any:
    for line in reversed(output.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise DrillError(code, f"{name} did not return valid JSON")


class CommandRunner:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def run(
        self,
        step: str,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        timeout: int = 300,
        failure_code: str = "command_failed",
    ) -> str:
        started_at = utc_now()
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.events.append(
                {
                    "step": step,
                    "started_at": started_at,
                    "duration_seconds": round(time.monotonic() - started, 6),
                    "exit_code": None,
                    "status": "error",
                }
            )
            raise DrillError(failure_code, f"{step} could not complete") from exc

        stdout = completed.stdout.strip()
        self.events.append(
            {
                "step": step,
                "started_at": started_at,
                "duration_seconds": round(time.monotonic() - started, 6),
                "exit_code": completed.returncode,
                "status": "ok" if completed.returncode == 0 else "error",
            }
        )
        if completed.returncode != 0:
            raise DrillError(failure_code, f"{step} exited with {completed.returncode}")
        return stdout

    def try_run(
        self,
        step: str,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> tuple[bool, str]:
        try:
            return True, self.run(step, argv, env=env, timeout=timeout)
        except DrillError:
            return False, ""


def inspect_labels(
    runner: CommandRunner, object_type: str, name: str
) -> dict[str, str]:
    output = runner.run(
        f"inspect_{object_type}",
        ["docker", object_type, "inspect", name, "--format", "{{json .Labels}}"],
        failure_code="isolation_target_missing",
    )
    try:
        labels = json.loads(output)
    except json.JSONDecodeError as exc:
        raise DrillError(
            "isolation_label_invalid", f"invalid labels for {name}"
        ) from exc
    if not isinstance(labels, dict):
        raise DrillError("isolation_label_invalid", f"missing labels for {name}")
    return {str(key): str(value) for key, value in labels.items()}


def validate_isolation(
    runner: CommandRunner,
    project: str,
    container: str,
    network: str,
    socket_volume: str,
) -> None:
    if PROJECT_PATTERN.fullmatch(project) is None:
        raise DrillError(
            "isolation_project_invalid", "project name is outside Story 39.3"
        )

    container_output = runner.run(
        "inspect_restore_container",
        ["docker", "inspect", container, "--format", "{{json .Config.Labels}}"],
        failure_code="isolation_target_missing",
    )
    try:
        container_labels = json.loads(container_output)
    except json.JSONDecodeError as exc:
        raise DrillError(
            "isolation_label_invalid", "restore container labels are invalid"
        ) from exc

    if not isinstance(container_labels, dict):
        raise DrillError(
            "isolation_label_invalid", "restore container labels are missing"
        )

    network_labels = inspect_labels(runner, "network", network)
    volume_labels = inspect_labels(runner, "volume", socket_volume)
    expected = {
        "com.dcim.story": "39.3",
        "com.docker.compose.project": project,
    }
    for key, value in expected.items():
        if (
            container_labels.get(key) != value
            or network_labels.get(key) != value
            or volume_labels.get(key) != value
        ):
            raise DrillError(
                "isolation_label_invalid", f"{key} does not match the requested project"
            )
    if container_labels.get("com.dcim.dr.role") != "restore":
        raise DrillError("isolation_label_invalid", "container is not a restore target")
    if network_labels.get("com.dcim.dr.role") != "restore-isolated":
        raise DrillError("isolation_label_invalid", "network is not restore-isolated")
    if volume_labels.get("com.dcim.dr.role") != "restore-socket":
        raise DrillError("isolation_label_invalid", "volume is not a restore-socket")

    runtime_output = runner.run(
        "inspect_restore_runtime",
        [
            "docker",
            "inspect",
            container,
            "--format",
            "{{json .State.Running}}|{{json .Mounts}}|{{json .NetworkSettings.Networks}}",
        ],
        failure_code="isolation_target_missing",
    )
    try:
        running_json, mounts_json, networks_json = runtime_output.split("|", 2)
        running = json.loads(running_json)
        mounts = json.loads(mounts_json)
        networks = json.loads(networks_json)
    except (ValueError, json.JSONDecodeError) as exc:
        raise DrillError(
            "isolation_runtime_invalid", "restore runtime inspection is invalid"
        ) from exc
    socket_attached = isinstance(mounts, list) and any(
        isinstance(mount, dict)
        and mount.get("Type") == "volume"
        and mount.get("Name") == socket_volume
        and mount.get("Destination") == POSTGRES_SOCKET_DIR
        for mount in mounts
    )
    if running is not True or not socket_attached:
        raise DrillError(
            "isolation_runtime_invalid",
            "restore container is not running with the validated socket volume",
        )
    if not isinstance(networks, dict) or network not in networks:
        raise DrillError(
            "isolation_runtime_invalid",
            "restore container is not attached to the validated network",
        )
    members_output = runner.run(
        "inspect_restore_network_members",
        ["docker", "network", "inspect", network, "--format", "{{json .Containers}}"],
        failure_code="isolation_target_missing",
    )
    try:
        members = json.loads(members_output)
    except json.JSONDecodeError as exc:
        raise DrillError(
            "isolation_runtime_invalid", "restore network membership is invalid"
        ) from exc
    if not isinstance(members, dict):
        raise DrillError(
            "isolation_runtime_invalid", "restore network membership is missing"
        )
    member_names = {
        str(member.get("Name"))
        for member in members.values()
        if isinstance(member, dict) and member.get("Name")
    }
    if member_names != {container}:
        raise DrillError(
            "isolation_runtime_invalid",
            "restore network must contain only the validated database before migration",
        )


def validate_image(
    runner: CommandRunner,
    step: str,
    image: str,
    expected_revision: str,
) -> None:
    if IMAGE_PATTERN.fullmatch(image) is None:
        raise DrillError(
            "mutable_application_image",
            f"{step} must use an immutable @sha256 reference",
        )
    output = runner.run(
        f"inspect_{step}_image",
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{json .Config.Labels}}",
        ],
        failure_code="application_image_missing",
    )
    try:
        labels = json.loads(output)
    except json.JSONDecodeError as exc:
        raise DrillError(
            "application_image_provenance_mismatch",
            f"{step} image labels are invalid",
        ) from exc
    if (
        not isinstance(labels, dict)
        or labels.get("org.opencontainers.image.revision") != expected_revision
    ):
        raise DrillError(
            "application_image_provenance_mismatch",
            f"{step} image source revision does not match the contract",
        )


def validate_socket_database_url(
    value: str,
    *,
    expected_database: str,
    expected_user: str,
    name: str,
) -> str:
    """Only accept credentials that connect through the validated restore socket."""

    parsed = urlsplit(value)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg"}:
        raise DrillError("database_url_invalid", f"{name} must use PostgreSQL")
    if parsed.hostname not in (None, "") or parsed.port is not None:
        raise DrillError(
            "database_url_target_invalid",
            f"{name} must not contain a TCP host or port",
        )
    database = unquote(parsed.path.lstrip("/"))
    if database != expected_database or unquote(parsed.username or "") != expected_user:
        raise DrillError(
            "database_url_target_invalid",
            f"{name} database or role does not match the validated target",
        )
    socket_values = parse_qs(parsed.query).get("host", [])
    if socket_values != [POSTGRES_SOCKET_DIR]:
        raise DrillError(
            "database_url_target_invalid",
            f"{name} must use {POSTGRES_SOCKET_DIR}",
        )
    if not parsed.password:
        raise DrillError("database_url_invalid", f"{name} has no password")
    return value


def psql(
    runner: CommandRunner,
    container: str,
    database: str,
    database_user: str,
    step: str,
    sql: str,
) -> str:
    return runner.run(
        step,
        [
            "docker",
            "exec",
            "--user",
            "postgres",
            container,
            "psql",
            "--no-psqlrc",
            "--tuples-only",
            "--no-align",
            "--set",
            "ON_ERROR_STOP=1",
            "--dbname",
            database,
            "--username",
            database_user,
            "--command",
            sql,
        ],
        failure_code="database_probe_failed",
    )


def quote_identifier(value: str) -> str:
    if IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise DrillError(
            "database_identifier_invalid",
            "database identifiers must be simple PostgreSQL names",
        )
    return f'"{value}"'


def role_can_login(
    runner: CommandRunner,
    container: str,
    database: str,
    migration_user: str,
    application_user: str,
) -> bool:
    role = quote_identifier(application_user)
    value = psql(
        runner,
        container,
        database,
        migration_user,
        "read_application_role_login",
        f"SELECT rolcanlogin::text FROM pg_roles WHERE rolname = '{application_user}';",
    )
    if value not in {"t", "f"}:
        raise DrillError(
            "application_role_missing", f"application role {role} does not exist"
        )
    return value == "t"


def set_application_login(
    runner: CommandRunner,
    container: str,
    database: str,
    migration_user: str,
    application_user: str,
    enabled: bool,
) -> None:
    role = quote_identifier(application_user)
    action = "LOGIN" if enabled else "NOLOGIN"
    psql(
        runner,
        container,
        database,
        migration_user,
        "enable_application_role" if enabled else "fence_application_role",
        f"ALTER ROLE {role} {action};",
    )
    if not enabled:
        psql(
            runner,
            container,
            database,
            migration_user,
            "terminate_application_sessions",
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE usename = '{application_user}' AND pid <> pg_backend_pid();",
        )
        active = psql(
            runner,
            container,
            database,
            migration_user,
            "verify_application_sessions_fenced",
            "SELECT count(*)::text FROM pg_stat_activity "
            f"WHERE usename = '{application_user}' AND pid <> pg_backend_pid();",
        )
        if active != "0":
            raise DrillError(
                "write_freeze_failed",
                "application sessions remained after database fence",
            )


def capture_timescaledb_fingerprint(
    runner: CommandRunner,
    container: str,
    database: str,
    migration_user: str,
    step: str,
) -> dict[str, Any]:
    output = psql(
        runner,
        container,
        database,
        migration_user,
        step,
        "SELECT json_build_object("
        "'hypertables', COALESCE((SELECT json_agg(json_build_object("
        "'schema', hypertable_schema, 'name', hypertable_name, "
        "'compression', compression_enabled) ORDER BY hypertable_name) "
        "FROM timescaledb_information.hypertables "
        "WHERE hypertable_schema = 'public' AND hypertable_name = 'point_history'), '[]'::json), "
        "'jobs', COALESCE((SELECT json_agg(json_build_object("
        "'proc_name', proc_name, 'schedule_interval', schedule_interval, "
        "'config', config) ORDER BY proc_name) "
        "FROM timescaledb_information.jobs "
        "WHERE hypertable_schema = 'public' AND hypertable_name = 'point_history' "
        "AND proc_name IN ('policy_compression', 'policy_retention')), '[]'::json)"
        ")::text;",
    )
    payload = parse_json_output(output, "timescaledb_fingerprint_invalid", step)
    if not isinstance(payload, dict):
        raise DrillError(
            "timescaledb_fingerprint_invalid",
            "TimescaleDB fingerprint is not an object",
        )
    hypertables = payload.get("hypertables")
    jobs = payload.get("jobs")
    if (
        not isinstance(hypertables, list)
        or len(hypertables) != 1
        or not isinstance(jobs, list)
        or len(jobs) != 2
    ):
        raise DrillError(
            "timescaledb_objects_missing",
            "point_history hypertable and both policies are required",
        )
    return payload


def capture_database_fingerprint(
    runner: CommandRunner,
    *,
    step: str,
    image: str,
    network: str,
    socket_volume: str,
    database_url: str,
    fault_tree_hmac_key: str,
) -> dict[str, Any]:
    output = run_app(
        runner,
        step=step,
        image=image,
        network=network,
        socket_volume=socket_volume,
        database_url=database_url,
        runtime_environment={FAULT_TREE_HMAC_KEY: fault_tree_hmac_key},
        entrypoint="python",
        arguments=["-c", DATABASE_FINGERPRINT_PROBE],
        failure_code="database_fingerprint_failed",
        timeout=900,
    )
    payload = parse_json_output(output, "database_fingerprint_invalid", step)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise DrillError(
            "database_fingerprint_invalid", "database fingerprint is not an object"
        )
    return payload


def create_archived_restore_point(
    runner: CommandRunner,
    *,
    container: str,
    database: str,
    migration_user: str,
    restore_point: str,
    timeout: float,
    poll_interval: float,
) -> dict[str, str]:
    output = psql(
        runner,
        container,
        database,
        migration_user,
        "create_archived_restore_point",
        f"CHECKPOINT; SELECT pg_create_restore_point('{restore_point}'); "
        "SELECT pg_walfile_name(pg_switch_wal());",
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        raise DrillError(
            "restore_point_invalid", "restore point command returned incomplete output"
        )
    restore_lsn, wal_segment = lines[-2:]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        archived = psql(
            runner,
            container,
            database,
            migration_user,
            "poll_restore_point_archive",
            "SELECT CASE WHEN COALESCE(last_archived_wal, '') >= "
            f"'{wal_segment}' THEN '1' ELSE '0' END FROM pg_stat_archiver;",
        )
        if archived == "1":
            return {"restore_lsn": restore_lsn, "wal_segment": wal_segment}
        time.sleep(poll_interval)
    raise DrillError(
        "restore_point_not_archived", "restore point WAL was not archived in time"
    )


def wait_for_pitr_evidence(
    path: Path,
    *,
    restore_point: str,
    restore_lsn: str,
    expected_head: str,
    expected_database_fingerprint: dict[str, Any],
    expected_timescaledb_fingerprint: dict[str, Any],
    created_after: float,
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            stat = path.stat()
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            time.sleep(poll_interval)
            continue
        if stat.st_mtime < created_after:
            raise DrillError("pitr_evidence_stale", "PITR evidence predates this drill")
        expected = {
            "schema_version": 1,
            "status": "pass",
            "isolated_restore": True,
            "restore_target_type": "name",
            "restore_target_value": restore_point,
            "restore_lsn": restore_lsn,
            "alembic_head": expected_head,
            "repository_check": "pass",
            "pg_amcheck": "pass",
            "rpo_missing_commit_count": 0,
        }
        if not isinstance(payload, dict) or any(
            payload.get(key) != value for key, value in expected.items()
        ):
            raise DrillError(
                "pitr_evidence_invalid",
                "PITR evidence does not match this restore point",
            )
        if payload.get("database_fingerprint") != expected_database_fingerprint:
            raise DrillError(
                "pitr_evidence_invalid", "PITR database fingerprint does not match"
            )
        if payload.get("timescaledb_fingerprint") != expected_timescaledb_fingerprint:
            raise DrillError(
                "pitr_evidence_invalid", "PITR TimescaleDB fingerprint does not match"
            )
        rto_seconds = payload.get("rto_seconds")
        if (
            not isinstance(rto_seconds, (int, float))
            or not 0 <= float(rto_seconds) <= MIGRATION_RTO_SECONDS_MAX
        ):
            raise DrillError(
                "pitr_recovery_objective_not_met",
                "PITR evidence exceeds the migration RTO",
            )
        return payload
    raise DrillError(
        "pitr_evidence_timeout", "isolated PITR evidence was not produced in time"
    )


def run_app(
    runner: CommandRunner,
    *,
    step: str,
    image: str,
    network: str,
    socket_volume: str,
    database_url: str,
    runtime_environment: dict[str, str] | None,
    entrypoint: str,
    arguments: list[str],
    failure_code: str,
    timeout: int = 300,
) -> str:
    environment = os.environ.copy()
    container_environment = {"DATABASE_URL": database_url}
    for name, value in (runtime_environment or {}).items():
        if ENVIRONMENT_NAME_PATTERN.fullmatch(name) is None or name == "DATABASE_URL":
            raise DrillError(
                "application_environment_invalid",
                "application environment name is invalid",
            )
        container_environment[name] = value
    environment.update(container_environment)

    environment_arguments: list[str] = []
    for name in sorted(container_environment):
        environment_arguments.extend(["--env", name])
    normalized_step = re.sub(r"[^a-z0-9]+", "-", step.lower()).strip("-")[:32]
    container_name = (
        f"dcim-story-39-3-migration-{normalized_step}-{uuid.uuid4().hex[:8]}"
    )
    runner.run(
        f"create_{step}",
        [
            "docker",
            "create",
            "--name",
            container_name,
            "--network",
            network,
            "--mount",
            f"type=volume,src={socket_volume},dst=/var/run/postgresql,readonly",
            "--label",
            "com.dcim.story=39.3",
            "--label",
            "com.dcim.dr.role=migration-probe",
            *environment_arguments,
            "--entrypoint",
            entrypoint,
            image,
            *arguments,
        ],
        env=environment,
        timeout=60,
        failure_code=failure_code,
    )
    try:
        return runner.run(
            step,
            ["docker", "start", "--attach", container_name],
            timeout=timeout,
            failure_code=failure_code,
        )
    finally:
        removed, _ = runner.try_run(
            f"remove_{step}",
            ["docker", "rm", "--force", container_name],
        )
        if not removed:
            raise DrillError(
                "migration_container_cleanup_failed",
                f"could not remove migration container for {step}",
            )


APP_PROBE = """
import asyncio
import os
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine
import app.main
from app.models.energy import PowerDevice

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                device_id = (await connection.execute(select(PowerDevice.id).limit(1))).scalar_one_or_none()
                if device_id is None:
                    raise RuntimeError("representative power device is missing")
                updated = await connection.execute(
                    update(PowerDevice)
                    .where(PowerDevice.id == device_id)
                    .values(device_code=PowerDevice.device_code)
                    .returning(PowerDevice.id)
                )
                if updated.scalar_one() != device_id:
                    raise RuntimeError("business write probe mismatch")
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()

asyncio.run(main())
""".strip()


APP_IMAGE_SCHEMA_PROBE = """
import json
import os
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base
import app.models

revision = os.environ["EXPECTED_RELEASE_REVISION"]
schema = os.environ["EXPECTED_IMAGE_SCHEMA"]
fields = [item for item in os.environ["EXPECTED_MODEL_FIELDS"].split(",") if item]
script = ScriptDirectory.from_config(Config("/app/alembic.ini"))
revision_present = script.get_revision(revision) is not None
power_devices = Base.metadata.tables["power_devices"]
present_fields = sorted(field for field in fields if field in power_devices.c)

if schema == "previous":
    valid = not revision_present and not present_fields
elif schema == "current":
    valid = revision_present and present_fields == sorted(fields)
else:
    raise RuntimeError("unsupported image schema expectation")

if not valid:
    raise RuntimeError("application image schema inventory mismatch")
print(json.dumps({"schema": schema, "revision_present": revision_present, "fields": present_fields}))
""".strip()


DATABASE_FINGERPRINT_PROBE = """
import asyncio
import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

CATALOG_SQL = '''
SELECT jsonb_build_object(
  'columns', COALESCE((
    SELECT jsonb_agg(to_jsonb(c) ORDER BY c.table_name, c.ordinal_position)
    FROM (
      SELECT table_name, ordinal_position, column_name, data_type, udt_name,
             is_nullable, column_default, is_identity
      FROM information_schema.columns
      WHERE table_schema = 'public'
    ) c
  ), '[]'::jsonb),
  'constraints', COALESCE((
    SELECT jsonb_agg(to_jsonb(c) ORDER BY c.table_name, c.name)
    FROM (
      SELECT cls.relname AS table_name, con.conname AS name,
             pg_get_constraintdef(con.oid, true) AS definition
      FROM pg_constraint con
      JOIN pg_class cls ON cls.oid = con.conrelid
      JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
      WHERE nsp.nspname = 'public'
    ) c
  ), '[]'::jsonb),
  'indexes', COALESCE((
    SELECT jsonb_agg(to_jsonb(i) ORDER BY i.tablename, i.indexname)
    FROM (
      SELECT tablename, indexname, indexdef
      FROM pg_indexes WHERE schemaname = 'public'
    ) i
  ), '[]'::jsonb),
  'sequences', COALESCE((
    SELECT jsonb_agg(to_jsonb(s) ORDER BY s.sequencename)
    FROM (
      SELECT sequencename, data_type, start_value, min_value, max_value,
             increment_by, cycle
      FROM pg_sequences WHERE schemaname = 'public'
    ) s
  ), '[]'::jsonb)
)::text;
'''

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.connect() as connection:
            table_names = [
                row[0]
                for row in (
                    await connection.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public' "
                             "AND tablename <> 'alembic_version' ORDER BY tablename")
                    )
                ).all()
            ]
            data = {}
            for table_name in table_names:
                quoted = connection.dialect.identifier_preparer.quote(table_name)
                query = text(
                    f"SELECT count(*)::bigint, "
                    f"md5(COALESCE(string_agg(to_jsonb(t)::text, E'\\n' "
                    f"ORDER BY to_jsonb(t)::text), '')) FROM {quoted} AS t"
                )
                count, digest = (await connection.execute(query)).one()
                data[table_name] = {"count": int(count), "digest": digest}
            catalog = json.loads((await connection.execute(text(CATALOG_SQL))).scalar_one())
            revision = (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one()
            print(json.dumps({"alembic_revision": revision, "catalog": catalog, "data": data}, sort_keys=True))
    finally:
        await engine.dispose()

asyncio.run(main())
""".strip()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--postgres-container", required=True)
    parser.add_argument("--network", required=True)
    parser.add_argument("--socket-volume", required=True)
    parser.add_argument("--database", default="dcim")
    parser.add_argument("--database-user", default="dcim")
    parser.add_argument("--migration-database-user", default="postgres")
    parser.add_argument("--database-url-file", type=Path, required=True)
    parser.add_argument("--migration-database-url-file", type=Path, required=True)
    parser.add_argument("--write-freeze-token-file", type=Path, required=True)
    parser.add_argument("--fault-tree-hmac-key-file", type=Path, required=True)
    parser.add_argument("--restore-point", default=os.getenv(MIGRATION_RESTORE_POINT))
    parser.add_argument("--current-app-image", default=os.getenv(CURRENT_APP_IMAGE))
    parser.add_argument("--previous-app-image", default=os.getenv(PREVIOUS_APP_IMAGE))
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--pitr-evidence-file", type=Path, required=True)
    parser.add_argument("--pitr-evidence-timeout-seconds", type=float, default=3600.0)
    return parser.parse_args()


def execute(
    args: argparse.Namespace, runner: CommandRunner, result: dict[str, Any]
) -> None:
    try:
        contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DrillError(
            "migration_contract_invalid", "cannot read migration contract"
        ) from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise DrillError(
            "migration_contract_invalid", "migration contract schema is invalid"
        )
    release = contract["release_migration"]
    compatibility = contract["application_compatibility"]
    head = str(release["revision"])
    down_revision = str(release["down_revision"])
    invariant = release["reversibility_invariant"]

    restore_point = require_value(
        args.restore_point, "restore_point_missing", MIGRATION_RESTORE_POINT
    )
    if RESTORE_POINT_PATTERN.fullmatch(restore_point) is None:
        raise DrillError("restore_point_invalid", "restore point name is invalid")
    current_image = require_value(
        args.current_app_image, "current_app_image_missing", CURRENT_APP_IMAGE
    )
    previous_image = require_value(
        args.previous_app_image, "previous_app_image_missing", PREVIOUS_APP_IMAGE
    )
    freeze_token = load_secret_file(
        args.write_freeze_token_file,
        "write_freeze_missing",
        MIGRATION_WRITE_FREEZE_TOKEN,
    )
    if FREEZE_TOKEN_PATTERN.fullmatch(freeze_token) is None:
        raise DrillError("write_freeze_missing", "write freeze token is invalid")
    database_url = load_secret_file(
        args.database_url_file, "database_url_missing", "database URL"
    )
    migration_database_url = load_secret_file(
        args.migration_database_url_file,
        "migration_database_url_missing",
        "migration database URL",
    )
    fault_tree_hmac_key = load_secret_file(
        args.fault_tree_hmac_key_file,
        "application_secret_missing",
        FAULT_TREE_HMAC_KEY,
        environment_name=FAULT_TREE_HMAC_KEY,
    )
    if len(fault_tree_hmac_key) < 32 or "placeholder" in fault_tree_hmac_key.lower():
        raise DrillError(
            "application_secret_missing", f"{FAULT_TREE_HMAC_KEY} is invalid"
        )
    database_user = require_value(
        args.database_user, "database_user_missing", "database user"
    )
    migration_database_user = require_value(
        args.migration_database_user,
        "migration_database_user_missing",
        "migration database user",
    )
    if database_user == migration_database_user:
        raise DrillError(
            "migration_role_invalid",
            "application and migration roles must be different",
        )
    if (
        IDENTIFIER_PATTERN.fullmatch(database_user) is None
        or IDENTIFIER_PATTERN.fullmatch(migration_database_user) is None
    ):
        raise DrillError(
            "database_identifier_invalid",
            "database roles must be simple PostgreSQL names",
        )
    database_url = validate_socket_database_url(
        database_url,
        expected_database=args.database,
        expected_user=database_user,
        name="application database URL",
    )
    migration_database_url = validate_socket_database_url(
        migration_database_url,
        expected_database=args.database,
        expected_user=migration_database_user,
        name="migration database URL",
    )
    if (
        args.archive_timeout_seconds <= 0
        or args.poll_interval_seconds <= 0
        or args.pitr_evidence_timeout_seconds <= 0
    ):
        raise DrillError(
            "timeout_invalid", "archive, poll, and PITR timeouts must be positive"
        )
    app_environment = {FAULT_TREE_HMAC_KEY: fault_tree_hmac_key}

    validate_isolation(
        runner,
        args.project,
        args.postgres_container,
        args.network,
        args.socket_volume,
    )
    validate_image(
        runner,
        "current_app",
        current_image,
        str(compatibility["current_source_revision"]),
    )
    validate_image(
        runner,
        "previous_app",
        previous_image,
        str(compatibility["previous_source_revision"]),
    )

    release_model_fields = compatibility["release_model_fields"]
    schema_environment = {
        **app_environment,
        "EXPECTED_RELEASE_REVISION": head,
        "EXPECTED_MODEL_FIELDS": ",".join(str(field) for field in release_model_fields),
    }
    run_app(
        runner,
        step="validate_previous_app_schema",
        image=previous_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment={**schema_environment, "EXPECTED_IMAGE_SCHEMA": "previous"},
        entrypoint="python",
        arguments=["-c", APP_IMAGE_SCHEMA_PROBE],
        failure_code="previous_app_incompatible",
    )
    run_app(
        runner,
        step="validate_current_app_schema",
        image=current_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment={**schema_environment, "EXPECTED_IMAGE_SCHEMA": "current"},
        entrypoint="python",
        arguments=["-c", APP_IMAGE_SCHEMA_PROBE],
        failure_code="current_app_incompatible",
    )
    if not role_can_login(
        runner,
        args.postgres_container,
        args.database,
        migration_database_user,
        database_user,
    ):
        raise DrillError(
            "application_role_missing",
            "application role must be login-capable before the drill",
        )

    role_fenced = False
    migration_started = False
    before_database_fingerprint: dict[str, Any] | None = None
    before_timescaledb_fingerprint: dict[str, Any] | None = None
    restore_info: dict[str, str] | None = None
    pitr_evidence_started = time.time()
    rto_started = time.monotonic()
    result["rto_started_at_utc"] = utc_now()

    def run_application_probe_under_fence(
        *, step: str, image: str, failure_code: str
    ) -> None:
        nonlocal role_fenced
        set_application_login(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            database_user,
            True,
        )
        role_fenced = False
        try:
            run_app(
                runner,
                step=step,
                image=image,
                network=args.network,
                socket_volume=args.socket_volume,
                database_url=database_url,
                runtime_environment=app_environment,
                entrypoint="python",
                arguments=["-c", APP_PROBE],
                failure_code=failure_code,
            )
        finally:
            set_application_login(
                runner,
                args.postgres_container,
                args.database,
                migration_database_user,
                database_user,
                False,
            )
            role_fenced = True

    try:
        try:
            set_application_login(
                runner,
                args.postgres_container,
                args.database,
                migration_database_user,
                database_user,
                False,
            )
        except Exception:
            result["quarantined"] = True
            raise
        role_fenced = True

        actual_head = psql(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            "alembic_current",
            "SELECT version_num FROM alembic_version;",
        )
        if actual_head != head:
            raise DrillError(
                "alembic_not_at_head", f"expected {head}, got {actual_head}"
            )

        before_timescaledb_fingerprint = capture_timescaledb_fingerprint(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            "capture_pre_migration_timescaledb",
        )
        invariant_count = int(
            psql(
                runner,
                args.postgres_container,
                args.database,
                migration_database_user,
                "new_flexibility_columns_are_empty",
                str(invariant["sql"]),
            )
        )
        if invariant_count != int(invariant["expected"]):
            raise DrillError(
                "migration_invariant_changed",
                "release migration contains non-reversible data",
            )
        before_database_fingerprint = capture_database_fingerprint(
            runner,
            step="capture_pre_migration_database",
            image=current_image,
            network=args.network,
            socket_volume=args.socket_volume,
            database_url=migration_database_url,
            fault_tree_hmac_key=fault_tree_hmac_key,
        )
        pitr_evidence_started = time.time()
        restore_info = create_archived_restore_point(
            runner,
            container=args.postgres_container,
            database=args.database,
            migration_user=migration_database_user,
            restore_point=restore_point,
            timeout=args.archive_timeout_seconds,
            poll_interval=args.poll_interval_seconds,
        )
        migration_started = True

        run_app(
            runner,
            step="alembic_downgrade",
            image=current_image,
            network=args.network,
            socket_volume=args.socket_volume,
            database_url=migration_database_url,
            runtime_environment=app_environment,
            entrypoint="alembic",
            arguments=["-c", "/app/alembic.ini", "downgrade", down_revision],
            failure_code="migration_command_failed",
        )
        downgraded_revision = psql(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            "verify_downgraded_revision",
            "SELECT version_num FROM alembic_version;",
        )
        if downgraded_revision != down_revision:
            raise DrillError(
                "migration_command_failed",
                "downgrade did not reach the approved revision",
            )

        run_application_probe_under_fence(
            step="previous_app_readiness_and_write_probe",
            image=previous_image,
            failure_code="previous_app_incompatible",
        )
        run_app(
            runner,
            step="alembic_upgrade",
            image=current_image,
            network=args.network,
            socket_volume=args.socket_volume,
            database_url=migration_database_url,
            runtime_environment=app_environment,
            entrypoint="alembic",
            arguments=["-c", "/app/alembic.ini", "upgrade", head],
            failure_code="migration_command_failed",
        )
        final_head = psql(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            "verify_final_head",
            "SELECT version_num FROM alembic_version;",
        )
        if final_head != head:
            raise DrillError(
                "alembic_not_at_head", "upgrade did not restore the release head"
            )

        final_timescaledb_fingerprint = capture_timescaledb_fingerprint(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            "capture_final_timescaledb",
        )
        final_invariant = int(
            psql(
                runner,
                args.postgres_container,
                args.database,
                migration_database_user,
                "verify_final_migration_invariant",
                str(invariant["sql"]),
            )
        )
        final_database_fingerprint = capture_database_fingerprint(
            runner,
            step="capture_final_database",
            image=current_image,
            network=args.network,
            socket_volume=args.socket_volume,
            database_url=migration_database_url,
            fault_tree_hmac_key=fault_tree_hmac_key,
        )
        if (
            final_invariant != int(invariant["expected"])
            or final_database_fingerprint != before_database_fingerprint
            or final_timescaledb_fingerprint != before_timescaledb_fingerprint
        ):
            raise DrillError(
                "migration_invariant_changed",
                "database catalog, data, or TimescaleDB state changed during rollback",
            )

        run_application_probe_under_fence(
            step="current_app_readiness_and_write_probe",
            image=current_image,
            failure_code="current_app_incompatible",
        )
        recovery_completed = time.monotonic()
        rto_seconds = round(recovery_completed - rto_started, 6)
        if rto_seconds > MIGRATION_RTO_SECONDS_MAX:
            raise DrillError(
                "migration_rto_objective_not_met",
                "migration rollback exceeded the 60 minute RTO",
            )
        pitr_evidence = wait_for_pitr_evidence(
            args.pitr_evidence_file,
            restore_point=restore_point,
            restore_lsn=str(restore_info["restore_lsn"]),
            expected_head=head,
            expected_database_fingerprint=before_database_fingerprint,
            expected_timescaledb_fingerprint=before_timescaledb_fingerprint,
            created_after=pitr_evidence_started,
            timeout=args.pitr_evidence_timeout_seconds,
            poll_interval=args.poll_interval_seconds,
        )
        set_application_login(
            runner,
            args.postgres_container,
            args.database,
            migration_database_user,
            database_user,
            True,
        )
        role_fenced = False
        result.update(
            {
                "status": "pass",
                "failure_code": None,
                "release_revision": head,
                "downgraded_revision": down_revision,
                "restore_point": restore_point,
                **restore_info,
                "current_app_image": current_image,
                "previous_app_image": previous_image,
                "before_fingerprint": before_database_fingerprint,
                "after_fingerprint": final_database_fingerprint,
                "before_timescaledb_fingerprint": before_timescaledb_fingerprint,
                "after_timescaledb_fingerprint": final_timescaledb_fingerprint,
                "rto_seconds": rto_seconds,
                "rto_seconds_max": MIGRATION_RTO_SECONDS_MAX,
                "rpo_missing_commit_count": 0,
                "rpo_seconds": 0,
                "pitr_evidence": pitr_evidence,
                "write_freeze": "database-role-fence",
            }
        )
    except Exception:
        if migration_started:
            try:
                current_revision = psql(
                    runner,
                    args.postgres_container,
                    args.database,
                    migration_database_user,
                    "inspect_recovery_revision",
                    "SELECT version_num FROM alembic_version;",
                )
                if current_revision != head:
                    run_app(
                        runner,
                        step="automatic_recovery_upgrade",
                        image=current_image,
                        network=args.network,
                        socket_volume=args.socket_volume,
                        database_url=migration_database_url,
                        runtime_environment=app_environment,
                        entrypoint="alembic",
                        arguments=["-c", "/app/alembic.ini", "upgrade", head],
                        failure_code="automatic_recovery_failed",
                    )
                recovered_fingerprint = capture_database_fingerprint(
                    runner,
                    step="verify_automatic_recovery",
                    image=current_image,
                    network=args.network,
                    socket_volume=args.socket_volume,
                    database_url=migration_database_url,
                    fault_tree_hmac_key=fault_tree_hmac_key,
                )
                if recovered_fingerprint != before_database_fingerprint:
                    raise DrillError(
                        "automatic_recovery_failed",
                        "automatic recovery fingerprint mismatch",
                    )
                result["automatic_recovery"] = "head_verified"
                set_application_login(
                    runner,
                    args.postgres_container,
                    args.database,
                    migration_database_user,
                    database_user,
                    True,
                )
                role_fenced = False
            except Exception as recovery_error:
                result["quarantined"] = True
                result["automatic_recovery_error"] = type(recovery_error).__name__
                try:
                    set_application_login(
                        runner,
                        args.postgres_container,
                        args.database,
                        migration_database_user,
                        database_user,
                        False,
                    )
                    role_fenced = True
                except Exception:
                    result["quarantined"] = True
        elif role_fenced:
            try:
                set_application_login(
                    runner,
                    args.postgres_container,
                    args.database,
                    migration_database_user,
                    database_user,
                    True,
                )
                role_fenced = False
            except Exception:
                result["quarantined"] = True
        raise


def main() -> int:
    args = parse_args()
    runner = CommandRunner()
    result: dict[str, Any] = {
        "schema_version": 1,
        "started_at": utc_now(),
        "status": "error",
        "failure_code": "unhandled_error",
    }
    output = args.output_dir / "migration-last-run.json"
    try:
        execute(args, runner, result)
    except DrillError as exc:
        result["failure_code"] = exc.code
        result["message"] = str(exc)
    except Exception as exc:
        result["message"] = type(exc).__name__
    finally:
        result["completed_at"] = utc_now()
        result["events"] = runner.events
        atomic_json(output, result)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
