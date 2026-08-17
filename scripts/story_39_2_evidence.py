"""Generate and independently validate Story 39.2 security evidence."""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import jsonschema
import yaml

from story_39_2_governance import validate_governance


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
FRONTEND_ROOT = ROOT / "frontend"
PROXY_ROOT = ROOT / "proxy"
DEFAULT_OUTPUT = ROOT / "_bmad-output" / "test-artifacts" / "epic-39" / "39.2"
SCHEMA_SOURCE = Path(__file__).with_name("story_39_2_manifest.schema.json")
BASELINE_COMMIT = "436a8e778037bf6fcf9140b757e9584e669ad33b"
IMAGE_TAG = "dcim-story-39-2-frontend:evidence"
GIT_SHA_LABEL = "org.opencontainers.image.revision"
SOURCE_SNAPSHOT_LABEL = "io.dcim.story-39-2.source-snapshot-sha256"
ENVIRONMENT_ID = "local-windows-docker-desktop-story-39-2"
ENVIRONMENT_KIND = "local integration evidence"
MAX_EXECUTION_WINDOW = timedelta(hours=4)
ACCEPTANCE_CRITERIA = ("AC1", "AC2", "AC3", "AC4", "AC5", "AC6")

PYTEST_TEST_FILES = (
    "tests/test_story_39_2_commands.py",
    "tests/test_command.py",
    "tests/services/test_device_control.py",
    "tests/services/test_execution_service.py",
    "tests/test_gateway_registration.py",
    "tests/test_story_39_2_production_config.py",
    "tests/test_story_39_2_cors.py",
    "tests/test_story_39_2_evidence.py",
)
VITEST_TEST_FILES = (
    "src/__tests__/api/websocket-auth.test.ts",
    "src/components/common/SafeRichText.test.ts",
    "src/security/html.test.ts",
    "src/security/html-sink-policy.test.ts",
    "src/utils/three/labelRenderer.test.ts",
    "src/views/diagnosis/Reports.test.ts",
)
EXPECTED_COMMAND_ENTRYPOINTS = {
    "ac_temp_set": ["command_api"],
    "device_decommission": ["command_api"],
    "device_regulation": [
        "device_control_batch",
        "execution_service",
        "load_regulation",
    ],
    "door_access": ["command_api"],
    "light_switch": ["command_api"],
    "power_off": ["command_api"],
    "ups_switch": ["command_api"],
}
ARTIFACT_SPECS: dict[str, tuple[str, list[str]]] = {
    "command-registry-snapshot.json": (
        "Runtime command registry and entrypoint drift snapshot",
        ["AC1", "AC2"],
    ),
    "pytest-security.xml": (
        "Raw backend command, approval, production config, and CORS tests",
        ["AC1", "AC2", "AC4", "AC5", "AC6"],
    ),
    "vitest-xss-results.json": (
        "Raw frontend sanitizer and HTML sink tests",
        ["AC3", "AC6"],
    ),
    "proxy-security-results.json": (
        "Raw Node proxy CORS and security-header tests",
        ["AC5", "AC6"],
    ),
    "backend-cors-runtime-results.json": (
        "Live Uvicorn CORS response matrix",
        ["AC5", "AC6"],
    ),
    "nginx-security-results.json": (
        "Actual Nginx artifact response matrix",
        ["AC5", "AC6"],
    ),
    "nginx-browser-results.json": (
        "Actual browser load under enforced Nginx CSP",
        ["AC3", "AC5", "AC6"],
    ),
    "quality-command-results.json": (
        "Static analysis, type checking, and compilation results",
        ["AC6"],
    ),
    "environment-fingerprint.json": (
        "Sanitized execution environment fingerprint",
        ["AC6"],
    ),
    "source-file-hashes.json": (
        "Story implementation source snapshot",
        list(ACCEPTANCE_CRITERIA),
    ),
    "manifest.schema.json": ("Evidence manifest JSON Schema", ["AC6"]),
}
REQUIRED_COMMAND_IDS = {
    "PYTEST-SECURITY",
    "VITEST-XSS",
    "PROXY-SECURITY",
    "BACKEND-CORS-RUNTIME",
    "FRONTEND-IMAGE",
    "NGINX-BROWSER",
    "BACKEND-RUFF",
    "BACKEND-RUFF-FORMAT",
    "BACKEND-COMPILE",
    "FRONTEND-TYPECHECK",
    "FRONTEND-ESLINT",
    "EVIDENCE-RUFF",
}

QUALITY_COMMANDS: tuple[tuple[str, Path, tuple[str, ...]], ...] = (
    (
        "BACKEND-RUFF",
        BACKEND_ROOT,
        ("ruff", "check", "app", "gateway", *PYTEST_TEST_FILES),
    ),
    (
        "BACKEND-RUFF-FORMAT",
        BACKEND_ROOT,
        ("ruff", "format", "--check", "app", "gateway", *PYTEST_TEST_FILES),
    ),
    (
        "BACKEND-COMPILE",
        BACKEND_ROOT,
        (sys.executable, "-m", "compileall", "-q", "app", "gateway"),
    ),
    ("FRONTEND-TYPECHECK", FRONTEND_ROOT, ("npm", "run", "typecheck")),
    ("FRONTEND-ESLINT", FRONTEND_ROOT, ("npm", "run", "lint")),
    (
        "EVIDENCE-RUFF",
        ROOT,
        (
            "ruff",
            "check",
            "scripts/story_39_2_evidence.py",
            "scripts/story_39_2_governance.py",
            "backend/tests/test_story_39_2_evidence.py",
        ),
    ),
)

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolved_command(command: tuple[str, ...] | list[str]) -> list[str]:
    executable = shutil.which(command[0]) or command[0]
    result = [executable, *command[1:]]
    if os.name == "nt" and Path(executable).suffix.lower() in {".bat", ".cmd"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *result]
    return result


