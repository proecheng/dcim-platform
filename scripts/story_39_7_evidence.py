#!/usr/bin/env python3
"""Independently validate Story 39.7 burn-in evidence from raw artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MANIFEST_SCHEMA = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.7" / "manifest.schema.json"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.contracts.observability import D39_03  # noqa: E402
from app.contracts.slo_evidence import (  # noqa: E402
    EvidenceValidationError,
    calculate_availability,
    calculate_mttr,
    parse_utc,
)


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_RE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
PLACEHOLDER_RE = re.compile(r"^(?:pending|tbd|todo|unknown|n/?a)(?:\b|:)", re.IGNORECASE)
UTC = timezone.utc


def _load_yaml(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{label} cannot be loaded: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _validate_contract(contract: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        ("schema_version",): 1,
        ("decision_id",): "D39-03",
        ("owner",): "proecheng",
        ("evidence_window", "minimum_duration_seconds"): D39_03.evidence_window_seconds,
        ("evidence_window", "critical_e2e_runs"): D39_03.critical_e2e_runs,
        ("evidence_window", "minimum_e2e_spacing_seconds"): D39_03.minimum_e2e_spacing_seconds,
        ("evidence_window", "maximum_monitoring_gap_seconds"): D39_03.monitoring_gap_seconds,
        ("evidence_window", "first_attempt_required"): True,
        ("evidence_window", "retries_allowed_for_gate"): 0,
        ("evidence_window", "minimum_resolved_critical_incidents"): 1,
        ("thresholds", "http_error_rate_5m", "warning_percent"): D39_03.error_warning_percent,
        ("thresholds", "http_error_rate_5m", "critical_percent"): D39_03.error_critical_percent,
        ("thresholds", "http_error_rate_5m", "recovery_evaluations"): D39_03.recovery_evaluations,
        ("thresholds", "resources", "warning_percent"): D39_03.resource_warning_percent,
        ("thresholds", "resources", "critical_percent"): D39_03.resource_critical_percent,
        ("thresholds", "resources", "recovery_below_percent"): D39_03.resource_recovery_percent,
        ("thresholds", "resources", "sustain_seconds"): D39_03.resource_sustain_seconds,
        ("thresholds", "resources", "recovery_evaluations"): D39_03.recovery_evaluations,
        ("thresholds", "backup_age", "warning_seconds"): D39_03.backup_warning_age_seconds,
        ("thresholds", "backup_age", "critical_seconds"): D39_03.backup_critical_age_seconds,
        ("thresholds", "gateway_backlog", "warning_consecutive_failures"): D39_03.gateway_warning_failures,
        ("thresholds", "gateway_backlog", "critical_heartbeat_age_seconds"): D39_03.gateway_heartbeat_critical_seconds,
        ("thresholds", "availability", "annual_slo_percent"): D39_03.annual_slo_percent,
        ("thresholds", "availability", "annual_error_budget_minutes"): D39_03.annual_error_budget_minutes,
        ("thresholds", "availability", "short_window_proves_annual_slo"): False,
        ("mttr", "starts_at"): "critical_alert_fired_at",
        ("mttr", "recovery_requires", "readiness_passed"): True,
        ("mttr", "recovery_requires", "critical_e2e_passed"): True,
        ("mttr", "recovery_requires", "consecutive_evaluations"): D39_03.recovery_evaluations,
    }
    for path, value in expected.items():
        current: Any = contract
        for key in path:
            current = current.get(key) if isinstance(current, Mapping) else None
        if current != value:
            errors.append(f"contract drift at {'.'.join(path)}: expected {value!r}, got {current!r}")
    required_artifacts = {
        "availability_samples", "provenance_samples", "e2e_runs", "incidents", "alerts",
        "maintenance_windows", "source_hashes", "backend_image_manifest",
        "frontend_image_manifest", "environment",
    }
    if set(contract.get("required_artifacts", ())) != required_artifacts:
        errors.append("contract required_artifacts drift")
    if contract.get("required_acceptance_criteria") != [f"AC{index}" for index in range(1, 8)]:
        errors.append("contract required_acceptance_criteria drift")
    source_paths = contract.get("required_source_paths")
    if not isinstance(source_paths, list) or not source_paths or len(source_paths) != len(set(source_paths)):
        errors.append("contract required_source_paths must be a unique non-empty list")


def _validate_manifest_schema(manifest: Mapping[str, Any], errors: list[str]) -> None:
    try:
        schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, SchemaError) as exc:
        errors.append(f"manifest schema cannot be loaded: {exc}")
        return
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        errors.append(f"manifest schema {path or '$'}: {error.message}")


def _artifact_path(root: Path, relative: Any, name: str, errors: list[str]) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        errors.append(f"artifact {name} path must be relative")
        return None
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        errors.append(f"artifact {name} is missing or outside the evidence root")
        return None
    if path.is_symlink() or not path.is_file():
        errors.append(f"artifact {name} must be a regular non-symlink file")
        return None
    return path


def _load_json_artifact(
    root: Path, artifacts: Mapping[str, Any], name: str, errors: list[str]
) -> Any:
    spec = artifacts.get(name)
    if not isinstance(spec, Mapping):
        errors.append(f"artifact {name} is not declared")
        return None
    path = _artifact_path(root, spec.get("path"), name, errors)
    expected_hash = spec.get("sha256")
    if path is None:
        return None
    data = path.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash) or expected_hash != actual_hash:
        errors.append(f"artifact {name} sha256 mismatch")
        return None
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"artifact {name} is not valid JSON: {exc}")
        return None


def _validate_manifest_shape(
    manifest: Mapping[str, Any], contract: Mapping[str, Any], errors: list[str]
) -> None:
    for field, expected in (
        ("schema_version", 1),
        ("story_id", "39.7"),
        ("owner", "proecheng"),
        ("decision_id", "D39-03"),
        ("annual_slo_proven", False),
    ):
        if manifest.get(field) != expected:
            errors.append(f"manifest {field} must be {expected!r}")
    if manifest.get("status") != "pass" or manifest.get("gate_result") != "PASS":
        errors.append(f"manifest is pending or blocked: status={manifest.get('status')!r}, gate={manifest.get('gate_result')!r}")
    commands = manifest.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("manifest commands must be non-empty")
    elif any(not isinstance(command, str) or not command.strip() or PLACEHOLDER_RE.match(command.strip()) for command in commands):
        errors.append("manifest commands contain a placeholder")
    tool_versions = manifest.get("tool_versions")
    if not isinstance(tool_versions, Mapping) or not tool_versions:
        errors.append("manifest tool_versions must be non-empty")
    elif any(
        not isinstance(tool, str) or not tool.strip() or not isinstance(version, str)
        or not version.strip() or PLACEHOLDER_RE.match(version.strip())
        for tool, version in tool_versions.items()
    ):
        errors.append("manifest tool_versions contain a placeholder")
    known_limits = manifest.get("known_limits")
    if not isinstance(known_limits, list) or not known_limits:
        errors.append("manifest known_limits must be non-empty")
    elif any(not isinstance(limit, str) or not limit.strip() or PLACEHOLDER_RE.match(limit.strip()) for limit in known_limits):
        errors.append("manifest known_limits contain a placeholder")
    ac_mapping = manifest.get("ac_mapping")
    for index in range(1, 8):
        key = f"AC{index}"
        if not isinstance(ac_mapping, Mapping) or not isinstance(ac_mapping.get(key), list) or not ac_mapping[key]:
            errors.append(f"manifest ac_mapping.{key} must be non-empty")
            continue
        required = set(contract.get("required_ac_artifacts", {}).get(key, ()))
        if not required.issubset(set(ac_mapping[key])):
            errors.append(f"manifest ac_mapping.{key} omits required artifacts")
    artifacts = manifest.get("artifacts")
    required_artifacts = set(contract.get("required_artifacts", ()))
    if not isinstance(artifacts, Mapping) or set(artifacts) != required_artifacts:
        errors.append("manifest artifacts must exactly match contract required_artifacts")


def _validate_provenance(manifest: Mapping[str, Any], errors: list[str]) -> dict[str, str]:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        errors.append("manifest provenance must be an object")
        return {}
    values = {key: provenance.get(key) for key in ("git_sha", "backend_image", "frontend_image", "environment_fingerprint")}
    if not isinstance(values["git_sha"], str) or not GIT_SHA_RE.fullmatch(values["git_sha"]):
        errors.append("provenance git_sha must be a 40-character lowercase SHA")
    for key in ("backend_image", "frontend_image"):
        if not isinstance(values[key], str) or not IMAGE_RE.fullmatch(values[key]):
            errors.append(f"provenance {key} must use an immutable @sha256 digest")
    if not isinstance(values["environment_fingerprint"], str) or not SHA256_RE.fullmatch(values["environment_fingerprint"]):
        errors.append("provenance environment_fingerprint must be a sha256 value")
    return {key: str(value) for key, value in values.items()}


def _validate_trusted_provenance(
    provenance: Mapping[str, str], trusted_provenance: Mapping[str, Any] | None, errors: list[str]
) -> None:
    if not isinstance(trusted_provenance, Mapping):
        errors.append("trusted provenance must be supplied outside the candidate manifest")
        return
    for key, value in provenance.items():
        if trusted_provenance.get(key) != value:
            errors.append(f"trusted provenance mismatch: {key}")


def _git_bytes(repository_root: Path, *args: str) -> bytes | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=repository_root, stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _validate_git_sources(
    repository_root: Path,
    git_sha: str,
    source_hashes: Any,
    required_source_paths: Any,
    errors: list[str],
) -> None:
    commit = _git_bytes(repository_root, "rev-parse", "--verify", f"{git_sha}^{{commit}}")
    if commit is None or commit.decode().strip() != git_sha:
        errors.append("provenance git_sha is not a commit in the trusted repository")
        return
    if not isinstance(required_source_paths, list):
        return
    required = set(required_source_paths)
    if not isinstance(source_hashes, Mapping) or set(source_hashes) != required:
        errors.append("source hashes do not contain the complete required source list")
        return
    for source_path in required_source_paths:
        source_hash = source_hashes.get(source_path)
        if not isinstance(source_path, str) or Path(source_path).is_absolute() or ".." in Path(source_path).parts:
            errors.append(f"required source path is invalid: {source_path!r}")
            continue
        if not isinstance(source_hash, str) or not SHA256_RE.fullmatch(source_hash):
            errors.append(f"source hash is invalid: {source_path}")
            continue
        content = _git_bytes(repository_root, "show", f"{git_sha}:{source_path}")
        if content is None:
            errors.append(f"required source is absent from trusted Git commit: {source_path}")
        elif hashlib.sha256(content).hexdigest() != source_hash:
            errors.append(f"source hash mismatch against trusted Git commit: {source_path}")


def _validate_content_provenance(
    artifacts: Mapping[str, Any],
    provenance: Mapping[str, str],
    image_manifests: Mapping[str, Any],
    environment: Any,
    errors: list[str],
) -> None:
    for artifact_name, provenance_key in (
        ("backend_image_manifest", "backend_image"),
        ("frontend_image_manifest", "frontend_image"),
    ):
        image = provenance.get(provenance_key, "")
        expected_digest = image.rsplit("@sha256:", 1)[-1]
        artifact = artifacts.get(artifact_name)
        if not isinstance(artifact, Mapping) or artifact.get("sha256") != expected_digest:
            errors.append(f"{provenance_key} digest is not bound to its OCI manifest bytes")
        manifest = image_manifests.get(artifact_name)
        revision = manifest.get("annotations", {}).get("org.opencontainers.image.revision") if isinstance(manifest, Mapping) else None
        if revision != provenance.get("git_sha"):
            errors.append(f"{provenance_key} OCI revision does not match Git provenance")
    environment_artifact = artifacts.get("environment")
    if not isinstance(environment_artifact, Mapping) or environment_artifact.get("sha256") != provenance.get("environment_fingerprint"):
        errors.append("environment fingerprint is not bound to environment artifact bytes")
    required_environment_fields = ("provider", "deployment_id", "cluster_uid", "configuration_digest")
    if not isinstance(environment, Mapping) or any(
        not isinstance(environment.get(field), str) or not environment[field].strip()
        for field in required_environment_fields
    ):
        errors.append("environment artifact is missing required identity fields")


def _validate_continuity(samples: Any, started_at, ended_at, errors: list[str]) -> None:
    if not isinstance(samples, list) or not samples:
        errors.append("availability samples must be a non-empty list")
        return
    expected = started_at
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            errors.append(f"availability sample {index} must be an object")
            return
        try:
            timestamp = parse_utc(sample.get("timestamp_utc"), f"availability sample {index}.timestamp_utc")
            duration = float(sample.get("duration_seconds", 60))
        except (EvidenceValidationError, TypeError, ValueError) as exc:
            errors.append(str(exc))
            return
        if not math.isfinite(duration) or duration <= 0 or duration > D39_03.monitoring_gap_seconds:
            errors.append(f"availability sample {index} duration exceeds monitoring gap")
            return
        if timestamp != expected:
            errors.append(f"availability samples are not continuous at index {index}")
            return
        expected = timestamp + timedelta(seconds=duration)
    if expected != ended_at:
        errors.append("availability samples do not cover the exact evidence window")


def _validate_provenance_continuity(
    samples: Any, started_at: datetime, ended_at: datetime, provenance: Mapping[str, str], errors: list[str]
) -> None:
    before = len(errors)
    _validate_continuity(samples, started_at, ended_at, errors)
    if len(errors) > before:
        errors[-1] = errors[-1].replace("availability samples", "provenance samples")
        return
    identity_fields = (
        "collector_instance_id", "process_start_utc", "restart_count",
        "backend_instance_id", "backend_process_start_utc", "backend_restart_count",
        "frontend_instance_id", "frontend_process_start_utc", "frontend_restart_count",
    )
    process_identity: tuple[Any, ...] | None = None
    for index, sample in enumerate(samples):
        if any(sample.get(key) != value for key, value in provenance.items()):
            errors.append(f"provenance sample {index} provenance drift")
        identity = tuple(sample.get(field) for field in identity_fields)
        if any(
            not isinstance(identity[position], str) or not identity[position]
            for position in (0, 1, 3, 4, 6, 7)
        ) or any(not isinstance(identity[position], int) or identity[position] != 0 for position in (2, 5, 8)):
            errors.append(f"provenance sample {index} has invalid collector identity")
        if process_identity is None:
            process_identity = identity
        elif identity != process_identity:
            errors.append(f"provenance sample {index} records a process/configuration restart")


def _validate_e2e(runs: Any, started_at, ended_at, provenance: Mapping[str, str], errors: list[str]) -> int:
    if not isinstance(runs, list):
        errors.append("e2e runs must be a list")
        return 0
    timestamps = []
    qualifying = 0
    run_ids: set[str] = set()
    for index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            errors.append(f"e2e run {index} must be an object")
            continue
        try:
            timestamp = parse_utc(run.get("timestamp_utc"), f"e2e run {index}.timestamp_utc")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
            continue
        timestamps.append(timestamp)
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id in run_ids:
            errors.append(f"e2e run {index} has a missing or duplicate run_id")
        else:
            run_ids.add(run_id)
        if not started_at <= timestamp <= ended_at:
            errors.append(f"e2e run {index} is outside the evidence window")
        if run.get("retry_count") != 0:
            errors.append(f"e2e run {index} used a retry")
        if run.get("status") != "passed" or run.get("first_attempt_passed") is not True:
            errors.append(f"e2e run {index} did not pass on the first attempt")
        if run.get("skipped_critical_tests") != 0:
            errors.append(f"e2e run {index} skipped critical tests")
        if any(run.get(key) != provenance.get(key) for key in provenance):
            errors.append(f"e2e run {index} provenance drift")
        if (
            run.get("retry_count") == 0
            and run.get("status") == "passed"
            and run.get("first_attempt_passed") is True
            and run.get("skipped_critical_tests") == 0
        ):
            qualifying += 1
    if len(timestamps) >= 2:
        for previous, current in zip(timestamps, timestamps[1:]):
            if current <= previous or (current - previous).total_seconds() < D39_03.minimum_e2e_spacing_seconds:
                errors.append("e2e runs are not strictly ordered with minimum spacing")
                break
        if (timestamps[-1] - timestamps[0]).total_seconds() < D39_03.evidence_window_seconds:
            errors.append("first and last qualifying e2e runs do not span 72 hours")
    if qualifying < D39_03.critical_e2e_runs:
        errors.append(f"only {qualifying} qualifying first-pass e2e runs; {D39_03.critical_e2e_runs} required")
    return qualifying


def _validate_maintenance_windows(
    windows: Any, samples: Any, started_at: datetime, ended_at: datetime, errors: list[str]
) -> None:
    if not isinstance(windows, list):
        errors.append("maintenance_windows must be a list")
        return
    approved_ids: set[str] = set()
    for index, window in enumerate(windows):
        if not isinstance(window, Mapping):
            errors.append(f"maintenance window {index} must be an object")
            continue
        maintenance_id = window.get("maintenance_id")
        try:
            approved_at = parse_utc(window.get("approved_at_utc"), f"maintenance window {index}.approved_at_utc")
            maintenance_start = parse_utc(window.get("started_at_utc"), f"maintenance window {index}.started_at_utc")
            maintenance_end = parse_utc(window.get("ended_at_utc"), f"maintenance window {index}.ended_at_utc")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(maintenance_id, str) or not maintenance_id or maintenance_id in approved_ids:
            errors.append(f"maintenance window {index} has invalid or duplicate maintenance_id")
        else:
            approved_ids.add(maintenance_id)
        if window.get("subject") != "service" or not all(
            isinstance(window.get(field), str) and window[field].strip() for field in ("approved_by", "change_id")
        ):
            errors.append(f"maintenance window {index} lacks independent approval identity")
        if not (started_at <= maintenance_start < maintenance_end <= ended_at) or approved_at >= maintenance_start:
            errors.append(f"maintenance window {index} is not pre-approved inside the evidence window")
    if not isinstance(samples, list):
        return
    for index, sample in enumerate(samples):
        if not isinstance(sample, Mapping):
            continue
        if "maintenance_excluded" in sample or "maintenance_approved_at_utc" in sample:
            errors.append(f"availability sample {index} contains self-reported maintenance exclusion")
        maintenance_id = sample.get("maintenance_id")
        if maintenance_id is not None and maintenance_id not in approved_ids:
            errors.append(f"availability sample {index} references unapproved maintenance")


def _validate_incident_alert_timeline(
    incidents: Any,
    alerts: Any,
    mttr: Mapping[str, Any] | None,
    started_at: datetime,
    ended_at: datetime,
    errors: list[str],
) -> None:
    if not isinstance(incidents, list) or not isinstance(alerts, list):
        return
    incident_map: dict[str, Mapping[str, Any]] = {}
    mttr_map = {
        item.get("incident_id"): item for item in (mttr or {}).get("incidents", ()) if isinstance(item, Mapping)
    }
    for index, incident in enumerate(incidents):
        if not isinstance(incident, Mapping):
            continue
        incident_id = incident.get("incident_id")
        try:
            fired_at = parse_utc(incident.get("alert_fired_at_utc"), f"incident {index}.alert_fired_at_utc")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
            continue
        if not started_at <= fired_at <= ended_at:
            errors.append(f"incident {incident_id} is outside the evidence window")
        for check_index, check in enumerate(incident.get("recovery_checks", ())):
            try:
                checked_at = parse_utc(check.get("timestamp_utc"), f"incident {incident_id} recovery {check_index}")
            except (AttributeError, EvidenceValidationError) as exc:
                errors.append(str(exc))
                continue
            if not started_at <= checked_at <= ended_at:
                errors.append(f"incident {incident_id} recovery is outside the evidence window")
        if isinstance(incident_id, str):
            incident_map[incident_id] = incident
    alert_ids: set[str] = set()
    matched_incidents: set[str] = set()
    if not alerts:
        errors.append("at least one actionable critical alert is required")
    for index, alert in enumerate(alerts):
        if not isinstance(alert, Mapping):
            errors.append(f"alert {index} must be an object")
            continue
        alert_id = alert.get("alert_id")
        incident_id = alert.get("incident_id")
        if not isinstance(alert_id, str) or not alert_id or alert_id in alert_ids:
            errors.append(f"alert {index} has an invalid or duplicate alert_id")
        else:
            alert_ids.add(alert_id)
        if alert.get("severity") != "critical" or incident_id not in incident_map:
            errors.append(f"critical alert {index} has no matching incident timeline")
            continue
        try:
            fired_at = parse_utc(alert.get("fired_at_utc"), f"alert {index}.fired_at_utc")
            resolved_at = parse_utc(alert.get("resolved_at_utc"), f"alert {index}.resolved_at_utc")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
            continue
        incident_fired = parse_utc(incident_map[incident_id].get("alert_fired_at_utc"), f"incident {incident_id}.alert_fired_at_utc")
        expected_resolved = mttr_map.get(incident_id, {}).get("resolved_at_utc")
        if not (started_at <= fired_at < resolved_at <= ended_at):
            errors.append(f"alert lifecycle {alert_id} is reversed or outside the evidence window")
        if fired_at != incident_fired or expected_resolved != resolved_at.isoformat().replace("+00:00", "Z"):
            errors.append(f"alert lifecycle {alert_id} does not align with incident recovery")
        matched_incidents.add(str(incident_id))
    if set(incident_map) - matched_incidents:
        errors.append("critical incident timeline has no matching actionable alert")


def validate_evidence(
    contract_path: str | Path,
    manifest_path: str | Path,
    *,
    evidence_root: str | Path | None = None,
    repository_root: str | Path = ROOT,
    trusted_provenance: Mapping[str, Any] | None = None,
    trusted_maintenance_sha256: str | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    derived: dict[str, Any] = {}
    contract_file = Path(contract_path)
    manifest_file = Path(manifest_path)
    contract = _load_yaml(contract_file, "contract", errors)
    manifest = _load_yaml(manifest_file, "manifest", errors)
    _validate_contract(contract, errors)
    _validate_manifest_schema(manifest, errors)
    _validate_manifest_shape(manifest, contract, errors)
    provenance = _validate_provenance(manifest, errors)
    _validate_trusted_provenance(provenance, trusted_provenance, errors)

    window = manifest.get("window") if isinstance(manifest.get("window"), Mapping) else {}
    started_at = ended_at = None
    try:
        started_at = parse_utc(window.get("started_at_utc"), "window.started_at_utc")
        ended_at = parse_utc(window.get("ended_at_utc"), "window.ended_at_utc")
        window_seconds = (ended_at - started_at).total_seconds()
        derived["window_seconds"] = window_seconds
        if window_seconds <= 0:
            errors.append("evidence window must end after it starts")
        if window_seconds < D39_03.evidence_window_seconds:
            errors.append("evidence window is shorter than 72 continuous hours")
        current_time = now_utc or datetime.now(UTC)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            errors.append("trusted current time must include a timezone")
        elif ended_at > current_time.astimezone(UTC):
            errors.append("evidence window ends in the future")
    except EvidenceValidationError as exc:
        errors.append(str(exc))

    root = Path(evidence_root) if evidence_root else manifest_file.parent
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), Mapping) else {}
    availability_samples = _load_json_artifact(root, artifacts, "availability_samples", errors)
    provenance_samples = _load_json_artifact(root, artifacts, "provenance_samples", errors)
    e2e_runs = _load_json_artifact(root, artifacts, "e2e_runs", errors)
    incidents = _load_json_artifact(root, artifacts, "incidents", errors)
    alerts = _load_json_artifact(root, artifacts, "alerts", errors)
    maintenance_windows = _load_json_artifact(root, artifacts, "maintenance_windows", errors)
    source_hashes = _load_json_artifact(root, artifacts, "source_hashes", errors)
    backend_image_manifest = _load_json_artifact(root, artifacts, "backend_image_manifest", errors)
    frontend_image_manifest = _load_json_artifact(root, artifacts, "frontend_image_manifest", errors)
    environment = _load_json_artifact(root, artifacts, "environment", errors)
    if isinstance(maintenance_windows, list) and maintenance_windows:
        maintenance_artifact = artifacts.get("maintenance_windows")
        maintenance_hash = maintenance_artifact.get("sha256") if isinstance(maintenance_artifact, Mapping) else None
        if trusted_maintenance_sha256 != maintenance_hash:
            errors.append("trusted maintenance approval sha256 is required for maintenance exclusions")

    _validate_content_provenance(
        artifacts,
        provenance,
        {"backend_image_manifest": backend_image_manifest, "frontend_image_manifest": frontend_image_manifest},
        environment,
        errors,
    )
    _validate_git_sources(
        Path(repository_root),
        provenance.get("git_sha", ""),
        source_hashes,
        contract.get("required_source_paths"),
        errors,
    )

    if started_at is not None and ended_at is not None:
        _validate_continuity(availability_samples, started_at, ended_at, errors)
        _validate_provenance_continuity(provenance_samples, started_at, ended_at, provenance, errors)
        _validate_maintenance_windows(maintenance_windows, availability_samples, started_at, ended_at, errors)
        derived["qualifying_e2e_runs"] = _validate_e2e(e2e_runs, started_at, ended_at, provenance, errors)
    if isinstance(availability_samples, list):
        try:
            derived["availability"] = calculate_availability(
                availability_samples,
                maintenance_windows=maintenance_windows if isinstance(maintenance_windows, list) else None,
            )
            if derived["availability"]["observed_availability_percent"] < D39_03.annual_slo_percent:
                errors.append("observed availability is below the 99.5% release threshold")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
    if isinstance(incidents, list):
        try:
            derived["mttr"] = calculate_mttr(incidents)
            if derived["mttr"]["unresolved_incidents"]:
                errors.append("critical incidents remain unresolved")
            if derived["mttr"]["resolved_incidents"] < 1:
                errors.append("at least one resolved critical incident drill is required")
        except EvidenceValidationError as exc:
            errors.append(str(exc))
    if started_at is not None and ended_at is not None:
        _validate_incident_alert_timeline(
            incidents,
            alerts,
            derived.get("mttr"),
            started_at,
            ended_at,
            errors,
        )

    return {
        "schema_version": 1,
        "story_id": "39.7",
        "valid": not errors,
        "errors": errors,
        "derived": derived,
        "annual_slo_proven": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--trusted-provenance", type=Path)
    parser.add_argument("--trusted-maintenance-sha256")
    args = parser.parse_args()
    trusted_provenance = None
    if args.trusted_provenance:
        try:
            trusted_provenance = json.loads(args.trusted_provenance.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            trusted_provenance = None
    result = validate_evidence(
        args.contract,
        args.manifest,
        repository_root=args.repository_root,
        trusted_provenance=trusted_provenance,
        trusted_maintenance_sha256=args.trusted_maintenance_sha256,
    )
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
