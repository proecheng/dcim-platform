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
from datetime import datetime, timezone
from typing import Any

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
    return runner.run(
        step,
        [
            "docker",
            "run",
            "--rm",
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
        timeout=timeout,
        failure_code=failure_code,
    )


APP_PROBE = """
import asyncio
import os
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine
import app.main
from app.models.energy import PowerDevice

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as connection:
            await connection.execute(select(PowerDevice).limit(1))
            await connection.execute(text("CREATE TEMP TABLE story_39_3_app_probe(value integer NOT NULL)"))
            await connection.execute(text("INSERT INTO story_39_3_app_probe(value) VALUES (1)"))
            value = (await connection.execute(text("SELECT value FROM story_39_3_app_probe"))).scalar_one()
            if value != 1:
                raise RuntimeError("write probe mismatch")
    finally:
        await engine.dispose()

asyncio.run(main())
""".strip()


APP_IMAGE_SCHEMA_PROBE = """
import json
import os
from pathlib import Path

revision = os.environ["EXPECTED_RELEASE_REVISION"]
schema = os.environ["EXPECTED_IMAGE_SCHEMA"]
fields = [item for item in os.environ["EXPECTED_MODEL_FIELDS"].split(",") if item]
versions = Path("/app/alembic/versions")
models = Path("/app/app/models")
revision_present = any(path.name.startswith(revision + "_") for path in versions.glob("*.py"))
model_source = "".join(
    path.read_text(encoding="utf-8", errors="ignore") for path in models.glob("*.py")
)
present_fields = sorted(field for field in fields if field in model_source)

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
    parser.add_argument("--database-url-file", type=Path, required=True)
    parser.add_argument("--write-freeze-token-file", type=Path, required=True)
    parser.add_argument("--fault-tree-hmac-key-file", type=Path, required=True)
    parser.add_argument("--restore-point", default=os.getenv(MIGRATION_RESTORE_POINT))
    parser.add_argument("--current-app-image", default=os.getenv(CURRENT_APP_IMAGE))
    parser.add_argument("--previous-app-image", default=os.getenv(PREVIOUS_APP_IMAGE))
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def execute(
    args: argparse.Namespace, runner: CommandRunner, result: dict[str, Any]
) -> None:
    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
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

    active_connections = int(
        psql(
            runner,
            args.postgres_container,
            args.database,
            database_user,
            "verify_write_freeze",
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
            "AND backend_type = 'client backend';",
        )
    )
    if active_connections != 0:
        raise DrillError(
            "active_application_connections",
            "database still has application connections",
        )

    actual_head = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "alembic current",
        "SELECT version_num FROM alembic_version;",
    )
    if actual_head != head:
        raise DrillError("alembic_not_at_head", f"expected {head}, got {actual_head}")

    timescale_ok = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "verify_timescaledb_objects",
        "SELECT CASE WHEN "
        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'point_history') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention') "
        "THEN 1 ELSE 0 END;",
    )
    if timescale_ok != "1":
        raise DrillError(
            "timescaledb_objects_missing", "required TimescaleDB objects are missing"
        )

    invariant_count = int(
        psql(
            runner,
            args.postgres_container,
            args.database,
            database_user,
            "new_flexibility_columns_are_empty",
            str(invariant["sql"]),
        )
    )
    if invariant_count != int(invariant["expected"]):
        raise DrillError(
            "migration_invariant_changed",
            "release migration contains non-reversible data",
        )

    fingerprint_sql = (
        "SELECT json_build_object("
        "'power_device_count', count(*), "
        "'power_device_digest', md5(COALESCE(string_agg(id::text || ':' || device_code, ',' ORDER BY id), ''))"
        ")::text FROM power_devices;"
    )
    before_fingerprint = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "capture_pre_migration_invariants",
        fingerprint_sql,
    )
    restore_lsn = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "pg_create_restore_point",
        f"CHECKPOINT; SELECT pg_create_restore_point('{restore_point}');",
    ).splitlines()[-1]

    run_app(
        runner,
        step="alembic downgrade",
        image=current_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment=app_environment,
        entrypoint="alembic",
        arguments=["-c", "/app/alembic.ini", "downgrade", down_revision],
        failure_code="migration_command_failed",
    )
    downgraded_revision = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "verify_downgraded_revision",
        "SELECT version_num FROM alembic_version;",
    )
    if downgraded_revision != down_revision:
        raise DrillError(
            "migration_command_failed", "downgrade did not reach the approved revision"
        )

    run_app(
        runner,
        step="previous_app_readiness_and_write_probe",
        image=previous_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment=app_environment,
        entrypoint="python",
        arguments=["-c", APP_PROBE],
        failure_code="previous_app_incompatible",
    )

    run_app(
        runner,
        step="alembic upgrade",
        image=current_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment=app_environment,
        entrypoint="alembic",
        arguments=["-c", "/app/alembic.ini", "upgrade", head],
        failure_code="migration_command_failed",
    )
    final_head = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "verify_final_head",
        "SELECT version_num FROM alembic_version;",
    )
    if final_head != head:
        raise DrillError(
            "alembic_not_at_head", "upgrade did not restore the release head"
        )

    final_timescale = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "verify_final_timescaledb_objects",
        "SELECT CASE WHEN "
        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'point_history') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention') "
        "THEN 1 ELSE 0 END;",
    )
    if final_timescale != "1":
        raise DrillError(
            "timescaledb_objects_missing", "TimescaleDB objects changed during rollback"
        )

    final_invariant = int(
        psql(
            runner,
            args.postgres_container,
            args.database,
            database_user,
            "verify_final_migration_invariant",
            str(invariant["sql"]),
        )
    )
    final_fingerprint = psql(
        runner,
        args.postgres_container,
        args.database,
        database_user,
        "capture_final_invariants",
        fingerprint_sql,
    )
    if (
        final_invariant != int(invariant["expected"])
        or final_fingerprint != before_fingerprint
    ):
        raise DrillError(
            "migration_invariant_changed", "database invariants changed during rollback"
        )

    run_app(
        runner,
        step="current_app_readiness_and_write_probe",
        image=current_image,
        network=args.network,
        socket_volume=args.socket_volume,
        database_url=database_url,
        runtime_environment=app_environment,
        entrypoint="python",
        arguments=["-c", APP_PROBE],
        failure_code="current_app_incompatible",
    )

    result.update(
        {
            "status": "pass",
            "failure_code": None,
            "release_revision": head,
            "downgraded_revision": down_revision,
            "restore_point": restore_point,
            "restore_lsn": restore_lsn,
            "current_app_image": current_image,
            "previous_app_image": previous_image,
            "before_fingerprint": json.loads(before_fingerprint),
            "after_fingerprint": json.loads(final_fingerprint),
        }
    )


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
