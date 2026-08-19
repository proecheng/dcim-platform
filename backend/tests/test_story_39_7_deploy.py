import json
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.story_39_7_deploy import (
    CommandResult,
    DeploymentError,
    FleetController,
    Target,
    build_compose_command,
    build_docker_command,
    load_inventory,
    parse_environment,
    redact_text,
    validate_environment,
)


CANDIDATE_SHA = "ba1177448958c90e7ab979a3666f8719208c2f8f"
BACKEND_DIGEST = "2024d5d0e953153674a769307dbfccb840cbe47596e3277a8efbb09b17b626fc"
FRONTEND_DIGEST = "28f85db1baf1f039614c2e1ea4b4a4a1fc610bfda3c30ce239f7b018f6ee0032"


def _write_environment(path: Path, *, redis_image: str | None = None) -> dict[str, str]:
    values = {
        "CANDIDATE_GIT_SHA": CANDIDATE_SHA,
        "DCIM_BACKEND_IMAGE": f"ghcr.io/example/backend@sha256:{BACKEND_DIGEST}",
        "DCIM_BACKEND_EXPECTED_ID": f"sha256:{BACKEND_DIGEST}",
        "DCIM_FRONTEND_IMAGE": f"ghcr.io/example/frontend@sha256:{FRONTEND_DIGEST}",
        "DCIM_FRONTEND_EXPECTED_ID": f"sha256:{FRONTEND_DIGEST}",
        "DCIM_REDIS_IMAGE": redis_image or f"redis@sha256:{'1' * 64}",
        "DCIM_EMQX_IMAGE": f"emqx/emqx@sha256:{'2' * 64}",
        "DCIM_DR_STATUS_VOLUME": "dcim-story-39-3-dr_dr-status",
        "DCIM_DR_DATABASE_NETWORK": "dcim-story-39-3-dr_database-client",
        "DATABASE_URL": "postgresql+asyncpg://dcim:database-secret@postgres-writer:5432/dcim",
        "SECRET_KEY": "s" * 64,
        "CORS_ORIGINS": "https://preprod.example.invalid",
        "REDIS_PASSWORD": "redis-secret",
        "REDIS_URL": "redis://:redis-secret@redis:6379/0",
        "MQTT_USERNAME": "e2e-mqtt",
        "MQTT_PASSWORD": "mqtt-secret",
        "GATEWAY_SECRET_KEY": "g" * 32,
        "VPP_API_KEY": "v" * 32,
        "LICENSE_KEY": "test-license-secret",
        "FAULT_TREE_HMAC_KEY": "f" * 32,
        "NGINX_PORT": "3000",
        "E2E_ADMIN_USER": "fleet-admin",
        "E2E_ADMIN_PASSWORD": "browser-secret",
    }
    path.write_text("\n".join(f'{key}="{value}"' for key, value in values.items()), encoding="utf-8")
    return values


def _write_inventory(tmp_path: Path, targets: list[dict]) -> Path:
    compose = tmp_path / "compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    inventory = {
        "version": 1,
        "concurrency": 3,
        "report_directory": "reports",
        "defaults": {
            "compose_file": "compose.yml",
            "platform": "linux/amd64",
            "e2e": {"mode": "disabled"},
        },
        "targets": targets,
    }
    path = tmp_path / "targets.yaml"
    path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
    return path


def test_inventory_resolves_paths_and_merges_nested_e2e_defaults(tmp_path):
    env_path = tmp_path / "node.env"
    _write_environment(env_path)
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "name": "linux-a",
                "docker_context": "ssh-linux-a",
                "env_file": "node.env",
                "project_name": "dcim-linux-a",
                "e2e": {
                    "mode": "ssh-tunnel",
                    "ssh_target": "deploy@linux-a",
                    "local_port": 13001,
                    "remote_port": 3000,
                    "headed": True,
                },
            }
        ],
    )

    inventory = load_inventory(inventory_path)

    target = inventory.targets[0]
    assert inventory.concurrency == 3
    assert target.compose_file == (tmp_path / "compose.yml").resolve()
    assert target.env_file == env_path.resolve()
    assert target.e2e.mode == "ssh-tunnel"
    assert target.e2e.headed is True


