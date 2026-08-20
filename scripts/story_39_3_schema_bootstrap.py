#!/usr/bin/env python3
"""Restore the approved canonical PostgreSQL schema into an empty DR primary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any
import uuid


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "deploy" / "postgres-backup"
DEFAULT_CANONICAL_DUMP = ARTIFACT_DIR / "canonical-schema.dump"
DEFAULT_CANONICAL_MANIFEST = ARTIFACT_DIR / "canonical-schema-manifest.json"
DEFAULT_SCHEMA_FILE = ARTIFACT_DIR / "expected-schema-tables.txt"
PROJECT_PATTERN = re.compile(r"^dcim-story-39-3-[a-z0-9][a-z0-9-]*$")
IMAGE_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
RELEASE_HEAD = "20260707_0100"
SOURCE_REVISION = "436a8e778037bf6fcf9140b757e9584e669ad33b"
EXPECTED_TABLE_COUNT = 189
EXPECTED_SCHEMA_SHA256 = (
    "0df268cf4fa358af46f127c716d5d6f40ccbe3c4d7017a8f5f68e33bc7dc6e25"
)
CANONICAL_CONTAINER_PATH = "/tmp/dcim-story-39-3-canonical-schema.dump"

CATALOG_SQL = """
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
  ), '[]'::jsonb),
  'alembic_head', (SELECT version_num FROM public.alembic_version),
  'timescaledb', jsonb_build_object(
    'hypertables', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'schema', hypertable_schema,
        'name', hypertable_name,
        'compression', compression_enabled
      ) ORDER BY hypertable_name)
      FROM timescaledb_information.hypertables
      WHERE hypertable_schema = 'public' AND hypertable_name = 'point_history'
    ), '[]'::jsonb),
    'jobs', COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'proc_name', proc_name,
        'schedule_interval', schedule_interval,
        'config', config
      ) ORDER BY proc_name)
      FROM timescaledb_information.jobs
      WHERE hypertable_schema = 'public' AND hypertable_name = 'point_history'
        AND proc_name IN ('policy_compression', 'policy_retention')
    ), '[]'::jsonb)
  )
)::text;
""".strip()

OCCUPANCY_SQL = """
SELECT json_build_object(
  'public_relations', (
    SELECT count(*) FROM pg_class cls
    JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace
    WHERE nsp.nspname = 'public'
  ),
  'public_functions', (
    SELECT count(*) FROM pg_proc proc
    JOIN pg_namespace nsp ON nsp.oid = proc.pronamespace
    WHERE nsp.nspname = 'public'
  ),
  'public_types', (
    SELECT count(*) FROM pg_type typ
    JOIN pg_namespace nsp ON nsp.oid = typ.typnamespace
    WHERE nsp.nspname = 'public' AND typ.typtype IN ('c', 'd', 'e', 'r')
  ),
  'user_schemas', (
    SELECT count(*) FROM pg_namespace
    WHERE nspname NOT IN ('public', 'information_schema')
      AND nspname NOT LIKE 'pg_%'
  ),
  'non_builtin_extensions', (
    SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql'
  )
)::text;
""".strip()


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


def file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BootstrapError(
            "canonical_artifact_missing", "cannot read canonical schema artifact"
        ) from exc
    return digest.hexdigest()


def normalized_schema_hash(names: list[str]) -> str:
    payload = ("\n".join(sorted(names)) + "\n").encode()
    return sha256(payload).hexdigest()


def normalized_json_hash(payload: Any) -> str:
    normalized = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
    return sha256(normalized.encode()).hexdigest()


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
            f"expected schema manifest must contain {EXPECTED_TABLE_COUNT} unique tables",
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


def load_canonical_manifest(
    path: Path, dump_path: Path, application_image: str
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapError(
            "canonical_manifest_invalid", "cannot read canonical schema manifest"
        ) from exc
    expected = {
        "schema_version": 1,
        "artifact": dump_path.name,
        "alembic_head": RELEASE_HEAD,
        "source_revision": SOURCE_REVISION,
        "application_image": application_image,
        "table_count": EXPECTED_TABLE_COUNT,
        "table_names_sha256": EXPECTED_SCHEMA_SHA256,
    }
    if not isinstance(payload, dict) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise BootstrapError(
            "canonical_manifest_invalid",
            "canonical schema provenance does not match this release",
        )
    artifact_hash = payload.get("artifact_sha256")
    catalog_hash = payload.get("catalog_sha256")
    runtime_image = payload.get("runtime_image")
    if (
        not isinstance(artifact_hash, str)
        or SHA256_PATTERN.fullmatch(artifact_hash) is None
        or not isinstance(catalog_hash, str)
        or SHA256_PATTERN.fullmatch(catalog_hash) is None
        or not isinstance(runtime_image, str)
        or IMAGE_PATTERN.fullmatch(runtime_image) is None
    ):
        raise BootstrapError(
            "canonical_manifest_invalid",
            "canonical manifest hashes or runtime image are invalid",
        )
    if file_sha256(dump_path) != artifact_hash:
        raise BootstrapError(
            "canonical_artifact_hash_mismatch",
            "canonical schema artifact hash does not match",
        )
    return payload


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
    if not (
        network_labels.get("com.dcim.dr.site") == "primary"
        or network_labels.get("com.dcim.dr.role") == "stable-endpoint"
    ):
        raise BootstrapError(
            "isolation_label_invalid",
            "network is neither the primary site nor the stable endpoint",
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

    def try_run(
        self, step: str, argv: list[str], *, timeout: int = 60
    ) -> tuple[bool, str]:
        try:
            return True, self.run(step, argv, timeout=timeout)
        except BootstrapError:
            return False, ""


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
) -> str:
    container_labels = inspect_labels(
        runner, "container", container, "{{json .Config.Labels}}"
    )
    network_labels = inspect_labels(runner, "network", network, "{{json .Labels}}")
    validate_isolation_labels(project, container_labels, network_labels)
    runtime = runner.run(
        "inspect_primary_runtime",
        [
            "docker",
            "inspect",
            container,
            "--format",
            "{{json .State.Running}}|{{.Config.Image}}|{{json .NetworkSettings.Networks}}",
        ],
        failure_code="isolation_target_missing",
    )
    try:
        running_json, image, networks_json = runtime.split("|", 2)
        running = json.loads(running_json)
        networks = json.loads(networks_json)
    except (ValueError, json.JSONDecodeError) as exc:
        raise BootstrapError(
            "isolation_runtime_invalid", "primary runtime inspection is invalid"
        ) from exc
    if running is not True or not isinstance(networks, dict) or network not in networks:
        raise BootstrapError(
            "isolation_runtime_invalid",
            "primary is not running on the validated network",
        )
    if IMAGE_PATTERN.fullmatch(image) is None:
        raise BootstrapError(
            "mutable_postgres_image", "primary image must use an immutable digest"
        )
    return image


def validate_application_image(runner: CommandRunner, image: str) -> str:
    immutable_image = validate_image_reference(image)
    output = runner.run(
        "inspect_application_image",
        [
            "docker",
            "image",
            "inspect",
            immutable_image,
            "--format",
            "{{json .Config.Labels}}",
        ],
        failure_code="application_image_missing",
    )
    labels = parse_json_output(
        output, "application_image_provenance_mismatch", "application image labels"
    )
    if (
        not isinstance(labels, dict)
        or labels.get("org.opencontainers.image.revision") != SOURCE_REVISION
    ):
        raise BootstrapError(
            "application_image_provenance_mismatch",
            "application image source revision does not match the canonical schema",
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


def query_database_occupancy(
    runner: CommandRunner, container: str, database: str, database_user: str
) -> dict[str, int]:
    output = psql(
        runner,
        container,
        database,
        database_user,
        "verify_empty_database",
        OCCUPANCY_SQL,
    )
    payload = parse_json_output(
        output, "database_occupancy_invalid", "database occupancy"
    )
    if not isinstance(payload, dict) or any(
        not isinstance(value, int) for value in payload.values()
    ):
        raise BootstrapError(
            "database_occupancy_invalid", "database occupancy is invalid"
        )
    return {str(key): int(value) for key, value in payload.items()}


def require_empty_database(occupancy: dict[str, int] | int) -> None:
    if isinstance(occupancy, int):
        occupied = occupancy != 0
    else:
        occupied = any(value != 0 for value in occupancy.values())
    if occupied:
        raise BootstrapError(
            "database_not_empty",
            "database must be empty of all user objects before bootstrap",
        )


def query_release_tables(
    runner: CommandRunner,
    container: str,
    database: str,
    database_user: str,
) -> list[str]:
    output = psql(
        runner,
        container,
        database,
        database_user,
        "query_release_tables",
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


def query_catalog(
    runner: CommandRunner,
    container: str,
    database: str,
    database_user: str,
) -> dict[str, Any]:
    output = psql(
        runner,
        container,
        database,
        database_user,
        "query_canonical_catalog",
        CATALOG_SQL,
    )
    payload = parse_json_output(output, "database_catalog_invalid", "database catalog")
    if not isinstance(payload, dict):
        raise BootstrapError(
            "database_catalog_invalid", "database catalog is not an object"
        )
    return payload


def validate_catalog(
    catalog: dict[str, Any],
    tables: list[str],
    expected_tables: list[str],
    manifest: dict[str, Any],
) -> str:
    if (
        tables != expected_tables
        or normalized_schema_hash(tables) != EXPECTED_SCHEMA_SHA256
    ):
        raise BootstrapError(
            "database_schema_hash_mismatch", "database table inventory does not match"
        )
    if catalog.get("alembic_head") != RELEASE_HEAD:
        raise BootstrapError(
            "alembic_not_at_head", "canonical schema is not at the release head"
        )
    timescaledb = catalog.get("timescaledb")
    if not isinstance(timescaledb, dict):
        raise BootstrapError(
            "timescaledb_objects_missing", "TimescaleDB catalog is missing"
        )
    hypertables = timescaledb.get("hypertables")
    jobs = timescaledb.get("jobs")
    if (
        not isinstance(hypertables, list)
        or len(hypertables) != 1
        or not isinstance(jobs, list)
        or len(jobs) != 2
    ):
        raise BootstrapError(
            "timescaledb_objects_missing",
            "public.point_history and both bound policies are required",
        )
    catalog_hash = normalized_json_hash(catalog)
    if catalog_hash != manifest["catalog_sha256"]:
        raise BootstrapError(
            "database_catalog_hash_mismatch",
            "database catalog differs from the canonical release",
        )
    return catalog_hash


def validate_application_metadata(
    runner: CommandRunner,
    image: str,
    expected_hash: str,
) -> None:
    probe = (
        "import json; from hashlib import sha256; "
        "from app.core.database import Base; import app.api.v1; import app.models; "
        "names=sorted(t.name for t in Base.metadata.sorted_tables if t.schema in (None,'public')); "
        "digest=sha256((chr(10).join(names)+chr(10)).encode()).hexdigest(); "
        "print(json.dumps({'table_count':len(names),'schema_sha256':digest},sort_keys=True))"
    )
    name = f"dcim-story-39-3-schema-metadata-{uuid.uuid4().hex[:10]}"
    probe_secret = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    process_environment = dict(os.environ)
    process_environment["FAULT_TREE_HMAC_KEY"] = probe_secret
    runner.run(
        "create_application_metadata_probe",
        [
            "docker",
            "create",
            "--name",
            name,
            "--network",
            "none",
            "--label",
            "com.dcim.story=39.3",
            "--label",
            "com.dcim.dr.role=schema-metadata",
            "--entrypoint",
            "python",
            "--env",
            "FAULT_TREE_HMAC_KEY",
            image,
            "-c",
            probe,
        ],
        env=process_environment,
        timeout=60,
        failure_code="application_metadata_probe_failed",
    )
    try:
        output = runner.run(
            "validate_application_metadata",
            ["docker", "start", "--attach", name],
            timeout=300,
            failure_code="application_metadata_probe_failed",
        )
    finally:
        removed, _ = runner.try_run(
            "remove_application_metadata_probe",
            ["docker", "rm", "--force", name],
        )
        if not removed:
            raise BootstrapError(
                "schema_container_cleanup_failed",
                "could not remove application metadata probe",
            )
    payload = parse_json_output(
        output, "application_metadata_invalid", "application metadata"
    )
    if (
        not isinstance(payload, dict)
        or payload.get("table_count") != EXPECTED_TABLE_COUNT
        or payload.get("schema_sha256") != expected_hash
    ):
        raise BootstrapError(
            "application_schema_hash_mismatch",
            "application model table inventory does not match the canonical release",
        )


def restore_canonical_schema(
    runner: CommandRunner,
    *,
    dump_path: Path,
    container: str,
    database: str,
    database_user: str,
) -> None:
    runner.run(
        "copy_canonical_schema",
        ["docker", "cp", str(dump_path), f"{container}:{CANONICAL_CONTAINER_PATH}"],
        timeout=120,
        failure_code="canonical_artifact_copy_failed",
    )
    try:
        runner.run(
            "restore_canonical_schema",
            [
                "docker",
                "exec",
                "--user",
                "postgres",
                container,
                "timeout",
                "--signal=KILL",
                "--kill-after=10",
                "900",
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                database,
                "--username",
                database_user,
                CANONICAL_CONTAINER_PATH,
            ],
            timeout=930,
            failure_code="canonical_restore_failed",
        )
    finally:
        removed, _ = runner.try_run(
            "remove_canonical_schema_copy",
            ["docker", "exec", container, "rm", "-f", CANONICAL_CONTAINER_PATH],
        )
        if not removed:
            raise BootstrapError(
                "canonical_artifact_cleanup_failed",
                "could not remove staged canonical artifact",
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
    parser.add_argument("--canonical-dump", type=Path, default=DEFAULT_CANONICAL_DUMP)
    parser.add_argument(
        "--canonical-manifest", type=Path, default=DEFAULT_CANONICAL_MANIFEST
    )
    parser.add_argument("--schema-file", type=Path, default=DEFAULT_SCHEMA_FILE)
    parser.add_argument("--expected-schema-sha256", default=EXPECTED_SCHEMA_SHA256)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def execute(
    args: argparse.Namespace, runner: CommandRunner, result: dict[str, Any]
) -> None:
    if (
        IDENTIFIER_PATTERN.fullmatch(args.database) is None
        or IDENTIFIER_PATTERN.fullmatch(args.database_user) is None
    ):
        raise BootstrapError(
            "database_identifier_invalid",
            "database identifiers must be simple PostgreSQL names",
        )
    expected_tables, table_hash = load_expected_schema(
        args.schema_file, args.expected_schema_sha256
    )
    application_image = validate_application_image(runner, args.application_image)
    manifest = load_canonical_manifest(
        args.canonical_manifest,
        args.canonical_dump,
        application_image,
    )
    runtime_image = validate_isolation(
        runner,
        args.project,
        args.postgres_container,
        args.network,
    )
    if runtime_image != manifest["runtime_image"]:
        raise BootstrapError(
            "canonical_runtime_mismatch",
            "primary runtime image does not match the canonical schema build",
        )
    require_value(
        args.postgres_password_file.read_text(encoding="utf-8"),
        "postgres_password_missing",
        "PostgreSQL password",
    )
    validate_application_metadata(runner, application_image, table_hash)
    occupancy = query_database_occupancy(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
    )
    require_empty_database(occupancy)
    restore_canonical_schema(
        runner,
        dump_path=args.canonical_dump,
        container=args.postgres_container,
        database=args.database,
        database_user=args.database_user,
    )
    tables = query_release_tables(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
    )
    catalog = query_catalog(
        runner,
        args.postgres_container,
        args.database,
        args.database_user,
    )
    catalog_hash = validate_catalog(catalog, tables, expected_tables, manifest)
    result.update(
        {
            "status": "pass",
            "failure_code": None,
            "project": args.project,
            "postgres_container": args.postgres_container,
            "network": args.network,
            "database": args.database,
            "database_user": args.database_user,
            "application_image": application_image,
            "runtime_image": runtime_image,
            "canonical_artifact_sha256": manifest["artifact_sha256"],
            "catalog_sha256": catalog_hash,
            "table_names_sha256": table_hash,
            "table_count": len(tables),
            "alembic_head": catalog["alembic_head"],
            "timescaledb": catalog["timescaledb"],
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
