#!/usr/bin/env python3
"""Run the fixed-candidate Story 39.7 burn-in evidence window."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

from scripts.story_39_7_deploy import (
    ROOT,
    DeploymentError,
    Target,
    load_inventory,
    parse_environment,
)
from scripts.story_39_7_evidence import validate_evidence


UTC = timezone.utc
COLLECTOR_VERSION = "1"
DEFAULT_EVIDENCE_DIR = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.7"
DEFAULT_CONTRACT = ROOT / "deploy" / "observability" / "story-39-7-contract.yaml"
DEFAULT_INVENTORY = ROOT / "deploy" / "observability" / "story-39-7-targets.yaml"
WINDOW_SECONDS = 72 * 60 * 60
SAMPLE_SECONDS = 60
MAXIMUM_GAP_SECONDS = 5 * 60
E2E_OFFSETS_SECONDS = tuple(
    [hour * 60 * 60 for hour in range(0, 61, 6)] + [72 * 60 * 60]
)
INCIDENT_OFFSET_SECONDS = 25 * 60 * 60
REQUIRED_SERVICES = ("backend", "nginx", "redis", "emqx")
ARTIFACT_NAMES = (
    "availability_samples",
    "provenance_samples",
    "e2e_runs",
    "incidents",
    "alerts",
    "maintenance_windows",
    "source_hashes",
    "backend_image_manifest",
    "frontend_image_manifest",
    "environment",
)


class BurnInError(RuntimeError):
    """Raised when the evidence window cannot continue safely."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_text(value: datetime | None = None) -> str:
    return (value or _utc_now()).astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Any) -> str:
    data = _canonical_json(payload)
    _atomic_bytes(path, data)
    return _sha256(data)


def _atomic_yaml(path: Path, payload: Mapping[str, Any]) -> None:
    data = yaml.safe_dump(dict(payload), sort_keys=False, allow_unicode=False).encode(
        "utf-8"
    )
    _atomic_bytes(path, data)


