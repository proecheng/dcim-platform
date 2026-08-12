"""Story 39.1 single-maintainer evidence governance tests."""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import story_39_1_evidence as EVIDENCE
import story_39_1_governance as GOVERNANCE


def _write_bound_test_reports(tmp_path: Path, *, started_at: str = "2026-08-12T10:05:00Z") -> None:
    suite = ET.Element(
        "testsuite",
        {
            "name": "pytest",
            "timestamp": started_at,
            "tests": str(len(EVIDENCE.PYTEST_TEST_FILES)),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
        },
    )
    for test_file in EVIDENCE.PYTEST_TEST_FILES:
        classname = test_file.removesuffix(".py").replace("/", ".")
        ET.SubElement(suite, "testcase", {"classname": classname, "name": "test_evidence", "time": "0.1"})
    ET.ElementTree(suite).write(tmp_path / "pytest-authz.xml", encoding="utf-8", xml_declaration=True)

    playwright = {
        "suites": [
            {"file": Path(test_file).name, "tests": [{"status": "expected"}]}
            for test_file in EVIDENCE.PLAYWRIGHT_TEST_FILES
        ],
        "stats": {
            "startTime": started_at,
            "duration": 1000,
            "expected": len(EVIDENCE.PLAYWRIGHT_TEST_FILES),
            "unexpected": 0,
            "skipped": 0,
            "flaky": 0,
        },
    }
    (tmp_path / "playwright-authz-results.json").write_text(json.dumps(playwright), encoding="utf-8")

    started_at_ms = int(datetime.fromisoformat(started_at.replace("Z", "+00:00")).timestamp() * 1000)
    vitest = {
        "startTime": started_at_ms,
        "numTotalTestSuites": len(EVIDENCE.VITEST_TEST_FILES),
        "numTotalTests": len(EVIDENCE.VITEST_TEST_FILES),
        "numPassedTests": len(EVIDENCE.VITEST_TEST_FILES),
        "numFailedTests": 0,
        "numPendingTests": 0,
        "success": True,
        "testResults": [
            {"name": str(ROOT / "frontend" / test_file), "assertionResults": [{"status": "passed"}]}
            for test_file in EVIDENCE.VITEST_TEST_FILES
        ],
    }
    (tmp_path / "vitest-websocket-results.json").write_text(json.dumps(vitest), encoding="utf-8")


@pytest.fixture
def verified_manifest():
    return {
        "governance": {
            "mode": "single-maintainer",
            "maintainer": "proecheng",
            "independent_approval_required": False,
            "decision": "VERIFIED",
        },
        "story_gate": {"status": "PASS", "blockers": []},
        "epic_production_gate": {
            "status": "BLOCKED",
            "blockers": ["Other Epic 39 Stories remain incomplete."],
        },
    }


def test_verified_single_maintainer_story_can_pass(verified_manifest):
    GOVERNANCE.validate_governance(verified_manifest)


def test_legacy_virtual_role_approvals_are_rejected(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["approvals"] = {"security": {"name": "Charlie"}}

    with pytest.raises(ValueError, match="不得包含虚拟角色审批"):
        GOVERNANCE.validate_governance(manifest)


def test_governance_decision_must_match_story_gate(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["governance"]["decision"] = "BLOCKED"

    with pytest.raises(ValueError, match="治理验证结论与 Story 门禁状态不一致"):
        GOVERNANCE.validate_governance(manifest)


def test_story_cannot_unblock_epic_production_gate(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["epic_production_gate"]["status"] = "APPROVED"

    with pytest.raises(ValueError, match="不得解除 Epic 39 总体生产门禁"):
        GOVERNANCE.validate_governance(manifest)


def test_empty_authorization_matrix_is_not_a_pass():
    result = EVIDENCE._matrix_result("empty", [])

    assert result["result"] == "FAIL"
    assert result["total"] == 0


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"tests": 2, "failures": 0, "errors": 0, "skipped": 0}, True),
        ({"tests": 2, "failures": 1, "errors": 0, "skipped": 0}, False),
        ({"tests": 2, "failures": 0, "errors": 0, "skipped": 1}, False),
        ({"tests": 0, "failures": 0, "errors": 0, "skipped": 0}, False),
    ],
)
def test_pytest_gate_requires_non_empty_zero_failure_run(metrics, expected):
    assert EVIDENCE._pytest_passed(metrics) is expected


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"expected": 2, "unexpected": 0, "skipped": 0, "flaky": 0}, True),
        ({"expected": 0, "unexpected": 0, "skipped": 4, "flaky": 0}, False),
        ({"expected": 2, "unexpected": 0, "skipped": 0, "flaky": 1}, False),
    ],
)
def test_playwright_gate_rejects_empty_skipped_or_flaky_runs(metrics, expected):
    assert EVIDENCE._playwright_passed(metrics) is expected


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"test_files": 1, "tests": 2, "passed": 2, "failed": 0, "pending": 0, "success": True}, True),
        ({"test_files": 0, "tests": 0, "passed": 0, "failed": 0, "pending": 0, "success": True}, False),
        ({"test_files": 1, "tests": 2, "passed": 1, "failed": 0, "pending": 1, "success": True}, False),
    ],
)
def test_vitest_gate_rejects_empty_or_pending_runs(metrics, expected):
    assert EVIDENCE._vitest_passed(metrics) is expected


