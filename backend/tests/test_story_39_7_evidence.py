import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "deploy" / "observability" / "story-39-7-contract.yaml"
PENDING_MANIFEST = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.7" / "manifest.yaml"
MANIFEST_SCHEMA = PENDING_MANIFEST.with_name("manifest.schema.json")
SCRIPT = ROOT / "scripts" / "story_39_7_evidence.py"
UTC = timezone.utc


def _write_json(path: Path, payload) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _candidate(tmp_path: Path) -> tuple[Path, dict]:
    start = datetime(2026, 8, 18, tzinfo=UTC)
    end = start + timedelta(hours=72)
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    repository = tmp_path / "repository"
    repository.mkdir()
    for source_path in contract["required_source_paths"]:
        path = repository / source_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"trusted test source: {source_path}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "story-39-7@example.invalid"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Story 39.7 Test"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "trusted candidate"], cwd=repository, check=True)
    git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    environment_record = {
        "provider": "preproduction-platform",
        "deployment_id": "deploy-39-7",
        "cluster_uid": "cluster-39-7",
        "configuration_digest": "sha256:" + "d" * 64,
    }
    environment_path = tmp_path / "environment.json"
    environment = _write_json(environment_path, environment_record)
    backend_manifest_path = tmp_path / "backend_image_manifest.json"
    backend_digest = _write_json(backend_manifest_path, {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": "sha256:" + "1" * 64},
        "layers": [],
        "annotations": {"org.opencontainers.image.revision": git_sha},
    })
    frontend_manifest_path = tmp_path / "frontend_image_manifest.json"
    frontend_digest = _write_json(frontend_manifest_path, {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": "sha256:" + "2" * 64},
        "layers": [],
        "annotations": {"org.opencontainers.image.revision": git_sha},
    })
    backend_image = "ghcr.io/example/backend@sha256:" + backend_digest
    frontend_image = "ghcr.io/example/frontend@sha256:" + frontend_digest
    samples = [
        {
            "timestamp_utc": _iso(start + timedelta(minutes=5 * index)),
            "duration_seconds": 300,
            "telemetry_present": True,
            "readiness_passed": True,
            "critical_e2e_passed": True,
        }
        for index in range(72 * 12)
    ]
    provenance_samples = [
        {
            "timestamp_utc": _iso(start + timedelta(minutes=5 * index)),
            "duration_seconds": 300,
            "git_sha": git_sha,
            "backend_image": backend_image,
            "frontend_image": frontend_image,
            "environment_fingerprint": environment,
            "collector_instance_id": "collector-39-7",
            "process_start_utc": _iso(start - timedelta(minutes=1)),
            "restart_count": 0,
            "backend_instance_id": "backend-39-7",
            "backend_process_start_utc": _iso(start - timedelta(minutes=2)),
            "backend_restart_count": 0,
            "frontend_instance_id": "frontend-39-7",
            "frontend_process_start_utc": _iso(start - timedelta(minutes=2)),
            "frontend_restart_count": 0,
        }
        for index in range(72 * 12)
    ]
    e2e_hours = [0, 6, 12, 18, 24, 30, 36, 42, 48, 54, 60, 72]
    e2e_runs = [
        {
            "run_id": f"run-{index + 1}",
            "timestamp_utc": _iso(start + timedelta(hours=hour)),
            "status": "passed",
            "first_attempt_passed": True,
            "retry_count": 0,
            "skipped_critical_tests": 0,
            "git_sha": git_sha,
            "backend_image": backend_image,
            "frontend_image": frontend_image,
            "environment_fingerprint": environment,
        }
        for index, hour in enumerate(e2e_hours)
    ]
    incident_start = start + timedelta(hours=24)
    incidents = [{
        "incident_id": "INC-DRILL-1",
        "severity": "critical",
        "alert_fired_at_utc": _iso(incident_start),
        "alert_fired_monotonic_seconds": 100.0,
        "recovery_checks": [
            {"timestamp_utc": _iso(incident_start + timedelta(minutes=1)), "monotonic_seconds": 160.0, "readiness_passed": True, "critical_e2e_passed": True},
            {"timestamp_utc": _iso(incident_start + timedelta(minutes=2)), "monotonic_seconds": 220.0, "readiness_passed": True, "critical_e2e_passed": True},
            {"timestamp_utc": _iso(incident_start + timedelta(minutes=3)), "monotonic_seconds": 280.0, "readiness_passed": True, "critical_e2e_passed": True},
        ],
    }]
    alerts = [{
        "alert_id": "ALERT-DRILL-1",
        "incident_id": "INC-DRILL-1",
        "severity": "critical",
        "fired_at_utc": _iso(incident_start),
        "resolved_at_utc": _iso(incident_start + timedelta(minutes=3)),
    }]
    source_hashes = {
        source_path: hashlib.sha256(
            subprocess.check_output(["git", "show", f"{git_sha}:{source_path}"], cwd=repository)
        ).hexdigest()
        for source_path in contract["required_source_paths"]
    }
    artifacts = {}
    for name, payload in (
        ("availability_samples", samples),
        ("provenance_samples", provenance_samples),
        ("e2e_runs", e2e_runs),
        ("incidents", incidents),
        ("alerts", alerts),
        ("maintenance_windows", []),
        ("source_hashes", source_hashes),
    ):
        path = tmp_path / f"{name}.json"
        artifacts[name] = {"path": path.name, "sha256": _write_json(path, payload)}
    artifacts["backend_image_manifest"] = {"path": backend_manifest_path.name, "sha256": backend_digest}
    artifacts["frontend_image_manifest"] = {"path": frontend_manifest_path.name, "sha256": frontend_digest}
    artifacts["environment"] = {"path": environment_path.name, "sha256": environment}
    manifest = {
        "schema_version": 1,
        "story_id": "39.7",
        "status": "pass",
        "gate_result": "PASS",
        "owner": "proecheng",
        "decision_id": "D39-03",
        "annual_slo_proven": False,
        "provenance": {
            "git_sha": git_sha,
            "backend_image": backend_image,
            "frontend_image": frontend_image,
            "environment_fingerprint": environment,
        },
        "window": {"started_at_utc": _iso(start), "ended_at_utc": _iso(end)},
        "artifacts": artifacts,
        "commands": ["pytest -q e2e/critical"],
        "tool_versions": {"pytest": "8.3.5", "playwright": "1.51.1"},
        "ac_mapping": contract["required_ac_artifacts"],
        "known_limits": ["The 72-hour window does not prove the annual SLO."],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path, manifest


def _validate(validate_evidence, manifest_path: Path, manifest: dict, **overrides):
    options = {
        "repository_root": manifest_path.parent / "repository",
        "trusted_provenance": manifest["provenance"],
        "now_utc": datetime.fromisoformat(manifest["window"]["ended_at_utc"].replace("Z", "+00:00"))
        + timedelta(minutes=1),
    }
    options.update(overrides)
    return validate_evidence(CONTRACT, manifest_path, **options)


def _load_validator():
    sys.path.insert(0, str(ROOT / "scripts"))
    from story_39_7_evidence import validate_evidence

    return validate_evidence


def _schema_errors(manifest: dict) -> list[str]:
    schema = json.loads(MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(manifest)]


def test_pending_manifest_conforms_to_lifecycle_schema():
    manifest = yaml.safe_load(PENDING_MANIFEST.read_text(encoding="utf-8"))
    assert _schema_errors(manifest) == []


@pytest.mark.parametrize(
    ("status", "gate_result"),
    [("pass", "PASS"), ("pass", "BLOCKED"), ("pending", "PASS")],
)
def test_manifest_schema_rejects_false_pass_and_status_gate_contradictions(status: str, gate_result: str):
    manifest = yaml.safe_load(PENDING_MANIFEST.read_text(encoding="utf-8"))
    manifest.update({"status": status, "gate_result": gate_result})
    assert _schema_errors(manifest)


def test_evidence_validator_applies_manifest_schema(tmp_path: Path):
    validate_evidence = _load_validator()
    manifest_path, manifest = _candidate(tmp_path)
    manifest["gate_result"] = "BLOCKED"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    result = _validate(validate_evidence, manifest_path, manifest)
    assert result["valid"] is False
    assert any("manifest schema gate_result" in error for error in result["errors"])


def test_valid_evidence_recomputes_72_hour_first_pass_gate(tmp_path: Path):
    validate_evidence = _load_validator()
    manifest_path, _ = _candidate(tmp_path)
    result = _validate(validate_evidence, manifest_path, yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    assert result["valid"] is True
    assert result["derived"]["window_seconds"] == 72 * 3600
    assert result["derived"]["qualifying_e2e_runs"] == 12
    assert result["derived"]["availability"]["observed_availability_percent"] == 100.0
    assert result["derived"]["availability"]["annual_slo_proven"] is False
    assert result["derived"]["mttr"]["resolved_incidents"] == 1


@pytest.mark.parametrize("mutation,expected", [
    ("retry", "retry"),
    ("gap", "continuous"),
    ("image_drift", "provenance"),
    ("unresolved", "unresolved"),
    ("orphan_alert", "incident"),
    ("low_availability", "availability"),
    ("source_drift", "source hash"),
    ("duplicate_run", "duplicate run_id"),
    ("missing_alert", "actionable critical alert"),
    ("annual_claim", "annual_slo_proven"),
    ("future_window", "future"),
    ("incident_outside", "outside the evidence window"),
    ("reversed_alert", "alert lifecycle"),
    ("incomplete_sources", "required source"),
    ("provenance_gap", "provenance samples are not continuous"),
    ("placeholder_command", "placeholder"),
    ("self_reported_maintenance", "maintenance"),
    ("ac_artifact_drift", "omits required artifacts"),
    ("untrusted_maintenance", "trusted maintenance approval"),
    ("backend_restart", "restart"),
])
def test_evidence_validator_rejects_false_pass_inputs(tmp_path: Path, mutation: str, expected: str):
    validate_evidence = _load_validator()
    manifest_path, manifest = _candidate(tmp_path)
    if mutation == "retry":
        payload = json.loads((tmp_path / "e2e_runs.json").read_text(encoding="utf-8"))
        payload[0]["retry_count"] = 1
        manifest["artifacts"]["e2e_runs"]["sha256"] = _write_json(tmp_path / "e2e_runs.json", payload)
    elif mutation == "gap":
        payload = json.loads((tmp_path / "availability_samples.json").read_text(encoding="utf-8"))
        del payload[10]
        manifest["artifacts"]["availability_samples"]["sha256"] = _write_json(tmp_path / "availability_samples.json", payload)
    elif mutation == "image_drift":
        payload = json.loads((tmp_path / "e2e_runs.json").read_text(encoding="utf-8"))
        payload[4]["backend_image"] = "ghcr.io/example/backend@sha256:" + "e" * 64
        manifest["artifacts"]["e2e_runs"]["sha256"] = _write_json(tmp_path / "e2e_runs.json", payload)
    elif mutation == "unresolved":
        payload = [{
            "incident_id": "INC-1",
            "severity": "critical",
            "alert_fired_at_utc": manifest["window"]["started_at_utc"],
            "alert_fired_monotonic_seconds": 10.0,
            "recovery_checks": [],
        }]
        manifest["artifacts"]["incidents"]["sha256"] = _write_json(tmp_path / "incidents.json", payload)
    elif mutation == "orphan_alert":
        payload = [{
            "alert_id": "ALERT-1",
            "incident_id": "INC-MISSING",
            "severity": "critical",
            "fired_at_utc": manifest["window"]["started_at_utc"],
            "resolved_at_utc": manifest["window"]["ended_at_utc"],
        }]
        manifest["artifacts"]["alerts"]["sha256"] = _write_json(tmp_path / "alerts.json", payload)
    elif mutation == "low_availability":
        payload = json.loads((tmp_path / "availability_samples.json").read_text(encoding="utf-8"))
        for sample in payload[:5]:
            sample["readiness_passed"] = False
        manifest["artifacts"]["availability_samples"]["sha256"] = _write_json(tmp_path / "availability_samples.json", payload)
    elif mutation == "source_drift":
        payload = {"backend/app/main.py": "0" * 64}
        manifest["artifacts"]["source_hashes"]["sha256"] = _write_json(tmp_path / "source_hashes.json", payload)
    elif mutation == "duplicate_run":
        payload = json.loads((tmp_path / "e2e_runs.json").read_text(encoding="utf-8"))
        payload[1]["run_id"] = payload[0]["run_id"]
        manifest["artifacts"]["e2e_runs"]["sha256"] = _write_json(tmp_path / "e2e_runs.json", payload)
    elif mutation == "missing_alert":
        manifest["artifacts"]["alerts"]["sha256"] = _write_json(tmp_path / "alerts.json", [])
    elif mutation == "annual_claim":
        manifest["annual_slo_proven"] = True
    elif mutation == "future_window":
        pass
    elif mutation == "incident_outside":
        payload = json.loads((tmp_path / "incidents.json").read_text(encoding="utf-8"))
        payload[0]["alert_fired_at_utc"] = _iso(datetime.fromisoformat(manifest["window"]["started_at_utc"].replace("Z", "+00:00")) - timedelta(minutes=1))
        manifest["artifacts"]["incidents"]["sha256"] = _write_json(tmp_path / "incidents.json", payload)
    elif mutation == "reversed_alert":
        payload = json.loads((tmp_path / "alerts.json").read_text(encoding="utf-8"))
        payload[0]["resolved_at_utc"] = _iso(datetime.fromisoformat(payload[0]["fired_at_utc"].replace("Z", "+00:00")) - timedelta(seconds=1))
        manifest["artifacts"]["alerts"]["sha256"] = _write_json(tmp_path / "alerts.json", payload)
    elif mutation == "incomplete_sources":
        payload = json.loads((tmp_path / "source_hashes.json").read_text(encoding="utf-8"))
        payload.pop(next(iter(payload)))
        manifest["artifacts"]["source_hashes"]["sha256"] = _write_json(tmp_path / "source_hashes.json", payload)
    elif mutation == "provenance_gap":
        payload = json.loads((tmp_path / "provenance_samples.json").read_text(encoding="utf-8"))
        del payload[10]
        manifest["artifacts"]["provenance_samples"]["sha256"] = _write_json(tmp_path / "provenance_samples.json", payload)
    elif mutation == "placeholder_command":
        manifest["commands"] = ["PENDING"]
    elif mutation == "ac_artifact_drift":
        manifest["ac_mapping"]["AC5"] = ["e2e_runs"]
    elif mutation == "untrusted_maintenance":
        window = {
            "maintenance_id": "MW-1",
            "subject": "service",
            "approved_at_utc": _iso(datetime.fromisoformat(manifest["window"]["started_at_utc"].replace("Z", "+00:00")) - timedelta(hours=1)),
            "started_at_utc": manifest["window"]["started_at_utc"],
            "ended_at_utc": _iso(datetime.fromisoformat(manifest["window"]["started_at_utc"].replace("Z", "+00:00")) + timedelta(minutes=5)),
            "approved_by": "change-manager",
            "change_id": "CHG-1",
        }
        manifest["artifacts"]["maintenance_windows"]["sha256"] = _write_json(tmp_path / "maintenance_windows.json", [window])
        samples = json.loads((tmp_path / "availability_samples.json").read_text(encoding="utf-8"))
        samples[0]["maintenance_id"] = "MW-1"
        manifest["artifacts"]["availability_samples"]["sha256"] = _write_json(tmp_path / "availability_samples.json", samples)
    elif mutation == "backend_restart":
        payload = json.loads((tmp_path / "provenance_samples.json").read_text(encoding="utf-8"))
        payload[10]["backend_restart_count"] = 1
        manifest["artifacts"]["provenance_samples"]["sha256"] = _write_json(tmp_path / "provenance_samples.json", payload)
    else:
        payload = json.loads((tmp_path / "availability_samples.json").read_text(encoding="utf-8"))
        payload[0].update({"maintenance_excluded": True, "maintenance_approved_at_utc": _iso(datetime(2020, 1, 1, tzinfo=UTC))})
        manifest["artifacts"]["availability_samples"]["sha256"] = _write_json(tmp_path / "availability_samples.json", payload)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    options = {}
    if mutation == "future_window":
        options["now_utc"] = datetime.fromisoformat(manifest["window"]["ended_at_utc"].replace("Z", "+00:00")) - timedelta(seconds=1)
    result = _validate(validate_evidence, manifest_path, manifest, **options)
    assert result["valid"] is False
    assert expected in " ".join(result["errors"]).lower()


def test_evidence_validator_requires_external_trust_anchors(tmp_path: Path):
    validate_evidence = _load_validator()
    manifest_path, manifest = _candidate(tmp_path)
    result = _validate(validate_evidence, manifest_path, manifest, trusted_provenance=None)
    assert result["valid"] is False
    assert "trusted provenance" in " ".join(result["errors"]).lower()


def test_checked_in_pending_manifest_fails_cli_closed(tmp_path: Path):
    output = tmp_path / "validation.json"
    environment = os.environ.copy()
    environment.pop("FAULT_TREE_HMAC_KEY", None)
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--contract", str(CONTRACT), "--manifest", str(PENDING_MANIFEST), "--output", str(output)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["valid"] is False
    assert any("pending" in error.lower() for error in result["errors"])