def _run(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise BurnInError(
            f"command failed ({completed.returncode}): {command[0]}: {detail[-1000:]}"
        )
    return completed


def _target(inventory_path: Path, target_name: str) -> Target:
    inventory = load_inventory(inventory_path)
    matches = [target for target in inventory.targets if target.name == target_name]
    if len(matches) != 1:
        raise BurnInError(f"inventory target not found: {target_name}")
    target = matches[0]
    if target.e2e.mode != "local" or not target.e2e.headed:
        raise BurnInError("burn-in target must use local headed E2E")
    if target.e2e.browser_channel != "msedge":
        raise BurnInError("burn-in target must use the external Microsoft Edge channel")
    return target


def _compose_command(target: Target, *arguments: str) -> list[str]:
    return [
        "docker",
        "--context",
        target.docker_context,
        "compose",
        "--project-name",
        target.project_name,
        "--env-file",
        str(target.env_file),
        "-f",
        str(target.compose_file),
        *arguments,
    ]


def _parse_json_lines(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, list):
            records.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            records.append(payload)
    return records


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: Mapping[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any]:
    request = Request(url, method=method, headers=dict(headers or {}), data=data)
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback only
            body = response.read()
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read()
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = None
        return exc.code, payload
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise BurnInError(f"loopback probe failed: {url}: {exc}") from exc


def _playwright_summary(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BurnInError(f"cannot read Playwright report: {path}") from exc
    stats = report.get("stats") if isinstance(report, Mapping) else None
    if not isinstance(stats, Mapping):
        raise BurnInError("Playwright report has no stats")
    retries: list[int] = []

    def walk_suite(suite: Mapping[str, Any]) -> None:
        for spec in suite.get("specs", ()):
            if not isinstance(spec, Mapping):
                continue
            for test in spec.get("tests", ()):
                if not isinstance(test, Mapping):
                    continue
                for result in test.get("results", ()):
                    if isinstance(result, Mapping) and isinstance(
                        result.get("retry"), int
                    ):
                        retries.append(result["retry"])
        for child in suite.get("suites", ()):
            if isinstance(child, Mapping):
                walk_suite(child)

    for suite in report.get("suites", ()):
        if isinstance(suite, Mapping):
            walk_suite(suite)
    skipped = int(stats.get("skipped", 0))
    unexpected = int(stats.get("unexpected", 0))
    flaky = int(stats.get("flaky", 0))
    expected = int(stats.get("expected", 0))
    first_attempt_passed = (
        expected > 0
        and skipped == 0
        and unexpected == 0
        and flaky == 0
        and all(retry == 0 for retry in retries)
    )
    return {
        "first_attempt_passed": first_attempt_passed,
        "expected": expected,
        "skipped": skipped,
        "unexpected": unexpected,
        "flaky": flaky,
        "maximum_retry": max(retries, default=0),
        "started_at_utc": stats.get("startTime"),
        "duration_milliseconds": stats.get("duration"),
    }


def _parse_fleet_test(stdout: str) -> tuple[Path, dict[str, Any]]:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BurnInError("fleet test command did not return JSON") from exc
    if report.get("summary", {}).get("failed") != 0:
        raise BurnInError("fleet test report contains a failed target")
    artifacts = [
        check.get("artifact")
        for result in report.get("results", ())
        if isinstance(result, Mapping)
        for check in result.get("checks", ())
        if isinstance(check, Mapping) and check.get("name") == "critical_e2e"
    ]
    if len(artifacts) != 1 or not isinstance(artifacts[0], str):
        raise BurnInError("fleet test report has no unique critical E2E artifact")
    artifact = Path(artifacts[0]).resolve()
    summary = _playwright_summary(artifact)
    if not summary["first_attempt_passed"]:
        raise BurnInError("critical E2E did not pass on its first attempt")
    return artifact, summary


class EvidenceStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.manifest_path = self.root / "manifest.yaml"
        self.trusted_provenance_path = self.root / "trusted-provenance.json"
        self.state_path = self.root / "burnin-state.json"
        self.stop_path = self.root / "burnin-stop.request"
        self.lock = threading.RLock()
        try:
            self.manifest = yaml.safe_load(
                self.manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, yaml.YAMLError) as exc:
            raise BurnInError("Story 39.7 baseline manifest is unavailable") from exc
        if not isinstance(self.manifest, dict):
            raise BurnInError("Story 39.7 baseline manifest must be an object")
        self.records: dict[str, list[dict[str, Any]]] = {
            name: []
            for name in (
                "availability_samples",
                "provenance_samples",
                "e2e_runs",
                "incidents",
                "alerts",
                "maintenance_windows",
            )
        }

    def _update_hash(self, name: str, digest: str) -> None:
        artifact = self.manifest.get("artifacts", {}).get(name)
        if not isinstance(artifact, dict):
            raise BurnInError(f"manifest artifact is missing: {name}")
        artifact["sha256"] = digest

    def _flush_records_locked(self) -> None:
        for name, records in self.records.items():
            digest = _atomic_json(self.root / f"{name}.json", records)
            self._update_hash(name, digest)
        _atomic_yaml(self.manifest_path, self.manifest)

    def initialize(
        self,
        *,
        provenance: Mapping[str, str],
        environment: Mapping[str, Any],
        started_at: datetime,
        commands: Sequence[str],
        tool_versions: Mapping[str, str],
    ) -> dict[str, str]:
        with self.lock:
            self.stop_path.unlink(missing_ok=True)
            for records in self.records.values():
                records.clear()
            environment_digest = _atomic_json(
                self.root / "environment.json", environment
            )
            final_provenance = dict(provenance)
            final_provenance["environment_fingerprint"] = environment_digest
            self.manifest.update(
                {
                    "status": "blocked",
                    "gate_result": "BLOCKED",
                    "annual_slo_proven": False,
                    "provenance": final_provenance,
                    "window": {
                        "started_at_utc": _utc_text(started_at),
                        "ended_at_utc": None,
                    },
                    "commands": list(commands),
                    "tool_versions": dict(tool_versions),
                    "known_limits": [
                        "This Docker Desktop host is a pre-production mechanism environment, not an independent failure domain.",
                        "The 72-hour result reports observed availability and does not prove the annual SLO.",
                        "The release gate remains BLOCKED until the complete window and incident drill validate independently.",
                    ],
                }
            )
            self._update_hash("environment", environment_digest)
            _atomic_json(self.trusted_provenance_path, final_provenance)
            self._flush_records_locked()
            return final_provenance

    def append_sample(
        self, availability: Mapping[str, Any], provenance: Mapping[str, Any]
    ) -> None:
        with self.lock:
            self.records["availability_samples"].append(dict(availability))
            self.records["provenance_samples"].append(dict(provenance))
            self._flush_records_locked()

    def append_e2e(self, run: Mapping[str, Any]) -> None:
        with self.lock:
            self.records["e2e_runs"].append(dict(run))
            self._flush_records_locked()

    def set_incident(
        self, incident: Mapping[str, Any], alert: Mapping[str, Any]
    ) -> None:
        with self.lock:
            self.records["incidents"] = [dict(incident)]
            self.records["alerts"] = [dict(alert)]
            self._flush_records_locked()

    def finish_window(self, ended_at: datetime) -> None:
        with self.lock:
            self.manifest["window"]["ended_at_utc"] = _utc_text(ended_at)
            self.manifest["status"] = "pass"
            self.manifest["gate_result"] = "PASS"
            self._flush_records_locked()

    def block(self) -> None:
        with self.lock:
            self.manifest["status"] = "blocked"
            self.manifest["gate_result"] = "BLOCKED"
            self._flush_records_locked()

    def write_state(self, payload: Mapping[str, Any]) -> None:
        _atomic_json(self.state_path, payload)


class BurnInRunner:
    def __init__(
        self,
        *,
        inventory_path: Path,
        target_name: str,
        evidence_dir: Path,
        contract_path: Path,
    ) -> None:
        self.inventory_path = inventory_path.resolve()
        self.target = _target(self.inventory_path, target_name)
        self.values = parse_environment(self.target.env_file)
        self.store = EvidenceStore(evidence_dir)
        self.contract_path = contract_path.resolve()
        self.base_url = f"http://127.0.0.1:{self.target.e2e.local_port}"
        self.collector_instance_id = f"collector-{uuid.uuid4().hex}"
        self.process_started_at = _utc_now()
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.provenance: dict[str, str] = {}
        self.initial_runtime: dict[str, Any] = {}
        self.last_critical_e2e_passed = False
        self.e2e_started: set[int] = set()
        self.e2e_threads: list[threading.Thread] = []
        self.e2e_lock = threading.Lock()
        self.incident_started = False
        self.incident_active = threading.Event()
        self.incident_thread: threading.Thread | None = None
        self.failure: str | None = None
        self.failure_lock = threading.Lock()

    def _fail(self, reason: str) -> None:
        with self.failure_lock:
            if self.failure is None:
                self.failure = reason

    def _runtime_snapshot(self) -> dict[str, Any]:
        compose = _run(
            _compose_command(self.target, "ps", "--all", "--format", "json"),
            timeout=30,
        )
        services = {
            item.get("Service"): item for item in _parse_json_lines(compose.stdout)
        }
        missing = set(REQUIRED_SERVICES) - set(services)
        if missing:
            raise BurnInError(f"required services are missing: {sorted(missing)}")
        expected_images = {
            "backend": self.values["DCIM_BACKEND_IMAGE"],
            "nginx": self.values["DCIM_FRONTEND_IMAGE"],
            "redis": self.values["DCIM_REDIS_IMAGE"],
            "emqx": self.values["DCIM_EMQX_IMAGE"],
        }
        service_records: dict[str, Any] = {}
        for name in REQUIRED_SERVICES:
            item = services[name]
            controlled_redis_outage = name == "redis" and self.incident_active.is_set()
            if not controlled_redis_outage and (
                item.get("State") != "running" or item.get("Health") != "healthy"
            ):
                raise BurnInError(
                    f"service {name} is not running and healthy: "
                    f"{item.get('State')}/{item.get('Health')}"
                )
            if item.get("Image") != expected_images[name]:
                raise BurnInError(f"service {name} image drift")
            container_id = str(item.get("ID", ""))
            inspected = json.loads(
                _run(
                    [
                        "docker",
                        "--context",
                        self.target.docker_context,
                        "container",
                        "inspect",
                        container_id,
                    ],
                    timeout=30,
                ).stdout
            )
            if not isinstance(inspected, list) or len(inspected) != 1:
                raise BurnInError(f"cannot inspect service {name}")
            details = inspected[0]
            service_records[name] = {
                "container_id": details.get("Id"),
                "started_at_utc": details.get("State", {}).get("StartedAt"),
                "restart_count": details.get("RestartCount"),
                "image": item.get("Image"),
                "configuration_hash": _label(
                    item.get("Labels", ""), "com.docker.compose.config-hash"
                ),
                "state": item.get("State"),
                "health": item.get("Health"),
            }
        health_status, health = _http_json(f"{self.base_url}/api/health")
        readiness_status, readiness = _http_json(f"{self.base_url}/api/readiness")
        health_ok = (
            health_status == 200
            and isinstance(health, Mapping)
            and health.get("status") == "healthy"
        )
        readiness_ok = (
            readiness_status == 200
            and isinstance(readiness, Mapping)
            and readiness.get("ready") is True
        )
        if not health_ok:
            raise BurnInError("proxy health probe failed")
        if not readiness_ok and not self.incident_active.is_set():
            raise BurnInError("proxy readiness probe failed")
        return {
            "services": service_records,
            "health": health,
            "readiness": readiness,
            "readiness_passed": readiness_ok,
        }

    def _assert_no_runtime_drift(self, runtime: Mapping[str, Any]) -> None:
        for name in REQUIRED_SERVICES:
            initial = self.initial_runtime["services"][name]
            current = runtime["services"][name]
            identity_fields = ["container_id", "image", "configuration_hash"]
            if name != "redis" or not self.incident_started:
                identity_fields.append("started_at_utc")
            for field in identity_fields:
                if current.get(field) != initial.get(field):
                    raise BurnInError(f"service {name} {field} drift")
            if name != "redis" and current.get("restart_count") != initial.get(
                "restart_count"
            ):
                raise BurnInError(f"service {name} restarted during the window")

    def _environment(self, runtime: Mapping[str, Any]) -> dict[str, Any]:
        docker_version = json.loads(
            _run(
                [
                    "docker",
                    "--context",
                    self.target.docker_context,
                    "version",
                    "--format",
                    "{{json .}}",
                ],
                timeout=30,
            ).stdout
        )
        configuration = {
            name: runtime["services"][name]["configuration_hash"]
            for name in REQUIRED_SERVICES
        }
        digest_payload = {
            "docker_context": self.target.docker_context,
            "project_name": self.target.project_name,
            "candidate_git_sha": self.values["CANDIDATE_GIT_SHA"],
            "images": {
                name: runtime["services"][name]["image"] for name in REQUIRED_SERVICES
            },
            "configuration_hashes": configuration,
        }
        return {
            "provider": "docker-desktop-preproduction",
            "deployment_id": f"story-39-7-{self.target.name}-20260822",
            "cluster_uid": docker_version.get("Server", {})
            .get("Platform", {})
            .get("Name", "docker-desktop"),
            "configuration_digest": "sha256:"
            + _sha256(_canonical_json(digest_payload)),
            "docker_context": self.target.docker_context,
            "project_name": self.target.project_name,
            "docker_server_version": docker_version.get("Server", {}).get("Version"),
            "host_os": platform.platform(),
            "candidate_git_sha": self.values["CANDIDATE_GIT_SHA"],
            "images": digest_payload["images"],
            "configuration_hashes": configuration,
            "initial_containers": {
                name: {
                    key: runtime["services"][name][key]
                    for key in ("container_id", "started_at_utc", "restart_count")
                }
                for name in REQUIRED_SERVICES
            },
        }

    def _tool_versions(self) -> dict[str, str]:
        docker_server = _run(
            [
                "docker",
                "--context",
                self.target.docker_context,
                "version",
                "--format",
                "{{.Server.Version}}",
            ],
            timeout=30,
        ).stdout.strip()
        compose = _run(["docker", "compose", "version"], timeout=30).stdout.strip()
        playwright = _run(
            ["npx.cmd" if os.name == "nt" else "npx", "playwright", "--version"],
            timeout=60,
        ).stdout.strip()
        return {
            "burnin_collector": COLLECTOR_VERSION,
            "python": platform.python_version(),
            "docker_server": docker_server,
            "docker_compose": compose,
            "playwright": playwright,
        }

    def initialize(self) -> None:
        self.initial_runtime = self._runtime_snapshot()
        baseline = self.store.manifest.get("provenance")
        if not isinstance(baseline, Mapping):
            raise BurnInError("baseline provenance is missing")
        expected = {
            "git_sha": self.values["CANDIDATE_GIT_SHA"],
            "backend_image": self.values["DCIM_BACKEND_IMAGE"],
            "frontend_image": self.values["DCIM_FRONTEND_IMAGE"],
        }
        for key, value in expected.items():
            if baseline.get(key) != value:
                raise BurnInError(f"baseline and runtime environment disagree: {key}")
        self.started_at = _utc_now()
        self.ended_at = self.started_at + timedelta(seconds=WINDOW_SECONDS)
        commands = [
            f"python -m scripts.story_39_7_burnin run --inventory {self.inventory_path} --target {self.target.name}",
            f"python -m scripts.story_39_7_deploy test --inventory {self.inventory_path} --target {self.target.name}",
            f"docker --context {self.target.docker_context} compose --project-name {self.target.project_name} stop redis",
            f"docker --context {self.target.docker_context} compose --project-name {self.target.project_name} start redis",
            f"python -m scripts.story_39_7_evidence --contract {self.contract_path} --manifest {self.store.manifest_path}",
        ]
        self.provenance = self.store.initialize(
            provenance=expected,
            environment=self._environment(self.initial_runtime),
            started_at=self.started_at,
            commands=commands,
            tool_versions=self._tool_versions(),
        )
        self._write_state("running")

    def _write_state(self, status: str, **extra: Any) -> None:
        e2e_runs = len(self.store.records["e2e_runs"])
        next_offsets = [
            offset for offset in E2E_OFFSETS_SECONDS if offset not in self.e2e_started
        ]
        next_e2e = (
            _utc_text(self.started_at + timedelta(seconds=next_offsets[0]))
            if self.started_at is not None and next_offsets
            else None
        )
        payload = {
            "schema_version": 1,
            "status": status,
            "release_gate": "PASS" if status == "pass" else "BLOCKED",
            "annual_slo_proven": False,
            "pid": os.getpid(),
            "target": self.target.name,
            "collector_instance_id": self.collector_instance_id,
            "process_started_at_utc": _utc_text(self.process_started_at),
            "window_started_at_utc": _utc_text(self.started_at)
            if self.started_at
            else None,
            "scheduled_end_at_utc": _utc_text(self.ended_at) if self.ended_at else None,
            "availability_samples": len(self.store.records["availability_samples"]),
            "e2e_runs": e2e_runs,
            "next_e2e_at_utc": next_e2e,
            "incident_drill_completed": bool(self.store.records["incidents"]),
            "failure": self.failure,
            "updated_at_utc": _utc_text(),
            **extra,
        }
        self.store.write_state(payload)

    def _provenance_sample(
        self, timestamp: datetime, runtime: Mapping[str, Any]
    ) -> dict[str, Any]:
        backend = runtime["services"]["backend"]
        frontend = runtime["services"]["nginx"]
        return {
            "timestamp_utc": _utc_text(timestamp),
            "duration_seconds": SAMPLE_SECONDS,
            **self.provenance,
            "collector_instance_id": self.collector_instance_id,
            "process_start_utc": _utc_text(self.process_started_at),
            "restart_count": 0,
            "backend_instance_id": backend["container_id"],
            "backend_process_start_utc": backend["started_at_utc"],
            "backend_restart_count": backend["restart_count"]
            - self.initial_runtime["services"]["backend"]["restart_count"],
            "frontend_instance_id": frontend["container_id"],
            "frontend_process_start_utc": frontend["started_at_utc"],
            "frontend_restart_count": frontend["restart_count"]
            - self.initial_runtime["services"]["nginx"]["restart_count"],
        }

    def collect_sample(self, timestamp: datetime, *, late: bool = False) -> None:
        if late:
            availability = {
                "timestamp_utc": _utc_text(timestamp),
                "duration_seconds": SAMPLE_SECONDS,
                "telemetry_present": False,
                "readiness_passed": False,
                "critical_e2e_passed": self.last_critical_e2e_passed,
            }
            runtime = self.initial_runtime
        else:
            runtime = self._runtime_snapshot()
            self._assert_no_runtime_drift(runtime)
            availability = {
                "timestamp_utc": _utc_text(timestamp),
                "duration_seconds": SAMPLE_SECONDS,
                "telemetry_present": True,
                "readiness_passed": runtime["readiness_passed"],
                "critical_e2e_passed": self.last_critical_e2e_passed,
                "health_status": runtime["health"].get("status"),
                "readiness_checks": (
                    runtime["readiness"].get("checks")
                    if isinstance(runtime["readiness"], Mapping)
                    else None
                ),
                "service_health": {
                    name: runtime["services"][name]["health"]
                    or runtime["services"][name]["state"]
                    for name in REQUIRED_SERVICES
                },
            }
        self.store.append_sample(
            availability, self._provenance_sample(timestamp, runtime)
        )
        self._write_state("running")

    def _fleet_test(self) -> tuple[Path, dict[str, Any], datetime, datetime]:
        started = _utc_now()
        completed = _run(
            [
                sys.executable,
                "-m",
                "scripts.story_39_7_deploy",
                "test",
                "--inventory",
                str(self.inventory_path),
                "--target",
                self.target.name,
            ],
            timeout=30 * 60,
        )
        finished = _utc_now()
        artifact, summary = _parse_fleet_test(completed.stdout)
        return artifact, summary, started, finished

    def _scheduled_e2e(self, offset: int, scheduled_at: datetime) -> None:
        try:
            with self.e2e_lock:
                artifact, summary, actual_started, actual_finished = self._fleet_test()
            self.last_critical_e2e_passed = True
            run = {
                "run_id": f"scheduled-{offset:06d}-{uuid.uuid4().hex[:12]}",
                "timestamp_utc": _utc_text(scheduled_at),
                "actual_started_at_utc": _utc_text(actual_started),
                "actual_finished_at_utc": _utc_text(actual_finished),
                "status": "passed",
                "first_attempt_passed": True,
                "retry_count": 0,
                "skipped_critical_tests": summary["skipped"],
                "expected_critical_tests": summary["expected"],
                "playwright_artifact": str(artifact.relative_to(ROOT)),
                **self.provenance,
            }
            self.store.append_e2e(run)
            self._write_state("running")
        except Exception as exc:
            self.last_critical_e2e_passed = False
            self._fail(f"scheduled E2E at +{offset}s failed: {exc}")

    def _start_scheduled_e2e(self, offset: int) -> None:
        assert self.started_at is not None
        self.e2e_started.add(offset)
        scheduled_at = self.started_at + timedelta(seconds=offset)
        thread = threading.Thread(
            target=self._scheduled_e2e,
            args=(offset, scheduled_at),
            name=f"story-39-7-e2e-{offset}",
            daemon=False,
        )
        self.e2e_threads.append(thread)
        thread.start()

    def _login_token(self) -> str:
        body = urlencode(
            {
                "username": self.values["E2E_ADMIN_USER"],
                "password": self.values["E2E_ADMIN_PASSWORD"],
            }
        ).encode("ascii")
        status, payload = _http_json(
            f"{self.base_url}/api/v1/auth/login",
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=body,
        )
        if status != 200 or not isinstance(payload, Mapping):
            raise BurnInError("incident drill authentication failed")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise BurnInError("incident drill authentication returned no token")
        return token

    def _observability(self, token: str) -> Mapping[str, Any]:
        status, payload = _http_json(
            f"{self.base_url}/api/v1/system/observability",
            headers={"Authorization": f"Bearer {token}"},
        )
        if status != 200 or not isinstance(payload, Mapping):
            raise BurnInError("authorized observability probe failed")
        return payload

    def _wait_for_dependency_alert(self, token: str) -> tuple[datetime, float]:
        deadline = time.monotonic() + 4 * 60
        while time.monotonic() < deadline:
            snapshot = self._observability(token)
            alerts = snapshot.get("alerts")
            dependency = (
                alerts.get("dependencies") if isinstance(alerts, Mapping) else None
            )
            if (
                isinstance(dependency, Mapping)
                and dependency.get("state") == "critical"
            ):
                fired_text = dependency.get("fired_at_utc")
                if not isinstance(fired_text, str):
                    raise BurnInError("dependency alert has no fired timestamp")
                fired_at = _parse_utc(fired_text)
                observed_utc = _utc_now()
                observed_monotonic = time.monotonic()
                fired_monotonic = observed_monotonic - max(
                    0.0, (observed_utc - fired_at).total_seconds()
                )
                return fired_at, fired_monotonic
            time.sleep(10)
        raise BurnInError(
            "Redis interruption did not produce a critical dependency alert"
        )

    def _wait_for_readiness(self, expected: bool, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                status, payload = _http_json(
                    f"{self.base_url}/api/readiness", timeout=5
                )
                ready = (
                    status == 200
                    and isinstance(payload, Mapping)
                    and payload.get("ready") is True
                )
            except BurnInError:
                ready = False
            if ready is expected:
                return
            time.sleep(5)
        raise BurnInError(f"readiness did not become {expected}")

    def _incident_drill(self) -> None:
        incident_id = f"INC-REDIS-{uuid.uuid4().hex[:12]}"
        actions: list[dict[str, Any]] = []
        redis_stopped = False
        try:
            self.incident_active.set()
            token = self._login_token()
            _run(_compose_command(self.target, "stop", "redis"), timeout=2 * 60)
            redis_stopped = True
            actions.append({"action": "stop_redis", "timestamp_utc": _utc_text()})
            self._wait_for_readiness(False, 2 * 60)
            fired_at, fired_monotonic = self._wait_for_dependency_alert(token)
            _run(_compose_command(self.target, "start", "redis"), timeout=2 * 60)
            redis_stopped = False
            actions.append({"action": "start_redis", "timestamp_utc": _utc_text()})
            self._wait_for_readiness(True, 3 * 60)
            self.incident_active.clear()
            recovery_checks: list[dict[str, Any]] = []
            previous_monotonic = fired_monotonic
            for index in range(3):
                with self.e2e_lock:
                    _artifact, summary, _started, _finished = self._fleet_test()
                now_monotonic = time.monotonic()
                if now_monotonic - previous_monotonic < 30:
                    time.sleep(30 - (now_monotonic - previous_monotonic))
                    now_monotonic = time.monotonic()
                checked_at = _utc_now()
                recovery_checks.append(
                    {
                        "timestamp_utc": _utc_text(checked_at),
                        "monotonic_seconds": now_monotonic,
                        "readiness_passed": True,
                        "critical_e2e_passed": summary["first_attempt_passed"],
                        "evaluation": index + 1,
                    }
                )
                previous_monotonic = now_monotonic
            resolved_at = recovery_checks[-1]["timestamp_utc"]
            incident = {
                "incident_id": incident_id,
                "severity": "critical",
                "alert_fired_at_utc": _utc_text(fired_at),
                "alert_fired_monotonic_seconds": fired_monotonic,
                "recovery_checks": recovery_checks,
                "operator_actions": actions,
                "owner": "proecheng",
                "runbook": "dependencies/redis-recovery",
            }
            alert = {
                "alert_id": f"ALERT-{incident_id}",
                "incident_id": incident_id,
                "severity": "critical",
                "fired_at_utc": _utc_text(fired_at),
                "resolved_at_utc": resolved_at,
                "owner": "proecheng",
                "runbook": "dependencies/redis-recovery",
            }
            self.store.set_incident(incident, alert)
            self.last_critical_e2e_passed = True
            self._write_state("running")
        except Exception as exc:
            self._fail(f"incident drill failed: {exc}")
        finally:
            if redis_stopped:
                try:
                    _run(
                        _compose_command(self.target, "start", "redis"), timeout=2 * 60
                    )
                except Exception as recovery_exc:
                    self._fail(f"Redis emergency restart failed: {recovery_exc}")
            self.incident_active.clear()

    def _start_incident(self) -> None:
        self.incident_started = True
        self.incident_thread = threading.Thread(
            target=self._incident_drill,
            name="story-39-7-incident-drill",
            daemon=False,
        )
        self.incident_thread.start()

    def _join_workers(self) -> None:
        for thread in self.e2e_threads:
            thread.join()
        if self.incident_thread is not None:
            self.incident_thread.join()

    def finalize(self) -> bool:
        assert self.ended_at is not None
        self._join_workers()
        if self.failure:
            self.store.block()
            self._write_state("blocked")
            return False
        if len(self.store.records["e2e_runs"]) != len(E2E_OFFSETS_SECONDS):
            self._fail("the window did not produce all 12 scheduled E2E runs")
        if not self.store.records["incidents"]:
            self._fail("the required resolved critical incident drill is missing")
        if self.failure:
            self.store.block()
            self._write_state("blocked")
            return False
        self.store.finish_window(self.ended_at)
        result = validate_evidence(
            self.contract_path,
            self.store.manifest_path,
            repository_root=ROOT,
            trusted_provenance=json.loads(
                self.store.trusted_provenance_path.read_text(encoding="utf-8")
            ),
        )
        _atomic_json(self.store.root / "final-validation.json", result)
        if not result["valid"]:
            self._fail("independent validator rejected final evidence")
            self.store.block()
            self._write_state("blocked", validation_errors=result["errors"])
            return False
        self._write_state("pass", validation=result["derived"])
        return True

    def run(self) -> bool:
        self.initialize()
        assert self.started_at is not None and self.ended_at is not None
        next_sample = self.started_at
        try:
            while True:
                now = _utc_now()
                elapsed = (now - self.started_at).total_seconds()
                for offset in E2E_OFFSETS_SECONDS:
                    if offset not in self.e2e_started and elapsed >= offset:
                        lateness = elapsed - offset
                        if lateness > MAXIMUM_GAP_SECONDS:
                            self._fail(f"E2E schedule missed by {lateness:.1f} seconds")
                            break
                        self._start_scheduled_e2e(offset)
                if (
                    not self.incident_started
                    and elapsed >= INCIDENT_OFFSET_SECONDS
                    and elapsed < WINDOW_SECONDS
                ):
                    self._start_incident()
                while next_sample < self.ended_at and now >= next_sample:
                    lateness = (now - next_sample).total_seconds()
                    if lateness > MAXIMUM_GAP_SECONDS:
                        self._fail(
                            f"monitoring schedule gap exceeded {MAXIMUM_GAP_SECONDS} seconds"
                        )
                        break
                    self.collect_sample(next_sample, late=lateness > SAMPLE_SECONDS)
                    next_sample += timedelta(seconds=SAMPLE_SECONDS)
                if self.failure:
                    break
                if self.store.stop_path.exists():
                    self._fail("operator stop requested")
                    break
                if now >= self.ended_at and WINDOW_SECONDS in self.e2e_started:
                    break
                time.sleep(1)
        except Exception as exc:
            self._fail(str(exc))
        return self.finalize()


def _label(labels: str, key: str) -> str | None:
    prefix = f"{key}="
    for entry in labels.split(","):
        if entry.startswith(prefix):
            return entry[len(prefix) :]
    return None


@contextlib.contextmanager
def _single_instance(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == "":
                handle.write("0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise BurnInError(
                    "another burn-in collector is already running"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise BurnInError(
                    "another burn-in collector is already running"
                ) from exc
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextlib.contextmanager
def _prevent_windows_sleep():
    if os.name != "nt":
        yield
        return
    execution_state = ctypes.windll.kernel32.SetThreadExecutionState
    continuous = 0x80000000
    system_required = 0x00000001
    if not execution_state(continuous | system_required):
        raise BurnInError("Windows sleep prevention could not be enabled")
    try:
        yield
    finally:
        execution_state(continuous)


def probe_runtime(
    inventory_path: Path, target_name: str, evidence_dir: Path
) -> dict[str, Any]:
    runner = BurnInRunner(
        inventory_path=inventory_path,
        target_name=target_name,
        evidence_dir=evidence_dir,
        contract_path=DEFAULT_CONTRACT,
    )
    runtime = runner._runtime_snapshot()
    return {
        "schema_version": 1,
        "status": "passed",
        "target": target_name,
        "captured_at_utc": _utc_text(),
        "services": {
            name: {
                "image": service["image"],
                "restart_count": service["restart_count"],
                "configuration_hash": service["configuration_hash"],
            }
            for name, service in runtime["services"].items()
        },
        "health": runtime["health"],
        "readiness": runtime["readiness"],
        "annual_slo_proven": False,
        "release_gate": "BLOCKED",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("probe", "run", "status", "stop"))
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--target", default="workstation")
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence_dir = args.evidence_dir.resolve()
    store = EvidenceStore(evidence_dir)
    try:
        if args.action == "status":
            if not store.state_path.is_file():
                print(json.dumps({"status": "not_started"}, ensure_ascii=False))
                return 1
            print(store.state_path.read_text(encoding="utf-8"))
            return 0
        if args.action == "stop":
            _atomic_bytes(store.stop_path, b"operator stop requested\n")
            print(json.dumps({"status": "stop_requested"}, ensure_ascii=False))
            return 0
        if args.action == "probe":
            print(
                json.dumps(
                    probe_runtime(args.inventory, args.target, evidence_dir),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        with _single_instance(evidence_dir / "burnin.lock"), _prevent_windows_sleep():
            runner = BurnInRunner(
                inventory_path=args.inventory,
                target_name=args.target,
                evidence_dir=evidence_dir,
                contract_path=args.contract,
            )
            return 0 if runner.run() else 1
    except (BurnInError, DeploymentError, KeyError, ValueError) as exc:
        error = {
            "schema_version": 1,
            "status": "blocked",
            "release_gate": "BLOCKED",
            "annual_slo_proven": False,
            "error": str(exc),
            "failed_at_utc": _utc_text(),
        }
        store.write_state(error)
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
