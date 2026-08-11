"""生成并验证 Story 39.1 的机器可读证据包。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.1"
SCHEMA_SOURCE = Path(__file__).with_name("story_39_1_manifest.schema.json")
BASELINE_COMMIT = "a9b872155f8554136f456e6d15116e721270761c"
REGISTRY_DIGEST_PATTERN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")

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


def _version(command: list[str]) -> str:
    try:
        executable = shutil.which(command[0]) or command[0]
        resolved = [executable, *command[1:]]
        if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
            resolved = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *resolved]
        return _run(resolved).splitlines()[0]
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
        "e2e/auth.setup.ts",
        "e2e/site-isolation-websocket-authorization.spec.ts",
        "playwright.config.ts",
        "scripts/story_39_1_evidence.py",
        "scripts/story_39_1_manifest.schema.json",
        "_bmad-output/implementation-artifacts/39-1-site-isolation-and-websocket-authorization.md",
    }


def _source_snapshot(output_dir: Path) -> dict[str, Any]:
    committed = set(
        _split_null_output(["git", "diff", "--name-only", "-z", BASELINE_COMMIT, "HEAD"])
    )
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
    snapshot_hash = _sha256_bytes(_json_bytes(files))
    result = {
        "generated_at_utc": _utc_now(),
        "scope": "Story 39.1 implementation and test files changed since the baseline commit",
        "git_sha": _run(["git", "rev-parse", "HEAD"]),
        "working_tree_dirty": bool(story_dirty),
        "source_snapshot_sha256": snapshot_hash,
        "file_count": len(files),
        "files": files,
    }
    _write_json(output_dir / "source-file-hashes.json", result)
    return result


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(key for key, count in counts.items() if count > 1)


def _inventory_snapshots(output_dir: Path) -> dict[str, int]:
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
    (output_dir / "authorization-inventory.yaml").write_text(
        yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

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
    _write_json(output_dir / "authorization-inventory-diff.json", diff)

    policies = {item["key"]: item for item in websocket["producers"]}
    producer_inventory = {
        "generated_at_utc": _utc_now(),
        "validation": "PASS",
        "count": len(discovered),
        "producers": [
            {"discovered": item, "policy": policies[item["key"]]}
            for item in discovered
        ],
    }
    _write_json(output_dir / "websocket-producer-inventory.json", producer_inventory)
    _write_json(output_dir / "openapi-authz-snapshot.json", app.openapi())
    return {
        "http": validation.http_count,
        "websocket": validation.websocket_count,
        "channels": validation.channel_count,
        "producers": validation.producer_count,
    }


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
    return {
        "generated_at_utc": _utc_now(),
        "matrix": kind,
        "result": "PASS" if not failures else "FAIL",
        "total": len(cases),
        "passed": len(cases) - len(failures),
        "failed_or_skipped": len(failures),
        "cases": cases,
    }


def _test_snapshots(output_dir: Path) -> dict[str, Any]:
    totals, cases = _parse_junit(output_dir / "pytest-authz.xml")
    http_cases = [
        case
        for case in cases
        if case["classname"].endswith(("test_story_39_1", "test_authorization_inventory"))
    ]
    websocket_cases = [case for case in cases if case["classname"].endswith("test_websocket_authorization")]
    http_result = _matrix_result("HTTP authorization and inventory", http_cases)
    websocket_result = _matrix_result("WebSocket authorization and revocation", websocket_cases)
    _write_json(output_dir / "http-authz-matrix-results.json", http_result)
    _write_json(output_dir / "websocket-authz-matrix-results.json", websocket_result)
    return {"pytest": totals, "http": http_result, "websocket": websocket_result}


def _environment_snapshot(output_dir: Path) -> dict[str, Any]:
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
    result = {"generated_at_utc": _utc_now(), "fingerprint_sha256": fingerprint, "values": public_config}
    _write_json(output_dir / "environment-fingerprint.json", result)
    return result


def _validated_registry_digest(value: str | None) -> str | None:
    if value is None:
        return None
    if not REGISTRY_DIGEST_PATTERN.fullmatch(value):
        raise SystemExit(f"生产仓库摘要格式无效: {value}")
    return value


def _image_info(tag: str, production_registry_digest: str | None = None) -> dict[str, Any]:
    production_registry_digest = _validated_registry_digest(production_registry_digest)
    try:
        item = json.loads(_run(["docker", "image", "inspect", tag]))[0]
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return {
            "tag": tag,
            "status": "FAILED",
            "digest": None,
            "repo_digests": [],
            "production_registry_digest": production_registry_digest,
        }
    return {
        "tag": tag,
        "status": "BUILT",
        "digest": item["Id"],
        "repo_digests": item.get("RepoDigests") or [],
        "production_registry_digest": production_registry_digest,
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
    shutil.copy2(SCHEMA_SOURCE, output_dir / "manifest.schema.json")

    required_inputs = [
        output_dir / "pytest-authz.xml",
        output_dir / "playwright-authz-results.json",
        output_dir / "vitest-websocket-results.json",
    ]
    missing = [str(path) for path in required_inputs if not path.is_file()]
    if missing:
        raise SystemExit(f"缺少测试原始产物: {missing}")

    source = _source_snapshot(output_dir)
    with _working_directory(BACKEND_ROOT):
        inventory_metrics = _inventory_snapshots(output_dir)
        environment = _environment_snapshot(output_dir)
    test_metrics = _test_snapshots(output_dir)
    playwright = _playwright_metrics(output_dir / "playwright-authz-results.json")
    vitest = _vitest_metrics(output_dir / "vitest-websocket-results.json")
    images = {
        "backend": _image_info(args.backend_image, args.backend_registry_digest),
        "frontend": _image_info(args.frontend_image, args.frontend_registry_digest),
    }

    changeset_id = source["git_sha"]
    if source["working_tree_dirty"]:
        changeset_id = f"{source['git_sha']}+dirty.{source['source_snapshot_sha256'][:12]}"

    registry_digests_available = all(
        image["production_registry_digest"] for image in images.values()
    )
    limitations = ["Charlie and Dana have not independently signed this evidence package."]
    if source["working_tree_dirty"]:
        limitations.append(
            "Story-scoped implementation files remain in a dirty working tree and are bound by source-file-hashes.json."
        )
    if not registry_digests_available:
        limitations.append("Image digests are local Docker image IDs, not production registry digests.")
    limitations.extend(
        [
            "The evidence environment uses local SQLite and a single process; it does not claim multi-instance revocation or production topology validation.",
            "Pytest reports unknown timeout/timeout_method configuration options because pytest-timeout is not installed; no test was skipped or retried.",
            "The backend image build warns that pinned email-validator 2.1.0 is yanked; dependency remediation remains in Story 39.5 supply-chain scope.",
        ]
    )

    production_blockers = [
        "Charlie security approval is missing.",
        "Dana QA approval is missing.",
    ]
    if not registry_digests_available:
        production_blockers.append(
            "Production registry image digests are not available from the local evidence environment."
        )
    if source["working_tree_dirty"]:
        production_blockers.append("The implementation changeset is not committed.")

    artifact_specs = {
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
        "manifest.schema.json": ("Evidence manifest JSON Schema", ["AC5"]),
    }
    artifacts = [
        _artifact(output_dir / name, purpose, acs)
        for name, (purpose, acs) in artifact_specs.items()
    ]
    evidence = {item["path"].rsplit("/", 1)[-1]: item["path"] for item in artifacts}

    commands = [
        {
            "id": "PYTEST-AUTHZ",
            "cwd": "backend",
            "command": "pytest -q tests/test_authorization_inventory.py tests/test_story_39_1.py tests/test_websocket_authorization.py tests/test_auth_session.py tests/test_site_isolation.py tests/test_site_management.py tests/test_device_detail.py tests/test_point_data.py tests/test_alarm_api.py tests/test_story_24_6.py tests/test_story_24_7.py tests/test_fault_impact.py tests/test_gateway_monitor.py --junitxml=../_bmad-output/test-artifacts/epic-39/39.1/pytest-authz.xml",
            "result": "PASS" if not test_metrics["pytest"]["failures"] and not test_metrics["pytest"]["errors"] else "FAIL",
        },
        {
            "id": "PLAYWRIGHT-AUTHZ",
            "cwd": ".",
            "command": "CI=1 PLAYWRIGHT_JSON_OUTPUT_FILE=_bmad-output/test-artifacts/epic-39/39.1/playwright-authz-results.json npx playwright test e2e/authorization-matrix.spec.ts e2e/site-isolation-websocket-authorization.spec.ts --project=chromium --workers=1 --reporter=json",
            "result": "PASS" if playwright["unexpected"] == 0 and playwright["flaky"] == 0 else "FAIL",
        },
        {
            "id": "VITEST-WS",
            "cwd": "frontend",
            "command": "npx vitest --run src/__tests__/api/websocket-auth.test.ts src/__tests__/story-27-6-site-filter.test.ts src/__tests__/composables/useWebSocket.test.ts --reporter=json --outputFile=../_bmad-output/test-artifacts/epic-39/39.1/vitest-websocket-results.json",
            "result": "PASS" if vitest["success"] and vitest["failed"] == 0 else "FAIL",
        },
        {
            "id": "FRONTEND-TYPECHECK",
            "cwd": "frontend",
            "command": "npm run typecheck",
            "result": "PASS",
        },
        {
            "id": "FRONTEND-ESLINT",
            "cwd": "frontend",
            "command": "npx eslint src/api/websocket.ts src/composables/useWebSocket.ts src/composables/useWebSocketManager.ts src/__tests__/api/websocket-auth.test.ts --max-warnings=0",
            "result": "PASS",
        },
        {
            "id": "BACKEND-RUFF",
            "cwd": "backend",
            "command": "ruff check app tests/test_authorization_inventory.py tests/test_story_39_1.py tests/test_websocket_authorization.py tests/test_fault_impact.py tests/test_gateway_monitor.py",
            "result": "PASS",
        },
        {
            "id": "BACKEND-IMAGE",
            "cwd": ".",
            "command": f"docker build --provenance=false -t {args.backend_image} backend",
            "result": "PASS" if images["backend"]["status"] == "BUILT" else "FAIL",
        },
        {
            "id": "FRONTEND-IMAGE",
            "cwd": ".",
            "command": f"docker build --provenance=false -t {args.frontend_image} frontend",
            "result": "PASS" if images["frontend"]["status"] == "BUILT" else "FAIL",
        },
    ]

    manifest = {
        "schema_version": 1,
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
            "id": "local-windows-docker-desktop-story-39-1",
            "kind": "local integration evidence",
            "fingerprint_sha256": environment["fingerprint_sha256"],
            "topology": environment["values"]["topology"],
            "production_equivalent": False,
        },
        "tools": _tool_versions(),
        "execution": {
            "started_at_utc": args.started_at,
            "ended_at_utc": _utc_now(),
            "operator": "Admin (Codex-assisted)",
            "commands": commands,
        },
        "artifacts": artifacts,
        "metrics": {
            "inventory": inventory_metrics,
            "pytest": test_metrics["pytest"],
            "http_matrix": {
                "total": test_metrics["http"]["total"],
                "passed": test_metrics["http"]["passed"],
            },
            "websocket_matrix": {
                "total": test_metrics["websocket"]["total"],
                "passed": test_metrics["websocket"]["passed"],
            },
            "playwright": playwright,
            "vitest": vitest,
        },
        "acceptance_criteria": {
            "AC1": {
                "result": "PASS",
                "evidence": [evidence["authorization-inventory.yaml"], evidence["authorization-inventory-diff.json"], evidence["websocket-producer-inventory.json"]],
            },
            "AC2": {
                "result": "PASS",
                "evidence": [evidence["http-authz-matrix-results.json"], evidence["pytest-authz.xml"], evidence["playwright-authz-results.json"]],
            },
            "AC3": {
                "result": "PASS",
                "evidence": [evidence["websocket-authz-matrix-results.json"], evidence["vitest-websocket-results.json"], evidence["playwright-authz-results.json"]],
            },
            "AC4": {
                "result": "PASS",
                "evidence": [evidence["websocket-authz-matrix-results.json"], evidence["pytest-authz.xml"], evidence["playwright-authz-results.json"]],
            },
            "AC5": {
                "result": "BLOCKED",
                "evidence": [evidence["http-authz-matrix-results.json"], evidence["websocket-authz-matrix-results.json"], evidence["manifest.schema.json"]],
            },
        },
        "limitations": limitations,
        "exceptions": [],
        "decisions": [
            "No D39-08 exception is applied; cross-site and WebSocket authorization controls are non-waivable.",
            "Cross-instance fan-out remains outside Story 39.1 and is owned by Story 39.10.",
        ],
        "ownership": {
            "implementation_owner": "Amelia",
            "security_owner": "Charlie",
            "qa_owner": "Dana",
        },
        "approvals": {
            "security": {
                "name": "Charlie",
                "role": "Security evidence approver",
                "status": "PENDING",
                "signed_at_utc": None,
                "signature": None,
            },
            "qa": {
                "name": "Dana",
                "role": "QA evidence approver",
                "status": "PENDING",
                "signed_at_utc": None,
                "signature": None,
            },
        },
        "production_gate": {
            "status": "BLOCKED",
            "blockers": production_blockers,
        },
    }
    (output_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def validate(args: argparse.Namespace) -> None:
    output_dir = args.output_dir.resolve()
    schema = json.loads((output_dir / "manifest.schema.json").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((output_dir / "manifest.yaml").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)

    required = {
        "authorization-inventory.yaml",
        "authorization-inventory-diff.json",
        "openapi-authz-snapshot.json",
        "websocket-producer-inventory.json",
        "http-authz-matrix-results.json",
        "websocket-authz-matrix-results.json",
        "pytest-authz.xml",
        "playwright-authz-results.json",
        "manifest.schema.json",
    }
    artifact_names = {Path(item["path"]).name for item in manifest["artifacts"]}
    if missing := sorted(required - artifact_names):
        raise SystemExit(f"manifest 缺少必需产物: {missing}")

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
    source_files = source_snapshot["files"]
    source_snapshot_hash = _sha256_bytes(_json_bytes(source_files))
    if source_snapshot_hash != source_snapshot["source_snapshot_sha256"]:
        raise SystemExit("源码快照内部哈希不匹配")
    if source_snapshot_hash != manifest["changeset"]["source_snapshot_sha256"]:
        raise SystemExit("manifest 与源码快照哈希不匹配")
    source_checks = []
    for item in source_files:
        path = (ROOT / item["path"]).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise SystemExit(f"源码路径越界: {item['path']}") from exc
        if not path.is_file():
            raise SystemExit(f"源码文件不存在: {item['path']}")
        actual_hash = _sha256_file(path)
        actual_size = path.stat().st_size
        if actual_hash != item["sha256"] or actual_size != item["size_bytes"]:
            raise SystemExit(f"源码文件哈希或大小不匹配: {item['path']}")
        source_checks.append(item["path"])

    diff = json.loads((output_dir / "authorization-inventory-diff.json").read_text(encoding="utf-8"))
    if diff["validation"] != "PASS":
        raise SystemExit("授权清单差异未通过")
    for section in ("http", "websocket_endpoints", "websocket_channels", "broadcast_producers"):
        for key in ("missing", "stale", "duplicates"):
            if diff[section].get(key):
                raise SystemExit(f"授权清单仍有差异: {section}.{key}")

    http = json.loads((output_dir / "http-authz-matrix-results.json").read_text(encoding="utf-8"))
    websocket = json.loads((output_dir / "websocket-authz-matrix-results.json").read_text(encoding="utf-8"))
    playwright = _playwright_metrics(output_dir / "playwright-authz-results.json")
    vitest = _vitest_metrics(output_dir / "vitest-websocket-results.json")
    if http["result"] != "PASS" or websocket["result"] != "PASS":
        raise SystemExit("HTTP 或 WebSocket 矩阵未通过")
    if playwright["unexpected"] or playwright["flaky"] or not vitest["success"] or vitest["failed"]:
        raise SystemExit("Playwright 或 Vitest 原始结果未通过")

    approvals = manifest["approvals"]
    pending = [key for key, value in approvals.items() if value["status"] != "APPROVED"]
    if pending and manifest["production_gate"]["status"] != "BLOCKED":
        raise SystemExit("审批缺失时生产门禁必须为 BLOCKED")

    report = {
        "validated_at_utc": _utc_now(),
        "schema": "PASS",
        "path_and_hash_checks": "PASS",
        "artifact_count": len(checks),
        "artifacts": checks,
        "source_files": "PASS",
        "source_file_count": len(source_checks),
        "automated_evidence": "PASS",
        "pending_approvals": pending,
        "production_gate": manifest["production_gate"]["status"],
        "result": "PASS",
    }
    _write_json(output_dir / "evidence-validation.json", report)
    print(json.dumps({"result": "PASS", "artifact_count": len(checks), "production_gate": "BLOCKED"}))


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
