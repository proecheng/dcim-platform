#!/usr/bin/env python3
"""Zero-to-one, upgrade, and rollback orchestration for Story 39.7 targets."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets as secret_generator
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence
from urllib.parse import unquote, urlsplit

import yaml

from scripts.story_39_3_schema_bootstrap import (
    CATALOG_SQL,
    EXPECTED_TABLE_COUNT,
    OCCUPANCY_SQL,
)
from scripts.story_39_7_deploy import (
    ROOT,
    DeploymentError,
    DRConfig,
    IMAGE_DIGEST_RE,
    IMAGE_ID_RE,
    Target,
    _parse_json_output,
    build_docker_command,
    is_local_image_reference,
    redact_text,
    validate_environment,
)

if TYPE_CHECKING:
    from scripts.story_39_7_deploy import FleetController


CANONICAL_MANIFEST = ROOT / "deploy/postgres-backup/canonical-schema-manifest.json"
VERSIONS_FILE = ROOT / "deploy/postgres-backup/versions.yaml"
SCHEMA_BOOTSTRAP = ROOT / "scripts/story_39_3_schema_bootstrap.py"
SECRET_FILES = {
    "POSTGRES_PASSWORD_FILE": "postgres_password",
    "REPLICATION_PASSWORD_FILE": "replication_password",
    "PGBACKREST_CIPHER_PASS_FILE": "pgbackrest_cipher_pass",
    "FENCE_TOKEN_FILE": "fence_token",
}
RELEASE_KEYS = (
    "CANDIDATE_GIT_SHA",
    "DCIM_BACKEND_IMAGE",
    "DCIM_BACKEND_EXPECTED_ID",
    "DCIM_FRONTEND_IMAGE",
    "DCIM_FRONTEND_EXPECTED_ID",
    "DCIM_REDIS_IMAGE",
    "DCIM_EMQX_IMAGE",
)
STATE_HMAC_FILE = "lifecycle_state_hmac"
SENSITIVE_ENV_KEYS = frozenset(
    {
        "DATABASE_URL",
        "E2E_ADMIN_PASSWORD",
        "FAULT_TREE_HMAC_KEY",
        "GATEWAY_SECRET_KEY",
        "LICENSE_KEY",
        "MQTT_PASSWORD",
        "REDIS_PASSWORD",
        "REDIS_URL",
        "SECRET_KEY",
        "VPP_API_KEY",
    }
)
SNAPSHOT_CONFIGURATION_KEYS = frozenset(
    {
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "ALGORITHM",
        "APP_NAME",
        "BACKUP_DAILY_HOUR",
        "BACKUP_FULL_WEEKDAY",
        "BACKUP_INCREMENTAL_HOURS",
        "COLLECT_INTERVAL",
        "CORS_ORIGINS",
        "DATA_RETENTION_DAYS",
        "DCIM_DR_DATABASE_NETWORK",
        "DCIM_DR_STATUS_VOLUME",
        "E2E_ADMIN_USER",
        "MAX_POINTS",
        "MQTT_USERNAME",
        "NGINX_PORT",
        "PREPROD_BIND_ADDRESS",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "TIMESCALEDB_ENABLED",
    }
)
DATABASE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BOOTSTRAP_PHASES = {
    "prepared",
    "canonical_running",
    "schema_verified",
    "runtime_started",
    "dr_verified",
}
LOCK_LEASE_SECONDS = 30 * 60
LOCK_HEARTBEAT_INTERVAL_SECONDS = 60
LOCK_HEARTBEAT_PATH = "/tmp/dcim-lifecycle-heartbeat"
LOCK_LABEL = "com.dcim.lifecycle.lock"
LOCK_OWNER_LABEL = "com.dcim.lifecycle.owner"
LOCK_ACTION_LABEL = "com.dcim.lifecycle.action"
LOCK_EXPIRES_LABEL = "com.dcim.lifecycle.expires-at"
BACKUP_LABEL_RE = re.compile(r"^[0-9]{8}-[0-9]{6}F$")


def _utc_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    _harden_windows_path(path.parent, directory=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        _harden_windows_path(path, directory=False)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        _harden_windows_path(path, directory=False)
    finally:
        temporary.unlink(missing_ok=True)


def _create_secret(path: Path, value: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        os.write(descriptor, f"{value}\n".encode("utf-8"))
    finally:
        os.close(descriptor)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_secret(path: Path) -> str:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise DeploymentError(
            f"cannot inspect existing DR secret file: {path.name}"
        ) from exc
    if path.is_symlink() or not path.is_file():
        raise DeploymentError(f"existing DR secret is not a regular file: {path.name}")
    if os.name != "nt" and metadata.st_uid != os.geteuid():
        raise DeploymentError(
            f"existing DR secret has an unexpected owner: {path.name}"
        )
    if os.name != "nt" and metadata.st_mode & 0o077:
        raise DeploymentError(
            f"existing DR secret permissions are too broad: {path.name}"
        )
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DeploymentError(
            f"cannot read existing DR secret file: {path.name}"
        ) from exc
    if len(value) < 12 or any(character.isspace() for character in value):
        raise DeploymentError(f"existing DR secret file is invalid: {path.name}")
    return value


def _harden_windows_path(path: Path, *, directory: bool) -> None:
    if os.name != "nt":
        return
    script = r"""
$ErrorActionPreference = 'Stop'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$sid = $identity.User
if ($null -eq $sid) { throw 'current token has no SID' }
if ($env:DCIM_ACL_KIND -eq 'directory') {
  $acl = [System.Security.AccessControl.DirectorySecurity]::new()
  $inheritance = [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
} else {
  $acl = [System.Security.AccessControl.FileSecurity]::new()
  $inheritance = [System.Security.AccessControl.InheritanceFlags]::None
}
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner($sid)
$rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
  $sid,
  [System.Security.AccessControl.FileSystemRights]::FullControl,
  $inheritance,
  [System.Security.AccessControl.PropagationFlags]::None,
  [System.Security.AccessControl.AccessControlType]::Allow
)
$acl.AddAccessRule($rule) | Out-Null
if ($env:DCIM_ACL_KIND -eq 'directory') {
  [System.IO.Directory]::SetAccessControl($env:DCIM_ACL_PATH, $acl)
  $actual = [System.IO.Directory]::GetAccessControl($env:DCIM_ACL_PATH)
} else {
  [System.IO.File]::SetAccessControl($env:DCIM_ACL_PATH, $acl)
  $actual = [System.IO.File]::GetAccessControl($env:DCIM_ACL_PATH)
}
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
    environment["DCIM_ACL_PATH"] = str(path)
    environment["DCIM_ACL_KIND"] = "directory" if directory else "file"
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
    if completed.returncode != 0:
        detail = (
            completed.stderr.strip().splitlines()[-1]
            if completed.stderr.strip()
            else "unknown error"
        )
        raise DeploymentError(f"cannot restrict Windows ACL for {path.name}: {detail}")


def _database_identity(database_url: str) -> tuple[str, str, str]:
    parsed = urlsplit(database_url)
    database = parsed.path.lstrip("/")
    database_user = unquote(parsed.username or "")
    database_password = unquote(parsed.password or "")
    if (
        parsed.scheme not in {"postgresql", "postgresql+asyncpg"}
        or parsed.hostname != "postgres-writer"
        or DATABASE_IDENTIFIER_RE.fullmatch(database_user) is None
        or parsed.password is None
        or len(database_password) < 12
        or any(character.isspace() for character in database_password)
        or DATABASE_IDENTIFIER_RE.fullmatch(unquote(database)) is None
    ):
        raise DeploymentError(
            "DATABASE_URL must use postgres-writer with valid database credentials"
        )
    return database_user, database_password, unquote(database)


def prepare_secret_files(dr: DRConfig, database_url: str) -> dict[str, Path]:
    """Create missing DR secrets once and verify all existing values without replacing them."""

    try:
        dr.secret_directory.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise DeploymentError("dr.secret_directory must be outside the repository")
    dr.secret_directory.mkdir(parents=True, exist_ok=True)
    try:
        dr.secret_directory.chmod(0o700)
    except OSError:
        pass
    _harden_windows_path(dr.secret_directory, directory=True)
    _user, database_password, _database = _database_identity(database_url)
    paths = {
        key: dr.secret_directory / filename for key, filename in SECRET_FILES.items()
    }
    expected = {"POSTGRES_PASSWORD_FILE": database_password}
    for key, path in paths.items():
        if path.exists():
            _harden_windows_path(path, directory=False)
            value = _read_secret(path)
            if key in expected and value != expected[key]:
                raise DeploymentError(
                    "existing PostgreSQL secret does not match DATABASE_URL"
                )
            continue
        value = expected.get(key) or secret_generator.token_urlsafe(48)
        try:
            _create_secret(path, value)
            _harden_windows_path(path, directory=False)
        except FileExistsError:
            value = _read_secret(path)
            if key in expected and value != expected[key]:
                raise DeploymentError(
                    "existing PostgreSQL secret does not match DATABASE_URL"
                )
    return paths


def _split_image(image: str) -> tuple[str, str]:
    repository, separator, digest = image.rpartition("@sha256:")
    if not separator or not repository or len(digest) != 64:
        raise DeploymentError("DR image must use an immutable digest reference")
    return repository, digest


