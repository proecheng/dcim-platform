"""Story 39.2 evidence integrity and governance tests."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import story_39_2_evidence as EVIDENCE
import story_39_2_governance as GOVERNANCE


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
            "blockers": ["Epic 39 production readiness remains incomplete."],
        },
    }


def test_verified_single_maintainer_story_can_pass(verified_manifest):
    GOVERNANCE.validate_governance(verified_manifest)


def test_virtual_role_approvals_are_rejected(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["approvals"] = {"security": {"name": "Charlie"}}

    with pytest.raises(ValueError, match="不得包含审批记录"):
        GOVERNANCE.validate_governance(manifest)


def test_story_cannot_unblock_epic_production_gate(verified_manifest):
    manifest = deepcopy(verified_manifest)
    manifest["epic_production_gate"]["status"] = "PASS"

    with pytest.raises(ValueError, match="不得解除 Epic 39"):
        GOVERNANCE.validate_governance(manifest)


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"tests": 4, "failures": 0, "errors": 0, "skipped": 0}, True),
        ({"tests": 0, "failures": 0, "errors": 0, "skipped": 0}, False),
        ({"tests": 4, "failures": 0, "errors": 0, "skipped": 1}, False),
        ({"tests": 4, "failures": 1, "errors": 0, "skipped": 0}, False),
    ],
)
def test_pytest_gate_rejects_empty_failed_or_skipped_runs(metrics, expected):
    assert EVIDENCE.pytest_passed(metrics) is expected


@pytest.mark.parametrize(
    ("metrics", "expected"),
    [
        ({"tests": 4, "passed": 4, "failed": 0, "pending": 0, "success": True}, True),
        ({"tests": 0, "passed": 0, "failed": 0, "pending": 0, "success": True}, False),
        ({"tests": 4, "passed": 3, "failed": 0, "pending": 1, "success": True}, False),
    ],
)
def test_vitest_gate_rejects_empty_or_pending_runs(metrics, expected):
    assert EVIDENCE.vitest_passed(metrics) is expected


def test_validator_uses_repository_schema_not_evidence_copy(monkeypatch, tmp_path):
    trusted = {"type": "object", "required": ["trusted"]}
    copied = {"type": "object"}
    schema_source = tmp_path / "trusted.schema.json"
    schema_source.write_text(json.dumps(trusted), encoding="utf-8")
    (tmp_path / "manifest.schema.json").write_text(json.dumps(copied), encoding="utf-8")
    monkeypatch.setattr(EVIDENCE, "SCHEMA_SOURCE", schema_source)

    assert EVIDENCE.load_trusted_schema() == trusted


def test_artifact_gate_rejects_schema_copy_that_differs_from_trusted_source(monkeypatch, tmp_path):
    trusted_schema = tmp_path / "trusted.schema.json"
    trusted_schema.write_text('{"type":"object"}', encoding="utf-8")
    (tmp_path / "manifest.schema.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(EVIDENCE, "SCHEMA_SOURCE", trusted_schema)
    artifacts = []
    for name in EVIDENCE.ARTIFACT_SPECS:
        path = tmp_path / name
        if not path.exists():
            path.write_text("evidence", encoding="utf-8")
        artifacts.append(
            {
                "path": f"{tmp_path.as_posix()}/{name}",
                "size_bytes": path.stat().st_size,
                "sha256": EVIDENCE.sha256_file(path),
            }
        )

    monkeypatch.setattr(EVIDENCE, "ROOT", tmp_path.parent)
    with pytest.raises(SystemExit, match="受信任仓库契约"):
        EVIDENCE.validate_artifacts({"artifacts": artifacts}, tmp_path)


def test_artifact_path_must_stay_inside_story_directory(tmp_path):
    output_dir = tmp_path / "39.2"
    output_dir.mkdir()

    with pytest.raises(SystemExit, match="非法证据路径"):
        EVIDENCE.resolve_artifact_path(output_dir, "../39.1/manifest.yaml")


def test_registry_snapshot_is_rebuilt_from_runtime(monkeypatch, tmp_path):
    current = {"registry": {"power_off": {"minimum_risk": "critical"}}, "validation": "PASS"}
    recorded = {"registry": {"power_off": {"minimum_risk": "normal"}}, "validation": "PASS"}
    (tmp_path / "command-registry-snapshot.json").write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(EVIDENCE, "collect_command_registry", lambda: current)

    with pytest.raises(SystemExit, match="命令注册表快照"):
        EVIDENCE.validate_registry_snapshot(tmp_path)


def test_registry_collection_does_not_require_application_settings():
    env = os.environ.copy()
    env.pop("FAULT_TREE_HMAC_KEY", None)
    command = (
        "import sys; "
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
        "import story_39_2_evidence as evidence; "
        "assert evidence.collect_command_registry()['validation'] == 'PASS'"
    )

    result = subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_evidence_commands_decode_output_as_utf8(monkeypatch):
    def fake_run(*args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        return SimpleNamespace(returncode=0, stdout="代理测试通过")

    monkeypatch.setattr(EVIDENCE.subprocess, "run", fake_run)

    assert EVIDENCE.run_result(["test-command"])["output"] == "代理测试通过"


@pytest.mark.parametrize(
    "output",
    [
        "# tests 5\n# pass 5\n# fail 0",
        "ℹ tests 5\nℹ pass 5\nℹ fail 0",
    ],
)
def test_node_test_metrics_support_current_and_tap_reporters(output):
    assert EVIDENCE.node_test_metrics(output, exit_code=0) == {
        "tests": 5,
        "passed": 5,
        "failed": 0,
    }


def test_manifest_command_drops_runtime_only_fields():
    record = {
        "id": "NGINX-BROWSER",
        "cwd": ".",
        "command": "npx playwright test",
        "result": "PASS",
        "output": "1 passed",
        "exit_code": 0,
    }

    assert EVIDENCE.manifest_command(record) == {
        "id": "NGINX-BROWSER",
        "cwd": ".",
        "command": "npx playwright test",
        "result": "PASS",
    }


def test_source_binding_requires_complete_current_file_set(monkeypatch, tmp_path):
    expected = [
        {"path": "backend/app/main.py", "size_bytes": 10, "sha256": "a" * 64},
        {"path": "scripts/story_39_2_evidence.py", "size_bytes": 20, "sha256": "b" * 64},
    ]
    recorded = {
        "git_sha": "c" * 40,
        "baseline_commit": EVIDENCE.BASELINE_COMMIT,
        "working_tree_dirty": True,
        "source_snapshot_sha256": EVIDENCE.sha256_json(expected[:1]),
        "file_count": 1,
        "files": expected[:1],
    }
    (tmp_path / "source-file-hashes.json").write_text(json.dumps(recorded), encoding="utf-8")
    monkeypatch.setattr(EVIDENCE, "current_source_files", lambda _output_dir: expected)
    monkeypatch.setattr(EVIDENCE, "git_head", lambda: "c" * 40)

    with pytest.raises(SystemExit, match="完整文件集合"):
        EVIDENCE.validate_source_binding(tmp_path)


def test_manifest_changeset_must_match_recomputed_source_snapshot():
    snapshot = {
        "git_sha": "c" * 40,
        "baseline_commit": EVIDENCE.BASELINE_COMMIT,
        "working_tree_dirty": True,
        "source_snapshot_sha256": "d" * 64,
        "file_count": 3,
    }
    changeset = {
        "git_sha": snapshot["git_sha"],
        "baseline_commit": snapshot["baseline_commit"],
        "working_tree_dirty": snapshot["working_tree_dirty"],
        "changeset_id": f"{snapshot['git_sha']}+{snapshot['source_snapshot_sha256']}",
        "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
        "source_file_count": snapshot["file_count"],
    }

    EVIDENCE.validate_changeset_binding({"changeset": changeset}, snapshot)

    changeset["source_file_count"] = 2
    with pytest.raises(SystemExit, match="changeset"):
        EVIDENCE.validate_changeset_binding({"changeset": changeset}, snapshot)


def test_security_header_gate_rejects_weak_default_policy():
    headers = {
        "content-security-policy": (
            "default-src 'self'; script-src 'self'; connect-src 'self' ws: wss:; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        ),
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "camera=()",
    }
    assert EVIDENCE.security_headers_pass(headers)

    headers["content-security-policy"] = headers["content-security-policy"].replace(
        "default-src 'self'", "default-src *"
    )
    assert not EVIDENCE.security_headers_pass(headers)


def test_artifact_gate_rejects_duplicate_manifest_entries(tmp_path):
    artifacts = [{"path": f"_bmad-output/test-artifacts/epic-39/39.2/{name}"} for name in EVIDENCE.ARTIFACT_SPECS]
    artifacts.append(deepcopy(artifacts[0]))

    with pytest.raises(SystemExit, match="文件集合不完整"):
        EVIDENCE.validate_artifacts({"artifacts": artifacts}, tmp_path)


def test_acceptance_evidence_mapping_is_trusted_and_bidirectional():
    artifacts = [
        {"path": name, "purpose": purpose, "acceptance_criteria": criteria.copy()}
        for name, (purpose, criteria) in EVIDENCE.ARTIFACT_SPECS.items()
    ]
    acceptance = {
        ac: {
            "result": "PASS",
            "evidence": [item["path"] for item in artifacts if ac in item["acceptance_criteria"]],
        }
        for ac in EVIDENCE.ACCEPTANCE_CRITERIA
    }

    EVIDENCE.validate_acceptance_mapping({"artifacts": artifacts, "acceptance_criteria": acceptance})

    artifacts[0]["acceptance_criteria"].clear()
    with pytest.raises(SystemExit, match="受信任证据映射"):
        EVIDENCE.validate_acceptance_mapping({"artifacts": artifacts, "acceptance_criteria": acceptance})


def test_manifest_command_set_cannot_omit_required_gate():
    commands = [
        {"id": command_id, "result": "PASS", "command": command_id} for command_id in EVIDENCE.REQUIRED_COMMAND_IDS
    ]
    for item in commands:
        if item["id"] == "PYTEST-SECURITY":
            item["command"] = " ".join(EVIDENCE.PYTEST_TEST_FILES)
        elif item["id"] == "VITEST-XSS":
            item["command"] = " ".join(EVIDENCE.VITEST_TEST_FILES)

    EVIDENCE.validate_execution_commands({"execution": {"commands": commands}})

    commands.pop()
    with pytest.raises(SystemExit, match="执行命令集合"):
        EVIDENCE.validate_execution_commands({"execution": {"commands": commands}})