def run_result(
    command: tuple[str, ...] | list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            resolved_command(command),
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
        )
        return {"exit_code": completed.returncode, "output": completed.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": 127, "output": f"{type(exc).__name__}: {exc}"}


def run_checked(
    command: tuple[str, ...] | list[str],
    *,
    cwd: Path = ROOT,
    timeout: int | None = None,
) -> str:
    result = run_result(command, cwd=cwd, timeout=timeout)
    if result["exit_code"] != 0:
        raise SystemExit(f"命令失败: {' '.join(command)}\n{result['output']}")
    return result["output"]


def command_text(command: tuple[str, ...] | list[str]) -> str:
    return subprocess.list2cmdline(list(command))


def manifest_command(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("id", "cwd", "command", "result")}


def git_head() -> str:
    return run_checked(("git", "rev-parse", "HEAD"))


def git_is_ancestor(ancestor: str, descendant: str) -> bool:
    result = run_result(("git", "merge-base", "--is-ancestor", ancestor, descendant))
    return result["exit_code"] == 0


def null_git_paths(command: tuple[str, ...]) -> set[str]:
    completed = subprocess.check_output(command, cwd=ROOT)
    return {item.decode("utf-8") for item in completed.split(b"\0") if item}


def is_story_source(path: str) -> bool:
    excluded = (
        "_bmad-output/test-artifacts/epic-39/39.1/",
        "_bmad-output/test-artifacts/epic-39/39.2/",
        "backend/reports/",
        "backend/.pytest_cache/",
        "frontend/dist/",
    )
    if path == "backend/coverage.xml" or path.startswith(excluded):
        return False
    if path.startswith(("backend/", "frontend/", "proxy/", "deploy/nginx/")):
        return True
    return path in {
        ".env.example",
        "docker-compose.yml",
        "e2e/story-39-2-nginx-security.spec.ts",
        "e2e/story-39-2.playwright.config.ts",
        "scripts/story_39_2_evidence.py",
        "scripts/story_39_2_governance.py",
        "scripts/story_39_2_manifest.schema.json",
    }


def current_source_files(output_dir: Path) -> list[dict[str, Any]]:
    changed = null_git_paths(
        ("git", "diff", "--name-only", "-z", BASELINE_COMMIT, "HEAD")
    )
    changed.update(null_git_paths(("git", "diff", "--name-only", "-z", "HEAD")))
    changed.update(
        null_git_paths(("git", "ls-files", "--others", "--exclude-standard", "-z"))
    )
    files = []
    for relative in sorted(path for path in changed if is_story_source(path)):
        absolute = ROOT / relative
        if absolute.is_file() and output_dir not in absolute.parents:
            files.append(
                {
                    "path": relative,
                    "size_bytes": absolute.stat().st_size,
                    "sha256": sha256_file(absolute),
                }
            )
    return files


def source_snapshot(output_dir: Path) -> dict[str, Any]:
    files = current_source_files(output_dir)
    return {
        "generated_at_utc": utc_now(),
        "scope": "Story 39.2 implementation, tests, deployment configuration, and evidence tooling",
        "git_sha": git_head(),
        "baseline_commit": BASELINE_COMMIT,
        "working_tree_dirty": bool(files),
        "source_snapshot_sha256": sha256_json(files),
        "file_count": len(files),
        "files": files,
    }


def collect_command_registry() -> dict[str, Any]:
    module_name = "_story_39_2_command_registry_snapshot"
    module = sys.modules.get(module_name)
    if module is None:
        source = BACKEND_ROOT / "app" / "services" / "command_registry.py"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise SystemExit("无法加载命令注册表源码")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
    command_definitions = module.COMMAND_DEFINITIONS

    registry = {}
    for name, definition in sorted(command_definitions.items()):
        registry[name] = {
            "parameter_schema": definition.parameter_schema.model_json_schema(),
            "minimum_risk": definition.minimum_risk,
            "requires_approval": definition.requires_approval,
            "description": definition.description,
            "entrypoints": sorted(definition.entrypoints),
            "test_ids": list(definition.test_ids),
        }

    services_root = BACKEND_ROOT / "app" / "services"
    callers = []
    for source_file in services_root.rglob("*.py"):
        tree = ast.parse(
            source_file.read_text(encoding="utf-8"), filename=str(source_file)
        )
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "control_device_regulation"
            for node in ast.walk(tree)
        ):
            callers.append(source_file.relative_to(services_root).as_posix())

    actual_entrypoints = {
        name: value["entrypoints"] for name, value in registry.items()
    }
    errors = []
    if actual_entrypoints != EXPECTED_COMMAND_ENTRYPOINTS:
        errors.append(
            "registered command entrypoints differ from the trusted inventory"
        )
    if sorted(callers) != [
        "device_control_service.py",
        "execution_service.py",
        "load_regulation.py",
    ]:
        errors.append("device regulation callers differ from the trusted inventory")
    for name, value in registry.items():
        if not value["test_ids"] or not value["entrypoints"]:
            errors.append(f"{name} has no test ID or execution entrypoint")
        if value["minimum_risk"] == "critical" and not value["requires_approval"]:
            errors.append(f"{name} is critical but does not require approval")

    return {
        "registry": registry,
        "device_regulation_callers": sorted(callers),
        "validation": "PASS" if not errors else "FAIL",
        "errors": errors,
    }