def test_quality_command_failure_is_preserved_in_raw_results(monkeypatch, tmp_path):
    monkeypatch.setattr(
        EVIDENCE,
        "QUALITY_COMMANDS",
        (("STATIC-CHECK", ROOT, ("fake-check",)),),
    )
    monkeypatch.setattr(
        EVIDENCE,
        "_run_command_result",
        lambda *_args, **_kwargs: {"exit_code": 7, "output": "lint failed"},
    )

    results = EVIDENCE._quality_snapshots(tmp_path)

    assert results[0]["result"] == "FAIL"
    assert results[0]["exit_code"] == 7
    assert json.loads((tmp_path / "quality-command-results.json").read_text(encoding="utf-8"))["results"] == results


def test_validator_reruns_quality_commands_instead_of_trusting_recorded_pass(monkeypatch):
    recorded = [
        {
            "id": "STATIC-CHECK",
            "cwd": ".",
            "command": "fake-check",
            "exit_code": 0,
            "result": "PASS",
            "output": "recorded pass",
        }
    ]
    monkeypatch.setattr(
        EVIDENCE,
        "_run_quality_commands",
        lambda: [
            {
                **recorded[0],
                "exit_code": 7,
                "result": "FAIL",
                "output": "current failure",
            }
        ],
    )

    with pytest.raises(SystemExit, match="重新执行结果不一致"):
        EVIDENCE._validate_quality_results(recorded)


def test_image_evidence_rejects_stale_tag_and_unowned_registry_digest(monkeypatch):
    current_id = "sha256:" + "1" * 64
    digest = "registry.example/dcim-backend@sha256:" + "2" * 64
    inspected = {
        "Id": current_id,
        "RepoDigests": [],
        "Config": {
            "Labels": {
                EVIDENCE.GIT_SHA_LABEL: "a" * 40,
                EVIDENCE.SOURCE_SNAPSHOT_LABEL: "b" * 64,
            }
        },
    }
    monkeypatch.setattr(EVIDENCE, "_inspect_image", lambda _reference: inspected)

    result = EVIDENCE._image_info(
        "registry.example/dcim-backend:rc",
        expected_git_sha="c" * 40,
        expected_source_snapshot="d" * 64,
        production_registry_digest=digest,
    )

    assert result["attestation_status"] == "FAILED"
    assert result["registry_digest_status"] == "FAILED"


def test_source_binding_requires_current_head_and_complete_file_set(monkeypatch, tmp_path):
    expected = [
        {"path": "backend/app/main.py", "size_bytes": 1, "sha256": "a" * 64},
        {"path": "scripts/story_39_1_evidence.py", "size_bytes": 1, "sha256": "b" * 64},
    ]
    monkeypatch.setattr(EVIDENCE, "_current_source_files", lambda _output_dir: expected)
    monkeypatch.setattr(EVIDENCE, "_run", lambda _command: "c" * 40)
    manifest = {
        "changeset": {
            "git_sha": "c" * 40,
            "baseline_commit": EVIDENCE.BASELINE_COMMIT,
            "source_snapshot_sha256": EVIDENCE._sha256_bytes(EVIDENCE._json_bytes(expected)),
            "source_file_count": len(expected),
            "working_tree_dirty": True,
        }
    }
    incomplete_snapshot = {
        "git_sha": "c" * 40,
        "baseline_commit": EVIDENCE.BASELINE_COMMIT,
        "working_tree_dirty": True,
        "source_snapshot_sha256": "b" * 64,
        "file_count": 1,
        "files": expected[:1],
    }

    with pytest.raises(SystemExit, match="完整文件集合"):
        EVIDENCE._validate_source_binding(manifest, incomplete_snapshot, tmp_path)