def test_repository_example_inventory_contains_ten_unique_targets():
    repository = Path(__file__).resolve().parents[2]
    inventory = load_inventory(repository / "deploy/observability/story-39-7-targets.example.yaml")

    assert len(inventory.targets) == 10
    assert len({target.e2e.local_port for target in inventory.targets}) == 10
    assert inventory.concurrency == 3


def test_critical_auth_spec_uses_configured_e2e_username():
    repository = Path(__file__).resolve().parents[2]
    auth_spec = (repository / "e2e/auth.spec.ts").read_text(encoding="utf-8")

    assert "process.env.E2E_ADMIN_USER || 'admin'" in auth_spec


def test_playwright_artifacts_can_be_isolated_per_fleet_target():
    repository = Path(__file__).resolve().parents[2]
    auth_setup = (repository / "e2e/auth.setup.ts").read_text(encoding="utf-8")
    playwright_config = (repository / "playwright.config.ts").read_text(encoding="utf-8")

    assert "process.env.E2E_AUTH_FILE" in auth_setup
    assert "process.env.E2E_AUTH_FILE" in playwright_config
    assert "process.env.E2E_OUTPUT_DIR" in playwright_config


@pytest.mark.parametrize(
    ("targets", "message"),
    [
        (
            [
                {"name": "same", "docker_context": "a", "env_file": "a.env", "project_name": "one"},
                {"name": "same", "docker_context": "b", "env_file": "b.env", "project_name": "two"},
            ],
            "target names",
        ),
        (
            [
                {
                    "name": "one",
                    "docker_context": "a",
                    "env_file": "a.env",
                    "project_name": "one",
                    "e2e": {
                        "mode": "ssh-tunnel",
                        "ssh_target": "a",
                        "local_port": 13001,
                        "remote_port": 3000,
                    },
                },
                {
                    "name": "two",
                    "docker_context": "b",
                    "env_file": "b.env",
                    "project_name": "two",
                    "e2e": {
                        "mode": "ssh-tunnel",
                        "ssh_target": "b",
                        "local_port": 13001,
                        "remote_port": 3000,
                    },
                },
            ],
            "local tunnel ports",
        ),
    ],
)
def test_inventory_rejects_ambiguous_fleet_targets(tmp_path, targets, message):
    inventory_path = _write_inventory(tmp_path, targets)

    with pytest.raises(DeploymentError, match=message):
        load_inventory(inventory_path)


def test_environment_requires_immutable_images_and_matching_candidate_ids(tmp_path):
    env_path = tmp_path / "node.env"
    _write_environment(env_path, redis_image="redis:7-alpine")

    values = parse_environment(env_path)

    with pytest.raises(DeploymentError, match="immutable digest"):
        validate_environment(values)


def test_environment_rejects_placeholders_without_echoing_secret(tmp_path):
    env_path = tmp_path / "node.env"
    values = _write_environment(env_path)
    values["SECRET_KEY"] = "<replace-with-secret>"
    env_path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")

    with pytest.raises(DeploymentError, match="SECRET_KEY") as error:
        validate_environment(parse_environment(env_path))

    assert "replace-with-secret" not in str(error.value)


def test_context_commands_are_shell_free_and_keep_secrets_out_of_arguments(tmp_path):
    target = Target(
        name="remote-a",
        docker_context="ssh-remote-a",
        compose_file=tmp_path / "compose.yml",
        env_file=tmp_path / "remote.env",
        project_name="dcim-remote-a",
    )

    assert build_docker_command(target, "info") == ["docker", "--context", "ssh-remote-a", "info"]
    command = build_compose_command(target, "up", "-d", "--no-build", "--pull", "never")
    assert command[:4] == ["docker", "--context", "ssh-remote-a", "compose"]
    assert command[-5:] == ["up", "-d", "--no-build", "--pull", "never"]
    assert "database-secret" not in " ".join(command)