def _env_text(values: Mapping[str, str]) -> str:
    return "".join(
        f"{key}={json.dumps(value, ensure_ascii=True)}\n"
        for key, value in sorted(values.items())
    )


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class LifecycleManager:
    def __init__(self, controller: FleetController):
        self.controller = controller
        self.runner = controller.runner
        self.last_checks: list[dict[str, Any]] = []
        self.current_stage = "initializing"

    @contextmanager
    def _target_lock(self, target: Target, action: str):
        """Serialize lifecycle actions locally and on the target Docker daemon."""
        assert target.dr is not None
        lock_path = self.controller.inventory.state_directory / f"{target.name}.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        daemon_lock = ""
        lock_owner = uuid.uuid4().hex
        daemon_lock_acquired = False
        lease_stop = threading.Event()
        lease_errors: list[Exception] = []
        lease_thread: threading.Thread | None = None
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                handle.write("0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            daemon_id = self._docker_daemon_id(target).encode()
            daemon_lock = (
                f"dcim-lifecycle-lock-{hashlib.sha256(daemon_id).hexdigest()[:20]}"
            )
            self._require_lock_image(target, action)
            self._acquire_daemon_lock(
                target, daemon_lock, lock_owner=lock_owner, action=action
            )
            daemon_lock_acquired = True
            lease_thread = threading.Thread(
                target=self._renew_daemon_lock,
                args=(target, daemon_lock, lease_stop, lease_errors),
                name=f"dcim-lock-renew-{target.name}",
                daemon=True,
            )
            lease_thread.start()
            yield
            if lease_errors:
                raise DeploymentError(
                    "lifecycle daemon lock renewal failed"
                ) from lease_errors[0]
        finally:
            try:
                lease_stop.set()
                if lease_thread is not None:
                    lease_thread.join(timeout=LOCK_HEARTBEAT_INTERVAL_SECONDS + 5)
                if daemon_lock_acquired:
                    self._release_daemon_lock(target, daemon_lock, lock_owner)
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def _require_lock_image(self, target: Target, action: str) -> None:
        assert target.dr is not None
        image = target.dr.final_runtime_image
        if action == "bootstrap":
            self.runner.run(
                build_docker_command(target, "pull", image),
                timeout=1800,
            )
        try:
            output = self.runner.run(
                build_docker_command(
                    target, "image", "inspect", image, "--format", "{{json .Id}}"
                )
            ).stdout.strip()
            image_id = _parse_json_output(output, "lifecycle lock image")
        except DeploymentError as exc:
            if action in {"upgrade", "rollback"}:
                raise DeploymentError(
                    f"{action} requires the approved DR runtime image to exist locally"
                ) from exc
            raise
        if not isinstance(image_id, str) or IMAGE_ID_RE.fullmatch(image_id) is None:
            raise DeploymentError("lifecycle lock image inspection is invalid")

    def _daemon_lock_details(self, target: Target, name: str) -> Mapping[str, Any]:
        output = self.runner.run(
            build_docker_command(
                target, "container", "inspect", name, "--format", "{{json .}}"
            )
        ).stdout.strip()
        details = _parse_json_output(output, "lifecycle daemon lock")
        if not isinstance(details, Mapping):
            raise DeploymentError("lifecycle daemon lock inspection is invalid")
        return details

    def _remove_expired_daemon_lock(self, target: Target, name: str) -> bool:
        try:
            details = self._daemon_lock_details(target, name)
            state = details.get("State", {})
            config = details.get("Config", {})
            if not isinstance(config, Mapping) or not isinstance(state, Mapping):
                return False
            labels = config.get("Labels", {})
            if not isinstance(labels, Mapping):
                return False
            expires_text = labels.get(LOCK_EXPIRES_LABEL)
            expires_at = datetime.fromisoformat(
                str(expires_text).replace("Z", "+00:00")
            )
        except (AttributeError, DeploymentError, TypeError, ValueError):
            return False
        if (
            labels.get(LOCK_LABEL) != "true"
            or state.get("Running") is True
            or expires_at.tzinfo is None
            or expires_at > datetime.now(timezone.utc)
        ):
            return False
        self.runner.run(
            build_docker_command(target, "container", "rm", "--force", name)
        )
        return True

    def _acquire_daemon_lock(
        self, target: Target, name: str, *, lock_owner: str, action: str
    ) -> None:
        assert target.dr is not None
        acquired_at = datetime.now(timezone.utc)
        expires_at = acquired_at + timedelta(seconds=LOCK_LEASE_SECONDS)
        command = build_docker_command(
            target,
            "container",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--label",
            f"{LOCK_LABEL}=true",
            "--label",
            f"{LOCK_OWNER_LABEL}={lock_owner}",
            "--label",
            f"{LOCK_ACTION_LABEL}={action}",
            "--label",
            f"{LOCK_EXPIRES_LABEL}={expires_at.isoformat().replace('+00:00', 'Z')}",
            "--entrypoint",
            "/bin/sh",
            target.dr.final_runtime_image,
            "-c",
            (
                f"touch {LOCK_HEARTBEAT_PATH}; "
                "while :; do "
                f"now=$(date +%s); heartbeat=$(stat -c %Y {LOCK_HEARTBEAT_PATH}); "
                f"test $((now - heartbeat)) -lt {LOCK_LEASE_SECONDS} || exit 75; "
                "sleep 15; done"
            ),
        )
        try:
            self.runner.run(command)
        except DeploymentError:
            if not self._remove_expired_daemon_lock(target, name):
                raise
            self.runner.run(command)
        details = self._daemon_lock_details(target, name)
        labels = details.get("Config", {}).get("Labels", {})
        state = details.get("State", {})
        if (
            not isinstance(labels, Mapping)
            or labels.get(LOCK_OWNER_LABEL) != lock_owner
            or not isinstance(state, Mapping)
            or state.get("Running") is not True
        ):
            raise DeploymentError("lifecycle daemon lock did not become active")

    def _renew_daemon_lock(
        self,
        target: Target,
        name: str,
        stop: threading.Event,
        errors: list[Exception],
    ) -> None:
        last_success = time.monotonic()
        while not stop.wait(LOCK_HEARTBEAT_INTERVAL_SECONDS):
            try:
                self.runner.run(
                    build_docker_command(
                        target,
                        "container",
                        "exec",
                        name,
                        "touch",
                        LOCK_HEARTBEAT_PATH,
                    )
                )
                last_success = time.monotonic()
            except Exception as exc:
                if time.monotonic() - last_success >= LOCK_LEASE_SECONDS / 2:
                    errors.append(exc)
                    return

    def _release_daemon_lock(self, target: Target, name: str, lock_owner: str) -> None:
        try:
            details = self._daemon_lock_details(target, name)
            labels = details.get("Config", {}).get("Labels", {})
            if (
                not isinstance(labels, Mapping)
                or labels.get(LOCK_OWNER_LABEL) != lock_owner
            ):
                return
            self.runner.run(
                build_docker_command(target, "container", "rm", "--force", name)
            )
        except (AttributeError, DeploymentError, TypeError):
            pass

    def execute(
        self,
        action: str,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
    ) -> list[dict[str, Any]]:
        if target.dr is None:
            raise DeploymentError(
                f"target {target.name} has no dr lifecycle configuration"
            )
        with self._target_lock(target, action):
            try:
                if action == "bootstrap":
                    return self._bootstrap(target, values, secrets)
                if action == "upgrade":
                    return self._upgrade(target, values, secrets)
                if action == "rollback":
                    return self._rollback(target, values, secrets)
                raise DeploymentError(f"unsupported lifecycle action: {action}")
            except Exception as exc:
                self._mark_pending_failure(target, exc, secrets)
                raise

    def status(self, target: Target, secrets: Sequence[str]) -> list[dict[str, Any]]:
        if target.dr is None:
            return []
        checks: list[dict[str, Any]] = []
        try:
            state = self._read_state(target, verify_runtime=False)
            current_environment = state["current"].get("application_environment", {})
            checks.append(
                {
                    "name": "lifecycle_journal",
                    "status": "passed",
                    "lifecycle_state": state["status"],
                    "last_action": state.get("last_action"),
                    "candidate_git_sha": current_environment.get("CANDIDATE_GIT_SHA"),
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "name": "lifecycle_journal",
                    "status": "failed",
                    "error": redact_text(str(exc), secrets),
                }
            )
        try:
            output = self.runner.run(
                self._dr_compose_command(
                    target, "runtime", "--profile", "backup", "ps", "--format", "json"
                ),
                secrets=secrets,
            ).stdout.strip()
            if not output:
                raise DeploymentError("DR Compose returned no service status")
            try:
                parsed = json.loads(output)
                items = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                items = [json.loads(line) for line in output.splitlines() if line]
            services = [
                {
                    "service": item.get("Service"),
                    "state": item.get("State"),
                    "health": item.get("Health"),
                    "image": item.get("Image"),
                }
                for item in items
                if isinstance(item, Mapping)
            ]
            by_service = {str(item["service"]): item for item in services}
            required = {"postgres-primary", "postgres-standby", "backup-scheduler"}
            missing = sorted(required - set(by_service))
            if missing:
                raise DeploymentError(
                    f"DR Compose services are missing: {', '.join(missing)}"
                )
            for name in sorted(required):
                state_value = str(by_service[name].get("state", "")).lower()
                health = str(by_service[name].get("health", "")).lower()
                if state_value != "running":
                    raise DeploymentError(f"DR service {name} is not running")
                if health and health != "healthy":
                    raise DeploymentError(f"DR service {name} is not healthy")
            checks.append(
                {"name": "dr_services", "status": "passed", "services": services}
            )
        except Exception as exc:
            checks.append(
                {
                    "name": "dr_services",
                    "status": "failed",
                    "error": redact_text(str(exc), secrets),
                }
            )
        return checks

    def _state_path(self, target: Target) -> Path:
        return self.controller.inventory.state_directory / f"{target.name}.json"

    def _protected_secret_directory(self, target: Target) -> Path:
        assert target.dr is not None
        directory = target.dr.secret_directory
        try:
            directory.relative_to(ROOT)
        except ValueError:
            pass
        else:
            raise DeploymentError("dr.secret_directory must be outside the repository")
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass
        _harden_windows_path(directory, directory=True)
        return directory

    def _state_hmac_key(self, target: Target) -> bytes:
        path = self._protected_secret_directory(target) / STATE_HMAC_FILE
        if not path.exists():
            try:
                _create_secret(path, secret_generator.token_urlsafe(48))
                _harden_windows_path(path, directory=False)
            except FileExistsError:
                pass
        return _read_secret(path).encode("utf-8")

    def _state_signature(self, target: Target, payload: Mapping[str, Any]) -> str:
        unsigned = dict(payload)
        unsigned.pop("integrity", None)
        return hmac.new(
            self._state_hmac_key(target),
            _canonical_json_bytes(unsigned),
            hashlib.sha256,
        ).hexdigest()

    def _release_artifact(
        self, target: Target, kind: str, content: bytes, suffix: str
    ) -> dict[str, str]:
        digest = _sha256_bytes(content)
        name = f"lifecycle-{kind}-{digest}.{suffix}"
        path = self._protected_secret_directory(target) / name
        if path.exists():
            try:
                existing = path.read_bytes()
            except OSError as exc:
                raise DeploymentError(f"cannot read lifecycle {kind} snapshot") from exc
            if not hmac.compare_digest(_sha256_bytes(existing), digest):
                raise DeploymentError(f"lifecycle {kind} snapshot is corrupted")
            _harden_windows_path(path, directory=False)
        else:
            _atomic_text(path, content.decode("utf-8"))
        return {"name": name, "sha256": digest}

    def _read_release_artifact(
        self, target: Target, reference: Any, kind: str, suffix: str
    ) -> bytes:
        if not isinstance(reference, Mapping):
            raise DeploymentError(f"lifecycle {kind} snapshot reference is invalid")
        name = reference.get("name")
        digest = reference.get("sha256")
        expected_name = f"lifecycle-{kind}-{digest}.{suffix}"
        if (
            not isinstance(name, str)
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or name != expected_name
        ):
            raise DeploymentError(f"lifecycle {kind} snapshot reference is invalid")
        path = self._protected_secret_directory(target) / name
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise DeploymentError(f"lifecycle {kind} snapshot is unavailable") from exc
        _harden_windows_path(path, directory=False)
        if not hmac.compare_digest(_sha256_bytes(content), digest):
            raise DeploymentError(f"lifecycle {kind} snapshot is corrupted")
        return content

    def _docker_endpoint(self, target: Target) -> str:
        output = self.runner.run(
            [
                "docker",
                "context",
                "inspect",
                target.docker_context,
                "--format",
                "{{json .Endpoints.docker.Host}}",
            ]
        ).stdout.strip()
        endpoint = _parse_json_output(output, "Docker context endpoint")
        if not isinstance(endpoint, str) or not endpoint:
            raise DeploymentError("Docker context has no trusted engine endpoint")
        return endpoint

    def _docker_daemon_id(self, target: Target) -> str:
        output = self.runner.run(
            build_docker_command(target, "info", "--format", "{{json .ID}}")
        ).stdout.strip()
        daemon_id = _parse_json_output(output, "Docker daemon identity")
        if not isinstance(daemon_id, str) or not daemon_id.strip():
            raise DeploymentError("Docker daemon has no stable identity")
        return daemon_id

    def _target_identity(self, target: Target) -> dict[str, Any]:
        dr = target.dr
        return {
            "docker_context": target.docker_context,
            "docker_endpoint": self._docker_endpoint(target),
            "docker_daemon_id": self._docker_daemon_id(target),
            "application_project": target.project_name,
            "dr_project": dr.project_name if dr else None,
            "repository_volume": dr.repository_volume if dr else None,
            "dr_mode": dr.mode if dr else None,
            "dr_ssh_target": dr.ssh_target if dr else None,
            "dr_remote_directory": dr.remote_directory if dr else None,
        }

    def _validate_target_identity(
        self, target: Target, identity: Any, *, verify_runtime: bool
    ) -> None:
        if not isinstance(identity, Mapping):
            raise DeploymentError("lifecycle target identity is invalid")
        dr = target.dr
        static_identity = {
            "docker_context": target.docker_context,
            "application_project": target.project_name,
            "dr_project": dr.project_name if dr else None,
            "repository_volume": dr.repository_volume if dr else None,
            "dr_mode": dr.mode if dr else None,
            "dr_ssh_target": dr.ssh_target if dr else None,
            "dr_remote_directory": dr.remote_directory if dr else None,
        }
        if any(identity.get(key) != value for key, value in static_identity.items()):
            raise DeploymentError("lifecycle target identity changed")
        if (
            not isinstance(identity.get("docker_endpoint"), str)
            or not identity["docker_endpoint"]
            or not isinstance(identity.get("docker_daemon_id"), str)
            or not identity["docker_daemon_id"]
            or set(identity)
            != {*static_identity, "docker_endpoint", "docker_daemon_id"}
        ):
            raise DeploymentError("lifecycle target identity is invalid")
        if verify_runtime and identity != self._target_identity(target):
            raise DeploymentError("lifecycle target runtime identity changed")

    def _read_state(
        self, target: Target, *, verify_runtime: bool = True
    ) -> dict[str, Any]:
        path = self._state_path(target)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeploymentError(
                f"target {target.name} has no valid verified lifecycle state"
            ) from exc
        integrity = payload.get("integrity") if isinstance(payload, dict) else None
        if (
            not isinstance(integrity, Mapping)
            or integrity.get("algorithm") != "hmac-sha256"
            or not isinstance(integrity.get("value"), str)
            or not hmac.compare_digest(
                integrity["value"], self._state_signature(target, payload)
            )
        ):
            raise DeploymentError(
                f"target {target.name} lifecycle state signature is invalid"
            )
        status = payload.get("status") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("target") != target.name
            or status
            not in {
                "verified",
                "bootstrap_pending",
                "upgrade_pending",
                "rollback_pending",
            }
            or not isinstance(payload.get("current"), dict)
            or (
                status == "bootstrap_pending"
                and payload.get("phase") not in BOOTSTRAP_PHASES
            )
        ):
            raise DeploymentError(
                f"target {target.name} lifecycle state is not trusted"
            )
        try:
            self._validate_target_identity(
                target, payload.get("target_identity"), verify_runtime=verify_runtime
            )
            self._validate_release_snapshot(target, payload["current"])
            self._require_same_database_runtime(target, payload["current"])
            previous = payload.get("previous")
            pending = payload.get("pending")
            if previous is not None:
                self._validate_release_snapshot(target, previous)
                self._require_same_database_runtime(target, previous)
            if pending is not None:
                self._validate_release_snapshot(target, pending)
                self._require_same_database_runtime(target, pending)
            if status == "verified" and pending is not None:
                raise DeploymentError("verified lifecycle state has pending release")
            if status in {"upgrade_pending", "rollback_pending"} and pending is None:
                raise DeploymentError("pending lifecycle state has no pending release")
            checkpoint_required = status != "bootstrap_pending" or payload.get(
                "phase"
            ) in {
                "schema_verified",
                "runtime_started",
                "dr_verified",
            }
            if checkpoint_required and verify_runtime:
                self._verify_schema_checkpoint_identity(target, payload)
            elif checkpoint_required:
                self._validate_schema_checkpoint(payload)
            backup_required = (
                status != "bootstrap_pending" or payload.get("phase") == "dr_verified"
            )
            if backup_required:
                self._validate_backup_checkpoint(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise DeploymentError(
                f"target {target.name} lifecycle state is not trusted"
            ) from exc
        return payload

    def _validate_release_snapshot(self, target: Target, release: Any) -> None:
        if not isinstance(release, Mapping):
            raise DeploymentError("lifecycle release snapshot is not trusted")
        environment = release.get("application_environment")
        configuration_reference = release.get("application_configuration")
        configuration_hash = release.get("application_configuration_sha256")
        compose_reference = release.get("application_compose")
        sensitive_keys = release.get("application_sensitive_keys")
        database = release.get("database")
        try:
            configuration = json.loads(
                self._read_release_artifact(
                    target, configuration_reference, "configuration", "json"
                ).decode("utf-8")
            )
            compose_content = self._read_release_artifact(
                target, compose_reference, "compose", "yml"
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeploymentError("lifecycle release artifact is invalid") from exc
        if (
            set(release)
            != {
                "application_compose",
                "application_configuration",
                "application_configuration_sha256",
                "application_environment",
                "application_sensitive_keys",
                "database",
            }
            or not isinstance(environment, Mapping)
            or set(environment) != set(RELEASE_KEYS)
            or any(not isinstance(value, str) for value in environment.values())
            or not isinstance(configuration, Mapping)
            or any(
                not isinstance(key, str)
                or not isinstance(value, str)
                or key not in SNAPSHOT_CONFIGURATION_KEYS
                for key, value in configuration.items()
            )
            or not isinstance(configuration_hash, str)
            or not isinstance(configuration_reference, Mapping)
            or not isinstance(compose_content, bytes)
            or not compose_content.strip()
            or not isinstance(sensitive_keys, list)
            or sensitive_keys != sorted(set(sensitive_keys))
            or any(key not in SENSITIVE_ENV_KEYS for key in sensitive_keys)
            or not isinstance(database, Mapping)
            or set(database)
            != {
                "canonical_runtime_image",
                "runtime_image",
                "schema_application_image",
                "project_name",
                "repository_volume",
            }
            or any(not isinstance(value, str) for value in database.values())
        ):
            raise DeploymentError("lifecycle release snapshot is not trusted")
        if configuration_hash != configuration_reference.get("sha256"):
            raise DeploymentError("lifecycle application configuration hash is invalid")
        expected_hash = _sha256_bytes(_canonical_json_bytes(dict(configuration)))
        if configuration_hash != expected_hash:
            raise DeploymentError("lifecycle application configuration hash is invalid")
        if re.fullmatch(r"[0-9a-f]{40}", environment["CANDIDATE_GIT_SHA"]) is None:
            raise DeploymentError("lifecycle release commit is invalid")
        for key in (
            "DCIM_BACKEND_IMAGE",
            "DCIM_FRONTEND_IMAGE",
            "DCIM_REDIS_IMAGE",
            "DCIM_EMQX_IMAGE",
        ):
            if IMAGE_DIGEST_RE.fullmatch(environment[key]) is None:
                raise DeploymentError("lifecycle release image is invalid")
        for image_key, id_key in (
            ("DCIM_BACKEND_IMAGE", "DCIM_BACKEND_EXPECTED_ID"),
            ("DCIM_FRONTEND_IMAGE", "DCIM_FRONTEND_EXPECTED_ID"),
        ):
            image_match = IMAGE_DIGEST_RE.fullmatch(environment[image_key])
            id_match = IMAGE_ID_RE.fullmatch(environment[id_key])
            if (
                image_match is None
                or id_match is None
                or image_match.group(1) != id_match.group(1)
            ):
                raise DeploymentError("lifecycle release image identity is invalid")
        for key in (
            "canonical_runtime_image",
            "runtime_image",
            "schema_application_image",
        ):
            if IMAGE_DIGEST_RE.fullmatch(database[key]) is None:
                raise DeploymentError("lifecycle database image is invalid")

    def _write_state(self, target: Target, payload: Mapping[str, Any]) -> None:
        signed = dict(payload)
        signed.pop("integrity", None)
        signed["integrity"] = {
            "algorithm": "hmac-sha256",
            "value": self._state_signature(target, signed),
        }
        _atomic_json(self._state_path(target), signed)

    def _release(self, target: Target, values: Mapping[str, str]) -> dict[str, Any]:
        assert target.dr is not None
        configuration = {
            key: values[key]
            for key in sorted(SNAPSHOT_CONFIGURATION_KEYS)
            if key in values
        }
        configuration_reference = self._release_artifact(
            target,
            "configuration",
            _canonical_json_bytes(configuration),
            "json",
        )
        try:
            compose_content = target.compose_file.read_bytes()
        except OSError as exc:
            raise DeploymentError(
                "application Compose file cannot be snapshotted"
            ) from exc
        if not compose_content.strip():
            raise DeploymentError("application Compose file is empty")
        for key in SENSITIVE_ENV_KEYS:
            value = values.get(key)
            if (
                isinstance(value, str)
                and len(value) >= 8
                and value.encode() in compose_content
            ):
                raise DeploymentError(
                    "application Compose file contains an expanded secret"
                )
        compose_reference = self._release_artifact(
            target, "compose", compose_content, "yml"
        )
        return {
            "application_environment": {key: values[key] for key in RELEASE_KEYS},
            "application_configuration": configuration_reference,
            "application_configuration_sha256": configuration_reference["sha256"],
            "application_compose": compose_reference,
            "application_sensitive_keys": sorted(
                key for key in SENSITIVE_ENV_KEYS if key in values
            ),
            "database": {
                "canonical_runtime_image": target.dr.canonical_runtime_image,
                "runtime_image": target.dr.final_runtime_image,
                "schema_application_image": target.dr.schema_application_image,
                "project_name": target.dr.project_name,
                "repository_volume": target.dr.repository_volume,
            },
        }

    def _verified_state(
        self,
        target: Target,
        current: Mapping[str, Any],
        *,
        previous: Mapping[str, Any] | None,
        action: str,
        schema_checkpoint: Mapping[str, Any] | None = None,
        backup_checkpoint: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert target.dr is not None
        if schema_checkpoint is None:
            schema_checkpoint = self._schema_checkpoint(
                target,
                {"catalog_sha256": self._load_manifest(target.dr)["catalog_sha256"]},
            )
        if backup_checkpoint is None:
            backup_checkpoint = self._backup_checkpoint(target, ())
        return {
            "schema_version": 1,
            "target": target.name,
            "status": "verified",
            "current": current,
            "previous": previous,
            "pending": None,
            "last_action": action,
            "verified_at_utc": _utc_text(),
            "schema_compatibility_asserted": self.controller.schema_compatible,
            "schema_checkpoint": dict(schema_checkpoint),
            "backup_checkpoint": dict(backup_checkpoint),
            "target_identity": self._target_identity(target),
            "qualification_window": {
                "annual_slo_proven": False,
                "release_gate": "BLOCKED",
                "invalidated_at_utc": _utc_text(),
                "reason": f"lifecycle_{action}",
            },
        }

    def _mark_pending_failure(
        self, target: Target, error: Exception, secrets: Sequence[str]
    ) -> None:
        try:
            state = self._read_state(target, verify_runtime=False)
        except DeploymentError:
            return
        state["last_failure"] = {
            "at_utc": _utc_text(),
            "stage": self.current_stage,
            "error": redact_text(str(error), secrets),
        }
        self._write_state(target, state)

    def _bootstrap_pending_state(
        self, target: Target, candidate: Mapping[str, Any], phase: str
    ) -> dict[str, Any]:
        if phase not in BOOTSTRAP_PHASES:
            raise DeploymentError(f"unsupported bootstrap phase: {phase}")
        now = _utc_text()
        return {
            "schema_version": 1,
            "target": target.name,
            "status": "bootstrap_pending",
            "phase": phase,
            "current": candidate,
            "previous": None,
            "pending": None,
            "last_action": "bootstrap",
            "pending_started_at_utc": now,
            "phase_updated_at_utc": now,
            "schema_compatibility_asserted": False,
            "target_identity": self._target_identity(target),
            "qualification_window": {
                "annual_slo_proven": False,
                "release_gate": "BLOCKED",
                "invalidated_at_utc": now,
                "reason": "lifecycle_bootstrap_pending",
            },
        }

    def _advance_bootstrap_state(
        self,
        target: Target,
        state: Mapping[str, Any],
        phase: str,
        *,
        candidate: Mapping[str, Any] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if phase not in BOOTSTRAP_PHASES:
            raise DeploymentError(f"unsupported bootstrap phase: {phase}")
        updated = dict(state)
        updated["phase"] = phase
        updated["phase_updated_at_utc"] = _utc_text()
        updated["last_failure"] = None
        if candidate is not None:
            updated["current"] = candidate
        if extra:
            updated.update(extra)
        self._write_state(target, updated)
        return updated

    def _load_manifest(self, dr: DRConfig) -> dict[str, Any]:
        try:
            payload = json.loads(CANONICAL_MANIFEST.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeploymentError("canonical schema manifest cannot be read") from exc
        if (
            not isinstance(payload, Mapping)
            or IMAGE_DIGEST_RE.fullmatch(str(payload.get("runtime_image", ""))) is None
            or IMAGE_DIGEST_RE.fullmatch(str(payload.get("application_image", "")))
            is None
            or payload.get("runtime_image") != dr.canonical_runtime_image
            or payload.get("application_image") != dr.schema_application_image
            or payload.get("table_count") != EXPECTED_TABLE_COUNT
            or payload.get("alembic_head") != "20260707_0100"
            or any(
                re.fullmatch(r"[0-9a-f]{64}", str(payload.get(key, ""))) is None
                for key in (
                    "artifact_sha256",
                    "catalog_sha256",
                    "table_names_sha256",
                )
            )
            or re.fullmatch(r"[0-9a-f]{40}", str(payload.get("source_revision", "")))
            is None
        ):
            raise DeploymentError(
                "DR canonical images or hashes do not match the approved schema manifest"
            )
        try:
            versions = yaml.safe_load(VERSIONS_FILE.read_text(encoding="utf-8"))
            accepted_runtime = versions["release_image"]["accepted_reference"]
        except (OSError, TypeError, KeyError, yaml.YAMLError) as exc:
            raise DeploymentError(
                "approved DR runtime versions cannot be read"
            ) from exc
        if (
            not isinstance(accepted_runtime, str)
            or IMAGE_DIGEST_RE.fullmatch(accepted_runtime) is None
            or dr.final_runtime_image != accepted_runtime
        ):
            raise DeploymentError(
                "DR final runtime does not match versions.yaml accepted_reference"
            )
        return payload

    def _engine_preflight(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        assert target.dr is not None
        dr = target.dr
        if not target.compose_file.is_file() or not dr.compose_file.is_file():
            raise DeploymentError("application or DR Compose file does not exist")
        manifest = self._load_manifest(dr)
        expected_network = f"{dr.project_name}_database-client"
        expected_status_volume = f"{dr.project_name}_dr-status"
        if values["DCIM_DR_DATABASE_NETWORK"] != expected_network:
            raise DeploymentError(
                "DCIM_DR_DATABASE_NETWORK does not match dr.project_name"
            )
        if values["DCIM_DR_STATUS_VOLUME"] != expected_status_volume:
            raise DeploymentError(
                "DCIM_DR_STATUS_VOLUME does not match dr.project_name"
            )
        result = self.runner.run(
            build_docker_command(target, "info", "--format", "{{json .}}"),
            secrets=secrets,
        )
        info = _parse_json_output(result.stdout.strip(), "engine info")
        if not isinstance(info, Mapping):
            raise DeploymentError("Docker engine info must be a JSON object")
        daemon_id = info.get("ID")
        if not isinstance(daemon_id, str) or not daemon_id.strip():
            raise DeploymentError("Docker engine info has no stable daemon ID")
        if str(info.get("OSType", "")).lower() != "linux":
            raise DeploymentError("lifecycle deployment requires Linux containers")
        if str(info.get("Architecture", "")).lower() not in {"amd64", "x86_64"}:
            raise DeploymentError("lifecycle deployment requires amd64")
        compose_version = self.runner.run(
            build_docker_command(target, "compose", "version"), secrets=secrets
        ).stdout.strip()
        if dr.mode == "ssh":
            context_host = self._docker_endpoint(target)
            expected_host = f"ssh://{dr.ssh_target}"
            if context_host != expected_host:
                raise DeploymentError(
                    "dr.ssh_target must match the Docker context SSH endpoint"
                )
        return [
            {
                "name": "lifecycle_preflight",
                "status": "passed",
                "docker_daemon_id": daemon_id,
                "docker_server_version": info.get("ServerVersion"),
                "compose_version": compose_version,
                "canonical_table_count": manifest["table_count"],
                "canonical_alembic_head": manifest["alembic_head"],
            }
        ]

    def _resource_lines(self, target: Target, kind: str, project: str) -> list[str]:
        command = [kind, "ls"]
        if kind == "container":
            command.append("--all")
        command.extend(
            [
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--format",
                "{{.ID}}",
            ]
        )
        output = self.runner.run(build_docker_command(target, *command)).stdout
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _require_empty_target(self, target: Target) -> None:
        assert target.dr is not None
        state_path = self._state_path(target)
        if state_path.exists():
            raise DeploymentError(
                "bootstrap refuses a target with existing lifecycle state"
            )
        for project in (target.project_name, target.dr.project_name):
            for kind in ("container", "network", "volume"):
                if self._resource_lines(target, kind, project):
                    raise DeploymentError(
                        f"bootstrap refuses existing {kind} resources for project {project}"
                    )
        exact_resources = {
            "container": [
                *(
                    f"{target.project_name}-{service}-1"
                    for service in ("redis", "emqx", "backend", "nginx")
                ),
                *(
                    f"{target.dr.project_name}-{service}-1"
                    for service in (
                        "postgres-primary",
                        "postgres-standby",
                        "backup-scheduler",
                    )
                ),
            ],
            "network": [
                f"{target.project_name}_dcim-network",
                *(
                    f"{target.dr.project_name}_{name}"
                    for name in (
                        "primary-site",
                        "standby-site",
                        "replication-transit",
                        "database-client",
                        "restore-isolated",
                    )
                ),
            ],
            "volume": [
                *(
                    f"{target.project_name}_{name}"
                    for name in ("redis-data", "emqx-data", "observability-state")
                ),
                *(
                    f"{target.dr.project_name}_{name}"
                    for name in (
                        "postgres-primary-data",
                        "postgres-standby-data",
                        "postgres-restore-data",
                        "postgres-socket",
                        "dr-status",
                        "restore-socket",
                    )
                ),
            ],
        }
        for kind, names in exact_resources.items():
            command = [kind, "ls"]
            if kind == "container":
                command.append("--all")
                format_value = "{{.Names}}"
            else:
                format_value = "{{.Name}}"
            command.extend(["--format", format_value])
            existing = {
                line.strip()
                for line in self.runner.run(
                    build_docker_command(target, *command)
                ).stdout.splitlines()
                if line.strip()
            }
            for name in names:
                if name in existing:
                    raise DeploymentError(
                        f"bootstrap refuses existing {kind} resource {name}"
                    )
        repositories = self.runner.run(
            build_docker_command(
                target,
                "volume",
                "ls",
                "--filter",
                f"name={target.dr.repository_volume}",
                "--format",
                "{{.Name}}",
            )
        ).stdout.splitlines()
        if target.dr.repository_volume in {line.strip() for line in repositories}:
            raise DeploymentError(
                "bootstrap refuses an existing pgBackRest repository volume"
            )

    def _dr_environment(
        self,
        target: Target,
        values: Mapping[str, str],
        secret_paths: Mapping[str, Path],
        runtime_image: str,
        *,
        remote: bool,
    ) -> dict[str, str]:
        assert target.dr is not None
        dr = target.dr
        database_user, _password, database = _database_identity(values["DATABASE_URL"])
        repository, digest = _split_image(runtime_image)
        if remote:
            assert dr.remote_directory is not None
            paths = {
                key: f"{dr.remote_directory}/secrets/{path.name}"
                for key, path in secret_paths.items()
            }
        else:
            paths = {key: str(path) for key, path in secret_paths.items()}
        return {
            "BACKUP_DAILY_HOUR": values.get("BACKUP_DAILY_HOUR", "2"),
            "BACKUP_FULL_WEEKDAY": values.get("BACKUP_FULL_WEEKDAY", "0"),
            "BACKUP_INCREMENTAL_HOURS": values.get(
                "BACKUP_INCREMENTAL_HOURS", "8,14,20"
            ),
            "DCIM_POSTGRES_IMAGE_DIGEST": digest,
            "DCIM_POSTGRES_IMAGE_REPOSITORY": repository,
            "EXPECTED_ALEMBIC_HEAD": "20260707_0100",
            "FENCE_TOKEN_FILE": paths["FENCE_TOKEN_FILE"],
            "PGBACKREST_CIPHER_PASS_FILE": paths["PGBACKREST_CIPHER_PASS_FILE"],
            "PGBACKREST_REPOSITORY_VOLUME": dr.repository_volume,
            "POSTGRES_DB": database,
            "POSTGRES_PASSWORD_FILE": paths["POSTGRES_PASSWORD_FILE"],
            "POSTGRES_USER": database_user,
            "REPLICATION_PASSWORD_FILE": paths["REPLICATION_PASSWORD_FILE"],
        }

    def _prepare_dr_files(
        self, target: Target, values: Mapping[str, str]
    ) -> tuple[dict[str, Path], dict[str, Path]]:
        assert target.dr is not None
        dr = target.dr
        secret_paths = prepare_secret_files(dr, values["DATABASE_URL"])
        remote = dr.mode == "ssh"
        environment_paths: dict[str, Path] = {}
        for stage, image in (
            ("canonical", dr.canonical_runtime_image),
            ("runtime", dr.final_runtime_image),
        ):
            path = dr.secret_directory / f"story-39-3-{stage}.env"
            _atomic_text(
                path,
                _env_text(
                    self._dr_environment(
                        target, values, secret_paths, image, remote=remote
                    )
                ),
            )
            environment_paths[stage] = path
        return secret_paths, environment_paths

    def _stage_remote_file(
        self,
        target: Target,
        local_path: Path,
        remote_directory: str,
        remote_name: str,
        secrets: Sequence[str],
        *,
        immutable: bool,
    ) -> None:
        assert target.dr is not None
        dr = target.dr
        assert dr.ssh_target is not None
        digest = _sha256_bytes(local_path.read_bytes())
        incoming_name = f".{remote_name}.incoming-{secret_generator.token_hex(8)}"
        incoming_path = f"{remote_directory}/{incoming_name}"
        final_path = f"{remote_directory}/{remote_name}"
        stale_pattern = f".{remote_name}.incoming-*"
        stale_cleanup = (
            f"find {remote_directory} -maxdepth 1 -type f "
            f'-name {shlex.quote(stale_pattern)} -user "$(id -u)" -delete'
        )
        self.runner.run(
            [
                "ssh",
                *dr.ssh_args,
                dr.ssh_target,
                "sh",
                "-c",
                shlex.quote(stale_cleanup),
            ],
            secrets=secrets,
        )
        cleanup = f"rm -f -- {incoming_path}"
        try:
            self.runner.run(
                [
                    "scp",
                    *dr.scp_args,
                    str(local_path),
                    f"{dr.ssh_target}:{incoming_path}",
                ],
                secrets=secrets,
                timeout=300,
            )
            existing_action = (
                f"test -f {final_path} && ! test -L {final_path} && "
                f'test "$(stat -c %u {final_path})" = "$(id -u)" && '
                f'test "$(stat -c %a {final_path})" = 600 && '
                f'test "$(sha256sum {final_path} | cut -d " " -f1)" = {digest} && '
                f"cmp -s {incoming_path} {final_path} || exit 73; "
                f"rm -f -- {incoming_path}"
                if immutable
                else f"chmod 0600 {incoming_path}; mv -f -- {incoming_path} {final_path}"
            )
            install_script = (
                f"trap 'rm -f -- {incoming_path}' EXIT HUP INT TERM; "
                f"test -f {incoming_path} && ! test -L {incoming_path} && "
                f'test "$(stat -c %u {incoming_path})" = "$(id -u)" && '
                f'test "$(sha256sum {incoming_path} | cut -d " " -f1)" = {digest} '
                f"|| exit 76; if test -e {final_path}; then {existing_action}; "
                f"else chmod 0600 {incoming_path}; mv -- {incoming_path} {final_path}; fi; "
                f"test -f {final_path} && ! test -L {final_path} && "
                f'test "$(stat -c %u {final_path})" = "$(id -u)" && '
                f'test "$(stat -c %a {final_path})" = 600 && '
                f'test "$(sha256sum {final_path} | cut -d " " -f1)" = {digest} '
                "|| exit 77; trap - EXIT HUP INT TERM"
            )
            self.runner.run(
                [
                    "ssh",
                    *dr.ssh_args,
                    dr.ssh_target,
                    "sh",
                    "-c",
                    shlex.quote(install_script),
                ],
                secrets=secrets,
            )
        except BaseException:
            try:
                self.runner.run(
                    [
                        "ssh",
                        *dr.ssh_args,
                        dr.ssh_target,
                        "sh",
                        "-c",
                        shlex.quote(cleanup),
                    ],
                    secrets=secrets,
                )
            except BaseException:
                pass
            raise

    def _stage_remote(
        self,
        target: Target,
        secret_paths: Mapping[str, Path],
        environment_paths: Mapping[str, Path],
        secrets: Sequence[str],
    ) -> None:
        assert target.dr is not None
        dr = target.dr
        if dr.mode != "ssh":
            return
        assert dr.ssh_target is not None and dr.remote_directory is not None
        remote_secret_directory = f"{dr.remote_directory}/secrets"
        self.runner.run(
            [
                "ssh",
                *dr.ssh_args,
                dr.ssh_target,
                "install",
                "-d",
                "-m",
                "0700",
                dr.remote_directory,
                remote_secret_directory,
            ],
            secrets=secrets,
        )
        self._stage_remote_file(
            target,
            dr.compose_file,
            dr.remote_directory,
            "docker-compose.dr.yml",
            secrets,
            immutable=False,
        )
        for path in environment_paths.values():
            self._stage_remote_file(
                target,
                path,
                dr.remote_directory,
                path.name,
                secrets,
                immutable=False,
            )
        for path in secret_paths.values():
            self._stage_remote_file(
                target,
                path,
                remote_secret_directory,
                path.name,
                secrets,
                immutable=True,
            )

    def _dr_compose_command(self, target: Target, stage: str, *args: str) -> list[str]:
        assert target.dr is not None
        dr = target.dr
        env_name = f"story-39-3-{stage}.env"
        if dr.mode == "local":
            return build_docker_command(
                target,
                "compose",
                "--env-file",
                str(dr.secret_directory / env_name),
                "--file",
                str(dr.compose_file),
                "--project-name",
                dr.project_name,
                *args,
            )
        assert dr.ssh_target is not None and dr.remote_directory is not None
        return [
            "ssh",
            *dr.ssh_args,
            dr.ssh_target,
            "docker",
            "compose",
            "--env-file",
            f"{dr.remote_directory}/{env_name}",
            "--file",
            f"{dr.remote_directory}/docker-compose.dr.yml",
            "--project-name",
            dr.project_name,
            *args,
        ]

    def _provision_e2e_admin(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
    ) -> dict[str, Any]:
        username = values.get("E2E_ADMIN_USER", "").strip()
        password = values.get("E2E_ADMIN_PASSWORD", "")
        if not username or not password:
            raise DeploymentError(
                "bootstrap requires E2E_ADMIN_USER and E2E_ADMIN_PASSWORD"
            )
        if len(password) < 12 or any(character.isspace() for character in password):
            raise DeploymentError(
                "E2E_ADMIN_PASSWORD must contain at least 12 non-whitespace characters"
            )

        script = """
import asyncio
import json
import os
from datetime import datetime

from sqlalchemy import delete, select

from app.core.database import async_session
from app.core.security import get_password_hash
from app.models import User, UserSession


async def provision():
    username = os.environ["E2E_ADMIN_USER"]
    password = os.environ["E2E_ADMIN_PASSWORD"]
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == username).with_for_update()
        )
        user = result.scalar_one_or_none()
        created = user is None
        if created:
            user = User(username=username)
            session.add(user)
        user.password_hash = get_password_hash(password)
        user.role = "admin"
        user.is_active = True
        user.password_changed_at = datetime.now()
        await session.flush()
        await session.execute(delete(UserSession).where(UserSession.user_id == user.id))
        await session.commit()
    print(json.dumps({"created": created, "role": "admin", "active": True}))


asyncio.run(provision())
""".strip()
        process_environment = dict(os.environ)
        for key in (
            "DATABASE_URL",
            "E2E_ADMIN_USER",
            "E2E_ADMIN_PASSWORD",
            "FAULT_TREE_HMAC_KEY",
        ):
            process_environment[key] = values[key]
        name = f"dcim-story-39-7-admin-{uuid.uuid4().hex[:10]}"
        result = self.runner.run(
            build_docker_command(
                target,
                "run",
                "--rm",
                "--name",
                name,
                "--network",
                values["DCIM_DR_DATABASE_NETWORK"],
                "--label",
                "com.dcim.story=39.7",
                "--label",
                "com.dcim.role=e2e-admin-bootstrap",
                "--entrypoint",
                "python",
                "--env",
                "DATABASE_URL",
                "--env",
                "E2E_ADMIN_USER",
                "--env",
                "E2E_ADMIN_PASSWORD",
                "--env",
                "FAULT_TREE_HMAC_KEY",
                values["DCIM_BACKEND_IMAGE"],
                "-c",
                script,
            ),
            env=process_environment,
            timeout=180,
            secrets=secrets,
        )
        payload = _parse_json_output(result.stdout.strip(), "E2E admin bootstrap")
        if (
            not isinstance(payload, Mapping)
            or payload.get("role") != "admin"
            or payload.get("active") is not True
        ):
            raise DeploymentError("E2E admin bootstrap returned an invalid result")
        return {
            "name": "e2e_admin_bootstrap",
            "status": "passed",
            "username": username,
            "created": payload.get("created") is True,
            "credentials_reported": False,
            "sessions_revoked": True,
        }

    def _pull_dr_images(
        self, target: Target, secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        assert target.dr is not None
        references = list(
            dict.fromkeys(
                [
                    target.dr.canonical_runtime_image,
                    target.dr.final_runtime_image,
                    target.dr.schema_application_image,
                ]
            )
        )
        inspected = []
        for reference in references:
            self.runner.run(
                build_docker_command(target, "pull", reference),
                timeout=1800,
                secrets=secrets,
            )
            output = self.runner.run(
                build_docker_command(
                    target, "image", "inspect", reference, "--format", "{{json .}}"
                ),
                secrets=secrets,
            ).stdout.strip()
            image = _parse_json_output(output, "DR image")
            if not isinstance(image, Mapping) or not str(
                image.get("Id", "")
            ).startswith("sha256:"):
                raise DeploymentError("DR image inspection is invalid")
            inspected.append({"reference": reference, "image_id": image["Id"]})
        return [{"name": "dr_images", "status": "passed", "images": inspected}]

    def _verify_candidate_schema(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
        *,
        pull_images: bool = True,
    ) -> dict[str, Any]:
        assert target.dr is not None
        manifest = self._load_manifest(target.dr)
        candidate_image = values["DCIM_BACKEND_IMAGE"]
        for image in {candidate_image, target.dr.schema_application_image}:
            if pull_images and not is_local_image_reference(image):
                self.runner.run(
                    build_docker_command(target, "pull", image),
                    timeout=1800,
                    secrets=secrets,
                )
            else:
                output = self.runner.run(
                    build_docker_command(
                        target, "image", "inspect", image, "--format", "{{json .Id}}"
                    ),
                    secrets=secrets,
                ).stdout.strip()
                image_id = _parse_json_output(output, "local schema image")
                if (
                    not isinstance(image_id, str)
                    or IMAGE_ID_RE.fullmatch(image_id) is None
                ):
                    raise DeploymentError(
                        "rollback schema image is unavailable locally"
                    )
        probe = """
import hashlib
import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.database import Base
import app.api.v1
import app.models


def normalized_table(table):
    columns = []
    for column in table.columns:
        enum_values = getattr(column.type, "enums", None)
        columns.append({
            "name": column.name,
            "type": str(column.type),
            "type_class": f"{type(column.type).__module__}.{type(column.type).__qualname__}",
            "enum_values": list(enum_values) if enum_values is not None else None,
            "nullable": column.nullable,
            "primary_key": column.primary_key,
            "unique": column.unique,
            "server_default": str(column.server_default.arg) if column.server_default is not None else None,
            "foreign_keys": sorted(key.target_fullname for key in column.foreign_keys),
        })
    constraints = sorted([
        {
            "kind": type(constraint).__name__,
            "name": constraint.name,
            "columns": sorted(column.name for column in constraint.columns),
            "expression": str(getattr(constraint, "sqltext", "")),
        }
        for constraint in table.constraints
    ], key=lambda item: json.dumps(item, sort_keys=True))
    indexes = sorted([
        {
            "name": index.name,
            "unique": index.unique,
            "expressions": [str(expression) for expression in index.expressions],
        }
        for index in table.indexes
    ], key=lambda item: json.dumps(item, sort_keys=True))
    return {"name": table.name, "columns": columns, "constraints": constraints, "indexes": indexes}


tables = [
    normalized_table(table)
    for table in Base.metadata.sorted_tables
    if table.schema in (None, "public")
]
names = sorted(table["name"] for table in tables)
contract = json.dumps(tables, sort_keys=True, separators=(",", ":"))
migration = hashlib.sha256()
for path in sorted(Path("alembic/versions").glob("*.py")):
    migration.update(path.name.encode())
    migration.update(b"\\0")
    migration.update(path.read_bytes())
heads = sorted(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
print(json.dumps({
    "table_count": len(names),
    "table_names_sha256": hashlib.sha256(("\\n".join(names) + "\\n").encode()).hexdigest(),
    "schema_contract_sha256": hashlib.sha256(contract.encode()).hexdigest(),
    "migration_sha256": migration.hexdigest(),
    "alembic_heads": heads,
}, sort_keys=True))
"""
        probe_secret = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
        process_environment = dict(os.environ)
        process_environment["FAULT_TREE_HMAC_KEY"] = probe_secret
        metadata_by_image: dict[str, Mapping[str, Any]] = {}
        for image in (target.dr.schema_application_image, candidate_image):
            name = f"dcim-story-39-7-schema-{target.name}-{uuid.uuid4().hex[:10]}"
            self.runner.run(
                build_docker_command(
                    target,
                    "create",
                    "--name",
                    name,
                    "--network",
                    "none",
                    "--label",
                    "com.dcim.story=39.7",
                    "--label",
                    "com.dcim.role=schema-metadata",
                    "--entrypoint",
                    "python",
                    "--env",
                    "FAULT_TREE_HMAC_KEY",
                    image,
                    "-c",
                    probe,
                ),
                env=process_environment,
                timeout=120,
                secrets=[*secrets, probe_secret],
            )
            try:
                output = self.runner.run(
                    build_docker_command(target, "start", "--attach", name),
                    timeout=300,
                    secrets=[*secrets, probe_secret],
                ).stdout.strip()
            finally:
                self.runner.run(
                    build_docker_command(target, "rm", "--force", name),
                    timeout=60,
                    secrets=secrets,
                )
            metadata: Any = None
            for line in reversed(output.splitlines()):
                try:
                    metadata = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if not isinstance(metadata, Mapping):
                raise DeploymentError("application schema contract probe is invalid")
            metadata_by_image[image] = metadata
        approved = metadata_by_image[target.dr.schema_application_image]
        candidate = metadata_by_image[candidate_image]
        if (
            approved.get("table_count") != manifest["table_count"]
            or approved.get("table_names_sha256") != manifest["table_names_sha256"]
            or approved.get("alembic_heads") != [manifest["alembic_head"]]
            or candidate != approved
        ):
            raise DeploymentError(
                "candidate schema contract or migrations do not match the approved canonical application"
            )
        return {
            "name": "candidate_schema_compatibility",
            "status": "passed",
            "table_count": candidate["table_count"],
            "table_names_sha256": candidate["table_names_sha256"],
            "schema_contract_sha256": candidate["schema_contract_sha256"],
            "migration_sha256": candidate["migration_sha256"],
            "alembic_heads": candidate["alembic_heads"],
        }

    def _create_repository(
        self, target: Target, secrets: Sequence[str]
    ) -> dict[str, Any]:
        assert target.dr is not None
        self.runner.run(
            build_docker_command(
                target,
                "volume",
                "create",
                "--label",
                "com.dcim.story=39.3",
                "--label",
                "com.dcim.dr.role=pgbackrest-repository",
                "--label",
                f"com.dcim.lifecycle.target={target.name}",
                target.dr.repository_volume,
            ),
            secrets=secrets,
        )
        inspection = self.runner.run(
            build_docker_command(
                target,
                "volume",
                "inspect",
                target.dr.repository_volume,
                "--format",
                "{{json .}}",
            ),
            secrets=secrets,
        ).stdout.strip()
        volume = _parse_json_output(inspection, "pgBackRest repository volume")
        fingerprint = self._repository_volume_fingerprint(target, volume=volume)
        return {
            "name": "pgbackrest_repository",
            "status": "passed",
            "volume": target.dr.repository_volume,
            "created_at": fingerprint["created_at"],
            "failure_domain": "mechanism-only",
        }

    def _repository_volume_fingerprint(
        self, target: Target, *, volume: Any | None = None
    ) -> dict[str, Any]:
        assert target.dr is not None
        if volume is None:
            output = self.runner.run(
                build_docker_command(
                    target,
                    "volume",
                    "inspect",
                    target.dr.repository_volume,
                    "--format",
                    "{{json .}}",
                )
            ).stdout.strip()
            volume = _parse_json_output(output, "pgBackRest repository volume")
        if not isinstance(volume, Mapping):
            raise DeploymentError("pgBackRest repository volume inspection is invalid")
        labels = volume.get("Labels")
        created_at = volume.get("CreatedAt")
        if (
            volume.get("Name") != target.dr.repository_volume
            or not isinstance(created_at, str)
            or not created_at.strip()
            or not isinstance(labels, Mapping)
            or labels.get("com.dcim.story") != "39.3"
            or labels.get("com.dcim.dr.role") != "pgbackrest-repository"
            or labels.get("com.dcim.lifecycle.target") != target.name
        ):
            raise DeploymentError("pgBackRest repository volume identity is invalid")
        return {
            "name": target.dr.repository_volume,
            "created_at": created_at,
            "labels": {str(key): str(labels[key]) for key in sorted(labels)},
        }

    def _primary_volume_fingerprint(self, target: Target) -> dict[str, Any]:
        assert target.dr is not None
        expected_name = f"{target.dr.project_name}_postgres-primary-data"
        output = self.runner.run(
            build_docker_command(
                target,
                "volume",
                "inspect",
                expected_name,
                "--format",
                "{{json .}}",
            )
        ).stdout.strip()
        volume = _parse_json_output(output, "primary PostgreSQL volume")
        if not isinstance(volume, Mapping):
            raise DeploymentError("primary PostgreSQL volume inspection is invalid")
        labels = volume.get("Labels")
        created_at = volume.get("CreatedAt")
        if (
            volume.get("Name") != expected_name
            or not isinstance(created_at, str)
            or not created_at.strip()
            or not isinstance(labels, Mapping)
            or labels.get("com.dcim.story") != "39.3"
            or labels.get("com.dcim.dr.role") != "primary-data"
            or labels.get("com.docker.compose.project") != target.dr.project_name
        ):
            raise DeploymentError("primary PostgreSQL volume identity is invalid")
        return {
            "name": expected_name,
            "created_at": created_at,
            "labels": {str(key): str(labels[key]) for key in sorted(labels)},
        }

    def _schema_checkpoint(
        self, target: Target, schema_check: Mapping[str, Any]
    ) -> dict[str, Any]:
        catalog_hash = schema_check.get("catalog_sha256")
        if (
            not isinstance(catalog_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", catalog_hash) is None
        ):
            raise DeploymentError("canonical schema report has no trusted catalog hash")
        return {
            "docker_daemon_id": self._docker_daemon_id(target),
            "primary_volume": self._primary_volume_fingerprint(target),
            "repository_volume": self._repository_volume_fingerprint(target),
            "catalog_sha256": catalog_hash,
            "verified_at_utc": _utc_text(),
        }

    def _validate_schema_checkpoint(
        self, state: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        checkpoint = state.get("schema_checkpoint")
        if not isinstance(checkpoint, Mapping):
            raise DeploymentError("lifecycle schema checkpoint is missing")
        if (
            not isinstance(checkpoint.get("docker_daemon_id"), str)
            or not checkpoint["docker_daemon_id"]
            or not isinstance(checkpoint.get("primary_volume"), Mapping)
            or not isinstance(checkpoint.get("repository_volume"), Mapping)
            or re.fullmatch(r"[0-9a-f]{64}", str(checkpoint.get("catalog_sha256", "")))
            is None
            or not isinstance(checkpoint.get("verified_at_utc"), str)
        ):
            raise DeploymentError("lifecycle schema checkpoint is invalid")
        return checkpoint

    def _probe_live_database(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
    ) -> dict[str, Any]:
        assert target.dr is not None
        manifest = self._load_manifest(target.dr)
        probe = f"""
import asyncio
import hashlib
import json
import os

import asyncpg

CATALOG_SQL = {CATALOG_SQL!r}
OCCUPANCY_SQL = {OCCUPANCY_SQL!r}


async def main():
    url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1)
    connection = await asyncio.wait_for(asyncpg.connect(url), timeout=30)
    try:
        occupancy_raw = await asyncio.wait_for(connection.fetchval(OCCUPANCY_SQL), timeout=60)
        occupancy = json.loads(occupancy_raw)
        if not isinstance(occupancy, dict) or any(not isinstance(value, int) for value in occupancy.values()):
            raise RuntimeError("database occupancy is invalid")
        if not any(occupancy.values()):
            print(json.dumps({{"database_state": "empty"}}, sort_keys=True))
            return
        raw = await asyncio.wait_for(connection.fetchval(CATALOG_SQL), timeout=60)
    finally:
        await connection.close()
    catalog = json.loads(raw)
    normalized = json.dumps(catalog, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    print(json.dumps({{
        "database_state": "occupied",
        "catalog_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "alembic_head": catalog.get("alembic_head"),
    }}, sort_keys=True))


asyncio.run(main())
""".strip()
        database_url = values["DATABASE_URL"]
        process_environment = dict(os.environ)
        process_environment["DATABASE_URL"] = database_url
        name = f"dcim-story-39-7-live-catalog-{target.name}-{uuid.uuid4().hex[:8]}"
        output = self.runner.run(
            build_docker_command(
                target,
                "container",
                "run",
                "--rm",
                "--name",
                name,
                "--network",
                values["DCIM_DR_DATABASE_NETWORK"],
                "--label",
                "com.dcim.story=39.7",
                "--label",
                "com.dcim.role=schema-catalog",
                "--env",
                "DATABASE_URL",
                "--entrypoint",
                "python",
                target.dr.schema_application_image,
                "-c",
                probe,
            ),
            env=process_environment,
            timeout=180,
            secrets=[*secrets, database_url],
        ).stdout.strip()
        result = _parse_json_output(output, "live canonical database")
        if isinstance(result, Mapping) and result.get("database_state") == "empty":
            return {
                "name": "live_canonical_catalog",
                "status": "passed",
                "database_state": "empty",
            }
        if (
            not isinstance(result, Mapping)
            or result.get("database_state") != "occupied"
            or result.get("catalog_sha256") != manifest["catalog_sha256"]
            or result.get("alembic_head") != manifest["alembic_head"]
        ):
            raise DeploymentError(
                "live canonical catalog differs from the approved manifest"
            )
        return {
            "name": "live_canonical_catalog",
            "status": "passed",
            "database_state": "canonical",
            "catalog_sha256": result["catalog_sha256"],
            "alembic_head": result["alembic_head"],
            "application_image": target.dr.schema_application_image,
        }

    def _verify_schema_checkpoint(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._verify_schema_checkpoint_identity(target, state)
        checkpoint = state.get("schema_checkpoint")
        assert isinstance(checkpoint, Mapping)
        daemon_id = str(checkpoint["docker_daemon_id"])
        live = self._probe_live_database(target, values, secrets)
        if live.get("database_state") != "canonical":
            raise DeploymentError("bootstrap canonical database is unexpectedly empty")
        checkpoint_refreshed = checkpoint.get("catalog_sha256") != live["catalog_sha256"]
        return {
            **live,
            "name": "bootstrap_schema_resume",
            "primary_volume": checkpoint["primary_volume"]["name"],
            "docker_daemon_id": daemon_id,
            "checkpoint_refreshed": checkpoint_refreshed,
            "previous_catalog_sha256": (
                checkpoint["catalog_sha256"] if checkpoint_refreshed else None
            ),
        }

    def _verify_schema_checkpoint_identity(
        self, target: Target, state: Mapping[str, Any]
    ) -> None:
        checkpoint = self._validate_schema_checkpoint(state)
        daemon_id = self._docker_daemon_id(target)
        if checkpoint.get("docker_daemon_id") != daemon_id:
            raise DeploymentError("lifecycle Docker daemon identity changed")
        if checkpoint.get("primary_volume") != self._primary_volume_fingerprint(target):
            raise DeploymentError("lifecycle primary PostgreSQL volume changed")
        if checkpoint.get("repository_volume") != self._repository_volume_fingerprint(
            target
        ):
            raise DeploymentError("lifecycle pgBackRest repository volume changed")

    def _schema_bootstrap(
        self,
        target: Target,
        values: Mapping[str, str],
        secret_paths: Mapping[str, Path],
        secrets: Sequence[str],
        *,
        output_directory: Path | None = None,
    ) -> dict[str, Any]:
        assert target.dr is not None
        database_user, _password, database = _database_identity(values["DATABASE_URL"])
        container = self.runner.run(
            self._dr_compose_command(
                target, "canonical", "ps", "-q", "postgres-primary"
            ),
            secrets=secrets,
        ).stdout.strip()
        if not container or "\n" in container:
            raise DeploymentError(
                "canonical PostgreSQL primary container is not unique"
            )
        if output_directory is None:
            output_directory = (
                self.controller.inventory.report_directory
                / f"schema-{target.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
            )
        process_environment = dict(os.environ)
        process_environment["DOCKER_CONTEXT"] = target.docker_context
        self.runner.run(
            [
                sys.executable,
                str(SCHEMA_BOOTSTRAP),
                "--project",
                target.dr.project_name,
                "--postgres-container",
                container,
                "--network",
                values["DCIM_DR_DATABASE_NETWORK"],
                "--application-image",
                target.dr.schema_application_image,
                "--postgres-password-file",
                str(secret_paths["POSTGRES_PASSWORD_FILE"]),
                "--database",
                database,
                "--database-user",
                database_user,
                "--output-dir",
                str(output_directory),
            ],
            env=process_environment,
            timeout=1800,
            secrets=secrets,
        )
        return self._read_schema_report(
            target, values, output_directory, expected_container=container
        )

    def _read_schema_report(
        self,
        target: Target,
        values: Mapping[str, str],
        output_directory: Path,
        *,
        expected_container: str | None = None,
    ) -> dict[str, Any]:
        assert target.dr is not None
        report_path = output_directory / "schema-bootstrap-last-run.json"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeploymentError(
                "schema bootstrap did not write a valid report"
            ) from exc
        manifest = self._load_manifest(target.dr)
        database_user, _password, database = _database_identity(values["DATABASE_URL"])
        if expected_container is None:
            expected_container = self.runner.run(
                self._dr_compose_command(
                    target, "canonical", "ps", "-q", "postgres-primary"
                )
            ).stdout.strip()
        expected = {
            "schema_version": 1,
            "status": "pass",
            "project": target.dr.project_name,
            "postgres_container": expected_container,
            "network": values["DCIM_DR_DATABASE_NETWORK"],
            "database": database,
            "database_user": database_user,
            "application_image": target.dr.schema_application_image,
            "runtime_image": target.dr.canonical_runtime_image,
            "canonical_artifact_sha256": manifest["artifact_sha256"],
            "catalog_sha256": manifest["catalog_sha256"],
            "table_names_sha256": manifest["table_names_sha256"],
            "table_count": manifest["table_count"],
            "alembic_head": manifest["alembic_head"],
        }
        if (
            not expected_container
            or "\n" in expected_container
            or not isinstance(report, Mapping)
            or any(report.get(key) != value for key, value in expected.items())
        ):
            raise DeploymentError("schema bootstrap report did not pass")
        return {
            "name": "canonical_schema",
            "status": "passed",
            "table_count": report["table_count"],
            "table_names_sha256": report["table_names_sha256"],
            "catalog_sha256": report["catalog_sha256"],
            "alembic_head": report["alembic_head"],
            "application_image": report["application_image"],
            "runtime_image": report["runtime_image"],
            "project": report["project"],
            "database": report["database"],
            "artifact": str(report_path),
        }

    def _read_backup_status(
        self, target: Target, secrets: Sequence[str]
    ) -> Mapping[str, Any]:
        status_output = self.runner.run(
            self._dr_compose_command(
                target,
                "runtime",
                "--profile",
                "backup",
                "exec",
                "-T",
                "backup-scheduler",
                "cat",
                "/var/lib/dcim-dr-status/last-run.json",
            ),
            secrets=secrets,
        ).stdout.strip()
        backup_status = _parse_json_output(status_output, "DR backup status")
        if (
            not isinstance(backup_status, Mapping)
            or backup_status.get("status") != "success"
            or backup_status.get("step") != "complete"
            or backup_status.get("exit_code") != 0
            or not isinstance(backup_status.get("run_id"), str)
            or not backup_status["run_id"]
        ):
            raise DeploymentError("DR backup status is not a completed successful run")
        return backup_status

    def _read_pgbackrest_info(
        self, target: Target, secrets: Sequence[str]
    ) -> dict[str, Any]:
        info_output = self.runner.run(
            self._dr_compose_command(
                target,
                "runtime",
                "--profile",
                "backup",
                "exec",
                "-T",
                "backup-scheduler",
                "cat",
                "/var/lib/dcim-dr-status/pgbackrest-info.json",
            ),
            secrets=secrets,
        ).stdout.strip()
        payload = _parse_json_output(info_output, "pgBackRest repository info")
        if not isinstance(payload, list) or len(payload) != 1:
            raise DeploymentError("pgBackRest repository info has no unique stanza")
        stanza = payload[0]
        if not isinstance(stanza, Mapping):
            raise DeploymentError("pgBackRest repository stanza is invalid")
        status = stanza.get("status")
        backups = stanza.get("backup")
        if (
            stanza.get("name") != "dcim"
            or not isinstance(status, Mapping)
            or status.get("code") != 0
            or not isinstance(backups, list)
        ):
            raise DeploymentError("pgBackRest repository stanza is not healthy")
        full_labels = sorted(
            {
                str(item.get("label"))
                for item in backups
                if isinstance(item, Mapping)
                and item.get("type") == "full"
                and item.get("error") in {False, None}
                and BACKUP_LABEL_RE.fullmatch(str(item.get("label", "")))
            }
        )
        if not full_labels:
            raise DeploymentError("pgBackRest repository has no valid full backup")
        return {"stanza": "dcim", "full_backup_labels": full_labels}

    def _backup_checkpoint(
        self, target: Target, secrets: Sequence[str]
    ) -> dict[str, Any]:
        repository = self._repository_volume_fingerprint(target)
        backup_status = self._read_backup_status(target, secrets)
        repository_info = self._read_pgbackrest_info(target, secrets)
        return {
            "repository_volume": repository,
            "stanza": repository_info["stanza"],
            "initial_full_backup_label": repository_info["full_backup_labels"][0],
            "last_verified_run_id": backup_status["run_id"],
            "verified_at_utc": _utc_text(),
        }

    def _validate_backup_checkpoint(
        self, state: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        checkpoint = state.get("backup_checkpoint")
        if (
            not isinstance(checkpoint, Mapping)
            or set(checkpoint)
            != {
                "repository_volume",
                "stanza",
                "initial_full_backup_label",
                "last_verified_run_id",
                "verified_at_utc",
            }
            or not isinstance(checkpoint.get("repository_volume"), Mapping)
            or checkpoint.get("stanza") != "dcim"
            or BACKUP_LABEL_RE.fullmatch(
                str(checkpoint.get("initial_full_backup_label", ""))
            )
            is None
            or not isinstance(checkpoint.get("last_verified_run_id"), str)
            or not checkpoint["last_verified_run_id"]
            or not isinstance(checkpoint.get("verified_at_utc"), str)
        ):
            raise DeploymentError("lifecycle backup checkpoint is invalid")
        return checkpoint

    def _verify_backup_checkpoint(
        self,
        target: Target,
        secrets: Sequence[str],
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        checkpoint = self._validate_backup_checkpoint(state)
        repository = self._repository_volume_fingerprint(target)
        if checkpoint.get("repository_volume") != repository:
            raise DeploymentError("lifecycle pgBackRest repository volume changed")
        backup_status = self._read_backup_status(target, secrets)
        repository_info = self._read_pgbackrest_info(target, secrets)
        if (
            checkpoint.get("stanza") != repository_info["stanza"]
            or checkpoint.get("initial_full_backup_label")
            not in repository_info["full_backup_labels"]
        ):
            raise DeploymentError("lifecycle initial full backup is unavailable")
        return {
            "name": "backup_checkpoint",
            "status": "passed",
            "repository_volume": repository["name"],
            "initial_full_backup_label": checkpoint["initial_full_backup_label"],
            "last_operation": backup_status.get("operation"),
        }

    def _verify_dr_services(
        self, target: Target, secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        assert target.dr is not None
        services_output = self.runner.run(
            self._dr_compose_command(
                target, "runtime", "--profile", "backup", "ps", "--format", "json"
            ),
            secrets=secrets,
        ).stdout.strip()
        try:
            parsed = json.loads(services_output)
            services = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            services = [
                json.loads(line) for line in services_output.splitlines() if line
            ]
        by_service = {
            str(item.get("Service")): item
            for item in services
            if isinstance(item, Mapping)
        }
        required = {"postgres-primary", "postgres-standby", "backup-scheduler"}
        if required - set(by_service):
            raise DeploymentError("DR Compose services are incomplete")
        for name in required:
            state = str(by_service[name].get("State", "")).lower()
            health = str(by_service[name].get("Health", "")).lower()
            if state != "running" or (health and health != "healthy"):
                raise DeploymentError(f"DR service {name} is not healthy")
            container = self.runner.run(
                self._dr_compose_command(
                    target, "runtime", "--profile", "backup", "ps", "-q", name
                ),
                secrets=secrets,
            ).stdout.strip()
            image_output = self.runner.run(
                build_docker_command(
                    target,
                    "container",
                    "inspect",
                    container,
                    "--format",
                    "{{json .Config.Image}}",
                ),
                secrets=secrets,
            ).stdout.strip()
            configured_image = _parse_json_output(
                image_output, f"DR service {name} image"
            )
            if configured_image != target.dr.final_runtime_image:
                raise DeploymentError(
                    f"DR service {name} did not transition to final runtime"
                )
        return [
            {
                "name": "dr_services",
                "status": "passed",
                "services": sorted(required),
                "runtime_image": target.dr.final_runtime_image if target.dr else None,
            },
        ]

    def _backup_and_verify_dr(
        self, target: Target, secrets: Sequence[str]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        operations = ["stanza", "full", "check", "verify", "status"]
        for operation in operations:
            self.runner.run(
                self._dr_compose_command(
                    target,
                    "runtime",
                    "--profile",
                    "backup",
                    "run",
                    "--rm",
                    "--no-deps",
                    "--user",
                    "postgres",
                    "backup-scheduler",
                    "/usr/local/bin/backup-job.sh",
                    operation,
                ),
                timeout=3600,
                secrets=secrets,
            )
        self.runner.run(
            self._dr_compose_command(
                target,
                "runtime",
                "--profile",
                "backup",
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never",
                "--wait",
                "--wait-timeout",
                "300",
                "backup-scheduler",
            ),
            timeout=600,
            secrets=secrets,
        )
        backup_checkpoint = self._backup_checkpoint(target, secrets)
        return (
            [
                {
                    "name": "first_full_backup",
                    "status": "passed",
                    "operations": operations,
                    "last_operation": "status",
                    "initial_full_backup_label": backup_checkpoint[
                        "initial_full_backup_label"
                    ],
                },
                *self._verify_dr_services(target, secrets),
            ],
            backup_checkpoint,
        )

    def _initialize_canonical_stanza(
        self, target: Target, secrets: Sequence[str]
    ) -> dict[str, Any]:
        self.runner.run(
            self._dr_compose_command(
                target,
                "canonical",
                "exec",
                "-T",
                "--user",
                "postgres",
                "postgres-primary",
                "/usr/local/bin/backup-job.sh",
                "stanza",
            ),
            timeout=600,
            secrets=secrets,
        )
        return {
            "name": "canonical_pgbackrest_stanza",
            "status": "passed",
            "operation": "stanza",
            "runs_as": "postgres",
        }

    def _verify_resumable_dr(
        self,
        target: Target,
        secrets: Sequence[str],
        state: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "name": "existing_backup",
                "status": "passed",
                "new_full_backup_created": False,
            },
            self._verify_backup_checkpoint(target, secrets, state),
            *self._verify_dr_services(target, secrets),
        ]

    def _verify_or_test(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        if target.e2e.mode == "disabled":
            return self.controller._verify(target, values, secrets)
        return self.controller._test(target, values, secrets)

    def _bootstrap(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        assert target.dr is not None
        self.current_stage = "lifecycle_preflight"
        checks = self.last_checks = self._engine_preflight(target, values, secrets)
        state_path = self._state_path(target)
        if state_path.exists():
            state = self._read_state(target)
            if state["status"] != "bootstrap_pending":
                raise DeploymentError(
                    "bootstrap refuses a target without a resumable bootstrap operation"
                )
            self._require_same_database_runtime(target, state["current"])
            candidate = self._release(target, values)
            self._require_same_database_runtime(target, candidate)
            checks.append(
                {
                    "name": "bootstrap_resume",
                    "status": "passed",
                    "phase": state["phase"],
                    "database_recreated": False,
                }
            )
            state = self._advance_bootstrap_state(
                target, state, state["phase"], candidate=candidate
            )
        else:
            self._require_empty_target(target)
            checks.append({"name": "empty_target", "status": "passed"})
            candidate = self._release(target, values)
            state = self._bootstrap_pending_state(target, candidate, "prepared")
            self._write_state(target, state)
            checks.append(
                {
                    "name": "bootstrap_checkpoint",
                    "status": "passed",
                    "phase": "prepared",
                    "path": str(state_path),
                }
            )

        secret_paths, environment_paths = self._prepare_dr_files(target, values)
        self._stage_remote(target, secret_paths, environment_paths, secrets)
        checks.append(
            {
                "name": "dr_secrets",
                "status": "passed",
                "created_or_reused": sorted(
                    path.name for path in secret_paths.values()
                ),
                "values_reported": False,
            }
        )
        checks.extend(self._pull_dr_images(target, secrets))
        checks.append(self._verify_candidate_schema(target, values, secrets))
        return self._continue_bootstrap(
            target,
            values,
            secrets,
            checks,
            state,
            candidate,
            secret_paths,
        )

    def _continue_bootstrap(
        self,
        target: Target,
        values: Mapping[str, str],
        secrets: Sequence[str],
        checks: list[dict[str, Any]],
        state: Mapping[str, Any],
        candidate: Mapping[str, Any],
        secret_paths: Mapping[str, Path],
    ) -> list[dict[str, Any]]:
        assert target.dr is not None
        starting_phase = str(state["phase"])

        if starting_phase in {"schema_verified", "runtime_started", "dr_verified"}:
            self.current_stage = "schema_resume_verification"
            schema_resume = self._verify_schema_checkpoint(
                target, values, secrets, state
            )
            checks.append(schema_resume)
            if schema_resume["checkpoint_refreshed"]:
                state = self._advance_bootstrap_state(
                    target,
                    state,
                    str(state["phase"]),
                    candidate=candidate,
                    extra={
                        "schema_checkpoint": self._schema_checkpoint(
                            target, schema_resume
                        )
                    },
                )
                checks.append(
                    {
                        "name": "schema_checkpoint_refresh",
                        "status": "passed",
                        "reason": "live catalog matches the updated canonical manifest",
                        "previous_catalog_sha256": schema_resume[
                            "previous_catalog_sha256"
                        ],
                        "catalog_sha256": schema_resume["catalog_sha256"],
                    }
                )

        if state["phase"] == "prepared":
            self.current_stage = "canonical_database_start"
            checks.append(self._create_repository(target, secrets))
            self.runner.run(
                self._dr_compose_command(
                    target,
                    "canonical",
                    "up",
                    "-d",
                    "--no-build",
                    "--pull",
                    "never",
                    "--wait",
                    "--wait-timeout",
                    "300",
                    "postgres-primary",
                ),
                timeout=600,
                secrets=secrets,
            )
            state = self._advance_bootstrap_state(
                target, state, "canonical_running", candidate=candidate
            )
            checks.append(
                {
                    "name": "bootstrap_checkpoint",
                    "status": "passed",
                    "phase": "canonical_running",
                }
            )

        if state["phase"] == "canonical_running":
            self.current_stage = "canonical_pgbackrest_stanza"
            checks.append(self._initialize_canonical_stanza(target, secrets))
            self.current_stage = "canonical_schema_bootstrap"
            artifact_value = state.get("schema_artifact_directory")
            if isinstance(artifact_value, str):
                output_directory = Path(artifact_value).resolve()
                try:
                    output_directory.relative_to(
                        self.controller.inventory.report_directory.resolve()
                    )
                except ValueError as exc:
                    raise DeploymentError(
                        "bootstrap schema artifact directory is outside report_directory"
                    ) from exc
            else:
                output_directory = (
                    self.controller.inventory.report_directory
                    / f"schema-{target.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:8]}"
                ).resolve()
                state = self._advance_bootstrap_state(
                    target,
                    state,
                    "canonical_running",
                    candidate=candidate,
                    extra={"schema_artifact_directory": str(output_directory)},
                )
            live_schema = self._probe_live_database(target, values, secrets)
            report_path = output_directory / "schema-bootstrap-last-run.json"
            schema_check = None
            if live_schema.get("database_state") == "canonical":
                if report_path.is_file():
                    try:
                        schema_check = self._read_schema_report(
                            target, values, output_directory
                        )
                    except DeploymentError:
                        pass
                if schema_check is None:
                    schema_check = {
                        **live_schema,
                        "name": "canonical_schema_recovered",
                        "table_count": self._load_manifest(target.dr)["table_count"],
                        "artifact": None,
                    }
            elif live_schema.get("database_state") != "empty":
                raise DeploymentError("canonical database state cannot be resumed")
            if schema_check is None:
                schema_check = self._schema_bootstrap(
                    target,
                    values,
                    secret_paths,
                    secrets,
                    output_directory=output_directory,
                )
            live_schema = self._probe_live_database(target, values, secrets)
            if live_schema.get("database_state") != "canonical":
                raise DeploymentError(
                    "canonical schema restore did not produce the approved catalog"
                )
            if schema_check.get("catalog_sha256") != live_schema.get("catalog_sha256"):
                raise DeploymentError("schema report and live canonical catalog differ")
            checks.append(schema_check)
            checks.append(live_schema)
            state = self._advance_bootstrap_state(
                target,
                state,
                "schema_verified",
                candidate=candidate,
                extra={
                    "schema_checkpoint": self._schema_checkpoint(target, live_schema)
                },
            )
            checks.append(
                {
                    "name": "bootstrap_checkpoint",
                    "status": "passed",
                    "phase": "schema_verified",
                }
            )

        if state["phase"] == "schema_verified":
            self.current_stage = "dr_runtime_start"
            self.runner.run(
                self._dr_compose_command(
                    target,
                    "runtime",
                    "--profile",
                    "backup",
                    "up",
                    "-d",
                    "--no-build",
                    "--pull",
                    "never",
                    "--wait",
                    "--wait-timeout",
                    "600",
                    "postgres-primary",
                    "postgres-standby",
                ),
                timeout=1200,
                secrets=secrets,
            )
            checks.append(
                {
                    "name": "dr_runtime_transition",
                    "status": "passed",
                    "from": target.dr.canonical_runtime_image,
                    "to": target.dr.final_runtime_image,
                }
            )
            state = self._advance_bootstrap_state(
                target, state, "runtime_started", candidate=candidate
            )
            checks.append(
                {
                    "name": "bootstrap_checkpoint",
                    "status": "passed",
                    "phase": "runtime_started",
                }
            )

        if state["phase"] == "runtime_started":
            self.current_stage = "e2e_admin_bootstrap"
            checks.append(self._provision_e2e_admin(target, values, secrets))
            self.current_stage = "first_full_backup"
            backup_checks, backup_checkpoint = self._backup_and_verify_dr(
                target, secrets
            )
            checks.extend(backup_checks)
            state = self._advance_bootstrap_state(
                target,
                state,
                "dr_verified",
                candidate=candidate,
                extra={"backup_checkpoint": backup_checkpoint},
            )
            checks.append(
                {
                    "name": "bootstrap_checkpoint",
                    "status": "passed",
                    "phase": "dr_verified",
                }
            )
        elif starting_phase == "dr_verified":
            self.current_stage = "dr_resume_verification"
            checks.extend(self._verify_resumable_dr(target, secrets, state))

        self.current_stage = "application_deploy"
        checks.extend(self.controller._deploy(target, values, secrets))
        self.current_stage = "application_verify"
        checks.extend(self._verify_or_test(target, values, secrets))
        self._write_state(
            target,
            self._verified_state(
                target,
                candidate,
                previous=None,
                action="bootstrap",
                schema_checkpoint=state["schema_checkpoint"],
                backup_checkpoint=state["backup_checkpoint"],
            ),
        )
        checks.append(
            {
                "name": "lifecycle_state",
                "status": "passed",
                "path": str(self._state_path(target)),
                "contains_secrets": False,
            }
        )
        return checks

    def _require_compatible(self, action: str) -> None:
        if not self.controller.schema_compatible:
            raise DeploymentError(
                f"{action} requires --schema-compatible; database migrations are not automated"
            )

    def _require_same_database_runtime(
        self, target: Target, release: Mapping[str, Any]
    ) -> None:
        assert target.dr is not None
        database = release.get("database")
        if (
            not isinstance(database, Mapping)
            or database.get("canonical_runtime_image")
            != target.dr.canonical_runtime_image
            or database.get("runtime_image") != target.dr.final_runtime_image
            or database.get("schema_application_image")
            != target.dr.schema_application_image
            or database.get("project_name") != target.dr.project_name
            or database.get("repository_volume") != target.dr.repository_volume
        ):
            raise DeploymentError(
                "database runtime changed; use the migration and restore-point workflow"
            )

    def _release_configuration(
        self, target: Target, release: Mapping[str, Any]
    ) -> dict[str, str]:
        try:
            payload = json.loads(
                self._read_release_artifact(
                    target,
                    release.get("application_configuration"),
                    "configuration",
                    "json",
                ).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeploymentError("rollback configuration snapshot is invalid") from exc
        if not isinstance(payload, Mapping) or any(
            key not in SNAPSHOT_CONFIGURATION_KEYS
            or not isinstance(key, str)
            or not isinstance(value, str)
            for key, value in payload.items()
        ):
            raise DeploymentError("rollback configuration snapshot is invalid")
        return {str(key): str(value) for key, value in payload.items()}

    @contextmanager
    def _release_compose_target(self, target: Target, release: Mapping[str, Any]):
        content = self._read_release_artifact(
            target, release.get("application_compose"), "compose", "yml"
        ).decode("utf-8")
        temporary = target.compose_file.parent / (
            f".dcim-story-39-7-rollback-{uuid.uuid4().hex}.yml"
        )
        try:
            _atomic_text(temporary, content)
            yield replace(target, compose_file=temporary)
        finally:
            temporary.unlink(missing_ok=True)

    def _upgrade(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._require_compatible("upgrade")
        state = self._read_state(target)
        if state["status"] != "verified" or state.get("pending") is not None:
            raise DeploymentError("upgrade refuses an unresolved lifecycle operation")
        current = state["current"]
        self._require_same_database_runtime(target, current)
        candidate = self._release(target, values)
        self._require_same_database_runtime(target, candidate)
        if candidate == current:
            raise DeploymentError(
                "upgrade candidate is identical to the verified release"
            )
        database_check = self._verify_schema_checkpoint(target, values, secrets, state)
        backup_check = self._verify_backup_checkpoint(target, secrets, state)
        schema_check = self._verify_candidate_schema(target, values, secrets)
        pending = dict(state)
        pending.update(
            {
                "status": "upgrade_pending",
                "pending": candidate,
                "pending_started_at_utc": _utc_text(),
            }
        )
        self._write_state(target, pending)
        checks = self.last_checks = [database_check, backup_check, schema_check]
        self.current_stage = "application_deploy"
        checks.extend(self.controller._deploy(target, values, secrets))
        self.current_stage = "application_verify"
        checks.extend(self._verify_or_test(target, values, secrets))
        self._write_state(
            target,
            self._verified_state(
                target,
                candidate,
                previous=current,
                action="upgrade",
                schema_checkpoint=state["schema_checkpoint"],
                backup_checkpoint=state["backup_checkpoint"],
            ),
        )
        checks.append(
            {
                "name": "upgrade_state",
                "status": "passed",
                "previous_git_sha": current["application_environment"][
                    "CANDIDATE_GIT_SHA"
                ],
                "current_git_sha": values["CANDIDATE_GIT_SHA"],
            }
        )
        return checks

    def _rollback(
        self, target: Target, values: Mapping[str, str], secrets: Sequence[str]
    ) -> list[dict[str, Any]]:
        self._require_compatible("rollback")
        state = self._read_state(target)
        current = state["current"]
        pending = state.get("pending")
        if state["status"] == "upgrade_pending" and isinstance(pending, Mapping):
            desired = current
        elif state["status"] == "rollback_pending" and isinstance(pending, Mapping):
            desired = pending
        else:
            desired = state.get("previous")
        if not isinstance(desired, Mapping):
            raise DeploymentError("rollback has no previous successful release")
        self._require_same_database_runtime(target, desired)
        database_check = self._verify_schema_checkpoint(target, values, secrets, state)
        backup_check = self._verify_backup_checkpoint(target, secrets, state)
        release_values = desired.get("application_environment")
        if not isinstance(release_values, Mapping):
            raise DeploymentError("rollback release references are invalid")
        sensitive_keys = desired.get("application_sensitive_keys")
        if not isinstance(sensitive_keys, list) or any(
            key not in SENSITIVE_ENV_KEYS or key not in values for key in sensitive_keys
        ):
            raise DeploymentError("rollback requires the verified release secret keys")
        restored_values = {key: str(values[key]) for key in sensitive_keys}
        restored_values.update(self._release_configuration(target, desired))
        restored_values.update({key: str(release_values[key]) for key in RELEASE_KEYS})
        validate_environment(restored_values)
        schema_check = self._verify_candidate_schema(
            target, restored_values, secrets, pull_images=False
        )
        rollback_pending = dict(state)
        rollback_pending.update(
            {
                "status": "rollback_pending",
                "pending": desired,
                "pending_started_at_utc": _utc_text(),
            }
        )
        self._write_state(target, rollback_pending)
        checks = self.last_checks = [database_check, backup_check, schema_check]
        with self._release_compose_target(target, desired) as rollback_target:
            self.current_stage = "application_deploy"
            checks.extend(
                self.controller._deploy(
                    rollback_target, restored_values, secrets, pull_images=False
                )
            )
            self.current_stage = "application_verify"
            checks.extend(
                self._verify_or_test(rollback_target, restored_values, secrets)
            )
        self._write_state(
            target,
            self._verified_state(
                target,
                desired,
                previous=current,
                action="rollback",
                schema_checkpoint=state["schema_checkpoint"],
                backup_checkpoint=state["backup_checkpoint"],
            ),
        )
        checks.append(
            {
                "name": "rollback_state",
                "status": "passed",
                "restored_git_sha": restored_values["CANDIDATE_GIT_SHA"],
                "volumes_deleted": False,
            }
        )
        return checks


__all__ = ["LifecycleManager", "prepare_secret_files"]