def test_validator_uses_repository_schema_not_evidence_copy(monkeypatch, tmp_path):
    trusted = {"type": "object", "required": ["trusted"]}
    copied = {"type": "object"}
    schema_source = tmp_path / "trusted.schema.json"
    schema_source.write_text(json.dumps(trusted), encoding="utf-8")
    (tmp_path / "manifest.schema.json").write_text(json.dumps(copied), encoding="utf-8")
    monkeypatch.setattr(EVIDENCE, "SCHEMA_SOURCE", schema_source)

    assert EVIDENCE._load_trusted_schema(tmp_path) == trusted


def test_ci_runs_story_39_1_site_and_websocket_e2e():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "e2e/site-isolation-websocket-authorization.spec.ts" in workflow
    assert "--workers=1" in workflow


def test_backend_docker_build_uses_official_defaults_and_hash_lock():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG DEBIAN_MIRROR=" in dockerfile
    assert "ARG PIP_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert "requirements.lock" in dockerfile
    assert "--require-hashes" in dockerfile
    assert (ROOT / "backend" / "requirements.lock").is_file()


def test_test_reports_must_start_inside_manifest_execution_window(tmp_path):
    _write_bound_test_reports(tmp_path, started_at="2026-08-11T10:05:00Z")

    with pytest.raises(SystemExit, match="执行窗口"):
        EVIDENCE._validate_test_report_bindings(
            tmp_path,
            started_at="2026-08-12T10:00:00Z",
            ended_at="2026-08-12T10:10:00Z",
        )


def test_test_reports_cannot_be_replayed_by_widening_execution_window(tmp_path):
    _write_bound_test_reports(tmp_path, started_at="2026-08-11T10:05:00Z")

    with pytest.raises(SystemExit, match="执行窗口过长"):
        EVIDENCE._validate_test_report_bindings(
            tmp_path,
            started_at="2026-08-11T10:00:00Z",
            ended_at="2026-08-12T10:10:00Z",
        )


def test_test_reports_must_cover_every_required_test_file(tmp_path):
    _write_bound_test_reports(tmp_path)
    report_path = tmp_path / "vitest-websocket-results.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["testResults"].pop()
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(SystemExit, match="Vitest.*必需测试文件"):
        EVIDENCE._validate_test_report_bindings(
            tmp_path,
            started_at="2026-08-12T10:00:00Z",
            ended_at="2026-08-12T10:10:00Z",
        )


def test_http_and_websocket_matrices_are_rebuilt_from_junit(tmp_path):
    _write_bound_test_reports(tmp_path)
    _write_json = EVIDENCE._write_json
    _, cases = EVIDENCE._parse_junit(tmp_path / "pytest-authz.xml")
    expected = EVIDENCE._derive_test_matrices(cases)
    _write_json(tmp_path / "http-authz-matrix-results.json", expected["http"])
    tampered = deepcopy(expected["websocket"])
    tampered["passed"] += 1
    _write_json(tmp_path / "websocket-authz-matrix-results.json", tampered)

    with pytest.raises(SystemExit, match="WebSocket.*JUnit"):
        EVIDENCE._validate_test_derivatives(tmp_path, cases)


def test_authorization_inventory_evidence_is_rebuilt_from_runtime(monkeypatch, tmp_path):
    current = {
        "inventory": {"version": 1},
        "diff": {"generated_at_utc": "current", "validation": "PASS", "http": {"runtime_count": 2}},
        "producer_inventory": {"generated_at_utc": "current", "validation": "PASS", "count": 1},
        "openapi": {"openapi": "3.1.0", "paths": {"/current": {}}},
        "metrics": {"http": 2, "websocket": 1, "channels": 1, "producers": 1},
    }
    monkeypatch.setattr(EVIDENCE, "_collect_inventory_evidence", lambda: current)
    (tmp_path / "authorization-inventory.yaml").write_text("version: 1\n", encoding="utf-8")
    EVIDENCE._write_json(
        tmp_path / "authorization-inventory-diff.json",
        {**current["diff"], "generated_at_utc": "recorded", "http": {"runtime_count": 999}},
    )
    EVIDENCE._write_json(
        tmp_path / "websocket-producer-inventory.json",
        {**current["producer_inventory"], "generated_at_utc": "recorded"},
    )
    EVIDENCE._write_json(tmp_path / "openapi-authz-snapshot.json", current["openapi"])

    with pytest.raises(SystemExit, match="当前运行时授权清单"):
        EVIDENCE._validate_inventory_derivatives(tmp_path)


