#!/usr/bin/env python3
"""Run the Story 39.3 controlled PostgreSQL failover/failback drill."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPO_ROOT / "deploy" / "postgres-backup" / "failover-contract.yaml"
PROJECT_PATTERN = re.compile(r"^dcim-story-39-3-[a-z0-9][a-z0-9-]*$")
IMAGE_PATTERN = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
RUN_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,80}$")
STABLE_ENDPOINT = "postgres-writer"
PROBE_TABLE = "story_39_3_failover_probe"
SAME_HOST_EVIDENCE_CLASS = "mechanism-only"
FAULT_TREE_HMAC_KEY = "FAULT_TREE_HMAC_KEY"

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
            await connection.execute(text("CREATE TEMP TABLE story_39_3_app_failover_probe(value integer NOT NULL)"))
            await connection.execute(text("INSERT INTO story_39_3_app_failover_probe(value) VALUES (1)"))
            value = (await connection.execute(text("SELECT value FROM story_39_3_app_failover_probe"))).scalar_one()
            if value != 1:
                raise RuntimeError("application write probe mismatch")
    finally:
        await engine.dispose()

asyncio.run(main())
""".strip()


class DrillError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("UTC timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def calculate_rpo(
    acknowledged: list[dict[str, Any]],
    recovered_sequences: set[int],
    recovered_at: str,
) -> dict[str, Any]:
    """Calculate missing acknowledged commits and the age of the newest missing commit."""

    recovered_time = parse_utc(recovered_at)
    commits: dict[int, datetime] = {}
    for item in acknowledged:
        sequence = int(item["sequence"])
        if sequence in commits:
            raise ValueError(f"duplicate acknowledged sequence: {sequence}")
        commits[sequence] = parse_utc(str(item["committed_at"]))

    missing_sequences = sorted(set(commits) - {int(item) for item in recovered_sequences})
    if missing_sequences:
        newest_missing = max(commits[sequence] for sequence in missing_sequences)
        missing_age = max(0.0, (recovered_time - newest_missing).total_seconds())
    else:
        missing_age = 0.0
    return {
        "missing_commit_count": len(missing_sequences),
        "missing_sequences": missing_sequences,
        "latest_missing_commit_age_seconds": round(missing_age, 6),
    }


class Timeline:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def record(self, event: str, *, status: str = "ok", **details: Any) -> float:
        monotonic_at = time.monotonic()
        payload = {
            "event": event,
            "status": status,
            "utc": utc_now(),
            "monotonic_seconds": round(monotonic_at, 6),
            **details,
        }
        with self._lock:
            self.events.append(payload)
        return monotonic_at


class CommandRunner:
    def __init__(self, timeline: Timeline) -> None:
        self.timeline = timeline
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def _execute(
        self,
        step: str,
        argv: list[str],
        *,
        env: dict[str, str] | None,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
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
            exit_code: int | None = completed.returncode
            status = "ok" if completed.returncode == 0 else "error"
        except (OSError, subprocess.TimeoutExpired) as exc:
            completed = subprocess.CompletedProcess(argv, 124, "", type(exc).__name__)
            exit_code = None
            status = "error"

        event = {
            "step": step,
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - started, 6),
            "exit_code": exit_code,
            "status": status,
        }
        with self._lock:
            self.events.append(event)
        self.timeline.record(step, status=status, exit_code=exit_code)
        return completed

    def run(
        self,
        step: str,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        timeout: float = 300,
        failure_code: str = "command_failed",
    ) -> str:
        completed = self._execute(step, argv, env=env, timeout=timeout)
        if completed.returncode != 0:
            raise DrillError(failure_code, f"{step} exited unsuccessfully")
        return completed.stdout.strip()

    def try_run(
        self,
        step: str,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        timeout: float = 60,
    ) -> tuple[bool, str]:
        completed = self._execute(step, argv, env=env, timeout=timeout)
        return completed.returncode == 0, completed.stdout.strip()