def pytest_metrics(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise SystemExit("后端 JUnit 不包含 testsuite")
    top = root if root.tag == "testsuites" else suites[0]
    return {
        "tests": int(
            top.attrib.get("tests", sum(int(s.attrib.get("tests", 0)) for s in suites))
        ),
        "failures": int(
            top.attrib.get(
                "failures", sum(int(s.attrib.get("failures", 0)) for s in suites)
            )
        ),
        "errors": int(
            top.attrib.get(
                "errors", sum(int(s.attrib.get("errors", 0)) for s in suites)
            )
        ),
        "skipped": int(
            top.attrib.get(
                "skipped", sum(int(s.attrib.get("skipped", 0)) for s in suites)
            )
        ),
    }


def pytest_passed(metrics: dict[str, int]) -> bool:
    return metrics["tests"] > 0 and all(
        metrics[key] == 0 for key in ("failures", "errors", "skipped")
    )


def vitest_metrics(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "test_files": int(report.get("numTotalTestSuites", 0)),
        "tests": int(report.get("numTotalTests", 0)),
        "passed": int(report.get("numPassedTests", 0)),
        "failed": int(report.get("numFailedTests", 0)),
        "pending": int(report.get("numPendingTests", 0)),
        "success": report.get("success") is True,
    }


def vitest_passed(metrics: dict[str, Any]) -> bool:
    return (
        metrics["tests"] > 0
        and metrics["passed"] == metrics["tests"]
        and metrics["failed"] == 0
        and metrics["pending"] == 0
        and metrics["success"] is True
    )


def playwright_metrics(path: Path) -> dict[str, Any]:
    stats = json.loads(path.read_text(encoding="utf-8"))["stats"]
    return {
        "expected": int(stats.get("expected", 0)),
        "unexpected": int(stats.get("unexpected", 0)),
        "skipped": int(stats.get("skipped", 0)),
        "flaky": int(stats.get("flaky", 0)),
        "duration_ms": float(stats.get("duration", 0)),
    }


def playwright_passed(metrics: dict[str, Any]) -> bool:
    return (
        metrics["expected"] > 0
        and metrics["unexpected"] == 0
        and metrics["skipped"] == 0
        and metrics["flaky"] == 0
    )


def collect_environment() -> dict[str, Any]:
    values = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "node": first_version(("node", "--version")),
        "npm": first_version(("npm", "--version")),
        "docker": first_version(
            ("docker", "version", "--format", "{{.Server.Version}}")
        ),
        "git": first_version(("git", "--version")),
        "topology": "local tests plus isolated Docker Nginx artifact and browser",
        "production_equivalent": False,
    }
    return {
        "generated_at_utc": utc_now(),
        "fingerprint_sha256": sha256_json(values),
        "values": values,
    }


def first_version(command: tuple[str, ...]) -> str:
    result = run_result(command)
    if result["exit_code"] != 0:
        return "unavailable"
    return result["output"].splitlines()[0] if result["output"] else "unknown"


def quality_results() -> list[dict[str, Any]]:
    records = []
    for command_id, cwd, command in QUALITY_COMMANDS:
        result = run_result(command, cwd=cwd, timeout=900)
        records.append(
            {
                "id": command_id,
                "cwd": cwd.relative_to(ROOT).as_posix() or ".",
                "command": command_text(command),
                "exit_code": result["exit_code"],
                "result": "PASS" if result["exit_code"] == 0 else "FAIL",
                "output": result["output"],
            }
        )
    return records


def node_test_metrics(output: str, *, exit_code: int) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in output.splitlines():
        match = re.fullmatch(r"(?:#|ℹ)\s+(tests|pass|fail)\s+(\d+)", line.strip())
        if match:
            values[match.group(1)] = int(match.group(2))
    return {
        "tests": values.get("tests", 0),
        "passed": values.get("pass", 0),
        "failed": values.get("fail", max(exit_code, 1)),
    }


def proxy_test_result() -> dict[str, Any]:
    command = ("npm", "test")
    started = utc_now()
    result = run_result(command, cwd=PROXY_ROOT, timeout=120)
    metrics = node_test_metrics(result["output"], exit_code=result["exit_code"])
    return {
        "started_at_utc": started,
        "ended_at_utc": utc_now(),
        "command": command_text(command),
        "exit_code": result["exit_code"],
        "result": "PASS"
        if result["exit_code"] == 0
        and metrics["tests"] > 0
        and metrics["passed"] == metrics["tests"]
        else "FAIL",
        "metrics": metrics,
        "output": result["output"],
    }


def reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def http_request(
    url: str, *, method: str = "GET", headers: dict[str, str] | None = None
) -> dict[str, Any]:
    request = Request(
        url,
        method=method,
        headers={"User-Agent": "story-39-2-evidence", **(headers or {})},
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        response = exc
    return {
        "status": int(response.status),
        "headers": {name.lower(): value for name, value in response.headers.items()},
        "body": response.read().decode("utf-8", errors="replace"),
    }


@contextmanager
def live_uvicorn():
    port = reserve_loopback_port()
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DEBUG": "false",
            "CORS_ORIGINS": "https://dcim.example.com",
            "FAULT_TREE_HMAC_KEY": "evidence-only-test-key-32-characters",
        }
    )
    command = (
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--lifespan",
        "off",
        "--log-level",
        "warning",
    )
    process = subprocess.Popen(
        resolved_command(command),
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = datetime.now(timezone.utc) + timedelta(seconds=30)
        while datetime.now(timezone.utc) < deadline:
            if process.poll() is not None:
                raise SystemExit(f"Uvicorn 在监听前退出，状态码 {process.returncode}")
            try:
                http_request(base_url + "/api/health")
                break
            except Exception:
                import time

                time.sleep(0.25)
        else:
            raise SystemExit("Uvicorn 未在 30 秒内监听")
        yield base_url, command
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def collect_backend_cors_runtime() -> tuple[dict[str, Any], tuple[str, ...]]:
    with live_uvicorn() as (base_url, command):
        allowed = http_request(
            base_url + "/api/health",
            method="OPTIONS",
            headers={
                "Origin": "https://dcim.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        rejected = http_request(
            base_url + "/api/health",
            method="OPTIONS",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        simple = http_request(
            base_url + "/api/health",
            headers={"Origin": "https://evil.example"},
        )

    def cors_headers(response: dict[str, Any]) -> dict[str, str]:
        return {
            name: response["headers"][name]
            for name in (
                "access-control-allow-origin",
                "access-control-allow-credentials",
                "access-control-allow-methods",
                "access-control-allow-headers",
                "vary",
            )
            if name in response["headers"]
        }

    passed = (
        allowed["status"] == 200
        and allowed["headers"].get("access-control-allow-origin")
        == "https://dcim.example.com"
        and allowed["headers"].get("access-control-allow-credentials") == "true"
        and allowed["headers"].get("access-control-allow-origin") != "*"
        and rejected["status"] == 400
        and "access-control-allow-origin" not in rejected["headers"]
        and simple["status"] == 200
        and "access-control-allow-origin" not in simple["headers"]
    )
    return (
        {
            "generated_at_utc": utc_now(),
            "cases": {
                "allowed_preflight": {
                    "status": allowed["status"],
                    "headers": cors_headers(allowed),
                },
                "rejected_preflight": {
                    "status": rejected["status"],
                    "headers": cors_headers(rejected),
                },
                "rejected_simple": {
                    "status": simple["status"],
                    "headers": cors_headers(simple),
                },
            },
            "result": "PASS" if passed else "FAIL",
        },
        command,
    )


def inspect_image(reference: str) -> dict[str, Any]:
    raw = run_checked(("docker", "image", "inspect", reference), timeout=30)
    inspected = json.loads(raw)[0]
    labels = inspected.get("Config", {}).get("Labels", {}) or {}
    return {
        "tag": reference,
        "id": inspected["Id"],
        "git_sha_label": labels.get(GIT_SHA_LABEL),
        "source_snapshot_label": labels.get(SOURCE_SNAPSHOT_LABEL),
    }


def build_frontend_image(git_sha: str, source_hash: str) -> dict[str, Any]:
    command = (
        "docker",
        "build",
        "--provenance=false",
        "--build-arg",
        f"VCS_REF={git_sha}",
        "--build-arg",
        f"STORY_39_2_SOURCE_SNAPSHOT={source_hash}",
        "-t",
        IMAGE_TAG,
        "frontend",
    )
    result = run_result(command, cwd=ROOT, timeout=1200)
    return {
        "id": "FRONTEND-IMAGE",
        "cwd": ".",
        "command": command_text(command),
        "result": "PASS" if result["exit_code"] == 0 else "FAIL",
        "output": result["output"],
    }


def docker_exact_exists(kind: str, name: str) -> bool:
    if kind == "container":
        output = run_checked(
            (
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^/{name}$",
                "--format",
                "{{.Names}}",
            )
        )
    else:
        output = run_checked(
            (
                "docker",
                "network",
                "ls",
                "--filter",
                f"name=^{name}$",
                "--format",
                "{{.Name}}",
            )
        )
    return output.strip() == name


@contextmanager
def nginx_artifact(image_tag: str):
    suffix = f"{os.getpid()}-{socket.socket().fileno()}"
    network = f"story-39-2-evidence-{suffix}"
    upstream = f"story-39-2-upstream-{suffix}"
    nginx = f"story-39-2-nginx-{suffix}"
    created: list[tuple[str, str]] = []
    try:
        if any(
            docker_exact_exists(kind, name)
            for kind, name in (
                ("network", network),
                ("container", upstream),
                ("container", nginx),
            )
        ):
            raise SystemExit("证据容器名称冲突")
        run_checked(("docker", "network", "create", network), timeout=30)
        created.append(("network", network))
        run_checked(
            (
                "docker",
                "run",
                "-d",
                "--name",
                upstream,
                "--network",
                network,
                "--network-alias",
                "backend",
                "nginx:alpine",
                "sh",
                "-c",
                "sed -i 's/listen       80;/listen 8080;/' /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'",
            ),
            timeout=60,
        )
        created.append(("container", upstream))
        run_checked(
            (
                "docker",
                "run",
                "-d",
                "--name",
                nginx,
                "--network",
                network,
                "-p",
                "127.0.0.1::80",
                image_tag,
            ),
            timeout=60,
        )
        created.append(("container", nginx))
        port_output = run_checked(("docker", "port", nginx, "80/tcp"))
        port = int(port_output.rsplit(":", 1)[1])
        yield f"http://127.0.0.1:{port}"
    finally:
        for kind, name in reversed(created):
            if kind == "container" and docker_exact_exists(kind, name):
                run_result(("docker", "rm", "-f", name), timeout=30)
            elif kind == "network" and docker_exact_exists(kind, name):
                run_result(("docker", "network", "rm", name), timeout=30)


def http_response(url: str) -> dict[str, Any]:
    response = http_request(url)
    header_names = (
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cache-Control",
        "Content-Type",
    )
    return {
        "status": response["status"],
        "headers": {
            name.lower(): response["headers"].get(name.lower(), "")
            for name in header_names
        },
        "body": response["body"],
    }


def wait_for_nginx(base_url: str) -> dict[str, Any]:
    deadline = datetime.now(timezone.utc) + timedelta(seconds=30)
    last_error: Exception | None = None
    while datetime.now(timezone.utc) < deadline:
        try:
            return http_response(base_url + "/")
        except Exception as exc:  # pragma: no cover - transient Docker startup path
            last_error = exc
            import time

            time.sleep(0.25)
    raise SystemExit(f"Nginx 制品未就绪: {last_error}")


def security_headers_pass(headers: dict[str, str]) -> bool:
    csp = headers.get("content-security-policy", "")
    directives = {
        parts[0]: set(parts[1:])
        for directive in csp.split(";")
        if (parts := directive.strip().split())
    }
    return (
        directives.get("default-src") == {"'self'"}
        and directives.get("script-src") == {"'self'"}
        and directives.get("object-src") == {"'none'"}
        and directives.get("base-uri") == {"'self'"}
        and directives.get("frame-ancestors") == {"'none'"}
        and directives.get("form-action") == {"'self'"}
        and "'self'" in directives.get("connect-src", set())
        and headers.get("x-content-type-options") == "nosniff"
        and headers.get("x-frame-options") == "DENY"
        and headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        and bool(headers.get("permissions-policy"))
    )


def collect_nginx_runtime(base_url: str, image: dict[str, Any]) -> dict[str, Any]:
    root = wait_for_nginx(base_url)
    asset_match = re.search(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', root["body"])
    if not asset_match:
        raise SystemExit("Nginx index.html 未引用构建后的 JS/CSS")
    cases = {
        "root": root,
        "asset": http_response(base_url + asset_match.group(1)),
        "spa_fallback": http_response(base_url + "/history/nonexistent-route"),
        "api_error": http_response(base_url + "/api/"),
        "static_404": http_response(base_url + "/assets/does-not-exist.js"),
    }
    sanitized_cases = {}
    expected_status = {
        "root": 200,
        "asset": 200,
        "spa_fallback": 200,
        "api_error": 404,
        "static_404": 404,
    }
    for name, response in cases.items():
        sanitized_cases[name] = {
            "status": response["status"],
            "headers": response["headers"],
            "security_headers": "PASS"
            if security_headers_pass(response["headers"])
            else "FAIL",
        }
    passed = all(
        value["status"] == expected_status[name] and value["security_headers"] == "PASS"
        for name, value in sanitized_cases.items()
    )
    return {
        "generated_at_utc": utc_now(),
        "image": image,
        "asset_path": asset_match.group(1),
        "cases": sanitized_cases,
        "result": "PASS" if passed else "FAIL",
    }


def run_nginx_and_browser(
    output_dir: Path, image: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    browser_path = output_dir / "nginx-browser-results.json"
    with nginx_artifact(IMAGE_TAG) as base_url:
        nginx_result = collect_nginx_runtime(base_url, image)
        env = os.environ.copy()
        env.update(
            {
                "CI": "1",
                "STORY_39_2_BASE_URL": base_url,
                "PLAYWRIGHT_JSON_OUTPUT_FILE": str(browser_path),
            }
        )
        command = (
            "npx",
            "playwright",
            "test",
            "--config=e2e/story-39-2.playwright.config.ts",
            "--reporter=json",
        )
        result = run_result(command, cwd=ROOT, env=env, timeout=180)
    if result["exit_code"] != 0 or not browser_path.is_file():
        raise SystemExit(f"Nginx 浏览器验证失败\n{result['output']}")
    return nginx_result, {
        "id": "NGINX-BROWSER",
        "cwd": ".",
        "command": command_text(command),
        "result": "PASS",
        "output": result["output"],
    }


def media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".xml": "application/xml",
    }.get(path.suffix, "application/yaml")


def artifact(output_dir: Path, name: str) -> dict[str, Any]:
    path = output_dir / name
    purpose, criteria = ARTIFACT_SPECS[name]
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "media_type": media_type(path),
        "purpose": purpose,
        "acceptance_criteria": criteria,
    }


def resolve_artifact_path(output_dir: Path, manifest_path: str) -> Path:
    candidate = (ROOT / manifest_path).resolve()
    expected_root = output_dir.resolve()
    if candidate.parent != expected_root:
        raise SystemExit(f"非法证据路径: {manifest_path}")
    return candidate


def load_trusted_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_SOURCE.read_text(encoding="utf-8"))


def validate_registry_snapshot(output_dir: Path) -> None:
    path = output_dir / "command-registry-snapshot.json"
    recorded = json.loads(path.read_text(encoding="utf-8"))
    current = collect_command_registry()
    if recorded != current:
        raise SystemExit("命令注册表快照与当前运行时不一致")
    if current["validation"] != "PASS":
        raise SystemExit(f"命令注册表漂移检查失败: {current['errors']}")


def validate_source_binding(output_dir: Path) -> dict[str, Any]:
    recorded = json.loads(
        (output_dir / "source-file-hashes.json").read_text(encoding="utf-8")
    )
    current_files = current_source_files(output_dir)
    if recorded.get("files") != current_files:
        raise SystemExit("源码快照未绑定当前完整文件集合")
    if recorded.get("working_tree_dirty") is not bool(current_files):
        raise SystemExit("源码快照工作区状态与当前文件集合不一致")
    if recorded.get("file_count") != len(current_files) or recorded.get(
        "source_snapshot_sha256"
    ) != sha256_json(current_files):
        raise SystemExit("源码快照数量或哈希不一致")
    if recorded.get("baseline_commit") != BASELINE_COMMIT:
        raise SystemExit("源码快照 Git 绑定不一致")
    recorded_sha = recorded.get("git_sha")
    current_sha = git_head()
    if not isinstance(recorded_sha, str):
        raise SystemExit("源码快照 Git 绑定不一致")
    if recorded_sha != current_sha:
        if not git_is_ancestor(recorded_sha, current_sha):
            raise SystemExit("源码快照提交不是当前 HEAD 的祖先")
        try:
            output_prefix = output_dir.relative_to(ROOT).as_posix().rstrip("/") + "/"
        except ValueError as exc:
            raise SystemExit("证据目录不在仓库内") from exc
        changed_after_snapshot = null_git_paths(
            ("git", "diff", "--name-only", "-z", recorded_sha, current_sha)
        )
        unexpected = sorted(
            path
            for path in changed_after_snapshot
            if not path.startswith(output_prefix)
        )
        if unexpected:
            raise SystemExit(f"证据生成后存在非证据源码提交: {unexpected}")
    return recorded


def validate_changeset_binding(
    manifest: dict[str, Any], snapshot: dict[str, Any]
) -> None:
    expected = {
        "git_sha": snapshot["git_sha"],
        "baseline_commit": snapshot["baseline_commit"],
        "working_tree_dirty": snapshot["working_tree_dirty"],
        "changeset_id": f"{snapshot['git_sha']}+{snapshot['source_snapshot_sha256']}",
        "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
        "source_file_count": snapshot["file_count"],
    }
    if manifest.get("changeset") != expected:
        raise SystemExit("manifest changeset 未绑定当前源码快照")


def validate_acceptance_mapping(manifest: dict[str, Any]) -> None:
    actual = {
        Path(item["path"]).name: (item["purpose"], item["acceptance_criteria"])
        for item in manifest["artifacts"]
    }
    if actual != ARTIFACT_SPECS:
        raise SystemExit("manifest 未遵守受信任证据映射")
    for ac in ACCEPTANCE_CRITERIA:
        expected = sorted(
            item["path"]
            for item in manifest["artifacts"]
            if ac in item["acceptance_criteria"]
        )
        actual_paths = sorted(manifest["acceptance_criteria"][ac]["evidence"])
        if actual_paths != expected:
            raise SystemExit(f"{ac} 证据映射不是双向完整映射")


def validate_execution_window(manifest: dict[str, Any], output_dir: Path) -> None:
    started = parse_datetime(manifest["execution"]["started_at_utc"])
    ended = parse_datetime(manifest["execution"]["ended_at_utc"])
    if ended <= started or ended - started > MAX_EXECUTION_WINDOW:
        raise SystemExit("证据执行窗口无效或过长")
    tolerance = timedelta(seconds=5)
    for name in ARTIFACT_SPECS:
        modified = datetime.fromtimestamp(
            (output_dir / name).stat().st_mtime, timezone.utc
        )
        if modified < started - tolerance or modified > ended + tolerance:
            raise SystemExit(f"证据不在执行窗口内: {name}")


def validate_execution_commands(manifest: dict[str, Any]) -> None:
    commands = manifest["execution"]["commands"]
    command_ids = [item["id"] for item in commands]
    if (
        len(command_ids) != len(set(command_ids))
        or set(command_ids) != REQUIRED_COMMAND_IDS
    ):
        raise SystemExit("manifest 执行命令集合与受信任门禁不一致")
    if any(item["result"] != "PASS" for item in commands):
        raise SystemExit("manifest 包含未通过的执行命令")

    command_by_id = {item["id"]: item for item in commands}
    expected_test_files = {
        "PYTEST-SECURITY": PYTEST_TEST_FILES,
        "VITEST-XSS": VITEST_TEST_FILES,
    }
    for command_id, test_files in expected_test_files.items():
        command = command_by_id[command_id]["command"].replace("\\", "/")
        if any(test_file not in command for test_file in test_files):
            raise SystemExit(f"{command_id} 命令未覆盖受信任必需测试集合")


def validate_test_file_bindings(output_dir: Path) -> None:
    junit_root = ET.parse(output_dir / "pytest-security.xml").getroot()
    classnames = {
        case.attrib.get("classname", "") for case in junit_root.iter("testcase")
    }
    for test_file in PYTEST_TEST_FILES:
        module = test_file.removesuffix(".py").replace("/", ".")
        if not any(module in classname for classname in classnames):
            raise SystemExit(f"后端 JUnit 缺少必需测试文件: {test_file}")

    vitest = json.loads(
        (output_dir / "vitest-xss-results.json").read_text(encoding="utf-8")
    )
    names = {
        str(item.get("name", "")).replace("\\", "/")
        for item in vitest.get("testResults", [])
    }
    for test_file in VITEST_TEST_FILES:
        if not any(name.endswith(test_file) for name in names):
            raise SystemExit(f"Vitest 报告缺少必需测试文件: {test_file}")


def validate_quality(recorded: dict[str, Any]) -> None:
    current = quality_results()
    recorded_results = recorded.get("results", [])
    if [(item["id"], item["result"]) for item in current] != [
        (item["id"], item["result"]) for item in recorded_results
    ]:
        raise SystemExit("质量命令重新执行结果不一致")
    if any(item["result"] != "PASS" for item in current):
        raise SystemExit("质量命令未全部通过")


def validate_environment(manifest: dict[str, Any], output_dir: Path) -> None:
    recorded = json.loads(
        (output_dir / "environment-fingerprint.json").read_text(encoding="utf-8")
    )
    current = collect_environment()
    if (
        recorded["values"] != current["values"]
        or recorded["fingerprint_sha256"] != current["fingerprint_sha256"]
    ):
        raise SystemExit("环境指纹与当前运行环境不一致")
    environment = manifest["environment"]
    if environment["fingerprint_sha256"] != recorded["fingerprint_sha256"]:
        raise SystemExit("manifest 环境指纹绑定不一致")


def validate_artifacts(manifest: dict[str, Any], output_dir: Path) -> None:
    expected_names = set(ARTIFACT_SPECS)
    artifact_names = [Path(item["path"]).name for item in manifest["artifacts"]]
    actual_names = set(artifact_names)
    if actual_names != expected_names or len(artifact_names) != len(expected_names):
        raise SystemExit("manifest 证据文件集合不完整")
    for item in manifest["artifacts"]:
        path = resolve_artifact_path(output_dir, item["path"])
        if not path.is_file() or path.stat().st_size <= 0:
            raise SystemExit(f"证据文件缺失或为空: {item['path']}")
        if item["size_bytes"] != path.stat().st_size or item["sha256"] != sha256_file(
            path
        ):
            raise SystemExit(f"证据大小或哈希不一致: {item['path']}")
    if sha256_file(output_dir / "manifest.schema.json") != sha256_file(SCHEMA_SOURCE):
        raise SystemExit("证据包 Schema 与受信任仓库契约不一致")


def generate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    commands = []

    snapshot = source_snapshot(output_dir)
    write_json(output_dir / "source-file-hashes.json", snapshot)
    registry = collect_command_registry()
    write_json(output_dir / "command-registry-snapshot.json", registry)

    pytest_command = (
        sys.executable,
        "-m",
        "pytest",
        *PYTEST_TEST_FILES,
        "-q",
        f"--junitxml={output_dir / 'pytest-security.xml'}",
    )
    pytest_result = run_result(pytest_command, cwd=BACKEND_ROOT, timeout=900)
    commands.append(
        {
            "id": "PYTEST-SECURITY",
            "cwd": "backend",
            "command": command_text(pytest_command),
            "result": "PASS" if pytest_result["exit_code"] == 0 else "FAIL",
        }
    )
    if pytest_result["exit_code"] != 0:
        raise SystemExit(f"后端安全测试失败\n{pytest_result['output']}")

    vitest_command = (
        "npx",
        "vitest",
        "--run",
        *VITEST_TEST_FILES,
        "--reporter=json",
        f"--outputFile={output_dir / 'vitest-xss-results.json'}",
    )
    vitest_result = run_result(vitest_command, cwd=FRONTEND_ROOT, timeout=600)
    commands.append(
        {
            "id": "VITEST-XSS",
            "cwd": "frontend",
            "command": command_text(vitest_command),
            "result": "PASS" if vitest_result["exit_code"] == 0 else "FAIL",
        }
    )
    if vitest_result["exit_code"] != 0:
        raise SystemExit(f"前端 XSS 测试失败\n{vitest_result['output']}")

    proxy = proxy_test_result()
    write_json(output_dir / "proxy-security-results.json", proxy)
    commands.append(
        {
            "id": "PROXY-SECURITY",
            "cwd": "proxy",
            "command": proxy["command"],
            "result": proxy["result"],
        }
    )
    if proxy["result"] != "PASS":
        raise SystemExit("Node 代理安全测试失败")

    backend_cors, backend_cors_command = collect_backend_cors_runtime()
    write_json(output_dir / "backend-cors-runtime-results.json", backend_cors)
    commands.append(
        {
            "id": "BACKEND-CORS-RUNTIME",
            "cwd": "backend",
            "command": command_text(backend_cors_command),
            "result": backend_cors["result"],
        }
    )
    if backend_cors["result"] != "PASS":
        raise SystemExit("实际 Uvicorn CORS 响应矩阵失败")

    image_command = build_frontend_image(
        snapshot["git_sha"], snapshot["source_snapshot_sha256"]
    )
    commands.append(manifest_command(image_command))
    if image_command["result"] != "PASS":
        raise SystemExit(f"前端 Nginx 镜像构建失败\n{image_command['output']}")
    image = inspect_image(IMAGE_TAG)
    if (
        image["git_sha_label"] != snapshot["git_sha"]
        or image["source_snapshot_label"] != snapshot["source_snapshot_sha256"]
    ):
        raise SystemExit("前端镜像未绑定当前 Git 与源码快照")

    nginx_result, browser_command = run_nginx_and_browser(output_dir, image)
    write_json(output_dir / "nginx-security-results.json", nginx_result)
    commands.append(manifest_command(browser_command))
    if nginx_result["result"] != "PASS":
        raise SystemExit("实际 Nginx 响应矩阵失败")

    quality = {"generated_at_utc": utc_now(), "results": quality_results()}
    write_json(output_dir / "quality-command-results.json", quality)
    commands.extend(manifest_command(item) for item in quality["results"])
    if any(item["result"] != "PASS" for item in quality["results"]):
        raise SystemExit("质量命令未全部通过")

    environment = collect_environment()
    write_json(output_dir / "environment-fingerprint.json", environment)
    shutil.copyfile(SCHEMA_SOURCE, output_dir / "manifest.schema.json")

    metrics = {
        "command_registry": {
            "commands": len(registry["registry"]),
            "entrypoints": sum(
                len(value["entrypoints"]) for value in registry["registry"].values()
            ),
            "validation": registry["validation"],
        },
        "pytest": pytest_metrics(output_dir / "pytest-security.xml"),
        "vitest": vitest_metrics(output_dir / "vitest-xss-results.json"),
        "proxy": proxy["metrics"],
        "backend_cors": {
            "cases": len(backend_cors["cases"]),
            "result": backend_cors["result"],
        },
        "nginx": {
            "cases": len(nginx_result["cases"]),
            "result": nginx_result["result"],
        },
        "playwright": playwright_metrics(output_dir / "nginx-browser-results.json"),
        "quality": {
            "commands": len(quality["results"]),
            "passed": sum(r["result"] == "PASS" for r in quality["results"]),
        },
        "frontend_image": image,
    }
    all_passed = (
        registry["validation"] == "PASS"
        and pytest_passed(metrics["pytest"])
        and vitest_passed(metrics["vitest"])
        and proxy["result"] == "PASS"
        and backend_cors["result"] == "PASS"
        and nginx_result["result"] == "PASS"
        and playwright_passed(metrics["playwright"])
        and metrics["quality"]["passed"] == metrics["quality"]["commands"]
    )
    artifacts = [artifact(output_dir, name) for name in ARTIFACT_SPECS]
    acceptance = {
        ac: {
            "result": "PASS" if all_passed else "BLOCKED",
            "evidence": [
                item["path"] for item in artifacts if ac in item["acceptance_criteria"]
            ],
        }
        for ac in ACCEPTANCE_CRITERIA
    }
    ended_at = utc_now()
    manifest = {
        "schema_version": 1,
        "story": {
            "id": "39.2",
            "key": "39-2-command-xss-and-production-credential-hardening",
            "title": "Command, XSS, and production credential hardening",
        },
        "changeset": {
            "git_sha": snapshot["git_sha"],
            "baseline_commit": BASELINE_COMMIT,
            "working_tree_dirty": snapshot["working_tree_dirty"],
            "changeset_id": f"{snapshot['git_sha']}+{snapshot['source_snapshot_sha256']}",
            "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
            "source_file_count": snapshot["file_count"],
        },
        "environment": {
            "id": ENVIRONMENT_ID,
            "kind": ENVIRONMENT_KIND,
            "fingerprint_sha256": environment["fingerprint_sha256"],
            "topology": environment["values"]["topology"],
            "production_equivalent": False,
        },
        "tools": {
            "python": first_version((sys.executable, "--version")),
            "pytest": first_version((sys.executable, "-m", "pytest", "--version")),
            "ruff": first_version(("ruff", "--version")),
            "node": first_version(("node", "--version")),
            "npm": first_version(("npm", "--version")),
            "playwright": first_version(("npx", "playwright", "--version")),
            "docker": first_version(("docker", "--version")),
            "git": first_version(("git", "--version")),
            "jsonschema": importlib.metadata.version("jsonschema"),
        },
        "execution": {
            "started_at_utc": started_at,
            "ended_at_utc": ended_at,
            "operator": "proecheng (Codex-assisted)",
            "commands": commands,
        },
        "artifacts": artifacts,
        "metrics": metrics,
        "acceptance_criteria": acceptance,
        "limitations": [
            "Validation used a local Docker Desktop topology with a stub API upstream; it is not a production deployment.",
            "Production credential custody, rotation, TLS, and encryption at rest remain in Story 39.9.",
        ],
        "exceptions": [],
        "decisions": [
            "Unknown commands and protected-command self-approval are non-waivable.",
            "Story 39.2 completion does not authorize production deployment or unblock Epic 39.",
        ],
        "ownership": {"maintainer": "proecheng"},
        "governance": {
            "mode": "single-maintainer",
            "maintainer": "proecheng",
            "independent_approval_required": False,
            "decision": "VERIFIED" if all_passed else "BLOCKED",
            "decided_at_utc": ended_at,
            "basis": [
                "All Story 39.2 acceptance criteria are evaluated from machine-readable evidence.",
                "The manifest, artifact hashes, runtime registry, source snapshot, tests, and actual Nginx responses pass validation.",
            ],
        },
        "story_gate": {
            "status": "PASS" if all_passed else "BLOCKED",
            "blockers": [] if all_passed else ["Evidence validation failed."],
        },
        "epic_production_gate": {
            "status": "BLOCKED",
            "blockers": [
                "Epic 39 Stories 39.3 through 39.12 and the refreshed NFR assessment are incomplete.",
                "Production-equivalent deployment, field UAT, and operational approval remain outside Story 39.2.",
            ],
        },
    }
    (output_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    validate(argparse.Namespace(output=str(output_dir)))


def validate(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    manifest_path = output_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise SystemExit("缺少 manifest.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        load_trusted_schema(), format_checker=jsonschema.FormatChecker()
    ).validate(manifest)
    validate_governance(manifest)
    validate_artifacts(manifest, output_dir)
    validate_acceptance_mapping(manifest)
    validate_execution_window(manifest, output_dir)
    validate_execution_commands(manifest)
    validate_test_file_bindings(output_dir)
    validate_registry_snapshot(output_dir)
    snapshot = validate_source_binding(output_dir)
    validate_changeset_binding(manifest, snapshot)
    validate_environment(manifest, output_dir)

    pytest_result = pytest_metrics(output_dir / "pytest-security.xml")
    vitest_result = vitest_metrics(output_dir / "vitest-xss-results.json")
    proxy = json.loads(
        (output_dir / "proxy-security-results.json").read_text(encoding="utf-8")
    )
    backend_cors = json.loads(
        (output_dir / "backend-cors-runtime-results.json").read_text(encoding="utf-8")
    )
    nginx = json.loads(
        (output_dir / "nginx-security-results.json").read_text(encoding="utf-8")
    )
    browser = playwright_metrics(output_dir / "nginx-browser-results.json")
    if not pytest_passed(pytest_result) or not vitest_passed(vitest_result):
        raise SystemExit("后端或前端原始测试报告未通过严格门禁")
    if proxy.get("result") != "PASS" or proxy["metrics"].get("tests", 0) <= 0:
        raise SystemExit("代理原始测试报告未通过严格门禁")
    current_backend_cors, _ = collect_backend_cors_runtime()
    if backend_cors.get("result") != "PASS" or current_backend_cors[
        "cases"
    ] != backend_cors.get("cases"):
        raise SystemExit("实际 Uvicorn CORS 响应矩阵重新验证结果不一致")
    if nginx.get("result") != "PASS" or not all(
        case.get("security_headers") == "PASS"
        for case in nginx.get("cases", {}).values()
    ):
        raise SystemExit("Nginx 原始响应矩阵未通过严格门禁")
    if not playwright_passed(browser):
        raise SystemExit("Nginx 浏览器原始报告未通过严格门禁")

    image = inspect_image(IMAGE_TAG)
    if image != nginx["image"]:
        raise SystemExit("Nginx 证据引用的镜像不是当前本地制品")
    if (
        image["git_sha_label"] != snapshot["git_sha"]
        or image["source_snapshot_label"] != snapshot["source_snapshot_sha256"]
    ):
        raise SystemExit("Nginx 镜像标签未绑定当前源码快照")
    with nginx_artifact(IMAGE_TAG) as base_url:
        current_nginx = collect_nginx_runtime(base_url, image)
    if (
        current_nginx["cases"] != nginx["cases"]
        or current_nginx["result"] != nginx["result"]
    ):
        raise SystemExit("实际 Nginx 制品重新验证结果不一致")

    quality = json.loads(
        (output_dir / "quality-command-results.json").read_text(encoding="utf-8")
    )
    validate_quality(quality)
    current_registry = collect_command_registry()
    quality_metrics = {
        "commands": len(quality["results"]),
        "passed": sum(item["result"] == "PASS" for item in quality["results"]),
    }
    expected_metrics = {
        "command_registry": {
            "commands": len(current_registry["registry"]),
            "entrypoints": sum(
                len(value["entrypoints"])
                for value in current_registry["registry"].values()
            ),
            "validation": current_registry["validation"],
        },
        "pytest": pytest_result,
        "vitest": vitest_result,
        "proxy": proxy["metrics"],
        "backend_cors": {
            "cases": len(backend_cors["cases"]),
            "result": backend_cors["result"],
        },
        "nginx": {"cases": len(nginx["cases"]), "result": nginx["result"]},
        "playwright": browser,
        "quality": quality_metrics,
        "frontend_image": image,
    }
    if manifest["metrics"] != expected_metrics:
        raise SystemExit("manifest metrics 与原始证据重算结果不一致")
    if any(
        value["result"] != "PASS" for value in manifest["acceptance_criteria"].values()
    ):
        raise SystemExit("并非所有 Story 39.2 验收标准均通过")
    if manifest["story_gate"]["status"] != "PASS":
        raise SystemExit("Story 39.2 证据门禁未通过")

    result = {
        "validated_at_utc": utc_now(),
        "validator": "scripts/story_39_2_evidence.py",
        "trusted_schema_sha256": sha256_file(SCHEMA_SOURCE),
        "manifest_sha256": sha256_file(manifest_path),
        "source_snapshot_sha256": snapshot["source_snapshot_sha256"],
        "artifact_count": len(manifest["artifacts"]),
        "acceptance_criteria": {ac: "PASS" for ac in ACCEPTANCE_CRITERIA},
        "story_gate": "PASS",
        "epic_production_gate": "BLOCKED",
        "result": "PASS",
    }
    write_json(output_dir / "evidence-validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    if args.command == "generate":
        generate(args)
    else:
        validate(args)


if __name__ == "__main__":
    main()
