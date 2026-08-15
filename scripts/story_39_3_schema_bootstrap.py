#!/usr/bin/env python3
"""Bootstrap the current release schema in an empty Story 39.3 primary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_FILE = (
    REPO_ROOT / "deploy" / "postgres-backup" / "expected-schema-tables.txt"
)
PROJECT_PATTERN = re.compile(r"^dcim-story-39-3-[a-z0-9][a-z0-9-]*$")
IMAGE_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
BOOTSTRAP_REVISION = "a001_full_schema"
TIMESCALE_REVISION = "a002_timescaledb_hypertable"
RELEASE_HEAD = "20260707_0100"
EXPECTED_TABLE_COUNT = 188
EXPECTED_SCHEMA_SHA256 = (
    "81cdd3d0d4d3a4ad5edc128981e383bcfff5f37bc1b9d30f491c1598fc1be6b3"
)


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_value(value: str | None, code: str, name: str) -> str:
    if value is None or not value.strip():
        raise BootstrapError(code, f"{name} is required")
    return value.strip()


def load_secret_file(path: Path, code: str, name: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise BootstrapError(code, f"cannot read {name}") from exc
    return require_value(value, code, name)


def normalized_schema_hash(names: list[str]) -> str:
    payload = ("\n".join(sorted(names)) + "\n").encode()
    return sha256(payload).hexdigest()


def validate_image_reference(image: str) -> str:
    value = require_value(image, "application_image_missing", "application image")
    if IMAGE_PATTERN.fullmatch(value) is None:
        raise BootstrapError(
            "mutable_application_image",
            "application image must use an immutable @sha256 reference",
        )
    return value


def load_expected_schema(path: Path, expected_hash: str) -> tuple[list[str], str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BootstrapError(
            "schema_manifest_missing", "cannot read expected schema manifest"
        ) from exc

    names = sorted(
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )
    if len(names) != EXPECTED_TABLE_COUNT or len(set(names)) != EXPECTED_TABLE_COUNT:
        raise BootstrapError(
            "schema_manifest_invalid",
            "expected schema manifest must contain 188 unique tables",
        )
    if any(TABLE_PATTERN.fullmatch(name) is None for name in names):
        raise BootstrapError(
            "schema_manifest_invalid",
            "expected schema manifest contains an invalid table name",
        )

    actual_hash = normalized_schema_hash(names)
    if actual_hash != expected_hash:
        raise BootstrapError(
            "schema_manifest_hash_mismatch",
            "expected schema manifest hash does not match the approved release",
        )
    return names, actual_hash


def validate_isolation_labels(
    project: str,
    container_labels: dict[str, str],
    network_labels: dict[str, str],
) -> None:
    if PROJECT_PATTERN.fullmatch(project) is None:
        raise BootstrapError(
            "isolation_project_invalid", "project name is outside Story 39.3"
        )

    expected = {
        "com.dcim.story": "39.3",
        "com.docker.compose.project": project,
    }
    for key, value in expected.items():
        if container_labels.get(key) != value or network_labels.get(key) != value:
            raise BootstrapError(
                "isolation_label_invalid", f"{key} does not match the requested project"
            )
    if container_labels.get("com.dcim.dr.role") != "primary":
        raise BootstrapError(
            "isolation_label_invalid", "container is not a Story 39.3 primary"
        )
    if network_labels.get("com.dcim.dr.site") != "primary":
        raise BootstrapError(
            "isolation_label_invalid", "network is not the primary site"
        )


def require_empty_database(table_count: int) -> None:
    if table_count != 0:
        raise BootstrapError(
            "database_not_empty", "database must be empty before schema bootstrap"
        )


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
            raise BootstrapError(failure_code, f"{step} could not complete") from exc

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
            raise BootstrapError(
                failure_code, f"{step} exited with {completed.returncode}"
            )
        return completed.stdout.strip()


def parse_json_output(output: str, code: str, name: str) -> Any:
    for line in reversed(output.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise BootstrapError(code, f"{name} did not return valid JSON")


def inspect_labels(
    runner: CommandRunner, object_type: str, name: str, format_value: str
) -> dict[str, str]:
    output = runner.run(
        f"inspect_{object_type}_labels",
        ["docker", object_type, "inspect", name, "--format", format_value],
        failure_code="isolation_target_missing",
    )
    labels = parse_json_output(
        output, "isolation_label_invalid", f"{object_type} labels"
    )
    if not isinstance(labels, dict):
        raise BootstrapError(
            "isolation_label_invalid", f"{object_type} labels are missing"
        )
    return {str(key): str(value) for key, value in labels.items()}


def validate_isolation(
    runner: CommandRunner, project: str, container: str, network: str
) -> None:
    container_labels = inspect_labels(
        runner, "container", container, "{{json .Config.Labels}}"
    )
    network_labels = inspect_labels(runner, "network", network, "{{json .Labels}}")
    validate_isolation_labels(project, container_labels, network_labels)

    running = runner.run(
        "inspect_primary_state",
        ["docker", "inspect", container, "--format", "{{.State.Running}}"],
        failure_code="isolation_target_missing",
    )
    if running.lower() != "true":
        raise BootstrapError("primary_not_running", "primary container must be running")


def validate_image(runner: CommandRunner, image: str) -> str:
    immutable_image = validate_image_reference(image)
    runner.run(
        "inspect_application_image",
        ["docker", "image", "inspect", immutable_image, "--format", "{{.Id}}"],
        failure_code="application_image_missing",
    )
    return immutable_image


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


APP_METADATA_PROBE = """
import json
from hashlib import sha256
from app.core.database import Base
import app.models