def test_manifest_metrics_must_match_recomputed_evidence():
    manifest = {"metrics": {"pytest": {"tests": 999}}}
    expected = {"pytest": {"tests": 12}}

    with pytest.raises(SystemExit, match="metrics"):
        EVIDENCE._validate_manifest_metrics(manifest, expected)


def test_manifest_test_commands_are_derived_from_required_file_sets():
    commands = [
        {"id": command_id, **definition, "result": "PASS"}
        for command_id, definition in EVIDENCE._evidence_test_commands().items()
    ]

    EVIDENCE._validate_test_commands(commands)

    commands[0]["command"] = commands[0]["command"].replace(EVIDENCE.PYTEST_TEST_FILES[-1], "")
    with pytest.raises(SystemExit, match="必需测试集合"):
        EVIDENCE._validate_test_commands(commands)


def test_environment_fingerprint_must_match_current_runtime(monkeypatch, tmp_path):
    current = {
        "generated_at_utc": "current",
        "fingerprint_sha256": "a" * 64,
        "values": {"topology": "current", "production_equivalent": False},
    }
    monkeypatch.setattr(EVIDENCE, "_collect_environment", lambda: current)
    recorded = {**current, "generated_at_utc": "recorded", "fingerprint_sha256": "b" * 64}
    EVIDENCE._write_json(tmp_path / "environment-fingerprint.json", recorded)
    manifest = {
        "environment": {
            "id": EVIDENCE.ENVIRONMENT_ID,
            "kind": EVIDENCE.ENVIRONMENT_KIND,
            "fingerprint_sha256": "b" * 64,
            "topology": "current",
            "production_equivalent": False,
        }
    }

    with pytest.raises(SystemExit, match="当前运行环境"):
        EVIDENCE._validate_environment_binding(manifest, tmp_path)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda manifest: manifest["acceptance_criteria"]["AC1"]["evidence"].append("missing.json"), "不存在"),
        (
            lambda manifest: manifest["artifacts"][0]["acceptance_criteria"].remove("AC1"),
            "双向",
        ),
        (
            lambda manifest: manifest["acceptance_criteria"]["AC1"]["evidence"].remove("evidence.json"),
            "必需证据",
        ),
    ],
)
def test_acceptance_evidence_graph_is_complete_and_bidirectional(mutate, message):
    manifest = {
        "artifacts": [
            {
                "path": "evidence.json",
                "acceptance_criteria": ["AC1"],
            }
        ],
        "acceptance_criteria": {
            "AC1": {"result": "PASS", "evidence": ["evidence.json"]},
        },
    }
    mutate(manifest)

    with pytest.raises(SystemExit, match=message):
        EVIDENCE._validate_acceptance_evidence(manifest)


def test_acceptance_evidence_graph_accepts_complete_artifact_mapping():
    artifacts = [
        {"path": name, "acceptance_criteria": acceptance_criteria}
        for name, (_, acceptance_criteria) in EVIDENCE.ARTIFACT_SPECS.items()
    ]
    manifest = {
        "artifacts": artifacts,
        "acceptance_criteria": {
            ac: {
                "result": "PASS",
                "evidence": [item["path"] for item in artifacts if ac in item["acceptance_criteria"]],
            }
            for ac in ("AC1", "AC2", "AC3", "AC4", "AC5")
        },
    }

    EVIDENCE._validate_acceptance_evidence(manifest)


def test_acceptance_evidence_graph_rejects_coordinated_mapping_tamper():
    artifacts = [
        {"path": name, "acceptance_criteria": acceptance_criteria.copy()}
        for name, (_, acceptance_criteria) in EVIDENCE.ARTIFACT_SPECS.items()
    ]
    target = next(item for item in artifacts if item["path"] == "pytest-authz.xml")
    target["acceptance_criteria"].remove("AC1")
    manifest = {
        "artifacts": artifacts,
        "acceptance_criteria": {
            ac: {
                "result": "PASS",
                "evidence": [item["path"] for item in artifacts if ac in item["acceptance_criteria"]],
            }
            for ac in ("AC1", "AC2", "AC3", "AC4", "AC5")
        },
    }

    with pytest.raises(SystemExit, match="受信任必需映射"):
        EVIDENCE._validate_acceptance_evidence(manifest)
