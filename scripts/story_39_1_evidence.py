"""生成并验证 Story 39.1 的机器可读证据包。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from story_39_1_governance import validate_governance


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.1"
SCHEMA_SOURCE = Path(__file__).with_name("story_39_1_manifest.schema.json")
BASELINE_COMMIT = "a9b872155f8554136f456e6d15116e721270761c"
REGISTRY_DIGEST_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
GIT_SHA_LABEL = "org.opencontainers.image.revision"
SOURCE_SNAPSHOT_LABEL = "io.dcim.story-39-1.source-snapshot-sha256"
ENVIRONMENT_ID = "local-windows-docker-desktop-story-39-1"
ENVIRONMENT_KIND = "local integration evidence"
MAX_EVIDENCE_EXECUTION_WINDOW = timedelta(hours=12)
PYTEST_TEST_FILES = (
    "tests/test_authorization_inventory.py",
    "tests/test_story_39_1.py",
    "tests/test_story_39_1_evidence_governance.py",
    "tests/test_websocket_authorization.py",
    "tests/test_auth_session.py",
    "tests/test_site_isolation.py",
    "tests/test_site_management.py",
    "tests/test_device_detail.py",
    "tests/test_point_data.py",
    "tests/test_alarm_api.py",
    "tests/test_story_24_6.py",
    "tests/test_story_24_7.py",
    "tests/test_fault_impact.py",
    "tests/test_gateway_monitor.py",
)
PLAYWRIGHT_TEST_FILES = (
    "e2e/authorization-matrix.spec.ts",
    "e2e/site-isolation-websocket-authorization.spec.ts",
)
VITEST_TEST_FILES = (
    "src/__tests__/api/websocket-auth.test.ts",
    "src/__tests__/story-27-6-site-filter.test.ts",
    "src/__tests__/composables/useWebSocket.test.ts",
)
ARTIFACT_SPECS = {
    "authorization-inventory.yaml": ("Reviewed authorization policy inventory", ["AC1", "AC2", "AC3"]),
    "authorization-inventory-diff.json": ("Runtime-to-policy drift comparison", ["AC1"]),
    "openapi-authz-snapshot.json": ("Mounted HTTP API snapshot", ["AC1", "AC2"]),
    "websocket-producer-inventory.json": ("Discovered producer scope inventory", ["AC1", "AC3"]),
    "http-authz-matrix-results.json": ("HTTP site and object authorization matrix", ["AC2", "AC5"]),
    "websocket-authz-matrix-results.json": ("WebSocket authorization and revocation matrix", ["AC3", "AC4", "AC5"]),
    "pytest-authz.xml": ("Raw backend authorization regression results", ["AC1", "AC2", "AC3", "AC4", "AC5"]),
    "playwright-authz-results.json": ("Raw live role and double-site browser matrix", ["AC2", "AC3", "AC4", "AC5"]),
    "vitest-websocket-results.json": ("Raw frontend authentication and site-subscription tests", ["AC3", "AC4"]),
    "environment-fingerprint.json": ("Sanitized execution environment fingerprint", ["AC5"]),
    "source-file-hashes.json": ("Story implementation source snapshot", ["AC5"]),
    "quality-command-results.json": ("Raw static quality command results", ["AC5"]),
    "manifest.schema.json": ("Evidence manifest JSON Schema", ["AC5"]),
}
QUALITY_COMMANDS = (
    ("FRONTEND-TYPECHECK", ROOT / "frontend", ("npm", "run", "typecheck")),
    (
        "FRONTEND-ESLINT",
        ROOT / "frontend",
        (
            "npx",
            "eslint",
            "src/api/websocket.ts",
            "src/composables/useWebSocket.ts",
            "src/composables/useWebSocketManager.ts",
            "src/__tests__/api/websocket-auth.test.ts",
            "--max-warnings=0",
        ),
    ),
    (
        "BACKEND-RUFF",
        BACKEND_ROOT,
        (
            "ruff",
            "check",
            "app",
            "tests/test_authorization_inventory.py",
            "tests/test_story_39_1.py",
            "tests/test_story_39_1_evidence_governance.py",
            "tests/test_websocket_authorization.py",
            "tests/test_fault_impact.py",
            "tests/test_gateway_monitor.py",
        ),
    ),
)
REQUIRED_ARTIFACT_NAMES = set(ARTIFACT_SPECS)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(command: list[str], *, cwd: Path = ROOT) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()


def _resolved_command(command: tuple[str, ...] | list[str]) -> list[str]:
    executable = shutil.which(command[0]) or command[0]
    resolved = [executable, *command[1:]]
    if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *resolved]
    return resolved


def _run_command_result(command: tuple[str, ...] | list[str], *, cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            _resolved_command(command),
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        return {"exit_code": 127, "output": f"{type(exc).__name__}: {exc}"}
    return {"exit_code": completed.returncode, "output": completed.stdout.strip()}


def _version(command: list[str]) -> str:
    try:
        return _run(_resolved_command(command)).splitlines()[0]
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"unavailable: {type(exc).__name__}"


def _split_null_output(command: list[str]) -> list[str]:
    output = subprocess.check_output(command, cwd=ROOT)
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def _is_story_source(path: str) -> bool:
    if path.startswith("backend/"):
        return path != "backend/coverage.xml" and not path.startswith(("backend/reports/", "backend/.pytest_cache/"))
    return path in {
        ".github/workflows/ci.yml",
        "frontend/src/api/websocket.ts",
        "frontend/src/composables/useWebSocket.ts",
        "frontend/src/composables/useWebSocketManager.ts",
        "frontend/src/__tests__/api/websocket-auth.test.ts",
        "frontend/vite.config.ts",
        "frontend/Dockerfile",
        "e2e/auth.setup.ts",
        "e2e/site-isolation-websocket-authorization.spec.ts",
        "playwright.config.ts",
        "scripts/story_39_1_evidence.py",
        "scripts/story_39_1_governance.py",
        "scripts/story_39_1_manifest.schema.json",
        "backend/tests/test_story_39_1_evidence_governance.py",
        "_bmad-output/implementation-artifacts/39-1-site-isolation-and-websocket-authorization.md",
    }


def _story_source_state(output_dir: Path) -> tuple[str, bool, list[dict[str, Any]]]:
    committed = set(_split_null_output(["git", "diff", "--name-only", "-z", BASELINE_COMMIT, "HEAD"]))
    dirty = set(_split_null_output(["git", "diff", "--name-only", "-z", "HEAD"]))
    dirty.update(_split_null_output(["git", "ls-files", "--others", "--exclude-standard", "-z"]))
    story_dirty = {path for path in dirty if _is_story_source(path)}
    changed = committed | dirty
    files = []
    for relative in sorted(path for path in changed if _is_story_source(path)):
        path = ROOT / relative
        if not path.is_file() or output_dir in path.parents:
            continue
        files.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    return _run(["git", "rev-parse", "HEAD"]), bool(story_dirty), files


def _current_source_files(output_dir: Path) -> list[dict[str, Any]]:
    return _story_source_state(output_dir)[2]


def _source_snapshot(output_dir: Path) -> dict[str, Any]:
    git_sha, working_tree_dirty, files = _story_source_state(output_dir)
    snapshot_hash = _sha256_bytes(_json_bytes(files))
    result = {
        "generated_at_utc": _utc_now(),
        "scope": "Story 39.1 implementation and test files changed since the baseline commit",
        "git_sha": git_sha,
        "baseline_commit": BASELINE_COMMIT,
        "working_tree_dirty": working_tree_dirty,
        "source_snapshot_sha256": snapshot_hash,
        "file_count": len(files),
        "files": files,
    }
    _write_json(output_dir / "source-file-hashes.json", result)
    return result


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(key for key, count in counts.items() if count > 1)


def _collect_inventory_evidence() -> dict[str, Any]:
    from app.core.authorization import (
        CHANNELS,
        FRONTEND_CHANNELS,
        discover_broadcast_producers,
        load_authorization_inventory,
        runtime_http_routes,
        runtime_websocket_routes,
        validate_authorization_inventory,
    )
    from app.main import app

    inventory = load_authorization_inventory()
    validation = validate_authorization_inventory(app, inventory=inventory)
    runtime_http = runtime_http_routes(app)
    runtime_ws = runtime_websocket_routes(app)
    discovered = discover_broadcast_producers()
    websocket = inventory["websocket"]
    policy_http_keys = [item["key"] for item in inventory["http"]]
    policy_ws_keys = [item["key"] for item in websocket["endpoints"]]
    policy_channels = [item["name"] for item in websocket["channels"]]
    policy_producer_keys = [item["key"] for item in websocket["producers"]]
    discovered_keys = [item["key"] for item in discovered]

    diff = {
        "generated_at_utc": _utc_now(),
        "validation": "PASS",
        "http": {
            "runtime_count": len(runtime_http),
            "policy_count": len(policy_http_keys),
            "missing": sorted(set(runtime_http) - set(policy_http_keys)),
            "stale": sorted(set(policy_http_keys) - set(runtime_http)),
            "duplicates": _duplicates(policy_http_keys),
            "runtime_keys": sorted(runtime_http),
            "policy_keys": sorted(policy_http_keys),
        },
        "websocket_endpoints": {
            "runtime_count": len(runtime_ws),
            "policy_count": len(policy_ws_keys),
            "missing": sorted(set(runtime_ws) - set(policy_ws_keys)),
            "stale": sorted(set(policy_ws_keys) - set(runtime_ws)),
            "duplicates": _duplicates(policy_ws_keys),
            "runtime_keys": sorted(runtime_ws),
            "policy_keys": sorted(policy_ws_keys),
        },
        "websocket_channels": {
            "runtime_count": len(CHANNELS),
            "policy_count": len(policy_channels),
            "missing": sorted(set(CHANNELS) - set(policy_channels)),
            "stale": sorted(set(policy_channels) - set(CHANNELS)),
            "duplicates": _duplicates(policy_channels),
            "frontend_declared": sorted(websocket["frontend_channels"]),
            "frontend_expected": sorted(FRONTEND_CHANNELS),
        },
        "broadcast_producers": {
            "runtime_count": len(discovered_keys),
            "policy_count": len(policy_producer_keys),
            "missing": sorted(set(discovered_keys) - set(policy_producer_keys)),
            "stale": sorted(set(policy_producer_keys) - set(discovered_keys)),
            "duplicates": _duplicates(policy_producer_keys),
        },
    }
    policies = {item["key"]: item for item in websocket["producers"]}
    producer_inventory = {
        "generated_at_utc": _utc_now(),
        "validation": "PASS",
        "count": len(discovered),
        "producers": [{"discovered": item, "policy": policies[item["key"]]} for item in discovered],
    }
    return {
        "inventory": inventory,
        "diff": diff,
        "producer_inventory": producer_inventory,
        "openapi": app.openapi(),
        "metrics": {
            "http": validation.http_count,
            "websocket": validation.websocket_count,
            "channels": validation.channel_count,
            "producers": validation.producer_count,
        },
    }


def _inventory_snapshots(output_dir: Path) -> dict[str, int]:
    evidence = _collect_inventory_evidence()
    (output_dir / "authorization-inventory.yaml").write_text(
        yaml.safe_dump(evidence["inventory"], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    _write_json(output_dir / "authorization-inventory-diff.json", evidence["diff"])
    _write_json(output_dir / "websocket-producer-inventory.json", evidence["producer_inventory"])
    _write_json(output_dir / "openapi-authz-snapshot.json", evidence["openapi"])
    return evidence["metrics"]


def _parse_junit(path: Path) -> tuple[dict[str, int], list[dict[str, Any]]]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    cases: list[dict[str, Any]] = []
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
        for case in suite.findall("testcase"):
            status = "PASS"
            if case.find("failure") is not None:
                status = "FAIL"
            elif case.find("error") is not None:
                status = "ERROR"
            elif case.find("skipped") is not None:
                status = "SKIPPED"
            cases.append(
                {
                    "classname": case.attrib.get("classname", ""),
                    "name": case.attrib.get("name", ""),
                    "duration_seconds": float(case.attrib.get("time", 0)),
                    "status": status,
                }
            )
    return totals, cases


def _matrix_result(kind: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [case for case in cases if case["status"] != "PASS"]
    passed = bool(cases) and not failures
    return {
        "generated_at_utc": _utc_now(),
        "matrix": kind,
        "result": "PASS" if passed else "FAIL",
        "total": len(cases),
        "passed": len(cases) - len(failures),
        "failed_or_skipped": len(failures),
        "cases": cases,
    }


def _derive_test_matrices(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    http_cases = [
        case for case in cases if case["classname"].endswith(("test_story_39_1", "test_authorization_inventory"))
    ]
    websocket_cases = [case for case in cases if case["classname"].endswith("test_websocket_authorization")]
    return {
        "http": _matrix_result("HTTP authorization and inventory", http_cases),
        "websocket": _matrix_result("WebSocket authorization and revocation", websocket_cases),
    }


def _test_snapshots(output_dir: Path) -> dict[str, Any]:
    totals, cases = _parse_junit(output_dir / "pytest-authz.xml")
    matrices = _derive_test_matrices(cases)
    http_result = matrices["http"]
    websocket_result = matrices["websocket"]
    _write_json(output_dir / "http-authz-matrix-results.json", http_result)
    _write_json(output_dir / "websocket-authz-matrix-results.json", websocket_result)
    return {"pytest": totals, "http": http_result, "websocket": websocket_result}


def _collect_environment() -> dict[str, Any]:
    from app.core.config import get_settings

    settings = get_settings()
    public_config = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "database_driver": settings.database_url.split(":", 1)[0],
        "debug": settings.debug,
        "redis_enabled": settings.redis_enabled,
        "mqtt_enabled": settings.mqtt_enabled,
        "simulation_enabled": settings.simulation_enabled,
        "backend_url": "http://127.0.0.1:8080",
        "frontend_url": "http://127.0.0.1:3000",
        "topology": "single local Uvicorn process plus Vite proxy",
        "production_equivalent": False,
    }
    fingerprint = _sha256_bytes(_json_bytes(public_config))
    return {"generated_at_utc": _utc_now(), "fingerprint_sha256": fingerprint, "values": public_config}


def _environment_snapshot(output_dir: Path) -> dict[str, Any]:
    result = _collect_environment()
    _write_json(output_dir / "environment-fingerprint.json", result)
    return result


def _validated_registry_digest(value: str | None) -> str | None:
    if value is None:
        return None
    if not REGISTRY_DIGEST_PATTERN.fullmatch(value):
        raise SystemExit(f"生产仓库摘要格式无效: {value}")
    return value


def _inspect_image(reference: str) -> dict[str, Any] | None:
    try:
        inspected = json.loads(_run(["docker", "image", "inspect", reference]))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    return inspected[0] if inspected else None


def _image_repository(reference: str) -> str:
    without_digest = reference.split("@", 1)[0]
    last_slash = without_digest.rfind("/")
    last_colon = without_digest.rfind(":")
    return without_digest[:last_colon] if last_colon > last_slash else without_digest


def _image_info(
    tag: str,
    *,
    expected_git_sha: str,
    expected_source_snapshot: str,
    production_registry_digest: str | None = None,
) -> dict[str, Any]:
    production_registry_digest = _validated_registry_digest(production_registry_digest)
    item = _inspect_image(tag)
    if item is None:
        return {
            "tag": tag,
            "status": "FAILED",
            "digest": None,
            "repo_digests": [],
            "production_registry_digest": production_registry_digest,
            "git_sha_label": None,
            "source_snapshot_label": None,
            "attestation_status": "FAILED",
            "registry_digest_status": "FAILED" if production_registry_digest else "NOT_PROVIDED",
        }
    labels = (item.get("Config") or {}).get("Labels") or {}
    repo_digests = item.get("RepoDigests") or []
    attestation_status = (
        "PASS"
        if labels.get(GIT_SHA_LABEL) == expected_git_sha
        and labels.get(SOURCE_SNAPSHOT_LABEL) == expected_source_snapshot
        else "FAILED"
    )
    registry_digest_status = "NOT_PROVIDED"
    if production_registry_digest:
        digest_item = _inspect_image(production_registry_digest)
        registry_digest_status = (
            "PASS"
            if production_registry_digest in repo_digests
            and _image_repository(production_registry_digest) == _image_repository(tag)
            and digest_item is not None
            and digest_item.get("Id") == item.get("Id")
            else "FAILED"
        )
    return {
        "tag": tag,
        "status": "BUILT",
        "digest": item["Id"],
        "repo_digests": repo_digests,
        "production_registry_digest": production_registry_digest,
        "git_sha_label": labels.get(GIT_SHA_LABEL),
        "source_snapshot_label": labels.get(SOURCE_SNAPSHOT_LABEL),
        "attestation_status": attestation_status,
        "registry_digest_status": registry_digest_status,
    }


def _artifact(path: Path, purpose: str, acceptance_criteria: list[str]) -> dict[str, Any]:
    media_types = {".json": "application/json", ".yaml": "application/yaml", ".xml": "application/xml"}
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256_file(path),
        "size_bytes": path.stat().st_size,
        "media_type": media_types[path.suffix],
        "purpose": purpose,
        "acceptance_criteria": acceptance_criteria,
    }


def _playwright_metrics(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    stats = report.get("stats", {})
    return {
        "expected": int(stats.get("expected", 0)),
        "unexpected": int(stats.get("unexpected", 0)),
        "skipped": int(stats.get("skipped", 0)),
        "flaky": int(stats.get("flaky", 0)),
        "duration_ms": float(stats.get("duration", 0)),
    }


def _vitest_metrics(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "test_files": int(report.get("numTotalTestSuites", 0)),
        "tests": int(report.get("numTotalTests", 0)),
        "passed": int(report.get("numPassedTests", 0)),
        "failed": int(report.get("numFailedTests", 0)),
        "pending": int(report.get("numPendingTests", 0)),
        "success": bool(report.get("success", False)),
    }


def _parse_report_datetime(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, (int, float)):
            parsed = datetime.fromtimestamp(value / 1000, timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            raise TypeError
    except (TypeError, ValueError, OSError) as exc:
        raise SystemExit(f"{label} 缺少有效 UTC 时间") from exc
    if parsed.tzinfo is None:
        raise SystemExit(f"{label} 时间必须包含时区")
    return parsed.astimezone(timezone.utc)


def _require_report_window(report_time: datetime, *, label: str, started_at: datetime, ended_at: datetime) -> None:
    if report_time < started_at or report_time > ended_at:
        raise SystemExit(f"{label} 开始时间不在 manifest 执行窗口内")


def _junit_modules(path: Path) -> tuple[list[datetime], set[str]]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    timestamps = [_parse_report_datetime(suite.attrib.get("timestamp"), "JUnit 报告") for suite in suites]
    modules = {case.attrib.get("classname", "") for suite in suites for case in suite.findall("testcase")}
    return timestamps, modules


def _missing_junit_files(classnames: set[str]) -> list[str]:
    missing = []
    for test_file in PYTEST_TEST_FILES:
        module = test_file.removesuffix(".py").replace("/", ".")
        if not any(classname == module or classname.startswith(f"{module}.") for classname in classnames):
            missing.append(test_file)
    return missing


def _playwright_files_with_tests(report: dict[str, Any]) -> set[str]:
    files = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("file") and isinstance(value.get("tests"), list) and value["tests"]:
                files.add(Path(value["file"].replace("\\", "/")).name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(report.get("suites", []))
    return files


def _validate_test_report_bindings(output_dir: Path, *, started_at: str, ended_at: str) -> None:
    window_start = _parse_report_datetime(started_at, "manifest execution.started_at_utc")
    window_end = _parse_report_datetime(ended_at, "manifest execution.ended_at_utc")
    if window_end < window_start:
        raise SystemExit("manifest 执行窗口结束时间早于开始时间")
    if window_end - window_start > MAX_EVIDENCE_EXECUTION_WINDOW:
        raise SystemExit("manifest 执行窗口过长，不能用于包容旧测试报告")

    junit_times, junit_modules = _junit_modules(output_dir / "pytest-authz.xml")
    for report_time in junit_times:
        _require_report_window(report_time, label="JUnit 报告", started_at=window_start, ended_at=window_end)
    if missing := _missing_junit_files(junit_modules):
        raise SystemExit(f"JUnit 报告缺少必需测试文件: {missing}")

    playwright_report = json.loads((output_dir / "playwright-authz-results.json").read_text(encoding="utf-8"))
    playwright_time = _parse_report_datetime(playwright_report.get("stats", {}).get("startTime"), "Playwright 报告")
    _require_report_window(playwright_time, label="Playwright 报告", started_at=window_start, ended_at=window_end)
    playwright_files = _playwright_files_with_tests(playwright_report)
    required_playwright = {Path(path).name for path in PLAYWRIGHT_TEST_FILES}
    if missing := sorted(required_playwright - playwright_files):
        raise SystemExit(f"Playwright 报告缺少必需测试文件: {missing}")

    vitest_report = json.loads((output_dir / "vitest-websocket-results.json").read_text(encoding="utf-8"))
    vitest_time = _parse_report_datetime(vitest_report.get("startTime"), "Vitest 报告")
    _require_report_window(vitest_time, label="Vitest 报告", started_at=window_start, ended_at=window_end)
    vitest_files = {
        str(item.get("name", "")).replace("\\", "/")
        for item in vitest_report.get("testResults", [])
        if item.get("assertionResults")
    }
    missing_vitest = [path for path in VITEST_TEST_FILES if not any(item.endswith(path) for item in vitest_files)]
    if missing_vitest:
        raise SystemExit(f"Vitest 报告缺少必需测试文件: {missing_vitest}")


def _without_generated_at(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "generated_at_utc"}


def _validate_test_derivatives(output_dir: Path, cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    expected = _derive_test_matrices(cases)
    for key, filename, label in (
        ("http", "http-authz-matrix-results.json", "HTTP 授权矩阵"),
        ("websocket", "websocket-authz-matrix-results.json", "WebSocket 授权矩阵"),
    ):
        recorded = json.loads((output_dir / filename).read_text(encoding="utf-8"))
        if _without_generated_at(recorded) != _without_generated_at(expected[key]):
            raise SystemExit(f"{label}与原始 JUnit cases 重新生成结果不一致")
    return expected


def _validate_inventory_derivatives(output_dir: Path) -> dict[str, Any]:
    current = _collect_inventory_evidence()
    recorded_inventory = yaml.safe_load((output_dir / "authorization-inventory.yaml").read_text(encoding="utf-8"))
    comparisons = (
        (recorded_inventory, current["inventory"]),
        (
            _without_generated_at(
                json.loads((output_dir / "authorization-inventory-diff.json").read_text(encoding="utf-8"))
            ),
            _without_generated_at(current["diff"]),
        ),
        (
            _without_generated_at(
                json.loads((output_dir / "websocket-producer-inventory.json").read_text(encoding="utf-8"))
            ),
            _without_generated_at(current["producer_inventory"]),
        ),
        (json.loads((output_dir / "openapi-authz-snapshot.json").read_text(encoding="utf-8")), current["openapi"]),
    )
    if any(recorded != expected for recorded, expected in comparisons):
        raise SystemExit("证据包与当前运行时授权清单重新生成结果不一致")
    return current


def _manifest_metrics(
    inventory: dict[str, int],
    pytest_metrics: dict[str, int],
    matrices: dict[str, dict[str, Any]],
    playwright: dict[str, Any],
    vitest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "inventory": inventory,
        "pytest": pytest_metrics,
        "http_matrix": {"total": matrices["http"]["total"], "passed": matrices["http"]["passed"]},
        "websocket_matrix": {
            "total": matrices["websocket"]["total"],
            "passed": matrices["websocket"]["passed"],
        },
        "playwright": playwright,
        "vitest": vitest,
    }


def _validate_manifest_metrics(manifest: dict[str, Any], expected: dict[str, Any]) -> None:
    if manifest.get("metrics") != expected:
        raise SystemExit("manifest.metrics 与原始报告和当前运行时重算结果不一致")


def _validate_environment_binding(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    recorded = json.loads((output_dir / "environment-fingerprint.json").read_text(encoding="utf-8"))
    current = _collect_environment()
    if _without_generated_at(recorded) != _without_generated_at(current):
        raise SystemExit("环境指纹与当前运行环境不一致")
    expected_manifest = {
        "id": ENVIRONMENT_ID,
        "kind": ENVIRONMENT_KIND,
        "fingerprint_sha256": current["fingerprint_sha256"],
        "topology": current["values"]["topology"],
        "production_equivalent": current["values"]["production_equivalent"],
    }
    actual_manifest = {key: manifest["environment"].get(key) for key in expected_manifest}
    if actual_manifest != expected_manifest:
        raise SystemExit("manifest 环境声明与当前运行环境不一致")
    return current


def _validate_acceptance_evidence(manifest: dict[str, Any]) -> None:
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    acceptance_criteria = manifest["acceptance_criteria"]
    for ac, result in acceptance_criteria.items():
        for reference in result["evidence"]:
            artifact = artifacts.get(reference)
            if artifact is None:
                raise SystemExit(f"{ac} 引用的证据不存在于 manifest.artifacts: {reference}")
            if ac not in artifact["acceptance_criteria"]:
                raise SystemExit(f"{ac} 与产物 {reference} 的 acceptance_criteria 不是双向引用")
    for path, artifact in artifacts.items():
        for ac in artifact["acceptance_criteria"]:
            if path not in acceptance_criteria[ac]["evidence"]:
                raise SystemExit(f"{ac} 未引用声明支持该标准的必需证据: {path}")
        name = Path(path).name
        expected_spec = ARTIFACT_SPECS.get(name)
        if expected_spec is None:
            raise SystemExit(f"产物 {path} 不属于仓库受信任必需映射")
        expected_criteria = expected_spec[1]
        if artifact["acceptance_criteria"] != expected_criteria:
            raise SystemExit(f"产物 {path} 的 AC 声明与仓库受信任必需映射不一致")


def _pytest_passed(metrics: dict[str, Any]) -> bool:
    return metrics["tests"] > 0 and metrics["failures"] == 0 and metrics["errors"] == 0 and metrics["skipped"] == 0


def _matrix_passed(metrics: dict[str, Any]) -> bool:
    return metrics["result"] == "PASS" and metrics["total"] > 0 and metrics["passed"] == metrics["total"]


def _playwright_passed(metrics: dict[str, Any]) -> bool:
    return metrics["expected"] > 0 and metrics["unexpected"] == 0 and metrics["skipped"] == 0 and metrics["flaky"] == 0


def _vitest_passed(metrics: dict[str, Any]) -> bool:
    return (
        metrics["success"]
        and metrics["test_files"] > 0
        and metrics["tests"] > 0
        and metrics["passed"] == metrics["tests"]
        and metrics["failed"] == 0
        and metrics["pending"] == 0
    )


def _command_text(command: tuple[str, ...] | list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def _evidence_test_commands() -> dict[str, dict[str, str]]:
    return {
        "PYTEST-AUTHZ": {
            "cwd": "backend",
            "command": (
                f"pytest -q {' '.join(PYTEST_TEST_FILES)} "
                "--junitxml=../_bmad-output/test-artifacts/epic-39/39.1/pytest-authz.xml"
            ),
        },
        "PLAYWRIGHT-AUTHZ": {
            "cwd": ".",
            "command": (
                "CI=1 PLAYWRIGHT_JSON_OUTPUT_FILE="
                "_bmad-output/test-artifacts/epic-39/39.1/playwright-authz-results.json "
                f"npx playwright test {' '.join(PLAYWRIGHT_TEST_FILES)} "
                "--project=chromium --workers=1 --reporter=json"
            ),
        },
        "VITEST-WS": {
            "cwd": "frontend",
            "command": (
                f"npx vitest --run {' '.join(VITEST_TEST_FILES)} --reporter=json "
                "--outputFile=../_bmad-output/test-artifacts/epic-39/39.1/vitest-websocket-results.json"
            ),
        },
    }


def _run_quality_commands() -> list[dict[str, Any]]:
    results = []
    for command_id, cwd, command in QUALITY_COMMANDS:
        raw = _run_command_result(command, cwd=cwd)
        results.append(
            {
                "id": command_id,
                "cwd": cwd.relative_to(ROOT).as_posix() or ".",
                "command": _command_text(command),
                "exit_code": raw["exit_code"],
                "result": "PASS" if raw["exit_code"] == 0 else "FAIL",
                "output": raw["output"],
            }
        )
    return results


def _quality_snapshots(output_dir: Path) -> list[dict[str, Any]]:
    results = _run_quality_commands()
    _write_json(output_dir / "quality-command-results.json", {"generated_at_utc": _utc_now(), "results": results})
    return results


def _validate_quality_results(recorded: list[dict[str, Any]]) -> None:
    current = _run_quality_commands()
    stable_keys = ("id", "cwd", "command", "exit_code", "result")
    recorded_stable = [{key: item.get(key) for key in stable_keys} for item in recorded]
    current_stable = [{key: item.get(key) for key in stable_keys} for item in current]
    if recorded_stable != current_stable:
        raise SystemExit("静态质量命令记录与当前重新执行结果不一致")


def _inventory_passed(output_dir: Path) -> bool:
    diff = json.loads((output_dir / "authorization-inventory-diff.json").read_text(encoding="utf-8"))
    if diff["validation"] != "PASS":
        return False
    return not any(
        diff[section].get(key)
        for section in ("http", "websocket_endpoints", "websocket_channels", "broadcast_producers")
        for key in ("missing", "stale", "duplicates")
    )


def _evaluate_gates(
    output_dir: Path,
    *,
    source: dict[str, Any],
    test_metrics: dict[str, Any],
    playwright: dict[str, Any],
    vitest: dict[str, Any],
    quality_results: list[dict[str, Any]],
    images: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    facts = {
        "inventory": _inventory_passed(output_dir),
        "pytest": _pytest_passed(test_metrics["pytest"]),
        "http_matrix": _matrix_passed(test_metrics["http"]),
        "websocket_matrix": _matrix_passed(test_metrics["websocket"]),
        "playwright": _playwright_passed(playwright),
        "vitest": _vitest_passed(vitest),
        "quality": bool(quality_results) and all(item["result"] == "PASS" for item in quality_results),
        "images_built": all(image["status"] == "BUILT" for image in images.values()),
        "images_attested": all(image["attestation_status"] == "PASS" for image in images.values()),
        "registry_digests": all(image["registry_digest_status"] == "PASS" for image in images.values()),
        "changeset_committed": not source["working_tree_dirty"],
    }
    blocker_conditions = (
        ("Authorization inventory has runtime drift.", "inventory"),
        ("The complete pytest evidence run did not pass with non-empty, zero-skipped results.", "pytest"),
        ("The HTTP authorization matrix is empty or has failed/skipped cases.", "http_matrix"),
        ("The WebSocket authorization matrix is empty or has failed/skipped cases.", "websocket_matrix"),
        ("The Playwright authorization run is empty, skipped, flaky, or failed.", "playwright"),
        ("The Vitest WebSocket run is empty, pending, or failed.", "vitest"),
        ("One or more recorded static quality commands failed.", "quality"),
        ("One or more Story images are missing.", "images_built"),
        ("One or more Story images are not attested to the current HEAD and source snapshot.", "images_attested"),
        (
            "Production registry digests are missing or are not owned by the inspected Story image tags.",
            "registry_digests",
        ),
        ("The implementation changeset is not committed.", "changeset_committed"),
    )
    blockers = [message for message, fact in blocker_conditions if not facts[fact]]
    acceptance_criteria = {
        "AC1": facts["inventory"] and facts["pytest"],
        "AC2": facts["pytest"] and facts["http_matrix"] and facts["playwright"],
        "AC3": facts["pytest"] and facts["websocket_matrix"] and facts["playwright"] and facts["vitest"],
        "AC4": facts["pytest"] and facts["websocket_matrix"] and facts["playwright"] and facts["vitest"],
        "AC5": not blockers,
    }
    return {
        "facts": facts,
        "blockers": blockers,
        "story_status": "BLOCKED" if blockers else "PASS",
        "acceptance_criteria": acceptance_criteria,
    }


def _load_trusted_schema(_output_dir: Path) -> dict[str, Any]:
    return json.loads(SCHEMA_SOURCE.read_text(encoding="utf-8"))


def _validate_test_commands(command_items: list[dict[str, Any]]) -> None:
    expected = _evidence_test_commands()
    actual = {item["id"]: {"cwd": item["cwd"], "command": item["command"]} for item in command_items}
    for command_id, command in expected.items():
        if actual.get(command_id) != command:
            raise SystemExit(f"manifest {command_id} 命令未绑定受信任必需测试集合")


def _validate_source_binding(manifest: dict[str, Any], source_snapshot: dict[str, Any], output_dir: Path) -> list[str]:
    changeset = manifest["changeset"]
    current_head = _run(["git", "rev-parse", "HEAD"])
    if changeset["git_sha"] != current_head or source_snapshot.get("git_sha") != current_head:
        raise SystemExit("证据源码快照未绑定当前 HEAD")
    if changeset["baseline_commit"] != BASELINE_COMMIT or source_snapshot.get("baseline_commit") != BASELINE_COMMIT:
        raise SystemExit("证据源码快照 baseline 与受信任基线不一致")

    current_files = _current_source_files(output_dir)
    source_files = source_snapshot["files"]
    if source_files != current_files:
        raise SystemExit("证据源码快照未覆盖当前 Story 完整文件集合")
    source_snapshot_hash = _sha256_bytes(_json_bytes(current_files))
    if source_snapshot_hash != source_snapshot["source_snapshot_sha256"]:
        raise SystemExit("源码快照内部哈希不匹配")
    if source_snapshot_hash != changeset["source_snapshot_sha256"]:
        raise SystemExit("manifest 与当前源码快照哈希不匹配")
    if changeset["source_file_count"] != len(current_files) or source_snapshot["file_count"] != len(current_files):
        raise SystemExit("manifest 与当前源码快照文件数量不匹配")
    current_dirty = _story_source_state(output_dir)[1]
    if changeset["working_tree_dirty"] != current_dirty or source_snapshot["working_tree_dirty"] != current_dirty:
        raise SystemExit("manifest 与当前工作区 dirty 状态不一致")
    return [item["path"] for item in current_files]


def _tool_versions() -> dict[str, str]:
    return {
        "python": _version([sys.executable, "--version"]),
        "pytest": _version(["pytest", "--version"]),
        "ruff": _version(["ruff", "--version"]),
        "node": _version(["node", "--version"]),
        "npm": _version(["npm", "--version"]),
        "playwright": _version(["npx", "playwright", "--version"]),
        "docker": _version(["docker", "--version"]),
        "git": _version(["git", "--version"]),
        "fastapi": importlib.metadata.version("fastapi"),
        "sqlalchemy": importlib.metadata.version("sqlalchemy"),
        "jsonschema": importlib.metadata.version("jsonschema"),
    }


def generate(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    required_inputs = [
        output_dir / "pytest-authz.xml",
        output_dir / "playwright-authz-results.json",
        output_dir / "vitest-websocket-results.json",
    ]
    missing = [str(path) for path in required_inputs if not path.is_file()]
    if missing:
        raise SystemExit(f"缺少测试原始产物: {missing}")
    _validate_test_report_bindings(output_dir, started_at=args.started_at, ended_at=_utc_now())
    shutil.copy2(SCHEMA_SOURCE, output_dir / "manifest.schema.json")

    source = _source_snapshot(output_dir)
    with _working_directory(BACKEND_ROOT):
        inventory_metrics = _inventory_snapshots(output_dir)
        environment = _environment_snapshot(output_dir)
    test_metrics = _test_snapshots(output_dir)
    playwright = _playwright_metrics(output_dir / "playwright-authz-results.json")
    vitest = _vitest_metrics(output_dir / "vitest-websocket-results.json")
    quality_results = _quality_snapshots(output_dir)
    images = {
        "backend": _image_info(
            args.backend_image,
            expected_git_sha=source["git_sha"],
            expected_source_snapshot=source["source_snapshot_sha256"],
            production_registry_digest=args.backend_registry_digest,
        ),
        "frontend": _image_info(
            args.frontend_image,
            expected_git_sha=source["git_sha"],
            expected_source_snapshot=source["source_snapshot_sha256"],
            production_registry_digest=args.frontend_registry_digest,
        ),
    }
    ended_at = _utc_now()

    changeset_id = source["git_sha"]
    if source["working_tree_dirty"]:
        changeset_id = f"{source['git_sha']}+dirty.{source['source_snapshot_sha256'][:12]}"

    registry_digests_verified = all(image["registry_digest_status"] == "PASS" for image in images.values())
    limitations = []
    if source["working_tree_dirty"]:
        limitations.append(
            "Story-scoped implementation files remain in a dirty working tree and are bound by source-file-hashes.json."
        )
    if not registry_digests_verified:
        limitations.append("Image digests are local Docker image IDs, not production registry digests.")
    limitations.extend(
        [
            "The evidence environment uses local SQLite and a single process; it does not claim multi-instance revocation or production topology validation.",
            "Pytest reports unknown timeout/timeout_method configuration options because pytest-timeout is not installed; no test was skipped or retried.",
            "The backend image build warns that pinned email-validator 2.1.0 is yanked; dependency remediation remains in Story 39.5 supply-chain scope.",
        ]
    )

    gate = _evaluate_gates(
        output_dir,
        source=source,
        test_metrics=test_metrics,
        playwright=playwright,
        vitest=vitest,
        quality_results=quality_results,
        images=images,
    )
    story_blockers = gate["blockers"]
    story_status = gate["story_status"]
    governance_decision = "BLOCKED" if story_blockers else "VERIFIED"

    artifacts = [_artifact(output_dir / name, purpose, acs) for name, (purpose, acs) in ARTIFACT_SPECS.items()]
    ac_evidence = {
        ac: [item["path"] for item in artifacts if ac in item["acceptance_criteria"]]
        for ac in ("AC1", "AC2", "AC3", "AC4", "AC5")
    }
    test_commands = _evidence_test_commands()

    commands = [
        {
            "id": "PYTEST-AUTHZ",
            **test_commands["PYTEST-AUTHZ"],
            "result": "PASS" if gate["facts"]["pytest"] else "FAIL",
        },
        {
            "id": "PLAYWRIGHT-AUTHZ",
            **test_commands["PLAYWRIGHT-AUTHZ"],
            "result": "PASS" if gate["facts"]["playwright"] else "FAIL",
        },
        {
            "id": "VITEST-WS",
            **test_commands["VITEST-WS"],
            "result": "PASS" if gate["facts"]["vitest"] else "FAIL",
        },
        {
            "id": "BACKEND-IMAGE",
            "cwd": ".",
            "command": (
                "docker build --provenance=false "
                f"--build-arg VCS_REF={source['git_sha']} "
                f"--build-arg STORY_SOURCE_SNAPSHOT={source['source_snapshot_sha256']} "
                f"-t {args.backend_image} backend"
            ),
            "result": "PASS"
            if images["backend"]["status"] == "BUILT" and images["backend"]["attestation_status"] == "PASS"
            else "FAIL",
        },
        {
            "id": "FRONTEND-IMAGE",
            "cwd": ".",
            "command": (
                "docker build --provenance=false "
                f"--build-arg VCS_REF={source['git_sha']} "
                f"--build-arg STORY_SOURCE_SNAPSHOT={source['source_snapshot_sha256']} "
                f"-t {args.frontend_image} frontend"
            ),
            "result": "PASS"
            if images["frontend"]["status"] == "BUILT" and images["frontend"]["attestation_status"] == "PASS"
            else "FAIL",
        },
    ] + [{key: item[key] for key in ("id", "cwd", "command", "result")} for item in quality_results]

    manifest = {
        "schema_version": 2,
        "story": {
            "id": "39.1",
            "key": "39-1-site-isolation-and-websocket-authorization",
            "title": "Site isolation and server-side WebSocket authorization",
        },
        "changeset": {
            "git_sha": source["git_sha"],
            "baseline_commit": BASELINE_COMMIT,
            "working_tree_dirty": source["working_tree_dirty"],
            "changeset_id": changeset_id,
            "source_snapshot_sha256": source["source_snapshot_sha256"],
            "source_file_count": source["file_count"],
        },
        "images": images,
        "environment": {
            "id": ENVIRONMENT_ID,
            "kind": ENVIRONMENT_KIND,
            "fingerprint_sha256": environment["fingerprint_sha256"],
            "topology": environment["values"]["topology"],
            "production_equivalent": False,
        },
        "tools": _tool_versions(),
        "execution": {
            "started_at_utc": args.started_at,
            "ended_at_utc": ended_at,
            "operator": "Admin (Codex-assisted)",
            "commands": commands,
        },
        "artifacts": artifacts,
        "metrics": _manifest_metrics(inventory_metrics, test_metrics["pytest"], test_metrics, playwright, vitest),
        "acceptance_criteria": {
            "AC1": {
                "result": "PASS" if gate["acceptance_criteria"]["AC1"] else "BLOCKED",
                "evidence": ac_evidence["AC1"],
            },
            "AC2": {
                "result": "PASS" if gate["acceptance_criteria"]["AC2"] else "BLOCKED",
                "evidence": ac_evidence["AC2"],
            },
            "AC3": {
                "result": "PASS" if gate["acceptance_criteria"]["AC3"] else "BLOCKED",
                "evidence": ac_evidence["AC3"],
            },
            "AC4": {
                "result": "PASS" if gate["acceptance_criteria"]["AC4"] else "BLOCKED",
                "evidence": ac_evidence["AC4"],
            },
            "AC5": {
                "result": "PASS" if gate["acceptance_criteria"]["AC5"] else "BLOCKED",
                "evidence": ac_evidence["AC5"],
            },
        },
        "limitations": limitations,
        "exceptions": [],
        "decisions": [
            "No D39-08 exception is applied; cross-site and WebSocket authorization controls are non-waivable.",
            "Cross-instance fan-out remains outside Story 39.1 and is owned by Story 39.10.",
            "The project uses single-maintainer evidence governance; virtual BMAD role signatures are not required.",
        ],
        "ownership": {
            "maintainer": "proecheng",
        },
        "governance": {
            "mode": "single-maintainer",
            "maintainer": "proecheng",
            "independent_approval_required": False,
            "decision": governance_decision,
            "decided_at_utc": _utc_now(),
            "basis": [
                "All Story 39.1 acceptance criteria are evaluated from machine-readable evidence.",
                "The manifest, artifact paths, SHA-256 hashes, source snapshot, and automated results pass validation.",
            ],
        },
        "story_gate": {
            "status": story_status,
            "blockers": story_blockers,
        },
        "epic_production_gate": {
            "status": "BLOCKED",
            "blockers": [
                "Epic 39 Stories 39.2 through 39.12 and the refreshed NFR assessment are not complete.",
                "Production-equivalent environment validation and field UAT remain outside Story 39.1.",
            ],
        },
    }
    (output_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def validate(args: argparse.Namespace) -> None:
    import jsonschema

    output_dir = args.output_dir.resolve()
    schema = _load_trusted_schema(output_dir)
    evidence_schema = json.loads((output_dir / "manifest.schema.json").read_text(encoding="utf-8"))
    if evidence_schema != schema:
        raise SystemExit("证据包 Schema 与仓库受信任 Schema 不一致")
    manifest = yaml.safe_load((output_dir / "manifest.yaml").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)

    artifact_names = [Path(item["path"]).name for item in manifest["artifacts"]]
    if duplicates := _duplicates(artifact_names):
        raise SystemExit(f"manifest 包含重复产物: {duplicates}")
    if missing := sorted(REQUIRED_ARTIFACT_NAMES - set(artifact_names)):
        raise SystemExit(f"manifest 缺少必需产物: {missing}")
    if unexpected := sorted(set(artifact_names) - REQUIRED_ARTIFACT_NAMES):
        raise SystemExit(f"manifest 包含非契约产物: {unexpected}")

    checks = []
    evidence_root = output_dir.resolve()
    for item in manifest["artifacts"]:
        path = (ROOT / item["path"]).resolve()
        if evidence_root not in path.parents:
            raise SystemExit(f"产物路径越界: {item['path']}")
        if not path.is_file():
            raise SystemExit(f"产物不存在: {item['path']}")
        actual_hash = _sha256_file(path)
        actual_size = path.stat().st_size
        if actual_hash != item["sha256"] or actual_size != item["size_bytes"]:
            raise SystemExit(f"产物哈希或大小不匹配: {item['path']}")
        checks.append({"path": item["path"], "sha256": actual_hash, "size_bytes": actual_size, "status": "PASS"})

    source_snapshot = json.loads((output_dir / "source-file-hashes.json").read_text(encoding="utf-8"))
    source_checks = _validate_source_binding(manifest, source_snapshot, output_dir)

    _validate_test_report_bindings(
        output_dir,
        started_at=manifest["execution"]["started_at_utc"],
        ended_at=manifest["execution"]["ended_at_utc"],
    )
    with _working_directory(BACKEND_ROOT):
        inventory_evidence = _validate_inventory_derivatives(output_dir)
        _validate_environment_binding(manifest, output_dir)

    diff = json.loads((output_dir / "authorization-inventory-diff.json").read_text(encoding="utf-8"))
    if diff["validation"] != "PASS":
        raise SystemExit("授权清单差异未通过")
    for section in ("http", "websocket_endpoints", "websocket_channels", "broadcast_producers"):
        for key in ("missing", "stale", "duplicates"):
            if diff[section].get(key):
                raise SystemExit(f"授权清单仍有差异: {section}.{key}")

    http = json.loads((output_dir / "http-authz-matrix-results.json").read_text(encoding="utf-8"))
    websocket = json.loads((output_dir / "websocket-authz-matrix-results.json").read_text(encoding="utf-8"))
    pytest_metrics, pytest_cases = _parse_junit(output_dir / "pytest-authz.xml")
    matrices = _validate_test_derivatives(output_dir, pytest_cases)
    playwright = _playwright_metrics(output_dir / "playwright-authz-results.json")
    vitest = _vitest_metrics(output_dir / "vitest-websocket-results.json")
    expected_metrics = _manifest_metrics(inventory_evidence["metrics"], pytest_metrics, matrices, playwright, vitest)
    _validate_manifest_metrics(manifest, expected_metrics)
    _validate_acceptance_evidence(manifest)
    quality = json.loads((output_dir / "quality-command-results.json").read_text(encoding="utf-8"))["results"]
    if not quality:
        raise SystemExit("静态质量命令原始结果为空")
    for item in quality:
        expected_result = "PASS" if item.get("exit_code") == 0 else "FAIL"
        if item.get("result") != expected_result:
            raise SystemExit(f"静态质量命令结果与退出码不一致: {item.get('id')}")
    _validate_quality_results(quality)

    images = manifest["images"]
    for image_name, image in images.items():
        verified = _image_info(
            image["tag"],
            expected_git_sha=manifest["changeset"]["git_sha"],
            expected_source_snapshot=manifest["changeset"]["source_snapshot_sha256"],
            production_registry_digest=image["production_registry_digest"],
        )
        for key in (
            "status",
            "digest",
            "repo_digests",
            "git_sha_label",
            "source_snapshot_label",
            "attestation_status",
            "registry_digest_status",
        ):
            if image[key] != verified[key]:
                raise SystemExit(f"{image_name} 镜像证据与当前 Docker inspect 不一致: {key}")

    test_metrics = {"pytest": pytest_metrics, "http": http, "websocket": websocket}
    source = {
        "git_sha": manifest["changeset"]["git_sha"],
        "working_tree_dirty": manifest["changeset"]["working_tree_dirty"],
        "source_snapshot_sha256": manifest["changeset"]["source_snapshot_sha256"],
    }
    gate = _evaluate_gates(
        output_dir,
        source=source,
        test_metrics=test_metrics,
        playwright=playwright,
        vitest=vitest,
        quality_results=quality,
        images=images,
    )

    command_items = manifest["execution"]["commands"]
    _validate_test_commands(command_items)
    command_ids = [item["id"] for item in command_items]
    if duplicates := _duplicates(command_ids):
        raise SystemExit(f"manifest 包含重复命令结果: {duplicates}")
    command_results = {item["id"]: item["result"] for item in command_items}
    expected_command_results = {
        "PYTEST-AUTHZ": "PASS" if gate["facts"]["pytest"] else "FAIL",
        "PLAYWRIGHT-AUTHZ": "PASS" if gate["facts"]["playwright"] else "FAIL",
        "VITEST-WS": "PASS" if gate["facts"]["vitest"] else "FAIL",
        "BACKEND-IMAGE": (
            "PASS"
            if images["backend"]["status"] == "BUILT" and images["backend"]["attestation_status"] == "PASS"
            else "FAIL"
        ),
        "FRONTEND-IMAGE": (
            "PASS"
            if images["frontend"]["status"] == "BUILT" and images["frontend"]["attestation_status"] == "PASS"
            else "FAIL"
        ),
        **{item["id"]: item["result"] for item in quality},
    }
    if command_results != expected_command_results:
        raise SystemExit("manifest 命令结果与受信任原始结果不一致")
    expected_ac_results = {key: "PASS" if passed else "BLOCKED" for key, passed in gate["acceptance_criteria"].items()}
    actual_ac_results = {key: value["result"] for key, value in manifest["acceptance_criteria"].items()}
    if actual_ac_results != expected_ac_results:
        raise SystemExit("manifest 验收标准结果与原始证据推导不一致")

    try:
        validate_governance(manifest)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    governance = manifest["governance"]
    story_gate = manifest["story_gate"]
    if story_gate["status"] != gate["story_status"] or story_gate["blockers"] != gate["blockers"]:
        raise SystemExit("manifest Story 门禁与原始证据推导不一致")

    report = {
        "validated_at_utc": _utc_now(),
        "schema": "PASS",
        "path_and_hash_checks": "PASS",
        "artifact_count": len(checks),
        "artifacts": checks,
        "source_files": "PASS",
        "source_file_count": len(source_checks),
        "automated_evidence": "PASS",
        "governance_mode": governance["mode"],
        "independent_approval_required": governance["independent_approval_required"],
        "story_gate": story_gate["status"],
        "epic_production_gate": manifest["epic_production_gate"]["status"],
        "result": "PASS",
    }
    _write_json(output_dir / "evidence-validation.json", report)
    print(
        json.dumps(
            {
                "result": "PASS",
                "artifact_count": len(checks),
                "story_gate": story_gate["status"],
                "epic_production_gate": manifest["epic_production_gate"]["status"],
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    generate_parser.add_argument("--started-at", required=True)
    generate_parser.add_argument("--backend-image", required=True)
    generate_parser.add_argument("--frontend-image", required=True)
    generate_parser.add_argument("--backend-registry-digest")
    generate_parser.add_argument("--frontend-registry-digest")
    generate_parser.set_defaults(handler=generate)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    validate_parser.set_defaults(handler=validate)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
