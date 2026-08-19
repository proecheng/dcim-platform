#!/usr/bin/env python3
"""Deploy and verify the fixed Story 39.7 candidate across Docker contexts."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST_RE = re.compile(r"^\S+@sha256:([0-9a-f]{64})$")
IMAGE_ID_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PLACEHOLDER_RE = re.compile(
    r"<[^>]+>|\b(?:change[-_ ]?me|replace[-_ ]?me|todo)\b", re.IGNORECASE
)
SUPPORTED_PLATFORM = "linux/amd64"
SUPPORTED_ACTIONS = {
    "bootstrap",
    "deploy",
    "plan",
    "preflight",
    "rollback",
    "status",
    "test",
    "upgrade",
    "verify",
}
LIFECYCLE_ACTIONS = {"bootstrap", "upgrade", "rollback"}
SUPPORTED_BROWSER_CHANNELS = {
    "chrome",
    "chrome-beta",
    "chrome-dev",
    "chrome-canary",
    "msedge",
    "msedge-beta",
    "msedge-dev",
    "msedge-canary",
}
APPLICATION_IMAGE_KEYS = {
    "backend": ("DCIM_BACKEND_IMAGE", "DCIM_BACKEND_EXPECTED_ID"),
    "frontend": ("DCIM_FRONTEND_IMAGE", "DCIM_FRONTEND_EXPECTED_ID"),
}
IMAGE_KEYS = (
    "DCIM_BACKEND_IMAGE",
    "DCIM_FRONTEND_IMAGE",
    "DCIM_REDIS_IMAGE",
    "DCIM_EMQX_IMAGE",
)
REQUIRED_ENV_KEYS = (
    "CANDIDATE_GIT_SHA",
    "DCIM_BACKEND_IMAGE",
    "DCIM_BACKEND_EXPECTED_ID",
    "DCIM_FRONTEND_IMAGE",
    "DCIM_FRONTEND_EXPECTED_ID",
    "DCIM_REDIS_IMAGE",
    "DCIM_EMQX_IMAGE",
    "DCIM_DR_STATUS_VOLUME",
    "DCIM_DR_DATABASE_NETWORK",
    "DATABASE_URL",
    "SECRET_KEY",
    "CORS_ORIGINS",
    "REDIS_PASSWORD",
    "REDIS_URL",
    "MQTT_USERNAME",
    "MQTT_PASSWORD",
    "GATEWAY_SECRET_KEY",
    "VPP_API_KEY",
    "LICENSE_KEY",
    "FAULT_TREE_HMAC_KEY",
)
SENSITIVE_KEY_MARKERS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "LICENSE_KEY",
    "DATABASE_URL",
    "REDIS_URL",
)
DEFAULT_E2E_SPECS = (
    "e2e/auth.spec.ts",
    "e2e/invalid-detail-pages.spec.ts",
    "e2e/authorization-matrix.spec.ts",
    "e2e/site-isolation-websocket-authorization.spec.ts",
)
_PROTECTED_ENVIRONMENT_PATHS: set[Path] = set()
_PROTECTED_ENVIRONMENT_PATHS_LOCK = threading.Lock()


class DeploymentError(RuntimeError):
    """Raised when a fleet input or target operation cannot be trusted."""


@dataclass(frozen=True)
class E2EConfig:
    mode: str = "disabled"
    ssh_target: str | None = None
    ssh_args: tuple[str, ...] = ()
    local_port: int | None = None
    remote_port: int | None = None
    headed: bool = False
    browser_channel: str | None = None
    specs: tuple[str, ...] = DEFAULT_E2E_SPECS


@dataclass(frozen=True)
class DRConfig:
    mode: str
    compose_file: Path
    project_name: str
    secret_directory: Path
    canonical_runtime_image: str
    final_runtime_image: str
    schema_application_image: str
    repository_volume: str
    ssh_target: str | None = None
    ssh_args: tuple[str, ...] = ()
    scp_args: tuple[str, ...] = ()
    remote_directory: str | None = None


@dataclass(frozen=True)
class Target:
    name: str
    docker_context: str
    compose_file: Path
    env_file: Path
    project_name: str
    platform: str = SUPPORTED_PLATFORM
    e2e: E2EConfig = field(default_factory=E2EConfig)
    dr: DRConfig | None = None


@dataclass(frozen=True)
class Inventory:
    targets: tuple[Target, ...]
    concurrency: int
    report_directory: Path
    state_directory: Path


@dataclass(frozen=True)
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat().replace("+00:00", "Z")


def _resolve_path(value: Any, base: Path, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise DeploymentError(f"{field_name} must be a non-empty path")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DeploymentError(f"{field_name} must be a YAML object")
    return value


def _parse_port(value: Any, field_name: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if isinstance(value, bool):
        raise DeploymentError(f"{field_name} must be a TCP port")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise DeploymentError(f"{field_name} must be a TCP port") from exc
    if not 1 <= port <= 65535:
        raise DeploymentError(f"{field_name} must be between 1 and 65535")
    return port


def _build_e2e(raw: Mapping[str, Any], target_name: str) -> E2EConfig:
    mode = raw.get("mode", "disabled")
    if mode not in {"disabled", "local", "ssh-tunnel"}:
        raise DeploymentError(
            f"target {target_name} has unsupported e2e mode: {mode!r}"
        )
    local_port = _parse_port(
        raw.get("local_port"), f"target {target_name} e2e.local_port", optional=True
    )
    remote_port = _parse_port(
        raw.get("remote_port"), f"target {target_name} e2e.remote_port", optional=True
    )
    ssh_target = raw.get("ssh_target")
    ssh_args_raw = raw.get("ssh_args", [])
    if not isinstance(ssh_args_raw, list) or not all(
        isinstance(item, str) and item for item in ssh_args_raw
    ):
        raise DeploymentError(
            f"target {target_name} e2e.ssh_args must be a list of strings"
        )
    specs_raw = raw.get("specs", list(DEFAULT_E2E_SPECS))
    if (
        not isinstance(specs_raw, list)
        or not specs_raw
        or not all(isinstance(item, str) and item for item in specs_raw)
    ):
        raise DeploymentError(
            f"target {target_name} e2e.specs must be a non-empty list of paths"
        )
    browser_channel = raw.get("browser_channel")
    if (
        browser_channel is not None
        and browser_channel not in SUPPORTED_BROWSER_CHANNELS
    ):
        raise DeploymentError(
            f"target {target_name} has unsupported e2e.browser_channel: {browser_channel!r}"
        )
    if mode == "ssh-tunnel":
        if not isinstance(ssh_target, str) or not ssh_target.strip():
            raise DeploymentError(
                f"target {target_name} ssh-tunnel mode requires ssh_target"
            )
        if ssh_target.startswith("-"):
            raise DeploymentError(
                f"target {target_name} e2e.ssh_target cannot start with '-'"
            )
        if local_port is None or remote_port is None:
            raise DeploymentError(
                f"target {target_name} ssh-tunnel mode requires local_port and remote_port"
            )
    return E2EConfig(
        mode=mode,
        ssh_target=ssh_target,
        ssh_args=tuple(ssh_args_raw),
        local_port=local_port,
        remote_port=remote_port,
        headed=bool(raw.get("headed", False)),
        browser_channel=browser_channel,
        specs=tuple(specs_raw),
    )


def _string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise DeploymentError(f"{field_name} must be a list of strings")
    return tuple(value)


def _immutable_image(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or IMAGE_DIGEST_RE.fullmatch(value) is None:
        raise DeploymentError(f"{field_name} must use an immutable digest reference")
    return value


def _build_dr(
    raw: Mapping[str, Any], target_name: str, inventory_directory: Path
) -> DRConfig | None:
    if not raw:
        return None
    mode = raw.get("mode")
    if mode not in {"local", "ssh"}:
        raise DeploymentError(f"target {target_name} dr.mode must be local or ssh")
    project_name = raw.get("project_name")
    repository_volume = raw.get("repository_volume")
    if not isinstance(project_name, str) or not NAME_RE.fullmatch(project_name):
        raise DeploymentError(f"target {target_name} requires a valid dr.project_name")
    if not isinstance(repository_volume, str) or not NAME_RE.fullmatch(
        repository_volume
    ):
        raise DeploymentError(
            f"target {target_name} requires a valid dr.repository_volume"
        )
    ssh_args = _string_list(
        raw.get("ssh_args", []), f"target {target_name} dr.ssh_args"
    )
    scp_args = _string_list(
        raw.get("scp_args", []), f"target {target_name} dr.scp_args"
    )
    ssh_target = raw.get("ssh_target")
    remote_directory = raw.get("remote_directory")
    if mode == "ssh":
        if (
            not isinstance(ssh_target, str)
            or not ssh_target.strip()
            or ssh_target.startswith("-")
        ):
            raise DeploymentError(f"target {target_name} ssh DR requires ssh_target")
        if (
            not isinstance(remote_directory, str)
            or not re.fullmatch(r"/[A-Za-z0-9._/-]+", remote_directory)
            or ".." in Path(remote_directory).parts
        ):
            raise DeploymentError(
                f"target {target_name} ssh DR requires a safe absolute remote_directory"
            )
    return DRConfig(
        mode=mode,
        compose_file=_resolve_path(
            raw.get("compose_file"),
            inventory_directory,
            f"target {target_name} dr.compose_file",
        ),
        project_name=project_name,
        secret_directory=_resolve_path(
            raw.get("secret_directory"),
            inventory_directory,
            f"target {target_name} dr.secret_directory",
        ),
        canonical_runtime_image=_immutable_image(
            raw.get("canonical_runtime_image"),
            f"target {target_name} dr.canonical_runtime_image",
        ),
        final_runtime_image=_immutable_image(
            raw.get("final_runtime_image"),
            f"target {target_name} dr.final_runtime_image",
        ),
        schema_application_image=_immutable_image(
            raw.get("schema_application_image"),
            f"target {target_name} dr.schema_application_image",
        ),
        repository_volume=repository_volume,
        ssh_target=ssh_target,
        ssh_args=ssh_args,
        scp_args=scp_args,
        remote_directory=remote_directory,
    )


def load_inventory(path: Path | str) -> Inventory:
    inventory_path = Path(path).expanduser().resolve()
    try:
        payload = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DeploymentError(f"cannot read inventory: {inventory_path}") from exc
    root = _mapping(payload, "inventory")
    if root.get("version") != 1:
        raise DeploymentError("inventory version must be 1")
    try:
        concurrency = int(root.get("concurrency", 3))
    except (TypeError, ValueError) as exc:
        raise DeploymentError("inventory concurrency must be an integer") from exc
    if not 1 <= concurrency <= 32:
        raise DeploymentError("inventory concurrency must be between 1 and 32")
    report_directory = _resolve_path(
        root.get("report_directory", "deployment-reports"),
        inventory_path.parent,
        "report_directory",
    )
    state_directory = _resolve_path(
        root.get("state_directory", str(report_directory / "state")),
        inventory_path.parent,
        "state_directory",
    )
    defaults = dict(_mapping(root.get("defaults", {}), "defaults"))
    defaults_e2e = dict(_mapping(defaults.pop("e2e", {}), "defaults.e2e"))
    defaults_dr = dict(_mapping(defaults.pop("dr", {}), "defaults.dr"))
    targets_raw = root.get("targets")
    if not isinstance(targets_raw, list) or not targets_raw:
        raise DeploymentError("inventory targets must be a non-empty list")

    targets: list[Target] = []
    for index, item in enumerate(targets_raw):
        target_raw = dict(defaults)
        item_mapping = dict(_mapping(item, f"targets[{index}]"))
        item_e2e = dict(_mapping(item_mapping.pop("e2e", {}), f"targets[{index}].e2e"))
        item_dr = dict(_mapping(item_mapping.pop("dr", {}), f"targets[{index}].dr"))
        target_raw.update(item_mapping)
        e2e_raw = {**defaults_e2e, **item_e2e}
        dr_raw = {**defaults_dr, **item_dr}
        name = target_raw.get("name")
        context = target_raw.get("docker_context")
        project_name = target_raw.get("project_name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise DeploymentError(
                f"targets[{index}].name contains unsupported characters"
            )
        if not isinstance(context, str) or not context.strip():
            raise DeploymentError(f"target {name} requires docker_context")
        if not isinstance(project_name, str) or not NAME_RE.fullmatch(project_name):
            raise DeploymentError(f"target {name} requires a valid project_name")
        platform = target_raw.get("platform", SUPPORTED_PLATFORM)
        if platform != SUPPORTED_PLATFORM:
            raise DeploymentError(
                f"target {name} must use {SUPPORTED_PLATFORM}; got {platform!r}"
            )
        targets.append(
            Target(
                name=name,
                docker_context=context,
                compose_file=_resolve_path(
                    target_raw.get("compose_file"),
                    inventory_path.parent,
                    f"target {name} compose_file",
                ),
                env_file=_resolve_path(
                    target_raw.get("env_file"),
                    inventory_path.parent,
                    f"target {name} env_file",
                ),
                project_name=project_name,
                platform=platform,
                e2e=_build_e2e(e2e_raw, name),
                dr=_build_dr(dr_raw, name, inventory_path.parent),
            )
        )

    names = [target.name for target in targets]
    if len(names) != len(set(names)):
        raise DeploymentError("inventory target names must be unique")
    projects = [(target.docker_context, target.project_name) for target in targets]
    if len(projects) != len(set(projects)):
        raise DeploymentError("project_name must be unique within each Docker context")
    dr_projects = [
        (target.docker_context, target.dr.project_name)
        for target in targets
        if target.dr is not None
    ]
    if len(dr_projects) != len(set(dr_projects)):
        raise DeploymentError(
            "dr.project_name must be unique within each Docker context"
        )
    all_projects = [*projects, *dr_projects]
    if len(all_projects) != len(set(all_projects)):
        raise DeploymentError(
            "application and DR project names must not overlap within a Docker context"
        )
    dr_volumes = [
        (target.docker_context, target.dr.repository_volume)
        for target in targets
        if target.dr is not None
    ]
    if len(dr_volumes) != len(set(dr_volumes)):
        raise DeploymentError(
            "dr.repository_volume must be unique within each Docker context"
        )
    remote_dr_roots = [
        (target.dr.ssh_target, target.dr.remote_directory)
        for target in targets
        if target.dr is not None and target.dr.mode == "ssh"
    ]
    if len(remote_dr_roots) != len(set(remote_dr_roots)):
        raise DeploymentError("remote DR directories must be unique per SSH host")
    tunnel_ports = [
        target.e2e.local_port
        for target in targets
        if target.e2e.mode == "ssh-tunnel" and target.e2e.local_port is not None
    ]
    if len(tunnel_ports) != len(set(tunnel_ports)):
        raise DeploymentError("ssh-tunnel local tunnel ports must be unique")
    for target in targets:
        if (
            target.dr is not None
            and target.dr.mode == "ssh"
            and target.e2e.mode == "ssh-tunnel"
            and target.dr.ssh_target != target.e2e.ssh_target
        ):
            raise DeploymentError(
                f"target {target.name} DR and E2E SSH destinations must match"
            )
    return Inventory(
        targets=tuple(targets),
        concurrency=concurrency,
        report_directory=report_directory,
        state_directory=state_directory,
    )


def _protect_environment_file(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise DeploymentError(
            f"cannot inspect target environment file: {path}"
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise DeploymentError("target environment file must be a regular file")
    if os.name != "nt":
        if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
            raise DeploymentError(
                "target environment file must be owner-only (mode 0600)"
            )
        return
    resolved = path.resolve()
    with _PROTECTED_ENVIRONMENT_PATHS_LOCK:
        if resolved in _PROTECTED_ENVIRONMENT_PATHS:
            return
        script = r"""