def test_redaction_removes_secret_values_and_url_credentials():
    message = "login browser-secret failed for postgresql+asyncpg://dcim:database-secret@postgres-writer:5432/dcim"

    redacted = redact_text(message, ["browser-secret", "database-secret"])

    assert "browser-secret" not in redacted
    assert "database-secret" not in redacted
    assert "***" in redacted


class _FakeRunner:
    def __init__(self, failing_context: str | None = None):
        self.failing_context = failing_context
        self.commands: list[list[str]] = []

    def run(self, command, **_kwargs):
        command = list(command)
        self.commands.append(command)
        context = command[command.index("--context") + 1]
        if context == self.failing_context:
            raise DeploymentError("command failed with browser-secret")
        if "info" in command:
            return CommandResult(
                stdout=json.dumps({"OSType": "linux", "Architecture": "x86_64", "ServerVersion": "29.4.0"}),
                stderr="",
                returncode=0,
            )
        if command[-2:] == ["compose", "version"]:
            return CommandResult(stdout="Docker Compose version v5.1.1", stderr="", returncode=0)
        return CommandResult(stdout="{}", stderr="", returncode=0)


class _DeployRunner:
    def __init__(self, *, revision: str = CANDIDATE_SHA):
        self.revision = revision
        self.commands: list[list[str]] = []

    def run(self, command, **_kwargs):
        command = list(command)
        self.commands.append(command)
        if "info" in command:
            return CommandResult(
                stdout=json.dumps({"OSType": "linux", "Architecture": "amd64", "ServerVersion": "29.4.0"}),
                stderr="",
                returncode=0,
            )
        if command[-2:] == ["compose", "version"]:
            return CommandResult(stdout="Docker Compose version v5.1.1", stderr="", returncode=0)
        if "image" in command and "inspect" in command:
            reference = command[command.index("inspect") + 1]
            digest = reference.rsplit("@sha256:", 1)[1]
            return CommandResult(
                stdout=json.dumps(
                    {
                        "Id": f"sha256:{digest}",
                        "Config": {"Labels": {"org.opencontainers.image.revision": self.revision}},
                    }
                ),
                stderr="",
                returncode=0,
            )
        if command[-2:] == ["config", "--images"]:
            env_values = parse_environment(Path(command[command.index("--env-file") + 1]))
            output = "\n".join(
                env_values[key]
                for key in (
                    "DCIM_BACKEND_IMAGE",
                    "DCIM_FRONTEND_IMAGE",
                    "DCIM_REDIS_IMAGE",
                    "DCIM_EMQX_IMAGE",
                )
            )
            return CommandResult(stdout=output, stderr="", returncode=0)
        if "--hash" in command:
            return CommandResult(stdout="backend sha256:abc\nnginx sha256:def\n", stderr="", returncode=0)
        if "ps" in command and "--format" in command:
            services = [
                {"Service": name, "State": "running", "Health": "healthy"}
                for name in ("redis", "emqx", "backend", "nginx")
            ]
            return CommandResult(stdout=json.dumps(services), stderr="", returncode=0)
        if "exec" in command:
            return CommandResult(stdout=json.dumps({"status": "healthy"}), stderr="", returncode=0)
        return CommandResult(stdout="", stderr="", returncode=0)


def test_fleet_preflight_isolates_failures_and_writes_sanitized_report(tmp_path):
    targets = []
    for name in ("good", "bad"):
        target_dir = tmp_path / name
        target_dir.mkdir()
        env_path = target_dir / "node.env"
        _write_environment(env_path)
        compose_path = target_dir / "compose.yml"
        compose_path.write_text("services: {}\n", encoding="utf-8")
        targets.append(
            {
                "name": name,
                "docker_context": name,
                "env_file": str(env_path),
                "compose_file": str(compose_path),
                "project_name": f"dcim-{name}",
            }
        )
    inventory = load_inventory(_write_inventory(tmp_path, targets))
    runner = _FakeRunner(failing_context="bad")
    controller = FleetController(inventory, runner=runner)

    report = controller.execute("preflight")
    second_report = controller.execute("preflight")

    assert report["summary"] == {"total": 2, "passed": 1, "failed": 1}
    by_name = {result["target"]: result for result in report["results"]}
    assert by_name["good"]["status"] == "passed"
    assert by_name["bad"]["status"] == "failed"
    report_text = Path(report["report_path"]).read_text(encoding="utf-8")
    assert "browser-secret" not in report_text
    assert "database-secret" not in report_text
    assert second_report["report_path"] != report["report_path"]