names = sorted(table.name for table in Base.metadata.sorted_tables if table.schema in (None, "public"))
digest = sha256((chr(10).join(names) + chr(10)).encode()).hexdigest()
print(json.dumps({"table_count": len(names), "schema_sha256": digest}, sort_keys=True))
""".strip()


APP_SCHEMA_BOOTSTRAP = """
import asyncio
from app.core.database import Base, engine
import app.models

async def main():
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

asyncio.run(main())
""".strip()


def run_application(
    runner: CommandRunner,
    *,
    step: str,
    image: str,
    network: str,
    environment_values: dict[str, str],
    entrypoint: str,
    arguments: list[str],
    failure_code: str,
    timeout: int = 300,
) -> str:
    environment = os.environ.copy()
    environment.update(environment_values)
    argv = [
        "docker",
        "run",
        "--rm",
        "--network",
        network,
        "--label",
        "com.dcim.story=39.3",
        "--label",
        "com.dcim.dr.role=schema-bootstrap",
    ]
    for name in sorted(environment_values):
        argv.extend(["--env", name])
    argv.extend(["--entrypoint", entrypoint, image, *arguments])
    return runner.run(
        step,
        argv,
        env=environment,
        timeout=timeout,
        failure_code=failure_code,
    )


def validate_application_metadata(
    runner: CommandRunner,
    image: str,
    expected_hash: str,
    hmac_key: str,
) -> None:
    output = run_application(
        runner,
        step="validate_application_metadata",
        image=image,
        network="none",
        environment_values={"FAULT_TREE_HMAC_KEY": hmac_key},
        entrypoint="python",
        arguments=["-c", APP_METADATA_PROBE],
        failure_code="application_metadata_probe_failed",
    )
    payload = parse_json_output(
        output, "application_metadata_invalid", "application metadata probe"
    )
    if not isinstance(payload, dict):
        raise BootstrapError(
            "application_metadata_invalid",
            "application metadata probe returned invalid data",
        )
    if (
        payload.get("table_count") != EXPECTED_TABLE_COUNT
        or payload.get("schema_sha256") != expected_hash
    ):
        raise BootstrapError(
            "application_schema_hash_mismatch",
            "application image metadata hash does not match the approved release schema",
        )


def query_release_tables(
    runner: CommandRunner,
    container: str,
    database: str,
    database_user: str,
    step: str,
) -> list[str]:
    output = psql(
        runner,
        container,
        database,
        database_user,
        step,
        "SELECT COALESCE(json_agg(tablename ORDER BY tablename)::text, '[]') "
        "FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version';",
    )
    payload = parse_json_output(
        output, "database_schema_invalid", "database schema query"
    )
    if not isinstance(payload, list) or any(
        not isinstance(item, str) for item in payload
    ):
        raise BootstrapError(
            "database_schema_invalid", "database schema query returned invalid data"
        )
    return sorted(payload)


def validate_database_schema(
    actual_tables: list[str], expected_tables: list[str], expected_hash: str
) -> None:
    if (
        actual_tables != expected_tables
        or normalized_schema_hash(actual_tables) != expected_hash
    ):
        raise BootstrapError(
            "database_schema_hash_mismatch",
            "database schema hash does not match the approved release schema",
        )


def create_release_schema(
    runner: CommandRunner,
    *,
    image: str,
    network: str,
    database_url: str,
    hmac_key: str,
) -> None:
    run_application(
        runner,
        step="create_release_schema",
        image=image,
        network=network,
        environment_values={
            "DATABASE_URL": database_url,
            "FAULT_TREE_HMAC_KEY": hmac_key,
        },
        entrypoint="python",
        arguments=["-c", APP_SCHEMA_BOOTSTRAP],
        failure_code="schema_create_failed",
        timeout=900,
    )


def run_alembic(
    runner: CommandRunner,
    *,
    step: str,
    image: str,
    network: str,
    database_url: str,
    hmac_key: str,
    arguments: list[str],
) -> None:
    run_application(
        runner,
        step=step,
        image=image,
        network=network,
        environment_values={
            "DATABASE_URL": database_url,
            "FAULT_TREE_HMAC_KEY": hmac_key,
        },
        entrypoint="alembic",
        arguments=["-c", "/app/alembic.ini", *arguments],
        failure_code="migration_command_failed",
        timeout=900,
    )


def verify_timescaledb(
    runner: CommandRunner,
    container: str,
    database: str,
    database_user: str,
) -> None:
    value = psql(
        runner,
        container,
        database,
        database_user,
        "verify_timescaledb_objects",
        "SELECT CASE WHEN "
        "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'point_history') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression') AND "
        "EXISTS (SELECT 1 FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention') "
        "THEN 1 ELSE 0 END;",
    )
    if value != "1":
        raise BootstrapError(
            "timescaledb_objects_missing", "required TimescaleDB objects are missing"
        )


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
    parser.add_argument("--application-image", required=True)
    parser.add_argument("--postgres-password-file", type=Path, required=True)
    parser.add_argument("--database", default="dcim")
    parser.add_argument("--database-user", default="dcim")
    parser.add_argument("--database-host", default="postgres-primary")
    parser.add_argument("--database-port", type=int, default=5432)
    parser.add_argument("--schema-file", type=Path, default=DEFAULT_SCHEMA_FILE)
    parser.add_argument("--expected-schema-sha256", default=EXPECTED_SCHEMA_SHA256)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def execute(
    args: argparse.Namespace, runner: CommandRunner, result: dict[str, Any]
) -> None:
    expected_tables, schema_hash = load_expected_schema(
        args.schema_file, args.expected_schema_sha256
    )
    image = validate_image(runner, args.application_image)
    validate_isolation(runner, args.project, args.postgres_container, args.network)

    hmac_key = secrets.token_hex(32)
    validate_application_metadata(runner, image, schema_hash, hmac_key)

    current_tables = query_release_tables(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
        "verify_empty_database",
    )
    require_empty_database(len(current_tables))

    password = load_secret_file(
        args.postgres_password_file,
        "postgres_password_missing",
        "PostgreSQL password",
    )
    database_url = (
        f"postgresql+asyncpg://{quote(args.database_user, safe='')}:{quote(password, safe='')}"
        f"@{args.database_host}:{args.database_port}/{quote(args.database, safe='')}"
    )

    create_release_schema(
        runner,
        image=image,
        network=args.network,
        database_url=database_url,
        hmac_key=hmac_key,
    )
    created_tables = query_release_tables(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
        "verify_created_schema",
    )
    validate_database_schema(created_tables, expected_tables, schema_hash)

    run_alembic(
        runner,
        step="stamp_bootstrap_revision",
        image=image,
        network=args.network,
        database_url=database_url,
        hmac_key=hmac_key,
        arguments=["stamp", BOOTSTRAP_REVISION],
    )
    run_alembic(
        runner,
        step="upgrade_timescaledb_revision",
        image=image,
        network=args.network,
        database_url=database_url,
        hmac_key=hmac_key,
        arguments=["upgrade", TIMESCALE_REVISION],
    )
    run_alembic(
        runner,
        step="stamp_release_head",
        image=image,
        network=args.network,
        database_url=database_url,
        hmac_key=hmac_key,
        arguments=["stamp", RELEASE_HEAD],
    )
    run_alembic(
        runner,
        step="verify_upgrade_head",
        image=image,
        network=args.network,
        database_url=database_url,
        hmac_key=hmac_key,
        arguments=["upgrade", "head"],
    )

    actual_head = psql(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
        "verify_alembic_head",
        "SELECT version_num FROM alembic_version;",
    )
    if actual_head != RELEASE_HEAD:
        raise BootstrapError(
            "alembic_not_at_head", f"expected {RELEASE_HEAD}, got {actual_head}"
        )

    verify_timescaledb(
        runner, args.postgres_container, args.database, args.database_user
    )
    final_tables = query_release_tables(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
        "verify_final_schema",
    )
    validate_database_schema(final_tables, expected_tables, schema_hash)

    result.update(
        {
            "status": "pass",
            "failure_code": None,
            "application_image": image,
            "schema_sha256": schema_hash,
            "table_count": len(final_tables),
            "alembic_head": actual_head,
            "timescaledb_revision": TIMESCALE_REVISION,
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
    output = args.output_dir / "schema-bootstrap-last-run.json"
    try:
        execute(args, runner, result)
    except BootstrapError as exc:
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