$ErrorActionPreference = 'Stop'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$sid = $identity.User
if ($null -eq $sid) { throw 'current token has no SID' }
$acl = [System.Security.AccessControl.FileSecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner($sid)
$rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
  $sid,
  [System.Security.AccessControl.FileSystemRights]::FullControl,
  [System.Security.AccessControl.InheritanceFlags]::None,
  [System.Security.AccessControl.PropagationFlags]::None,
  [System.Security.AccessControl.AccessControlType]::Allow
)
$acl.AddAccessRule($rule) | Out-Null
[System.IO.File]::SetAccessControl($env:DCIM_ENV_ACL_PATH, $acl)
$actual = [System.IO.File]::GetAccessControl($env:DCIM_ENV_ACL_PATH)
$rules = @($actual.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
$full = [System.Security.AccessControl.FileSystemRights]::FullControl
if (-not $actual.AreAccessRulesProtected -or $rules.Count -ne 1 -or
    $rules[0].IdentityReference.Value -ne $sid.Value -or
    $rules[0].AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
    (($rules[0].FileSystemRights -band $full) -ne $full)) {
  throw 'restricted DACL verification failed'
}
""".strip()
        environment = dict(os.environ)
        environment["DCIM_ENV_ACL_PATH"] = str(resolved)
        try:
            completed = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    script,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                shell=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeploymentError(
                "cannot restrict Windows ACL for target environment file"
            ) from exc
        if completed.returncode != 0:
            detail = (
                completed.stderr.strip().splitlines()[-1]
                if completed.stderr.strip()
                else "unknown error"
            )
            raise DeploymentError(
                f"cannot restrict Windows ACL for target environment file: {detail}"
            )
        _PROTECTED_ENVIRONMENT_PATHS.add(resolved)


def parse_environment(path: Path | str) -> dict[str, str]:
    env_path = Path(path)
    _protect_environment_file(env_path)
    try:
        lines = env_path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise DeploymentError(
            f"cannot read target environment file: {env_path}"
        ) from exc
    values: dict[str, str] = {}
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            raise DeploymentError(
                f"invalid environment assignment at line {line_number}"
            )
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not ENV_NAME_RE.fullmatch(key):
            raise DeploymentError(f"invalid environment key at line {line_number}")
        if key in values:
            raise DeploymentError(f"duplicate environment key: {key}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def validate_environment(values: Mapping[str, str]) -> None:
    missing = [key for key in REQUIRED_ENV_KEYS if not values.get(key)]
    if missing:
        raise DeploymentError(
            f"environment is missing required keys: {', '.join(missing)}"
        )
    placeholders = [
        key for key, value in values.items() if PLACEHOLDER_RE.search(value)
    ]
    if placeholders:
        raise DeploymentError(
            f"environment contains unresolved placeholders in: {', '.join(sorted(placeholders))}"
        )
    git_sha = values["CANDIDATE_GIT_SHA"]
    if not GIT_SHA_RE.fullmatch(git_sha):
        raise DeploymentError(
            "CANDIDATE_GIT_SHA must be a lowercase 40-character commit SHA"
        )
    image_digests: dict[str, str] = {}
    for key in IMAGE_KEYS:
        match = IMAGE_DIGEST_RE.fullmatch(values[key])
        if match is None:
            raise DeploymentError(f"{key} must use an immutable digest reference")
        image_digests[key] = match.group(1)
    for _service, (image_key, id_key) in APPLICATION_IMAGE_KEYS.items():
        expected_id = values[id_key]
        match = IMAGE_ID_RE.fullmatch(expected_id)
        if match is None:
            raise DeploymentError(f"{id_key} must be a sha256 image ID")
        if match.group(1) != image_digests[image_key]:
            raise DeploymentError(f"{id_key} does not match {image_key}")
    redis_url = urlsplit(values["REDIS_URL"])
    if redis_url.scheme not in {"redis", "rediss"} or not redis_url.hostname:
        raise DeploymentError("REDIS_URL must be a valid Redis URL")
    if unquote(redis_url.password or "") != values["REDIS_PASSWORD"]:
        raise DeploymentError(
            "REDIS_PASSWORD does not match the password encoded in REDIS_URL"
        )
    if "NGINX_PORT" in values:
        _parse_port(values["NGINX_PORT"], "NGINX_PORT")


def _secret_values(values: Mapping[str, str]) -> list[str]:
    secrets = []
    for key, value in values.items():
        if any(marker in key.upper() for marker in SENSITIVE_KEY_MARKERS):
            secrets.append(value)
        if "://" in value:
            parsed = urlsplit(value)
            if parsed.password:
                secrets.append(unquote(parsed.password))
    return sorted(
        {secret for secret in secrets if len(secret) >= 4}, key=len, reverse=True
    )


def redact_text(text: str, secrets: Sequence[str] = ()) -> str:
    redacted = text
    for secret in sorted(
        {item for item in secrets if len(item) >= 4}, key=len, reverse=True
    ):
        redacted = redacted.replace(secret, "***")
    redacted = re.sub(r"([A-Za-z][A-Za-z0-9+.-]*://)([^/@\s]+)@", r"\1***@", redacted)
    redacted = re.sub(
        r"(?i)\b([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|LICENSE_KEY))\s*=\s*([^\s,;]+)",
        r"\1=***",
        redacted,
    )
    return redacted


class CommandRunner:
    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path = ROOT,
        env: Mapping[str, str] | None = None,
        timeout: int = 300,
        secrets: Sequence[str] = (),
    ) -> CommandResult:
        try:
            completed = subprocess.run(
                list(command),
                cwd=cwd,
                env=dict(env) if env is not None else None,
                timeout=timeout,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                encoding="utf-8",
                errors="replace",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeploymentError(
                redact_text(f"cannot run {' '.join(command)}: {exc}", secrets)
            ) from exc
        result = CommandResult(completed.stdout, completed.stderr, completed.returncode)
        if result.returncode != 0:
            detail = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"exit code {result.returncode}"
            )
            raise DeploymentError(
                redact_text(f"command failed ({' '.join(command)}): {detail}", secrets)
            )
        return result


def build_docker_command(target: Target, *args: str) -> list[str]:
    return ["docker", "--context", target.docker_context, *args]


def build_compose_command(target: Target, *args: str) -> list[str]:
    return build_docker_command(
        target,
        "compose",
        "--env-file",
        str(target.env_file),
        "--file",
        str(target.compose_file),
        "--project-name",
        target.project_name,
        *args,
    )


def _parse_json_output(output: str, description: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise DeploymentError(
            f"Docker returned invalid JSON for {description}"
        ) from exc


class FleetController:
    def __init__(
        self,
        inventory: Inventory,
        *,
        runner: CommandRunner | Any | None = None,
        schema_compatible: bool = False,
    ):
        self.inventory = inventory
        self.runner = runner or CommandRunner()
        self.schema_compatible = schema_compatible

    def execute(
        self, action: str, target_names: Sequence[str] | None = None
    ) -> dict[str, Any]:
        if action not in SUPPORTED_ACTIONS:
            raise DeploymentError(f"unsupported action: {action}")
        targets = self._select_targets(target_names)
        if action in LIFECYCLE_ACTIONS:
            self._validate_runtime_resource_uniqueness(targets)
        started = _utc_now()
        results_by_name: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(
            max_workers=min(self.inventory.concurrency, len(targets))
        ) as executor:
            futures = {
                executor.submit(self._execute_target, action, target): target
                for target in targets
            }
            for future in as_completed(futures):
                target = futures[future]
                try:
                    results_by_name[target.name] = future.result()
                except Exception as exc:  # defensive isolation between fleet targets
                    results_by_name[target.name] = {
                        "target": target.name,
                        "docker_context": target.docker_context,
                        "action": action,
                        "status": "failed",
                        "error": redact_text(str(exc)),
                        "checks": [],
                    }
        results = [results_by_name[target.name] for target in targets]
        passed = sum(result["status"] == "passed" for result in results)
        report: dict[str, Any] = {
            "schema_version": 1,
            "action": action,
            "started_at_utc": _utc_text(started),
            "finished_at_utc": _utc_text(),
            "annual_slo_proven": False,
            "release_gate": "BLOCKED",
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
            },
            "results": results,
        }
        report_path = self._write_report(report, started)
        report["report_path"] = str(report_path)
        return report

    def _select_targets(self, target_names: Sequence[str] | None) -> list[Target]:
        if not target_names:
            return list(self.inventory.targets)
        requested = list(dict.fromkeys(target_names))
        by_name = {target.name: target for target in self.inventory.targets}
        unknown = [name for name in requested if name not in by_name]
        if unknown:
            raise DeploymentError(f"unknown inventory targets: {', '.join(unknown)}")
        return [by_name[name] for name in requested]

    def _runtime_engine_identity(self, target: Target) -> tuple[str, str]:
        endpoint_output = self.runner.run(
            [
                "docker",
                "context",
                "inspect",
                target.docker_context,
                "--format",
                "{{json .Endpoints.docker.Host}}",
            ]
        ).stdout.strip()
        daemon_output = self.runner.run(
            build_docker_command(target, "info", "--format", "{{json .ID}}")
        ).stdout.strip()
        endpoint = _parse_json_output(endpoint_output, "Docker context endpoint")
        daemon_id = _parse_json_output(daemon_output, "Docker daemon identity")
        if (
            not isinstance(endpoint, str)
            or not endpoint
            or not isinstance(daemon_id, str)
            or not daemon_id
        ):
            raise DeploymentError("Docker engine identity is invalid")
        return endpoint, daemon_id

    def _validate_runtime_resource_uniqueness(self, targets: Sequence[Target]) -> None:
        resolved = [
            (target, *self._runtime_engine_identity(target)) for target in targets
        ]
        for index, (left, left_endpoint, left_daemon) in enumerate(resolved):
            for right, right_endpoint, right_daemon in resolved[index + 1 :]:
                if left_endpoint != right_endpoint and left_daemon != right_daemon:
                    continue
                left_projects = {left.project_name}
                right_projects = {right.project_name}
                if left.dr is not None:
                    left_projects.add(left.dr.project_name)
                if right.dr is not None:
                    right_projects.add(right.dr.project_name)
                overlap = sorted(left_projects & right_projects)
                if overlap:
                    raise DeploymentError(
                        "targets "
                        f"{left.name} and {right.name} resolve to the same Docker engine "
                        f"and reuse project {overlap[0]}"
                    )
                if (
                    left.dr is not None
                    and right.dr is not None
                    and left.dr.repository_volume == right.dr.repository_volume
                ):
                    raise DeploymentError(
                        "targets "
                        f"{left.name} and {right.name} resolve to the same Docker engine "
                        f"and reuse repository volume {left.dr.repository_volume}"
                    )

    def _execute_target(self, action: str, target: Target) -> dict[str, Any]:
        started = time.monotonic()
        started_at = _utc_text()
        secrets: list[str] = []
        checks: list[dict[str, Any]] = []
        lifecycle_manager = None
        try:
            if action == "status":
                try:
                    values = parse_environment(target.env_file)
                except DeploymentError:
                    values = {}
            else:
                values = parse_environment(target.env_file)
            secrets = _secret_values(values)
            if action not in {"rollback", "status"}:
                validate_environment(values)
            if action == "plan":
                checks = self._plan(target, values)
            elif action == "preflight":
                checks = self._preflight(target, values, secrets)
            elif action == "deploy":
                checks = self._deploy(target, values, secrets)
            elif action == "verify":
                checks = self._verify(target, values, secrets)
            elif action == "test":
                checks = self._test(target, values, secrets)
            elif action in LIFECYCLE_ACTIONS:
                from scripts.story_39_7_lifecycle import LifecycleManager

                lifecycle_manager = LifecycleManager(self)
                checks = lifecycle_manager.execute(action, target, values, secrets)
            else:
                checks = self._status(target, values, secrets)
            status = (
                "partial"
                if action == "status"
                and any(check.get("status") == "failed" for check in checks)
                else "passed"
            )
            error = None
        except Exception as exc:
            if lifecycle_manager is not None:
                checks.extend(lifecycle_manager.last_checks)
            checks.append(
                {
                    "name": "action_failure",
                    "status": "failed",
                    "error": redact_text(str(exc), secrets),
                }
            )
            status = "failed"
            error = redact_text(str(exc), secrets)
        result: dict[str, Any] = {
            "target": target.name,
            "docker_context": target.docker_context,
            "project_name": target.project_name,
            "platform": target.platform,
            "action": action,
            "status": status,
            "started_at_utc": started_at,
            "finished_at_utc": _utc_text(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "checks": checks,
        }
        if error:
            result["error"] = error
        return result

    def _plan(self, target: Target, values: Mapping[str, str]) -> list[dict[str, Any]]:
        checks = [
            {"name": "inventory", "status": "passed"},
            {
                "name": "environment",
                "status": "passed",
                "required_values_present": len(REQUIRED_ENV_KEYS),
            },
            {
                "name": "candidate",
                "status": "passed",
                "git_sha": values["CANDIDATE_GIT_SHA"],
            },
            {
                "name": "images",
                "status": "passed",
                "references": [values[key] for key in IMAGE_KEYS],
            },
            {
                "name": "external_resources",
                "status": "passed",
                "network": values["DCIM_DR_DATABASE_NETWORK"],
                "volume": values["DCIM_DR_STATUS_VOLUME"],
            },
            {
                "name": "e2e",
                "status": "passed",
                "mode": target.e2e.mode,
                "headed": target.e2e.headed,
                "browser_channel": target.e2e.browser_channel or "bundled-chromium",
            },
        ]
        if target.dr is not None:
            checks.append(
                {
                    "name": "dr_lifecycle",
                    "status": "passed",
                    "mode": target.dr.mode,
                    "project_name": target.dr.project_name,
                    "canonical_runtime_image": target.dr.canonical_runtime_image,
                    "final_runtime_image": target.dr.final_runtime_image,
                    "schema_application_image": target.dr.schema_application_image,
                    "state_directory": str(self.inventory.state_directory),
                }
            )
        return checks

    def _preflight(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
        compose_environment: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        if not target.compose_file.is_file():
            raise DeploymentError(f"compose file does not exist: {target.compose_file}")
        if os.name != "nt" and target.env_file.stat().st_mode & 0o077:
            raise DeploymentError(
                "target environment file must not be readable by group or other users"
            )
        info_result = self.runner.run(
            build_docker_command(target, "info", "--format", "{{json .}}"),
            secrets=secrets,
        )
        info = _parse_json_output(info_result.stdout.strip(), "engine info")
        if not isinstance(info, Mapping):
            raise DeploymentError("Docker engine info must be a JSON object")
        os_type = str(info.get("OSType", "")).lower()
        architecture = str(info.get("Architecture", "")).lower()
        if os_type != "linux":
            raise DeploymentError(
                f"Docker context {target.docker_context} is not using Linux containers"
            )
        if architecture not in {"amd64", "x86_64"}:
            raise DeploymentError(
                f"Docker context {target.docker_context} is not amd64"
            )
        compose_version = self.runner.run(
            build_docker_command(target, "compose", "version"), secrets=secrets
        ).stdout.strip()
        self.runner.run(
            build_docker_command(
                target, "network", "inspect", values["DCIM_DR_DATABASE_NETWORK"]
            ),
            secrets=secrets,
        )
        self.runner.run(
            build_docker_command(
                target, "volume", "inspect", values["DCIM_DR_STATUS_VOLUME"]
            ),
            secrets=secrets,
        )
        self.runner.run(
            build_compose_command(target, "config", "--quiet"),
            env=compose_environment,
            secrets=secrets,
        )
        return [
            {
                "name": "docker_engine",
                "status": "passed",
                "os": os_type,
                "architecture": architecture,
                "server_version": info.get("ServerVersion"),
            },
            {"name": "docker_compose", "status": "passed", "version": compose_version},
            {"name": "environment", "status": "passed"},
            {"name": "compose_config", "status": "passed"},
            {
                "name": "story_39_3_network",
                "status": "passed",
                "name_value": values["DCIM_DR_DATABASE_NETWORK"],
            },
            {
                "name": "story_39_3_status_volume",
                "status": "passed",
                "name_value": values["DCIM_DR_STATUS_VOLUME"],
            },
        ]

    def _verify_images(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        checks = []
        for service, (image_key, id_key) in APPLICATION_IMAGE_KEYS.items():
            result = self.runner.run(
                build_docker_command(
                    target,
                    "image",
                    "inspect",
                    values[image_key],
                    "--format",
                    "{{json .}}",
                ),
                secrets=secrets,
            )
            image = _parse_json_output(result.stdout.strip(), f"{service} image")
            if not isinstance(image, Mapping):
                raise DeploymentError(
                    f"{service} image inspection must be a JSON object"
                )
            actual_id = image.get("Id")
            config = image.get("Config")
            labels = config.get("Labels") if isinstance(config, Mapping) else None
            revision = (
                labels.get("org.opencontainers.image.revision")
                if isinstance(labels, Mapping)
                else None
            )
            if actual_id != values[id_key]:
                raise DeploymentError(
                    f"{service} image ID does not match the fixed candidate"
                )
            if revision != values["CANDIDATE_GIT_SHA"]:
                raise DeploymentError(
                    f"{service} OCI revision does not match the fixed candidate"
                )
            checks.append(
                {
                    "name": f"{service}_image",
                    "status": "passed",
                    "reference": values[image_key],
                    "image_id": actual_id,
                    "revision": revision,
                }
            )
        return checks

    def _deploy(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
        *,
        pull_images: bool = True,
    ) -> list[dict[str, Any]]:
        compose_environment = dict(os.environ)
        compose_environment.update(values)
        checks = self._preflight(
            target, values, secrets, compose_environment=compose_environment
        )
        if pull_images:
            for key in IMAGE_KEYS:
                self.runner.run(
                    build_docker_command(target, "pull", values[key]),
                    secrets=secrets,
                    timeout=1800,
                )
        else:
            for key in IMAGE_KEYS:
                output = self.runner.run(
                    build_docker_command(
                        target,
                        "image",
                        "inspect",
                        values[key],
                        "--format",
                        "{{json .Id}}",
                    ),
                    secrets=secrets,
                ).stdout.strip()
                image_id = _parse_json_output(output, f"local {key} image")
                if (
                    not isinstance(image_id, str)
                    or IMAGE_ID_RE.fullmatch(image_id) is None
                ):
                    raise DeploymentError(f"local {key} image is unavailable")
        checks.append(
            {
                "name": "image_pull" if pull_images else "local_images",
                "status": "passed",
                "references": [values[key] for key in IMAGE_KEYS],
                "registry_contacted": pull_images,
            }
        )
        checks.extend(self._verify_images(target, values, secrets))
        images = self.runner.run(
            build_compose_command(target, "config", "--images"),
            env=compose_environment,
            secrets=secrets,
        ).stdout.splitlines()
        configured_images = sorted(line.strip() for line in images if line.strip())
        expected_images = sorted(values[key] for key in IMAGE_KEYS)
        if configured_images != expected_images:
            raise DeploymentError(
                "rendered Compose images do not match the immutable inventory"
            )
        hashes = self.runner.run(
            build_compose_command(target, "config", "--hash", "*"),
            env=compose_environment,
            secrets=secrets,
        ).stdout.splitlines()
        self.runner.run(
            build_compose_command(target, "up", "-d", "--no-build", "--pull", "never"),
            env=compose_environment,
            secrets=secrets,
            timeout=1800,
        )
        checks.append(
            {
                "name": "compose_deploy",
                "status": "passed",
                "configured_images": configured_images,
                "configuration_hashes": sorted(
                    line.strip() for line in hashes if line.strip()
                ),
                "build_disabled": True,
                "pull_during_startup": False,
            }
        )
        checks.extend(
            self._verify_runtime(
                target, secrets, compose_environment=compose_environment
            )
        )
        return checks

    def _verify(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        compose_environment = dict(os.environ)
        compose_environment.update(values)
        checks = self._preflight(
            target, values, secrets, compose_environment=compose_environment
        )
        checks.extend(self._verify_images(target, values, secrets))
        checks.extend(
            self._verify_runtime(
                target, secrets, compose_environment=compose_environment
            )
        )
        return checks

    def _compose_ps(
        self,
        target: Target,
        secrets: Sequence[str],
        compose_environment: Mapping[str, str] | None = None,
    ) -> list[Mapping[str, Any]]:
        output = self.runner.run(
            build_compose_command(target, "ps", "--format", "json"),
            env=compose_environment,
            secrets=secrets,
        ).stdout.strip()
        if not output:
            raise DeploymentError("Compose returned no service status")
        try:
            parsed = json.loads(output)
            items = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            items = []
            for line in output.splitlines():
                parsed_line = _parse_json_output(line, "Compose service status")
                items.append(parsed_line)
        if not all(isinstance(item, Mapping) for item in items):
            raise DeploymentError("Compose service status must contain JSON objects")
        return items

    def _verify_runtime(
        self,
        target: Target,
        secrets: Sequence[str],
        compose_environment: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        items = self._compose_ps(
            target, secrets, compose_environment=compose_environment
        )
        by_service = {str(item.get("Service")): item for item in items}
        required = {"redis", "emqx", "backend", "nginx"}
        missing = sorted(required - set(by_service))
        if missing:
            raise DeploymentError(f"Compose services are missing: {', '.join(missing)}")
        service_status = []
        for name in sorted(required):
            item = by_service[name]
            state = str(item.get("State", "")).lower()
            health = str(item.get("Health", "")).lower()
            if state != "running":
                raise DeploymentError(f"service {name} is not running")
            if health and health != "healthy":
                raise DeploymentError(f"service {name} is not healthy")
            service_status.append(
                {"service": name, "state": state, "health": health or "not-configured"}
            )
        backend_health = self._json_probe(
            target,
            "backend",
            ["curl", "-fsS", "http://127.0.0.1:8080/api/health"],
            "backend health",
            secrets,
            compose_environment,
        )
        proxy_health = self._json_probe(
            target,
            "nginx",
            ["wget", "-qO-", "http://127.0.0.1/api/health"],
            "proxy health",
            secrets,
            compose_environment,
        )
        proxy_readiness = self._json_probe(
            target,
            "nginx",
            ["wget", "-qO-", "http://127.0.0.1/api/readiness"],
            "proxy readiness",
            secrets,
            compose_environment,
        )
        return [
            {"name": "services", "status": "passed", "services": service_status},
            {
                "name": "backend_health",
                "status": "passed",
                "response_status": backend_health.get("status"),
            },
            {
                "name": "proxy_health",
                "status": "passed",
                "response_status": proxy_health.get("status"),
            },
            {
                "name": "proxy_readiness",
                "status": "passed",
                "response_status": proxy_readiness.get("status"),
            },
        ]

    def _json_probe(
        self,
        target: Target,
        service: str,
        probe_command: Sequence[str],
        description: str,
        secrets: Sequence[str],
        compose_environment: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        output = self.runner.run(
            build_compose_command(target, "exec", "-T", service, *probe_command),
            env=compose_environment,
            secrets=secrets,
        ).stdout.strip()
        payload = _parse_json_output(output, description)
        if not isinstance(payload, Mapping):
            raise DeploymentError(f"{description} response must be a JSON object")
        status = str(payload.get("status", "")).lower()
        if status in {"failed", "unhealthy", "unknown", "not_ready", "not-ready"}:
            raise DeploymentError(f"{description} returned {status}")
        return payload

    def _status(
        self, target: Target, _values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        try:
            items = self._compose_ps(target, secrets)
            by_service = {str(item.get("Service")): item for item in items}
            required = {"redis", "emqx", "backend", "nginx"}
            missing = sorted(required - set(by_service))
            if missing:
                raise DeploymentError(
                    f"Compose services are missing: {', '.join(missing)}"
                )
            for name in sorted(required):
                state = str(by_service[name].get("State", "")).lower()
                health = str(by_service[name].get("Health", "")).lower()
                if state != "running":
                    raise DeploymentError(f"service {name} is not running")
                if health and health != "healthy":
                    raise DeploymentError(f"service {name} is not healthy")
            services = [
                {
                    "service": item.get("Service"),
                    "state": item.get("State"),
                    "health": item.get("Health"),
                    "image": item.get("Image"),
                }
                for item in items
            ]
            checks.append(
                {"name": "compose_status", "status": "passed", "services": services}
            )
        except Exception as exc:
            checks.append(
                {
                    "name": "compose_status",
                    "status": "failed",
                    "error": redact_text(str(exc), secrets),
                }
            )
        if target.dr is not None:
            from scripts.story_39_7_lifecycle import LifecycleManager

            try:
                checks.extend(LifecycleManager(self).status(target, secrets))
            except Exception as exc:
                checks.append(
                    {
                        "name": "lifecycle_status",
                        "status": "failed",
                        "error": redact_text(str(exc), secrets),
                    }
                )
        return checks

    def _test(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        checks = self._verify(target, values, secrets)
        if target.e2e.mode == "disabled":
            raise DeploymentError(f"target {target.name} has e2e testing disabled")
        configured_port = target.e2e.local_port or _parse_port(
            values.get("NGINX_PORT", "3000"), "NGINX_PORT"
        )
        assert configured_port is not None
        artifact = (
            self.inventory.report_directory
            / f"e2e-{target.name}-{_utc_now().strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )
        artifact.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "npx.cmd" if os.name == "nt" else "npx",
            "playwright",
            "test",
            *target.e2e.specs,
            "--project=chromium",
            "--workers=1",
            "--retries=0",
            "--reporter=json",
        ]
        if target.e2e.headed:
            command.append("--headed")
        with tempfile.TemporaryDirectory(prefix=f"dcim-e2e-{target.name}-") as temp_dir:
            process_env = dict(os.environ)
            process_env.update(
                {
                    "CI": "1",
                    "E2E_BASE_URL": f"http://127.0.0.1:{configured_port}",
                    "E2E_ADMIN_USER": values.get("E2E_ADMIN_USER", ""),
                    "E2E_ADMIN_PASSWORD": values.get("E2E_ADMIN_PASSWORD", ""),
                    "E2E_AUTH_FILE": str(Path(temp_dir) / "admin.json"),
                    "E2E_OUTPUT_DIR": str(Path(temp_dir) / "test-results"),
                    "PLAYWRIGHT_JSON_OUTPUT_FILE": str(artifact),
                }
            )
            if target.e2e.browser_channel:
                process_env["E2E_BROWSER_CHANNEL"] = target.e2e.browser_channel
            if (
                not process_env["E2E_ADMIN_USER"]
                or not process_env["E2E_ADMIN_PASSWORD"]
            ):
                raise DeploymentError(
                    "E2E_ADMIN_USER and E2E_ADMIN_PASSWORD are required for test"
                )
            if target.e2e.mode == "ssh-tunnel":
                assert (
                    target.e2e.ssh_target is not None
                    and target.e2e.remote_port is not None
                )
                with self._ssh_tunnel(target.e2e, secrets):
                    self.runner.run(
                        command,
                        cwd=ROOT,
                        env=process_env,
                        timeout=7200,
                        secrets=secrets,
                    )
            else:
                self.runner.run(
                    command, cwd=ROOT, env=process_env, timeout=7200, secrets=secrets
                )
        if not artifact.is_file():
            raise DeploymentError("Playwright did not create its JSON result artifact")
        checks.append(
            {
                "name": "critical_e2e",
                "status": "passed",
                "headed": target.e2e.headed,
                "browser_channel": target.e2e.browser_channel or "bundled-chromium",
                "retries": 0,
                "artifact": str(artifact),
            }
        )
        return checks

    @contextmanager
    def _ssh_tunnel(self, config: E2EConfig, secrets: Sequence[str]) -> Iterator[None]:
        assert (
            config.ssh_target is not None
            and config.local_port is not None
            and config.remote_port is not None
        )
        command = [
            "ssh",
            *config.ssh_args,
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-L",
            f"127.0.0.1:{config.local_port}:127.0.0.1:{config.remote_port}",
            config.ssh_target,
        ]
        try:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise DeploymentError(f"cannot start SSH tunnel: {exc}") from exc
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    _stdout, stderr = process.communicate(timeout=2)
                    raise DeploymentError(
                        redact_text(
                            f"SSH tunnel exited early: {stderr.strip()}", secrets
                        )
                    )
                try:
                    with socket.create_connection(
                        ("127.0.0.1", config.local_port), timeout=0.5
                    ):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise DeploymentError(
                    "SSH tunnel did not become ready within 20 seconds"
                )
            yield
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def _write_report(self, report: Mapping[str, Any], started: datetime) -> Path:
        directory = self.inventory.report_directory
        directory.mkdir(parents=True, exist_ok=True)
        path = (
            directory
            / f"{report['action']}-{started.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted(SUPPORTED_ACTIONS))
    parser.add_argument(
        "--inventory", type=Path, required=True, help="YAML target inventory"
    )
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        help="target name; repeat to select multiple",
    )
    parser.add_argument(
        "--concurrency", type=int, help="override inventory concurrency (1-32)"
    )
    parser.add_argument(
        "--schema-compatible",
        action="store_true",
        help="assert that upgrade or rollback keeps the existing database schema compatible",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = load_inventory(args.inventory)
        if args.concurrency is not None:
            if not 1 <= args.concurrency <= 32:
                raise DeploymentError("--concurrency must be between 1 and 32")
            inventory = replace(inventory, concurrency=args.concurrency)
        report = FleetController(
            inventory, schema_compatible=args.schema_compatible
        ).execute(args.action, args.targets)
    except DeploymentError as exc:
        print(
            json.dumps(
                {"status": "failed", "error": redact_text(str(exc))}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