def test_command_runner_contract_uses_utf8_without_a_shell(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("scripts.story_39_7_deploy.subprocess.run", fake_run)
    from scripts.story_39_7_deploy import CommandRunner

    result = CommandRunner().run(["docker", "version"])

    assert result.stdout == "ok"
    assert captured["shell"] is False
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_deploy_pulls_fixed_images_starts_without_build_and_verifies_runtime(tmp_path):
    env_path = tmp_path / "node.env"
    values = _write_environment(env_path)
    inventory = load_inventory(
        _write_inventory(
            tmp_path,
            [
                {
                    "name": "candidate",
                    "docker_context": "candidate",
                    "env_file": str(env_path),
                    "project_name": "dcim-candidate",
                }
            ],
        )
    )
    runner = _DeployRunner()

    report = FleetController(inventory, runner=runner).execute("deploy")

    assert report["summary"] == {"total": 1, "passed": 1, "failed": 0}
    pull_commands = [command for command in runner.commands if "pull" in command and "compose" not in command]
    assert {command[-1] for command in pull_commands} == {
        values["DCIM_BACKEND_IMAGE"],
        values["DCIM_FRONTEND_IMAGE"],
        values["DCIM_REDIS_IMAGE"],
        values["DCIM_EMQX_IMAGE"],
    }
    assert any(command[-5:] == ["up", "-d", "--no-build", "--pull", "never"] for command in runner.commands)
    assert report["annual_slo_proven"] is False
    assert report["release_gate"] == "BLOCKED"


def test_deploy_stops_before_start_when_oci_revision_drifts(tmp_path):
    env_path = tmp_path / "node.env"
    _write_environment(env_path)
    inventory = load_inventory(
        _write_inventory(
            tmp_path,
            [
                {
                    "name": "drifted",
                    "docker_context": "drifted",
                    "env_file": str(env_path),
                    "project_name": "dcim-drifted",
                }
            ],
        )
    )
    runner = _DeployRunner(revision="0" * 40)

    report = FleetController(inventory, runner=runner).execute("deploy")

    assert report["summary"]["failed"] == 1
    assert "OCI revision" in report["results"][0]["error"]
    assert not any("up" in command for command in runner.commands)


def test_e2e_uses_target_specific_temporary_auth_and_output_paths(tmp_path, monkeypatch):
    env_path = tmp_path / "node.env"
    values = _write_environment(env_path)
    inventory = load_inventory(
        _write_inventory(
            tmp_path,
            [
                {
                    "name": "browser-a",
                    "docker_context": "browser-a",
                    "env_file": str(env_path),
                    "project_name": "dcim-browser-a",
                    "e2e": {"mode": "local", "local_port": 13001, "headed": True},
                }
            ],
        )
    )

    class E2ERunner:
        environment = None

        def run(self, _command, **kwargs):
            self.environment = kwargs["env"]
            Path(self.environment["PLAYWRIGHT_JSON_OUTPUT_FILE"]).write_text("{}", encoding="utf-8")
            return CommandResult(stdout="", stderr="", returncode=0)

    runner = E2ERunner()
    controller = FleetController(inventory, runner=runner)
    monkeypatch.setattr(controller, "_verify", lambda *_args: [])

    checks = controller._test(inventory.targets[0], values, ["browser-secret"])

    assert checks[0]["name"] == "critical_e2e"
    assert runner.environment["E2E_AUTH_FILE"] != str(Path("e2e/.auth/admin.json"))
    assert "dcim-e2e-browser-a-" in runner.environment["E2E_AUTH_FILE"]
    assert not Path(runner.environment["E2E_AUTH_FILE"]).parent.exists()