def parse_json_output(output: str, code: str, name: str) -> Any:
    for line in reversed(output.splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise DrillError(code, f"{name} did not return valid JSON")


def load_secret_file(path: Path, code: str, name: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DrillError(code, f"cannot read {name}") from exc
    if not value or "placeholder" in value.lower():
        raise DrillError(code, f"{name} is invalid")
    return value


def inspect_json(runner: CommandRunner, object_type: str, name: str, template: str) -> Any:
    output = runner.run(
        f"inspect_{object_type}_{name}",
        ["docker", object_type, "inspect", name, "--format", template],
        failure_code="isolation_target_missing",
    )
    return parse_json_output(output, "isolation_label_invalid", f"{object_type} inspection")


def inspect_labels(runner: CommandRunner, object_type: str, name: str) -> dict[str, str]:
    labels = inspect_json(runner, object_type, name, "{{json .Labels}}")
    if not isinstance(labels, dict):
        raise DrillError("isolation_label_invalid", f"{object_type} labels are missing")
    return {str(key): str(value) for key, value in labels.items()}


def inspect_container_labels(runner: CommandRunner, name: str) -> dict[str, str]:
    labels = inspect_json(runner, "container", name, "{{json .Config.Labels}}")
    if not isinstance(labels, dict):
        raise DrillError("isolation_label_invalid", "container labels are missing")
    return {str(key): str(value) for key, value in labels.items()}


def require_labels(
    labels: dict[str, str],
    *,
    project: str,
    role_key: str,
    role_value: str,
) -> None:
    expected = {
        "com.dcim.story": "39.3",
        "com.docker.compose.project": project,
        role_key: role_value,
    }
    for key, value in expected.items():
        if labels.get(key) != value:
            raise DrillError("isolation_label_invalid", f"{key} does not match the drill contract")


def container_running(runner: CommandRunner, container: str) -> bool:
    value = runner.run(
        f"inspect_running_{container}",
        ["docker", "inspect", container, "--format", "{{.State.Running}}"],
        failure_code="isolation_target_missing",
    )
    return value.lower() == "true"


def network_container_names(runner: CommandRunner, network: str) -> set[str]:
    payload = inspect_json(runner, "network", network, "{{json .Containers}}")
    if not isinstance(payload, dict):
        return set()
    return {str(item.get("Name")) for item in payload.values() if isinstance(item, dict) and item.get("Name")}


def validate_isolation(
    runner: CommandRunner,
    *,
    project: str,
    primary: str,
    standby: str,
    stable_network: str,
    replication_network: str,
    primary_site_network: str,
) -> None:
    if PROJECT_PATTERN.fullmatch(project) is None:
        raise DrillError("isolation_project_invalid", "project name is outside Story 39.3")

    require_labels(
        inspect_container_labels(runner, primary),
        project=project,
        role_key="com.dcim.dr.role",
        role_value="primary",
    )
    require_labels(
        inspect_container_labels(runner, standby),
        project=project,
        role_key="com.dcim.dr.role",
        role_value="standby",
    )
    require_labels(
        inspect_labels(runner, "network", stable_network),
        project=project,
        role_key="com.dcim.dr.role",
        role_value="stable-endpoint",
    )
    require_labels(
        inspect_labels(runner, "network", replication_network),
        project=project,
        role_key="com.dcim.dr.role",
        role_value="replication-transit",
    )
    require_labels(
        inspect_labels(runner, "network", primary_site_network),
        project=project,
        role_key="com.dcim.dr.site",
        role_value="primary",
    )
    if not container_running(runner, primary) or not container_running(runner, standby):
        raise DrillError("topology_not_ready", "primary and standby must both be running")

    endpoint_members = network_container_names(runner, stable_network)
    if primary not in endpoint_members or standby in endpoint_members:
        raise DrillError("stable_endpoint_invalid", "postgres-writer must initially resolve only to primary")


def psql_container(
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


def load_primary_runtime(runner: CommandRunner, primary: str) -> dict[str, Any]:
    image = runner.run(
        "inspect_primary_image",
        ["docker", "inspect", primary, "--format", "{{.Config.Image}}"],
        failure_code="primary_runtime_invalid",
    )
    mounts = inspect_json(runner, "container", primary, "{{json .Mounts}}")
    if not isinstance(mounts, list):
        raise DrillError("primary_runtime_invalid", "primary runtime inspection is incomplete")
    if IMAGE_PATTERN.fullmatch(image) is None:
        raise DrillError("mutable_postgres_image", "PostgreSQL image must use an immutable @sha256 reference")
    return {"image": image, "mounts": mounts}


def mount_by_destination(runtime: dict[str, Any], destination: str) -> dict[str, Any]:
    for mount in runtime["mounts"]:
        if isinstance(mount, dict) and mount.get("Destination") == destination:
            return mount
    raise DrillError("primary_runtime_invalid", f"required mount {destination} is missing")


def create_probe_client(
    runner: CommandRunner,
    *,
    project: str,
    stable_network: str,
    runtime: dict[str, Any],
) -> str:
    password_mount = mount_by_destination(runtime, "/run/secrets/postgres_password")
    if password_mount.get("Type") != "bind" or not password_mount.get("Source"):
        raise DrillError("postgres_password_missing", "PostgreSQL password secret mount is invalid")

    name = f"{project}-failover-probe-{uuid.uuid4().hex[:10]}"
    runner.run(
        "create_failover_probe_client",
        [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--network",
            stable_network,
            "--label",
            "com.dcim.story=39.3",
            "--label",
            f"com.docker.compose.project={project}",
            "--label",
            "com.dcim.dr.role=failover-probe",
            "--mount",
            f"type=bind,src={password_mount['Source']},dst=/run/secrets/postgres_password,readonly",
            "--entrypoint",
            "sleep",
            str(runtime["image"]),
            "infinity",
        ],
        failure_code="probe_client_create_failed",
    )
    return name


def probe_psql_argv(
    probe_client: str,
    database: str,
    database_user: str,
    sql: str,
) -> list[str]:
    return [
        "docker",
        "exec",
        probe_client,
        "bash",
        "-ceu",
        'export PGPASSWORD="$(</run/secrets/postgres_password)"; exec "$@"',
        "bash",
        "psql",
        "--no-psqlrc",
        "--tuples-only",
        "--no-align",
        "--set",
        "ON_ERROR_STOP=1",
        "--host",
        STABLE_ENDPOINT,
        "--port",
        "5432",
        "--dbname",
        database,
        "--username",
        database_user,
        "--command",
        sql,
    ]


class ProbeWriter:
    def __init__(
        self,
        *,
        runner: CommandRunner,
        timeline: Timeline,
        probe_client: str,
        database: str,
        database_user: str,
        run_id: str,
        interval_seconds: float,
    ) -> None:
        self.runner = runner
        self.timeline = timeline
        self.probe_client = probe_client
        self.database = database
        self.database_user = database_user
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.acknowledged: list[dict[str, Any]] = []
        self.attempts: list[dict[str, Any]] = []
        self._sequence = 0
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._active = threading.Event()
        self._condition = threading.Condition()
        self._thread = threading.Thread(target=self._run, name="story-39-3-write-probe", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._paused.clear()
        if self._thread.is_alive():
            self._thread.join(timeout=10)

    def pause_and_wait(self, timeout: float) -> None:
        self._paused.set()
        deadline = time.monotonic() + timeout
        while self._active.is_set():
            if time.monotonic() >= deadline:
                raise DrillError("write_probe_pause_timeout", "write probe did not pause")
            self._stop.wait(0.05)
        self.timeline.record("continuous_write_probe_paused")

    def resume(self) -> None:
        self._paused.clear()
        self.timeline.record("continuous_write_probe_resumed")

    def wait_for_acknowledged(self, count: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        with self._condition:
            while len(self.acknowledged) < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DrillError("write_probe_not_ready", "continuous write probe did not warm up")
                self._condition.wait(min(remaining, 1.0))

    def wait_for_consecutive_successes(
        self,
        *,
        after_monotonic: float,
        required: int,
        timeout: float,
    ) -> float:
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                consecutive = 0
                completed_at: float | None = None
                for attempt in self.attempts:
                    if attempt["monotonic_seconds"] <= after_monotonic:
                        continue
                    if attempt["success"]:
                        consecutive += 1
                        if consecutive >= required:
                            completed_at = float(attempt["monotonic_seconds"])
                            break
                    else:
                        consecutive = 0
                if completed_at is not None:
                    return completed_at
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DrillError("stable_endpoint_not_ready", "stable endpoint did not recover in time")
                self._condition.wait(min(remaining, 1.0))

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._paused.is_set():
                self._stop.wait(0.05)
                continue
            self._active.set()
            self._sequence += 1
            sequence = self._sequence
            sql = (
                f"INSERT INTO {PROBE_TABLE}(run_id, sequence, committed_at) "
                f"VALUES ('{self.run_id}', {sequence}, clock_timestamp()) "
                "RETURNING json_build_object("
                "'sequence', sequence, "
                "'committed_at', to_char(committed_at AT TIME ZONE 'UTC', "
                '\'YYYY-MM-DD"T"HH24:MI:SS.US"Z"\'), '
                "'writer_identity', inet_server_addr()::text)::text;"
            )
            try:
                success, output = self.runner.try_run(
                    f"continuous_write_probe_{sequence}",
                    probe_psql_argv(self.probe_client, self.database, self.database_user, sql),
                    timeout=max(5.0, self.interval_seconds * 4),
                )
                monotonic_at = time.monotonic()
                attempt = {
                    "sequence": sequence,
                    "success": success,
                    "utc": utc_now(),
                    "monotonic_seconds": monotonic_at,
                }
                if success:
                    try:
                        payload = parse_json_output(output, "write_probe_invalid", "write probe")
                    except DrillError:
                        success = False
                        attempt["success"] = False
                    else:
                        acknowledged = {
                            "sequence": int(payload["sequence"]),
                            "committed_at": str(payload["committed_at"]),
                            "writer_identity": str(payload.get("writer_identity", "")),
                        }
                        self.acknowledged.append(acknowledged)
                        self.timeline.record("write_acknowledged", sequence=sequence)
                if not success:
                    self.timeline.record("write_unavailable", status="expected-during-failover", sequence=sequence)
                with self._condition:
                    self.attempts.append(attempt)
                    self._condition.notify_all()
            finally:
                self._active.clear()
            self._stop.wait(self.interval_seconds)


def lsn_to_int(value: str) -> int:
    upper, lower = value.strip().split("/", 1)
    return (int(upper, 16) << 32) + int(lower, 16)


def wait_for_replay_catchup(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    primary: str,
    standby: str,
    database: str,
    database_user: str,
    timeout: float,
    poll_interval: float,
) -> dict[str, str]:
    primary_output = psql_container(
        runner,
        primary,
        database,
        database_user,
        "capture_primary_wal_lsn",
        "CHECKPOINT; SELECT pg_current_wal_lsn();",
    )
    primary_lsn = primary_output.splitlines()[-1]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        standby_lsn = psql_container(
            runner,
            standby,
            database,
            database_user,
            "poll_standby_replay_lsn",
            "SELECT COALESCE(pg_last_wal_replay_lsn()::text, '0/0');",
        ).splitlines()[-1]
        if lsn_to_int(standby_lsn) >= lsn_to_int(primary_lsn):
            timeline.record("replay_lsn_caught_up", primary_lsn=primary_lsn, standby_lsn=standby_lsn)
            return {"primary_lsn": primary_lsn, "standby_lsn": standby_lsn}
        time.sleep(poll_interval)
    raise DrillError("replay_lsn_timeout", "standby replay LSN did not catch up")


def verify_fence(runner: CommandRunner, *, primary: str, stable_network: str) -> None:
    if container_running(runner, primary):
        raise DrillError("primary_not_fenced", "old primary container is still running")
    if primary in network_container_names(runner, stable_network):
        raise DrillError("primary_not_fenced", "old primary remains attached to the stable endpoint network")


def fence_primary(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    primary: str,
    stable_network: str,
    abrupt: bool,
) -> None:
    if abrupt:
        runner.run(
            "kill_old_primary_process",
            ["docker", "kill", "--signal", "KILL", primary],
            timeout=60,
            failure_code="primary_fence_failed",
        )
    else:
        runner.run(
            "stop_old_primary",
            ["docker", "stop", "--time", "30", primary],
            timeout=60,
            failure_code="primary_fence_failed",
        )
    disconnected, _ = runner.try_run(
        "disconnect_old_primary_stable_endpoint",
        ["docker", "network", "disconnect", "--force", stable_network, primary],
    )
    if not disconnected and primary in network_container_names(runner, stable_network):
        raise DrillError("primary_fence_failed", "old primary could not be disconnected")
    verify_fence(runner, primary=primary, stable_network=stable_network)
    timeline.record(
        "primary_fenced",
        container_stopped=True,
        stable_endpoint_disconnected=True,
        fault_injection="sigkill" if abrupt else "controlled-stop",
    )


def promote_standby(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    primary: str,
    standby: str,
    stable_network: str,
    database: str,
    database_user: str,
) -> None:
    verify_fence(runner, primary=primary, stable_network=stable_network)
    recovery_state = psql_container(
        runner,
        standby,
        database,
        database_user,
        "verify_standby_before_promotion",
        "SELECT pg_is_in_recovery();",
    )
    if recovery_state != "t":
        raise DrillError("standby_not_in_recovery", "promotion target is not a standby")
    promoted = psql_container(
        runner,
        standby,
        database,
        database_user,
        "pg_promote",
        "SELECT pg_promote(wait_seconds => 60);",
    )
    if promoted != "t":
        raise DrillError("promotion_failed", "PostgreSQL did not acknowledge promotion")
    final_state = psql_container(
        runner,
        standby,
        database,
        database_user,
        "verify_promotion",
        "SELECT pg_is_in_recovery();",
    )
    if final_state != "f":
        raise DrillError("promotion_failed", "promoted standby remains in recovery")
    timeline.record("standby_promoted")


def switch_writer_alias(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    stable_network: str,
    standby: str,
) -> float:
    if standby in network_container_names(runner, stable_network):
        runner.run(
            "reset_standby_stable_endpoint_attachment",
            ["docker", "network", "disconnect", "--force", stable_network, standby],
            failure_code="endpoint_switch_failed",
        )
    runner.run(
        "connect_promoted_writer_alias",
        ["docker", "network", "connect", "--alias", STABLE_ENDPOINT, stable_network, standby],
        failure_code="endpoint_switch_failed",
    )
    if standby not in network_container_names(runner, stable_network):
        raise DrillError("endpoint_switch_failed", "promoted standby is not on the stable endpoint network")
    return timeline.record("stable_endpoint_switched", hostname=STABLE_ENDPOINT, target=standby)


def recovered_probe_state(
    runner: CommandRunner,
    *,
    standby: str,
    database: str,
    database_user: str,
    run_id: str,
) -> tuple[set[int], dict[str, Any]]:
    output = psql_container(
        runner,
        standby,
        database,
        database_user,
        "read_recovered_probe_sequences",
        "SELECT json_build_object("
        "'sequences', COALESCE(json_agg(sequence ORDER BY sequence), '[]'::json), "
        "'row_count', count(*), "
        "'distinct_count', count(DISTINCT sequence))::text "
        f"FROM {PROBE_TABLE} WHERE run_id = '{run_id}';",
    )
    payload = parse_json_output(output, "recovered_probe_invalid", "recovered probe")
    if payload["row_count"] != payload["distinct_count"]:
        raise DrillError("duplicate_recovered_commit", "recovered probe contains duplicate sequences")
    sequences = {int(item) for item in payload["sequences"]}
    return sequences, payload


def run_application_probe(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    application_image: str,
    stable_network: str,
    database: str,
    database_user: str,
    postgres_password_file: Path,
    fault_tree_hmac_key_env: str,
) -> None:
    if IMAGE_PATTERN.fullmatch(application_image) is None:
        raise DrillError(
            "mutable_application_image",
            "application probe must use an immutable @sha256 reference",
        )
    runner.run(
        "inspect_application_image",
        ["docker", "image", "inspect", application_image, "--format", "{{.Id}}"],
        failure_code="application_image_missing",
    )
    password = load_secret_file(
        postgres_password_file,
        "postgres_password_missing",
        "PostgreSQL password",
    )
    hmac_key = os.environ.get(fault_tree_hmac_key_env, "").strip()
    if len(hmac_key) < 32 or "placeholder" in hmac_key.lower():
        raise DrillError(
            "application_secret_missing",
            f"{fault_tree_hmac_key_env} is missing or invalid",
        )
    database_url = (
        f"postgresql+asyncpg://{quote(database_user, safe='')}:{quote(password, safe='')}"
        f"@{STABLE_ENDPOINT}:5432/{quote(database, safe='')}"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DATABASE_URL": database_url,
            FAULT_TREE_HMAC_KEY: hmac_key,
        }
    )
    runner.run(
        "application_readiness_and_critical_write",
        [
            "docker",
            "run",
            "--rm",
            "--network",
            stable_network,
            "--label",
            "com.dcim.story=39.3",
            "--label",
            "com.dcim.dr.role=failover-application-probe",
            "--env",
            "DATABASE_URL",
            "--env",
            FAULT_TREE_HMAC_KEY,
            "--entrypoint",
            "python",
            application_image,
            "-c",
            APP_PROBE,
        ],
        env=environment,
        timeout=300,
        failure_code="application_probe_failed",
    )
    timeline.record("application_readiness_and_critical_write_passed")


def refuse_untreated_old_primary(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    primary: str,
    stable_network: str,
) -> bool:
    verify_fence(runner, primary=primary, stable_network=stable_network)
    timeline.record("old_primary_rejoin_refused", untreated_old_primary_allowed=False)
    return True


def volume_name(mount: dict[str, Any], destination: str) -> str:
    if mount.get("Type") != "volume" or not mount.get("Name"):
        raise DrillError("primary_runtime_invalid", f"{destination} must use a named volume")
    return str(mount["Name"])


def bind_mount_argument(mount: dict[str, Any]) -> str:
    if mount.get("Type") != "bind" or not mount.get("Source") or not mount.get("Destination"):
        raise DrillError("primary_runtime_invalid", "secret bind mount is invalid")
    suffix = ",readonly" if not mount.get("RW", False) else ""
    return f"type=bind,src={mount['Source']},dst={mount['Destination']}{suffix}"


def full_rebuild_old_primary(
    runner: CommandRunner,
    timeline: Timeline,
    *,
    project: str,
    primary: str,
    promoted_standby: str,
    stable_network: str,
    replication_network: str,
    primary_site_network: str,
    database: str,
    database_user: str,
    run_id: str,
    expected_probe_count: int,
    runtime: dict[str, Any],
    allow_full_rebuild: bool,
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    if not allow_full_rebuild:
        raise DrillError("full_rebuild_not_authorized", "old primary full rebuild requires explicit authorization")
    verify_fence(runner, primary=primary, stable_network=stable_network)

    data_mount = mount_by_destination(runtime, "/var/lib/postgresql/data")
    repository_mount = mount_by_destination(runtime, "/var/lib/pgbackrest")
    replication_secret = mount_by_destination(runtime, "/run/secrets/replication_password")
    cipher_secret = mount_by_destination(runtime, "/run/secrets/pgbackrest_cipher_pass")
    data_volume = volume_name(data_mount, "/var/lib/postgresql/data")
    repository_volume = volume_name(repository_mount, "/var/lib/pgbackrest")

    require_labels(
        inspect_labels(runner, "volume", data_volume),
        project=project,
        role_key="com.dcim.dr.role",
        role_value="primary-data",
    )
    slot = "dcim_old_primary_slot"
    psql_container(
        runner,
        promoted_standby,
        database,
        database_user,
        "create_old_primary_replication_slot",
        f"SELECT pg_create_physical_replication_slot('{slot}') "
        f"WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = '{slot}');",
    )

    runner.run(
        "remove_fenced_old_primary_container",
        ["docker", "rm", primary],
        failure_code="full_rebuild_failed",
    )
    runner.run(
        "clear_fenced_old_primary_data_volume",
        [
            "docker",
            "run",
            "--rm",
            "--label",
            "com.dcim.story=39.3",
            "--mount",
            f"type=volume,src={data_volume},dst=/var/lib/postgresql/data",
            "--entrypoint",
            "bash",
            str(runtime["image"]),
            "-ceu",
            "find /var/lib/postgresql/data -mindepth 1 -depth -delete",
        ],
        failure_code="full_rebuild_failed",
    )

    runner.run(
        "start_full_rebuild_as_standby",
        [
            "docker",
            "run",
            "--detach",
            "--name",
            primary,
            "--hostname",
            "postgres-primary",
            "--label",
            "com.dcim.story=39.3",
            "--label",
            f"com.docker.compose.project={project}",
            "--label",
            "com.dcim.dr.role=standby-rejoined",
            "--network",
            replication_network,
            "--network-alias",
            "postgres-primary",
            "--env",
            "PGDATA=/var/lib/postgresql/data",
            "--env",
            "PRIMARY_HOST=postgres-standby",
            "--env",
            "PRIMARY_PORT=5432",
            "--env",
            f"REPLICATION_SLOT={slot}",
            "--env",
            "REPLICATION_PASSWORD_FILE=/run/secrets/replication_password",
            "--env",
            "PGBACKREST_REPO1_CIPHER_PASS_FILE=/run/secrets/pgbackrest_cipher_pass",
            "--mount",
            f"type=volume,src={data_volume},dst=/var/lib/postgresql/data",
            "--mount",
            f"type=volume,src={repository_volume},dst=/var/lib/pgbackrest",
            "--mount",
            bind_mount_argument(replication_secret),
            "--mount",
            bind_mount_argument(cipher_secret),
            "--entrypoint",
            "/usr/local/bin/standby-entrypoint.sh",
            str(runtime["image"]),
        ],
        timeout=60,
        failure_code="full_rebuild_failed",
    )
    runner.run(
        "connect_rebuilt_old_primary_site",
        ["docker", "network", "connect", "--alias", "postgres-primary", primary_site_network, primary],
        failure_code="full_rebuild_failed",
    )

    writer_lsn = psql_container(
        runner,
        promoted_standby,
        database,
        database_user,
        "capture_promoted_writer_lsn_for_rejoin",
        "SELECT pg_current_wal_lsn();",
    )
    deadline = time.monotonic() + timeout
    replay_lsn = ""
    while time.monotonic() < deadline:
        ok, output = runner.try_run(
            "poll_rebuilt_old_primary",
            [
                "docker",
                "exec",
                "--user",
                "postgres",
                primary,
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
                "SELECT pg_is_in_recovery()::text || '|' || COALESCE(pg_last_wal_replay_lsn()::text, '');",
            ],
        )
        if ok and output.startswith("true|"):
            candidate_lsn = output.split("|", 1)[1]
            if candidate_lsn and lsn_to_int(candidate_lsn) >= lsn_to_int(writer_lsn):
                replay_lsn = candidate_lsn
                break
        time.sleep(poll_interval)
    if not replay_lsn:
        raise DrillError("full_rebuild_failed", "rebuilt old primary did not catch up as a standby")
    probe_count = int(
        psql_container(
            runner,
            primary,
            database,
            database_user,
            "verify_rebuilt_old_primary_probe_data",
            f"SELECT count(*) FROM {PROBE_TABLE} WHERE run_id = '{run_id}';",
        )
    )
    if probe_count != expected_probe_count:
        raise DrillError(
            "full_rebuild_failed",
            "rebuilt old primary does not contain the recovered probe set",
        )
    timeline.record(
        "old_primary_full_rebuild_complete",
        writer_lsn=writer_lsn,
        replay_lsn=replay_lsn,
        probe_count=probe_count,
    )
    return {
        "method": "full_rebuild",
        "container": primary,
        "replication_slot": slot,
        "writer_lsn": writer_lsn,
        "replay_lsn": replay_lsn,
        "probe_count": probe_count,
        "in_recovery": True,
    }


def classify_evidence(
    *,
    failure_domain: str,
    attestation: Path | None,
    contract: dict[str, Any],
) -> dict[str, Any]:
    evidence_contract = contract["evidence_classification"]
    if failure_domain == "same-host":
        if evidence_contract["same_host"] != SAME_HOST_EVIDENCE_CLASS:
            raise DrillError(
                "failover_contract_invalid",
                "same-host evidence must remain mechanism-only",
            )
        return {
            "class": SAME_HOST_EVIDENCE_CLASS,
            "formal_pass_allowed": False,
            "independent_failure_domain_required": bool(evidence_contract["independent_failure_domain_required"]),
        }
    if attestation is None:
        raise DrillError("failure_domain_attestation_missing", "independent evidence requires an attestation")
    raise DrillError(
        "independent_failure_domain_unsupported",
        "a local attestation cannot prove independent failure domains; use externally collected evidence",
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
    parser.add_argument(
        "--scenario",
        choices=("planned_switchover", "unexpected_primary_failure", "site_restore"),
        required=True,
    )
    parser.add_argument("--primary-container")
    parser.add_argument("--standby-container")
    parser.add_argument("--stable-network")
    parser.add_argument("--replication-network")
    parser.add_argument("--primary-site-network")
    parser.add_argument("--database", default="dcim")
    parser.add_argument("--database-user", default="dcim")
    parser.add_argument("--application-image", required=True)
    parser.add_argument("--postgres-password-file", type=Path, required=True)
    parser.add_argument("--fault-tree-hmac-key-env", default=FAULT_TREE_HMAC_KEY)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--failure-domain", choices=("same-host", "independent"), default="same-host")
    parser.add_argument("--failure-domain-attestation", type=Path)
    parser.add_argument("--probe-interval-seconds", type=float, default=1.0)
    parser.add_argument("--warmup-commits", type=int, default=3)
    parser.add_argument("--operation-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0)
    parser.add_argument("--allow-full-rebuild", action="store_true")
    return parser.parse_args()


def execute(
    args: argparse.Namespace,
    runner: CommandRunner,
    timeline: Timeline,
    result: dict[str, Any],
) -> None:
    try:
        contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise DrillError("failover_contract_invalid", "cannot read failover contract") from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise DrillError("failover_contract_invalid", "failover contract schema is invalid")

    primary = args.primary_container or f"{args.project}-postgres-primary-1"
    standby = args.standby_container or f"{args.project}-postgres-standby-1"
    stable_network = args.stable_network or f"{args.project}_database-client"
    replication_network = args.replication_network or f"{args.project}_replication-transit"
    primary_site_network = args.primary_site_network or f"{args.project}_primary-site"
    for name in (args.database, args.database_user):
        if IDENTIFIER_PATTERN.fullmatch(name) is None:
            raise DrillError("database_identifier_invalid", "database identifiers must be simple PostgreSQL names")
    if args.probe_interval_seconds <= 0 or args.poll_interval_seconds <= 0:
        raise DrillError("interval_invalid", "probe and poll intervals must be positive")
    if args.warmup_commits < 1 or args.operation_timeout_seconds <= 0:
        raise DrillError("timeout_invalid", "warmup count and timeout must be positive")

    validate_isolation(
        runner,
        project=args.project,
        primary=primary,
        standby=standby,
        stable_network=stable_network,
        replication_network=replication_network,
        primary_site_network=primary_site_network,
    )
    runtime = load_primary_runtime(runner, primary)
    evidence = classify_evidence(
        failure_domain=args.failure_domain,
        attestation=args.failure_domain_attestation,
        contract=contract,
    )
    result["evidence_classification"] = evidence
    result["scenario"] = args.scenario
    result["stable_endpoint"] = STABLE_ENDPOINT

    probe_client = create_probe_client(
        runner,
        project=args.project,
        stable_network=stable_network,
        runtime=runtime,
    )
    writer: ProbeWriter | None = None
    run_id = f"story39_3_{uuid.uuid4().hex}"
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise DrillError("run_id_invalid", "generated run identifier is invalid")
    try:
        create_table_sql = (
            f"CREATE TABLE IF NOT EXISTS {PROBE_TABLE}("
            "run_id text NOT NULL, sequence bigint NOT NULL, committed_at timestamptz NOT NULL, "
            "PRIMARY KEY(run_id, sequence));"
        )
        runner.run(
            "initialize_failover_probe",
            probe_psql_argv(probe_client, args.database, args.database_user, create_table_sql),
            failure_code="stable_endpoint_not_ready",
        )
        initial_role = runner.run(
            "verify_initial_writer_role",
            probe_psql_argv(
                probe_client,
                args.database,
                args.database_user,
                "SELECT pg_is_in_recovery();",
            ),
            failure_code="stable_endpoint_not_ready",
        )
        if initial_role != "f":
            raise DrillError("stable_endpoint_invalid", "postgres-writer does not target the primary")

        writer = ProbeWriter(
            runner=runner,
            timeline=timeline,
            probe_client=probe_client,
            database=args.database,
            database_user=args.database_user,
            run_id=run_id,
            interval_seconds=args.probe_interval_seconds,
        )
        writer.start()
        writer.wait_for_acknowledged(args.warmup_commits, args.operation_timeout_seconds)
        timeline.record("continuous_write_probe_ready", acknowledged=len(writer.acknowledged))

        replay: dict[str, str] | None = None
        if args.scenario == "planned_switchover":
            writer.pause_and_wait(args.operation_timeout_seconds)
            rto_started = timeline.record("planned_switchover_decision")
            replay = wait_for_replay_catchup(
                runner,
                timeline,
                primary=primary,
                standby=standby,
                database=args.database,
                database_user=args.database_user,
                timeout=args.operation_timeout_seconds,
                poll_interval=args.poll_interval_seconds,
            )
        elif args.scenario == "unexpected_primary_failure":
            rto_started = timeline.record("unexpected_primary_failure_injected")
        else:
            rto_started = timeline.record("site_restore_decision")

        abrupt_failure = args.scenario != "planned_switchover"
        fence_primary(
            runner,
            timeline,
            primary=primary,
            stable_network=stable_network,
            abrupt=abrupt_failure,
        )
        promote_standby(
            runner,
            timeline,
            primary=primary,
            standby=standby,
            stable_network=stable_network,
            database=args.database,
            database_user=args.database_user,
        )
        endpoint_switched_at = switch_writer_alias(
            runner,
            timeline,
            stable_network=stable_network,
            standby=standby,
        )
        writer.resume()
        required_successes = int(contract["stable_endpoint"]["consecutive_successes_required"])
        writer.wait_for_consecutive_successes(
            after_monotonic=endpoint_switched_at,
            required=required_successes,
            timeout=args.operation_timeout_seconds,
        )
        run_application_probe(
            runner,
            timeline,
            application_image=args.application_image,
            stable_network=stable_network,
            database=args.database,
            database_user=args.database_user,
            postgres_password_file=args.postgres_password_file,
            fault_tree_hmac_key_env=args.fault_tree_hmac_key_env,
        )
        recovery_completed = time.monotonic()
        recovered_at = utc_now()
        rto_seconds = round(recovery_completed - rto_started, 6)
        timeline.record(
            "application_critical_write_recovered",
            consecutive_successes=required_successes,
            rto_seconds=rto_seconds,
        )

        writer.stop()
        recovered_sequences, recovered_state = recovered_probe_state(
            runner,
            standby=standby,
            database=args.database,
            database_user=args.database_user,
            run_id=run_id,
        )
        rpo = calculate_rpo(writer.acknowledged, recovered_sequences, recovered_at)
        old_primary_rejoin_refused = refuse_untreated_old_primary(
            runner,
            timeline,
            primary=primary,
            stable_network=stable_network,
        )
        rejoin = full_rebuild_old_primary(
            runner,
            timeline,
            project=args.project,
            primary=primary,
            promoted_standby=standby,
            stable_network=stable_network,
            replication_network=replication_network,
            primary_site_network=primary_site_network,
            database=args.database,
            database_user=args.database_user,
            run_id=run_id,
            expected_probe_count=len(recovered_sequences),
            runtime=runtime,
            allow_full_rebuild=args.allow_full_rebuild,
            timeout=args.operation_timeout_seconds,
            poll_interval=args.poll_interval_seconds,
        )

        objective = contract["scenarios"][args.scenario]
        rto_ok = rto_seconds <= float(objective["rto_seconds_max"])
        rpo_ok = rpo["latest_missing_commit_age_seconds"] <= float(objective["rpo_seconds_max"]) and (
            args.scenario != "planned_switchover" or rpo["missing_commit_count"] == 0
        )
        scenario_pass = rto_ok and rpo_ok
        result.update(
            {
                "run_id": run_id,
                "status": "pass" if evidence["formal_pass_allowed"] else "mechanism-pass",
                "failure_code": None,
                "formal_pass": bool(evidence["formal_pass_allowed"] and scenario_pass),
                "scenario_objective_met": scenario_pass,
                "rto_seconds": rto_seconds,
                "rto_seconds_max": float(objective["rto_seconds_max"]),
                "rpo_seconds_max": float(objective["rpo_seconds_max"]),
                **rpo,
                "acknowledged_commit_count": len(writer.acknowledged),
                "recovered_commit_count": int(recovered_state["row_count"]),
                "replay_catchup": replay,
                "fault_injection": "sigkill" if abrupt_failure else "controlled-stop",
                "application_probe": "pass",
                "old_primary_rejoin_refused": old_primary_rejoin_refused,
                "old_primary_rejoin": rejoin,
            }
        )
        if not scenario_pass:
            result["status"] = "failed"
            raise DrillError("recovery_objective_not_met", "scenario RTO or RPO objective was not met")
    finally:
        if writer is not None:
            writer.stop()
            result.setdefault("acknowledged_commit_count", len(writer.acknowledged))
        runner.try_run("remove_failover_probe_client", ["docker", "rm", "--force", probe_client])


def main() -> int:
    args = parse_args()
    timeline = Timeline()
    runner = CommandRunner(timeline)
    result: dict[str, Any] = {
        "schema_version": 1,
        "started_at": utc_now(),
        "status": "error",
        "failure_code": "unhandled_error",
    }
    output = args.output_dir / "failover-last-run.json"
    try:
        execute(args, runner, timeline, result)
    except DrillError as exc:
        result["failure_code"] = exc.code
        result["message"] = str(exc)
    except Exception as exc:
        result["message"] = type(exc).__name__
    finally:
        result["completed_at"] = utc_now()
        result["timeline"] = timeline.events
        result["commands"] = runner.events
        atomic_json(output, result)
    return 0 if result["status"] in {"pass", "mechanism-pass"} else 1


if __name__ == "__main__":
    sys.exit(main())
