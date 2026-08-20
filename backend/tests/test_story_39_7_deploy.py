import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import scripts.story_39_7_lifecycle as lifecycle_module
import scripts.story_39_7_deploy as deploy_module
from scripts.story_39_7_deploy import (
    CommandResult,
    DRConfig,
    DeploymentError,
    FleetController,
    Target,
    build_compose_command,
    build_docker_command,
    is_local_image_reference,
    load_inventory,
    parse_environment,
    redact_text,
    validate_environment,
)
from scripts.story_39_7_lifecycle import LifecycleManager, prepare_secret_files


CANDIDATE_SHA = "ba1177448958c90e7ab979a3666f8719208c2f8f"
BACKEND_DIGEST = "2024d5d0e953153674a769307dbfccb840cbe47596e3277a8efbb09b17b626fc"
FRONTEND_DIGEST = "28f85db1baf1f039614c2e1ea4b4a4a1fc610bfda3c30ce239f7b018f6ee0032"
APPROVED_FINAL_RUNTIME_IMAGE = (
    "ghcr.io/proecheng/dcim-platform/postgres:16.15-ts2.29.1-pgb2.59.0-schema-gate-v1"
    "@sha256:ad57905638f480f574c1955bf433e5414ddf8158a4a5f76ad2ee7d5e683e0f76"
)


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
    assert {target.e2e.browser_channel for target in inventory.targets} == {"msedge"}
    assert all(target.dr is not None for target in inventory.targets)
    assert {target.dr.mode for target in inventory.targets if target.dr} == {"local", "ssh"}
    assert all(
        target.dr and target.dr.canonical_runtime_image.startswith("ghcr.io/proecheng/") for target in inventory.targets
    )


def test_local_immutable_image_references_are_not_pulled_from_registry():
    assert is_local_image_reference("localhost/dcim/backend@sha256:" + "a" * 64)
    assert is_local_image_reference("localhost:5000/dcim/backend@sha256:" + "b" * 64)
    assert not is_local_image_reference("ghcr.io/proecheng/dcim-platform/backend@sha256:" + "c" * 64)


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
    assert "process.env.E2E_BROWSER_CHANNEL" in playwright_config


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


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("project_name", "dr.project_name"),
        ("repository_volume", "dr.repository_volume"),
    ],
)
def test_inventory_rejects_shared_dr_resources_on_one_docker_engine(tmp_path, field, message):
    dr = _lifecycle_dr_config(tmp_path)
    targets = []
    for index in (1, 2):
        env_path = tmp_path / f"node-{index}.env"
        _write_environment(env_path)
        dr_values = {
            "mode": "local",
            "compose_file": str(dr.compose_file),
            "project_name": f"dr-{index}",
            "secret_directory": str(tmp_path / f"secrets-{index}"),
            "canonical_runtime_image": dr.canonical_runtime_image,
            "final_runtime_image": dr.final_runtime_image,
            "schema_application_image": dr.schema_application_image,
            "repository_volume": f"repository-{index}",
        }
        dr_values[field] = "shared"
        targets.append(
            {
                "name": f"node-{index}",
                "docker_context": "shared-engine",
                "env_file": str(env_path),
                "project_name": f"application-{index}",
                "dr": dr_values,
            }
        )

    with pytest.raises(DeploymentError, match=message):
        load_inventory(_write_inventory(tmp_path, targets))


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
    assert any(
        command[-8:]
        == [
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "600",
        ]
        for command in runner.commands
    )
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
                    "e2e": {
                        "mode": "local",
                        "local_port": 13001,
                        "headed": True,
                        "browser_channel": "msedge",
                    },
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
    assert runner.environment["E2E_BROWSER_CHANNEL"] == "msedge"
    assert not Path(runner.environment["E2E_AUTH_FILE"]).parent.exists()


def test_e2e_specs_use_the_controller_auth_file():
    for path in (
        deploy_module.ROOT / "e2e/authorization-matrix.spec.ts",
        deploy_module.ROOT / "e2e/site-isolation-websocket-authorization.spec.ts",
    ):
        source = path.read_text(encoding="utf-8")
        assert "process.env.E2E_AUTH_FILE" in source


def _lifecycle_dr_config(tmp_path: Path) -> DRConfig:
    repository = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (repository / "deploy/postgres-backup/canonical-schema-manifest.json").read_text(encoding="utf-8")
    )
    return DRConfig(
        mode="local",
        compose_file=repository / "deploy/dr/docker-compose.dr.yml",
        project_name="dcim-story-39-3-dr",
        secret_directory=tmp_path / "secrets",
        canonical_runtime_image=manifest["runtime_image"],
        final_runtime_image=APPROVED_FINAL_RUNTIME_IMAGE,
        schema_application_image=manifest["application_image"],
        repository_volume="dcim-story-39-3-dr-pgbackrest",
    )


def test_dr_inventory_resolves_lifecycle_configuration(tmp_path):
    env_path = tmp_path / "node.env"
    _write_environment(env_path)
    dr = _lifecycle_dr_config(tmp_path)
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "name": "lifecycle",
                "docker_context": "lifecycle",
                "env_file": str(env_path),
                "project_name": "dcim-lifecycle",
                "dr": {
                    "mode": "local",
                    "compose_file": str(dr.compose_file),
                    "project_name": dr.project_name,
                    "secret_directory": str(dr.secret_directory),
                    "canonical_runtime_image": dr.canonical_runtime_image,
                    "final_runtime_image": dr.final_runtime_image,
                    "schema_application_image": dr.schema_application_image,
                    "repository_volume": dr.repository_volume,
                },
            }
        ],
    )

    inventory = load_inventory(inventory_path)

    assert inventory.state_directory == (tmp_path / "reports/state").resolve()
    assert inventory.targets[0].dr == dr


def test_prepare_dr_secrets_never_overwrites_existing_files(tmp_path):
    dr = _lifecycle_dr_config(tmp_path)
    database_url = "postgresql+asyncpg://dcim:database-secret@postgres-writer:5432/dcim"

    paths = prepare_secret_files(dr, database_url)
    first_values = {key: path.read_text(encoding="utf-8") for key, path in paths.items()}
    second_paths = prepare_secret_files(dr, database_url)

    assert second_paths == paths
    assert {key: path.read_text(encoding="utf-8") for key, path in paths.items()} == first_values
    assert paths["POSTGRES_PASSWORD_FILE"].read_text(encoding="utf-8").strip() == "database-secret"

    paths["POSTGRES_PASSWORD_FILE"].write_text("different-secret\n", encoding="utf-8")
    with pytest.raises(DeploymentError, match="does not match DATABASE_URL"):
        prepare_secret_files(dr, database_url)
    assert paths["POSTGRES_PASSWORD_FILE"].read_text(encoding="utf-8") == "different-secret\n"


def test_remote_secret_staging_uses_compare_and_no_clobber_install(tmp_path):
    dr = replace(
        _lifecycle_dr_config(tmp_path),
        mode="ssh",
        ssh_target="deploy@example.invalid",
        remote_directory="/opt/dcim/story-39-3",
    )
    target = Target(
        name="remote",
        docker_context="remote",
        compose_file=tmp_path / "app-compose.yml",
        env_file=tmp_path / "app.env",
        project_name="dcim-remote",
        dr=dr,
    )
    runner = _LifecycleRunner()
    controller = SimpleNamespace(
        runner=runner,
        inventory=SimpleNamespace(report_directory=tmp_path, state_directory=tmp_path),
    )
    manager = LifecycleManager(controller)
    values = _write_environment(target.env_file)
    target.compose_file.write_text("services: {}\n", encoding="utf-8")
    secret_paths, environment_paths = manager._prepare_dr_files(target, values)

    manager._stage_remote(target, secret_paths, environment_paths, ["database-secret"])

    secret_uploads = [command for command in runner.commands if command[0] == "scp" and "/secrets/" in command[-1]]
    assert len(secret_uploads) == 4
    assert all(".incoming-" in command[-1] for command in secret_uploads)
    all_uploads = [command for command in runner.commands if command[0] == "scp"]
    assert len(all_uploads) == 7
    assert all(".incoming-" in command[-1] for command in all_uploads)
    install_commands = [" ".join(command) for command in runner.commands if command[:1] == ["ssh"]]
    assert sum("cmp -s" in command and "exit 73" in command for command in install_commands) == 4
    assert sum("trap" in command and ".incoming-" in command for command in install_commands) == 7
    assert sum("find" in command and ".incoming-*" in command for command in install_commands) == 7
    assert sum("sha256sum" in command and "mv -f" in command for command in install_commands) == 3
    secret_installs = [command for command in runner.commands if command[:1] == ["ssh"] and "cmp -s" in command[-1]]
    assert all(command[-2] == "-c" and command[-1].startswith("'") for command in secret_installs)
    assert manager._engine_preflight(target, values, ["database-secret"])[0]["status"] == "passed"

    mismatched_target = replace(target, dr=replace(dr, ssh_target="deploy@different.example.invalid"))
    with pytest.raises(DeploymentError, match="must match"):
        manager._engine_preflight(mismatched_target, values, ["database-secret"])


def test_remote_secret_upload_failure_removes_exact_incoming_file(tmp_path):
    dr = replace(
        _lifecycle_dr_config(tmp_path),
        mode="ssh",
        ssh_target="deploy@example.invalid",
        remote_directory="/opt/dcim/story-39-3",
    )
    target = Target(
        name="remote",
        docker_context="remote",
        compose_file=tmp_path / "app-compose.yml",
        env_file=tmp_path / "app.env",
        project_name="dcim-remote",
        dr=dr,
    )

    class InterruptedScpRunner(_LifecycleRunner):
        failed_destination = ""

        def run(self, command, **kwargs):
            command_list = list(command)
            if command_list[0] == "scp" and "/secrets/" in command_list[-1] and not self.failed_destination:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                self.failed_destination = command_list[-1].split(":", 1)[1]
                raise KeyboardInterrupt("interrupted scp")
            return super().run(command_list, **kwargs)

    runner = InterruptedScpRunner()
    manager = LifecycleManager(
        SimpleNamespace(
            runner=runner,
            inventory=SimpleNamespace(report_directory=tmp_path, state_directory=tmp_path),
        )
    )
    values = _write_environment(target.env_file)
    target.compose_file.write_text("services: {}\n", encoding="utf-8")
    secret_paths, environment_paths = manager._prepare_dr_files(target, values)

    with pytest.raises(KeyboardInterrupt, match="interrupted scp"):
        manager._stage_remote(target, secret_paths, environment_paths, [])

    cleanup_commands = [
        command
        for command in runner.commands
        if command[:1] == ["ssh"]
        and "rm -f --" in command[-1]
        and runner.failed_destination in command[-1]
        and "trap" not in command[-1]
    ]
    assert len(cleanup_commands) == 1
    assert runner.failed_destination in cleanup_commands[0][-1]


@pytest.mark.skipif(lifecycle_module.os.name != "nt", reason="Windows ACL only")
def test_windows_acl_uses_current_sid_replaces_dacl_and_fails_closed(tmp_path, monkeypatch):
    calls = []

    def success(command, **kwargs):
        calls.append((list(command), kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(lifecycle_module.subprocess, "run", success)
    lifecycle_module._harden_windows_path(tmp_path, directory=True)

    command, options = calls[0]
    script = command[-1]
    assert command[0] == "powershell.exe"
    assert "WindowsIdentity]::GetCurrent" in script
    assert "SetAccessRuleProtection($true, $false)" in script
    assert "$rules.Count -ne 1" in script
    assert options["env"]["DCIM_ACL_PATH"] == str(tmp_path)

    monkeypatch.setattr(
        lifecycle_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, "", "restricted DACL verification failed"),
    )
    with pytest.raises(DeploymentError, match="cannot restrict Windows ACL"):
        lifecycle_module._harden_windows_path(tmp_path, directory=True)


class _LifecycleRunner:
    def __init__(self):
        self.commands: list[list[str]] = []
        self.call_options: list[dict] = []
        self.lock_labels: dict[str, str] = {}
        self.daemon_id = "test-daemon-id"
        self.database_empty = True
        self.primary_volume_created_at = "2026-08-19T00:00:00Z"
        self.repository_volume_created_at = "2026-08-19T00:00:01Z"
        self.full_backup_label = "20260819-000002F"
        self.backup_status = "success"
        self.backup_step = "complete"
        self.backup_exit_code = 0
        self.repository_status_code = 0

    def run(self, command, **kwargs):
        command = list(command)
        self.commands.append(command)
        self.call_options.append(kwargs)
        joined = " ".join(command)
        if "com.dcim.role=e2e-admin-bootstrap" in command:
            return CommandResult(
                stdout=json.dumps({"created": True, "role": "admin", "active": True}),
                stderr="",
                returncode=0,
            )
        if " container run " in f" {joined} " and "com.dcim.lifecycle.lock=true" in command:
            self.lock_labels = {
                value.split("=", 1)[0]: value.split("=", 1)[1]
                for index, value in enumerate(command)
                if index > 0 and command[index - 1] == "--label" and "=" in value
            }
            return CommandResult(stdout=f"sha256:{'9' * 64}\n", stderr="", returncode=0)
        if command[-3:] == ["info", "--format", "{{json .}}"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "ID": self.daemon_id,
                        "OSType": "linux",
                        "Architecture": "x86_64",
                        "ServerVersion": "28.0",
                    }
                ),
                stderr="",
                returncode=0,
            )
        if command[-3:] == ["info", "--format", "{{json .ID}}"]:
            return CommandResult(stdout=json.dumps(self.daemon_id), stderr="", returncode=0)
        if command[-2:] == ["compose", "version"]:
            return CommandResult(stdout="Docker Compose version v5.1.1", stderr="", returncode=0)
        if command[:3] == ["docker", "context", "inspect"]:
            return CommandResult(
                stdout=json.dumps("ssh://deploy@example.invalid"),
                stderr="",
                returncode=0,
            )
        if " image inspect " in f" {joined} " and command[-1] == "{{json .Id}}":
            return CommandResult(stdout=json.dumps(f"sha256:{'a' * 64}"), stderr="", returncode=0)
        if " image inspect " in f" {joined} ":
            return CommandResult(stdout=json.dumps({"Id": f"sha256:{'a' * 64}"}), stderr="", returncode=0)
        if " container inspect " in f" {joined} ":
            if "dcim-lifecycle-lock-" in joined and command[-1] == "{{json .}}":
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "Config": {"Labels": self.lock_labels},
                            "State": {"Running": True},
                        }
                    ),
                    stderr="",
                    returncode=0,
                )
            return CommandResult(
                stdout=json.dumps(APPROVED_FINAL_RUNTIME_IMAGE),
                stderr="",
                returncode=0,
            )
        if " volume inspect " in f" {joined} ":
            volume_name = command[command.index("inspect") + 1]
            if volume_name.endswith("_postgres-primary-data"):
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "Name": volume_name,
                            "CreatedAt": self.primary_volume_created_at,
                            "Labels": {
                                "com.dcim.story": "39.3",
                                "com.dcim.dr.role": "primary-data",
                                "com.docker.compose.project": "dcim-story-39-3-dr",
                            },
                        }
                    ),
                    stderr="",
                    returncode=0,
                )
            return CommandResult(
                stdout=json.dumps(
                    {
                        "Name": volume_name,
                        "CreatedAt": self.repository_volume_created_at,
                        "Labels": {
                            "com.dcim.story": "39.3",
                            "com.dcim.dr.role": "pgbackrest-repository",
                            "com.dcim.lifecycle.target": "lifecycle",
                        },
                    }
                ),
                stderr="",
                returncode=0,
            )
        if "story_39_3_schema_bootstrap.py" in joined:
            self.database_empty = False
            output_dir = Path(command[command.index("--output-dir") + 1])
            output_dir.mkdir(parents=True)
            manifest = json.loads(lifecycle_module.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
            (output_dir / "schema-bootstrap-last-run.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "pass",
                        "project": "dcim-story-39-3-dr",
                        "postgres_container": "postgres-primary-container",
                        "network": "dcim-story-39-3-dr_database-client",
                        "database": "dcim",
                        "database_user": "dcim",
                        "application_image": manifest["application_image"],
                        "runtime_image": manifest["runtime_image"],
                        "canonical_artifact_sha256": manifest["artifact_sha256"],
                        "catalog_sha256": manifest["catalog_sha256"],
                        "table_names_sha256": manifest["table_names_sha256"],
                        "table_count": manifest["table_count"],
                        "alembic_head": manifest["alembic_head"],
                    }
                ),
                encoding="utf-8",
            )
            return CommandResult(stdout="", stderr="", returncode=0)
        if "com.dcim.role=schema-catalog" in command:
            if self.database_empty:
                return CommandResult(
                    stdout=json.dumps({"database_state": "empty"}),
                    stderr="",
                    returncode=0,
                )
            manifest = json.loads(lifecycle_module.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
            return CommandResult(
                stdout=json.dumps(
                    {
                        "database_state": "occupied",
                        "catalog_sha256": manifest["catalog_sha256"],
                        "alembic_head": manifest["alembic_head"],
                    }
                ),
                stderr="",
                returncode=0,
            )
        if "start" in command and "--attach" in command:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "table_count": 189,
                        "table_names_sha256": "0df268cf4fa358af46f127c716d5d6f40ccbe3c4d7017a8f5f68e33bc7dc6e25",
                        "schema_contract_sha256": "a" * 64,
                        "migration_sha256": "b" * 64,
                        "alembic_heads": ["20260707_0100"],
                    }
                ),
                stderr="",
                returncode=0,
            )
        if len(command) >= 3 and command[-3:-1] == ["ps", "-q"]:
            return CommandResult(stdout=f"{command[-1]}-container\n", stderr="", returncode=0)
        if command[-2:] == ["cat", "/var/lib/dcim-dr-status/last-run.json"]:
            return CommandResult(
                stdout=json.dumps(
                    {
                        "run_id": "20260819T000003000000000-1",
                        "operation": "status",
                        "status": self.backup_status,
                        "step": self.backup_step,
                        "exit_code": self.backup_exit_code,
                        "failure_code": "",
                    }
                ),
                stderr="",
                returncode=0,
            )
        if command[-2:] == ["cat", "/var/lib/dcim-dr-status/pgbackrest-info.json"]:
            return CommandResult(
                stdout=json.dumps(
                    [
                        {
                            "name": "dcim",
                            "status": {
                                "code": self.repository_status_code,
                                "message": "ok",
                            },
                            "backup": [
                                {
                                    "label": self.full_backup_label,
                                    "type": "full",
                                    "error": False,
                                }
                            ],
                        }
                    ]
                ),
                stderr="",
                returncode=0,
            )
        if command[-3:] == ["ps", "--format", "json"]:
            services = [
                {"Service": name, "State": "running", "Health": "healthy"}
                for name in ("postgres-primary", "postgres-standby", "backup-scheduler")
            ]
            return CommandResult(stdout=json.dumps(services), stderr="", returncode=0)
        return CommandResult(stdout="", stderr="", returncode=0)


def _lifecycle_inventory(tmp_path: Path):
    env_path = tmp_path / "node.env"
    values = _write_environment(env_path)
    dr = _lifecycle_dr_config(tmp_path)
    inventory_path = _write_inventory(
        tmp_path,
        [
            {
                "name": "lifecycle",
                "docker_context": "lifecycle",
                "env_file": str(env_path),
                "project_name": "dcim-lifecycle",
                "dr": {
                    "mode": "local",
                    "compose_file": str(dr.compose_file),
                    "project_name": dr.project_name,
                    "secret_directory": str(dr.secret_directory),
                    "canonical_runtime_image": dr.canonical_runtime_image,
                    "final_runtime_image": dr.final_runtime_image,
                    "schema_application_image": dr.schema_application_image,
                    "repository_volume": dr.repository_volume,
                },
            }
        ],
    )
    return load_inventory(inventory_path), values, env_path


def test_bootstrap_runs_two_stage_database_backup_and_writes_sanitized_state(tmp_path, monkeypatch):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    runner = _LifecycleRunner()
    controller = FleetController(inventory, runner=runner)
    monkeypatch.setattr(controller, "_deploy", lambda *_args: [{"name": "application_deploy"}])
    monkeypatch.setattr(controller, "_verify", lambda *_args: [{"name": "application_verify"}])

    report = controller.execute("bootstrap")

    assert report["summary"] == {"total": 1, "passed": 1, "failed": 0}
    commands = [" ".join(command) for command in runner.commands]
    canonical_up = next(
        index for index, command in enumerate(commands) if "canonical.env" in command and " up " in command
    )
    schema = next(index for index, command in enumerate(commands) if "story_39_3_schema_bootstrap.py" in command)
    runtime_up = next(index for index, command in enumerate(commands) if "runtime.env" in command and " up " in command)
    assert "backup-scheduler" not in runner.commands[runtime_up]
    admin_bootstrap = next(
        index for index, command in enumerate(runner.commands) if "com.dcim.role=e2e-admin-bootstrap" in command
    )
    first_backup = next(
        index
        for index, command in enumerate(runner.commands)
        if "/usr/local/bin/backup-job.sh" in command and command[-1] == "full"
    )
    assert canonical_up < schema < runtime_up < admin_bootstrap < first_backup
    schema_command = runner.commands[schema]
    assert schema_command[schema_command.index("--database") + 1] == "dcim"
    assert schema_command[schema_command.index("--database-user") + 1] == "dcim"
    backup_operations = [command[-1] for command in runner.commands if "/usr/local/bin/backup-job.sh" in command]
    assert backup_operations == [
        "stanza",
        "stanza",
        "full",
        "check",
        "verify",
        "status",
    ]
    runtime_backup_commands = [
        command
        for command in runner.commands
        if "/usr/local/bin/backup-job.sh" in command and any("runtime.env" in argument for argument in command)
    ]
    assert all("run" in command and "--rm" in command for command in runtime_backup_commands)
    scheduler_up = next(
        index
        for index, command in enumerate(runner.commands)
        if "backup-scheduler" in command and "up" in command and any("runtime.env" in argument for argument in command)
    )
    assert first_backup < scheduler_up
    canonical_stanza = next(
        index
        for index, command in enumerate(runner.commands)
        if any("canonical.env" in argument for argument in command) and "/usr/local/bin/backup-job.sh" in command
    )
    assert canonical_up < canonical_stanza < schema < runtime_up
    assert runner.commands[canonical_stanza][-5:-2] == [
        "--user",
        "postgres",
        "postgres-primary",
    ]
    assert not any(" down " in f" {' '.join(command)} " or "-v" in command for command in runner.commands)
    metadata_commands = [
        command for command in runner.commands if "create" in command and "com.dcim.role=schema-metadata" in command
    ]
    assert metadata_commands
    assert all(not argument.startswith("FAULT_TREE_HMAC_KEY=") for command in metadata_commands for argument in command)
    metadata_calls = [
        options
        for command, options in zip(runner.commands, runner.call_options, strict=True)
        if "create" in command and "com.dcim.role=schema-metadata" in command
    ]
    assert all(options["env"]["FAULT_TREE_HMAC_KEY"] for options in metadata_calls)
    admin_command = runner.commands[admin_bootstrap]
    admin_options = runner.call_options[admin_bootstrap]
    assert values["E2E_ADMIN_PASSWORD"] not in admin_command
    assert admin_options["env"]["E2E_ADMIN_PASSWORD"] == values["E2E_ADMIN_PASSWORD"]
    assert "E2E_ADMIN_PASSWORD" in admin_command
    admin_script = admin_command[-1]
    assert admin_script.index("user.password_hash =") < admin_script.index("await session.flush()")
    state_text = (inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8")
    assert values["SECRET_KEY"] not in state_text
    assert "database-secret" not in state_text
    assert '"release_gate": "BLOCKED"' in state_text


def test_failed_bootstrap_application_deploy_resumes_without_recreating_database(tmp_path, monkeypatch):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    runner = _LifecycleRunner()
    controller = FleetController(inventory, runner=runner)
    deploy_attempts = 0

    def fail_once(*_args):
        nonlocal deploy_attempts
        deploy_attempts += 1
        if deploy_attempts == 1:
            raise DeploymentError("application deployment failed")
        return [{"name": "application_deploy"}]

    monkeypatch.setattr(controller, "_deploy", fail_once)
    monkeypatch.setattr(controller, "_verify", lambda *_args: [{"name": "application_verify"}])

    first_report = controller.execute("bootstrap")
    pending = json.loads((inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8"))
    first_commands = len(runner.commands)
    second_report = controller.execute("bootstrap")
    resumed_commands = runner.commands[first_commands:]

    assert first_report["summary"]["failed"] == 1
    assert any(check["name"] == "first_full_backup" for check in first_report["results"][0]["checks"])
    assert pending["status"] == "bootstrap_pending"
    assert pending["phase"] == "dr_verified"
    assert pending["last_failure"]["error"] == "application deployment failed"
    assert pending["last_failure"]["stage"] == "application_deploy"
    assert second_report["summary"]["failed"] == 0
    assert deploy_attempts == 2
    assert not any("story_39_3_schema_bootstrap.py" in " ".join(command) for command in resumed_commands)
    assert not any("/usr/local/bin/backup-job.sh" in command for command in resumed_commands)
    assert not any(" volume create " in f" {' '.join(command)} " for command in resumed_commands)
    assert not any("canonical.env" in command and "up" in command for command in resumed_commands)
    assert not any("runtime.env" in command and "up" in command for command in resumed_commands)
    state = json.loads((inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8"))
    assert state["status"] == "verified"
    assert state["current"]["application_environment"]["CANDIDATE_GIT_SHA"] == values["CANDIDATE_GIT_SHA"]


def test_bootstrap_resumes_from_schema_checkpoint_after_runtime_start_failure(tmp_path, monkeypatch):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)

    class RuntimeStartFailsOnce(_LifecycleRunner):
        fail_runtime_start = True

        def run(self, command, **kwargs):
            command_list = list(command)
            if self.fail_runtime_start and "runtime.env" in " ".join(command_list) and "up" in command_list:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                self.fail_runtime_start = False
                raise DeploymentError("runtime start failed")
            return super().run(command_list, **kwargs)

    runner = RuntimeStartFailsOnce()
    controller = FleetController(inventory, runner=runner)
    monkeypatch.setattr(controller, "_deploy", lambda *_args: [{"name": "application_deploy"}])
    monkeypatch.setattr(controller, "_verify", lambda *_args: [{"name": "application_verify"}])

    first_report = controller.execute("bootstrap")
    pending = json.loads((inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8"))
    first_commands = len(runner.commands)
    second_report = controller.execute("bootstrap")
    resumed_commands = runner.commands[first_commands:]

    assert first_report["summary"]["failed"] == 1
    assert pending["phase"] == "schema_verified"
    assert pending["last_failure"]["stage"] == "dr_runtime_start"
    assert second_report["summary"]["failed"] == 0
    assert not any("story_39_3_schema_bootstrap.py" in " ".join(command) for command in resumed_commands)
    assert not any("canonical.env" in command and "up" in command for command in resumed_commands)
    assert not any(" volume create " in f" {' '.join(command)} " for command in resumed_commands)


def test_upgrade_and_rollback_require_schema_assertion_and_restore_previous_release(tmp_path, monkeypatch):
    inventory, old_values, env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    controller = FleetController(inventory, runner=runner, schema_compatible=True)
    manager = LifecycleManager(controller)
    manager._write_state(
        target,
        manager._verified_state(target, manager._release(target, old_values), previous=None, action="bootstrap"),
    )
    runner.database_empty = False
    deployed: list[str] = []
    monkeypatch.setattr(
        controller,
        "_deploy",
        lambda _target, values, _secrets, **_kwargs: deployed.append(values["CANDIDATE_GIT_SHA"]) or [],
    )
    monkeypatch.setattr(controller, "_verify", lambda *_args: [])
    new_values = dict(old_values)
    new_values.update(
        {
            "CANDIDATE_GIT_SHA": "c" * 40,
            "DCIM_BACKEND_IMAGE": f"ghcr.io/example/backend@sha256:{'d' * 64}",
            "DCIM_BACKEND_EXPECTED_ID": f"sha256:{'d' * 64}",
            "DCIM_FRONTEND_IMAGE": f"ghcr.io/example/frontend@sha256:{'e' * 64}",
            "DCIM_FRONTEND_EXPECTED_ID": f"sha256:{'e' * 64}",
            "NEW_CANDIDATE_FEATURE": "enabled",
        }
    )
    env_path.write_text("\n".join(f'{key}="{value}"' for key, value in new_values.items()), encoding="utf-8")

    upgrade_report = controller.execute("upgrade")
    rollback_report = controller.execute("rollback")

    assert upgrade_report["summary"]["failed"] == 0
    assert rollback_report["summary"]["failed"] == 0
    assert deployed == ["c" * 40, CANDIDATE_SHA]
    state = json.loads((inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8"))
    assert state["current"]["application_environment"]["CANDIDATE_GIT_SHA"] == CANDIDATE_SHA
    assert state["last_action"] == "rollback"
    assert not any("down" in command or "-v" in command for command in runner.commands)

    blocked = FleetController(inventory, runner=runner).execute("upgrade")
    assert blocked["summary"]["failed"] == 1
    assert "--schema-compatible" in blocked["results"][0]["error"]


def test_failed_upgrade_journal_can_rollback_to_last_verified_release(tmp_path, monkeypatch):
    inventory, old_values, env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    controller = FleetController(inventory, runner=runner, schema_compatible=True)
    manager = LifecycleManager(controller)
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, old_values),
            previous=None,
            action="bootstrap",
        ),
    )
    runner.database_empty = False
    new_values = dict(old_values)
    new_values.update(
        {
            "CANDIDATE_GIT_SHA": "c" * 40,
            "DCIM_BACKEND_IMAGE": f"ghcr.io/example/backend@sha256:{'d' * 64}",
            "DCIM_BACKEND_EXPECTED_ID": f"sha256:{'d' * 64}",
            "DCIM_FRONTEND_IMAGE": f"ghcr.io/example/frontend@sha256:{'e' * 64}",
            "DCIM_FRONTEND_EXPECTED_ID": f"sha256:{'e' * 64}",
            "NEW_CANDIDATE_FEATURE": "enabled",
        }
    )
    env_path.write_text(
        "\n".join(f'{key}="{value}"' for key, value in new_values.items()),
        encoding="utf-8",
    )
    deployed: list[tuple[str, str, bool]] = []

    def fail_candidate_then_restore(_target, values, _secrets, **_kwargs):
        deployed.append(
            (
                values["CANDIDATE_GIT_SHA"],
                values["CORS_ORIGINS"],
                "NEW_CANDIDATE_FEATURE" in values,
            )
        )
        if values["CANDIDATE_GIT_SHA"] == "c" * 40:
            raise DeploymentError("candidate verification failed")
        return []

    monkeypatch.setattr(controller, "_deploy", fail_candidate_then_restore)
    monkeypatch.setattr(controller, "_verify", lambda *_args: [])

    failed_upgrade = controller.execute("upgrade")
    pending = json.loads((inventory.state_directory / "lifecycle.json").read_text(encoding="utf-8"))
    broken_values = dict(new_values)
    broken_values.update(
        {
            "CANDIDATE_GIT_SHA": "invalid",
            "DCIM_BACKEND_IMAGE": "backend:latest",
            "CORS_ORIGINS": "https://broken.example.invalid",
        }
    )
    env_path.write_text(
        "\n".join(f'{key}="{value}"' for key, value in broken_values.items()),
        encoding="utf-8",
    )
    rollback = controller.execute("rollback")

    assert failed_upgrade["summary"]["failed"] == 1
    assert pending["status"] == "upgrade_pending"
    assert pending["current"]["application_environment"]["CANDIDATE_GIT_SHA"] == CANDIDATE_SHA
    assert rollback["summary"]["failed"] == 0
    assert deployed == [
        ("c" * 40, old_values["CORS_ORIGINS"], True),
        (CANDIDATE_SHA, old_values["CORS_ORIGINS"], False),
    ]


def test_status_reports_journal_and_dr_when_application_is_not_running(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]

    class PartialStatusRunner(_LifecycleRunner):
        def run(self, command, **kwargs):
            command_list = list(command)
            if command_list[-3:] == ["ps", "--format", "json"] and "--profile" not in command_list:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                return CommandResult(stdout="", stderr="", returncode=0)
            return super().run(command_list, **kwargs)

    runner = PartialStatusRunner()
    controller = FleetController(inventory, runner=runner)
    manager = LifecycleManager(controller)
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, values),
            previous=None,
            action="bootstrap",
        ),
    )
    target.env_file.unlink()

    report = controller.execute("status")
    checks = report["results"][0]["checks"]

    assert report["summary"]["failed"] == 1
    assert report["results"][0]["status"] == "partial"
    assert next(check for check in checks if check["name"] == "compose_status")["status"] == "failed"
    assert next(check for check in checks if check["name"] == "lifecycle_journal")["status"] == "passed"
    assert next(check for check in checks if check["name"] == "dr_services")["status"] == "passed"


def test_lifecycle_state_is_bound_to_target_identity(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, values),
            previous=None,
            action="bootstrap",
        ),
    )

    mismatched = replace(target, docker_context="different-context")
    with pytest.raises(DeploymentError, match="identity changed"):
        manager._read_state(mismatched)

    runner.daemon_id = "replacement-daemon-id"
    with pytest.raises(DeploymentError, match="runtime identity changed"):
        manager._read_state(target)


def test_lifecycle_state_rejects_configuration_hash_corruption(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, values),
            previous=None,
            action="bootstrap",
        ),
    )
    state_path = inventory.state_directory / "lifecycle.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current"]["application_environment"]["CANDIDATE_GIT_SHA"] = "f" * 40
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(DeploymentError, match="signature"):
        manager._read_state(target)

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current"]["application_environment"]["CANDIDATE_GIT_SHA"] = CANDIDATE_SHA
    state["current"]["application_configuration_sha256"] = "f" * 64
    manager._write_state(target, state)
    with pytest.raises(DeploymentError, match="configuration hash"):
        manager._read_state(target)

    state["current"]["application_configuration_sha256"] = state["current"]["application_configuration"]["sha256"]
    state["current"]["database"]["schema_application_image"] = f"example.invalid/schema@sha256:{'e' * 64}"
    manager._write_state(target, state)
    with pytest.raises(DeploymentError, match="database runtime changed"):
        manager._read_state(target)


def test_rollback_lock_is_local_only_running_leased_and_owner_guarded(tmp_path):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))

    with manager._target_lock(target, "rollback"):
        pass

    commands = runner.commands
    assert not any(
        " pull " in f" {' '.join(command)} " and target.dr.final_runtime_image in command for command in commands
    )
    lock_run = next(
        command
        for command in commands
        if " container run " in f" {' '.join(command)} " and "com.dcim.lifecycle.lock=true" in command
    )
    assert "--detach" in lock_run
    assert "--rm" in lock_run
    assert "com.dcim.lifecycle.action=rollback" in lock_run
    assert any(value.startswith("com.dcim.lifecycle.owner=") for value in lock_run)
    assert any(value.startswith("com.dcim.lifecycle.expires-at=") for value in lock_run)


def test_expired_stopped_daemon_lock_is_removed_but_active_lock_is_preserved(tmp_path):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]

    class ExistingLockRunner(_LifecycleRunner):
        running = False

        def run(self, command, **kwargs):
            command_list = list(command)
            joined = " ".join(command_list)
            if " container inspect " in f" {joined} " and "dcim-lifecycle-lock" in joined:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "Config": {
                                "Labels": {
                                    "com.dcim.lifecycle.lock": "true",
                                    "com.dcim.lifecycle.expires-at": "2000-01-01T00:00:00Z",
                                }
                            },
                            "State": {"Running": self.running},
                        }
                    ),
                    stderr="",
                    returncode=0,
                )
            return super().run(command_list, **kwargs)

    runner = ExistingLockRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    assert manager._remove_expired_daemon_lock(target, "dcim-lifecycle-lock-test") is True
    assert any("rm" in command and "--force" in command for command in runner.commands)

    runner.commands.clear()
    runner.running = True
    assert manager._remove_expired_daemon_lock(target, "dcim-lifecycle-lock-test") is False
    assert not any("rm" in command for command in runner.commands)


def test_schema_resume_rejects_replaced_primary_volume(tmp_path, monkeypatch):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)

    class RuntimeStartFailsOnce(_LifecycleRunner):
        fail_runtime_start = True

        def run(self, command, **kwargs):
            command_list = list(command)
            if self.fail_runtime_start and "runtime.env" in " ".join(command_list) and "up" in command_list:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                self.fail_runtime_start = False
                raise DeploymentError("runtime start failed")
            return super().run(command_list, **kwargs)

    runner = RuntimeStartFailsOnce()
    controller = FleetController(inventory, runner=runner)
    monkeypatch.setattr(controller, "_deploy", lambda *_args: [])
    monkeypatch.setattr(controller, "_verify", lambda *_args: [])

    first = controller.execute("bootstrap")
    first_command_count = len(runner.commands)
    runner.primary_volume_created_at = "2026-08-19T01:00:00Z"
    second = controller.execute("bootstrap")
    resumed_commands = runner.commands[first_command_count:]

    assert first["summary"]["failed"] == 1
    assert second["summary"]["failed"] == 1
    assert "primary PostgreSQL volume changed" in second["results"][0]["error"]
    assert not any("com.dcim.role=schema-catalog" in command for command in resumed_commands)


def test_schema_resume_rejects_live_catalog_drift(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]

    class CatalogDriftRunner(_LifecycleRunner):
        def run(self, command, **kwargs):
            command_list = list(command)
            if "com.dcim.role=schema-catalog" in command_list:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                return CommandResult(
                    stdout=json.dumps(
                        {
                            "database_state": "occupied",
                            "catalog_sha256": "f" * 64,
                            "alembic_head": "20260707_0100",
                        }
                    ),
                    stderr="",
                    returncode=0,
                )
            return super().run(command_list, **kwargs)

    runner = CatalogDriftRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    manifest = json.loads(lifecycle_module.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
    state = manager._bootstrap_pending_state(target, manager._release(target, values), "schema_verified")
    state["schema_checkpoint"] = manager._schema_checkpoint(target, {"catalog_sha256": manifest["catalog_sha256"]})

    with pytest.raises(DeploymentError, match="live canonical catalog differs"):
        manager._verify_schema_checkpoint(target, values, [], state)


def test_schema_resume_refreshes_stale_checkpoint_only_for_approved_live_catalog(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    runner.database_empty = False
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    manifest = json.loads(lifecycle_module.CANONICAL_MANIFEST.read_text(encoding="utf-8"))
    state = manager._bootstrap_pending_state(
        target, manager._release(target, values), "dr_verified"
    )
    state["schema_checkpoint"] = manager._schema_checkpoint(
        target, {"catalog_sha256": "e" * 64}
    )

    result = manager._verify_schema_checkpoint(target, values, [], state)

    assert result["checkpoint_refreshed"] is True
    assert result["previous_catalog_sha256"] == "e" * 64
    assert result["catalog_sha256"] == manifest["catalog_sha256"]


def test_reused_schema_report_is_bound_to_project_database_images_and_hashes(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    output_directory = tmp_path / "schema-report"
    secret_paths = {"POSTGRES_PASSWORD_FILE": tmp_path / "postgres-password"}

    check = manager._schema_bootstrap(target, values, secret_paths, [], output_directory=output_directory)
    assert check["catalog_sha256"]

    report_path = output_directory / "schema-bootstrap-last-run.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["database"] = "other_database"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(DeploymentError, match="did not pass"):
        manager._read_schema_report(target, values, output_directory)


def test_candidate_schema_contract_rejects_column_or_migration_drift(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)

    class DriftingSchemaRunner(_LifecycleRunner):
        probe_count = 0

        def run(self, command, **kwargs):
            command_list = list(command)
            result = super().run(command_list, **kwargs)
            if "start" in command_list and "--attach" in command_list:
                self.probe_count += 1
                if self.probe_count == 2:
                    payload = json.loads(result.stdout)
                    payload["schema_contract_sha256"] = "f" * 64
                    return CommandResult(stdout=json.dumps(payload), stderr="", returncode=0)
            return result

    manager = LifecycleManager(FleetController(inventory, runner=DriftingSchemaRunner()))

    with pytest.raises(DeploymentError, match="schema contract or migrations"):
        manager._verify_candidate_schema(inventory.targets[0], values, [])


def test_schema_contract_probe_serializes_enum_members(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))

    manager._verify_candidate_schema(inventory.targets[0], values, [])

    probe_commands = [command for command in runner.commands if "com.dcim.role=schema-metadata" in command]
    assert probe_commands
    assert all('"enum_values"' in command[-1] for command in probe_commands)


def test_repository_and_initial_full_backup_checkpoints_fail_closed(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    state = manager._verified_state(
        target,
        manager._release(target, values),
        previous=None,
        action="bootstrap",
    )
    manager._write_state(target, state)

    runner.repository_volume_created_at = "2026-08-19T01:00:00Z"
    with pytest.raises(DeploymentError, match="repository volume changed"):
        manager._read_state(target)

    runner.repository_volume_created_at = "2026-08-19T00:00:01Z"
    runner.full_backup_label = "20260820-000002F"
    with pytest.raises(DeploymentError, match="initial full backup is unavailable"):
        manager._verify_backup_checkpoint(target, [], state)


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        ("backup_step", "status_snapshot", "completed successful run"),
        ("backup_exit_code", 1, "completed successful run"),
        ("repository_status_code", 1, "stanza is not healthy"),
    ],
)
def test_backup_checkpoint_rejects_incomplete_or_unhealthy_metadata(tmp_path, attribute, value, message):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    runner = _LifecycleRunner()
    setattr(runner, attribute, value)
    manager = LifecycleManager(FleetController(inventory, runner=runner))

    with pytest.raises(DeploymentError, match=message):
        manager._backup_checkpoint(inventory.targets[0], [])


def test_status_reads_signed_journal_while_docker_daemon_is_offline(tmp_path, monkeypatch):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    controller = FleetController(inventory, runner=runner)
    manager = LifecycleManager(controller)
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, values),
            previous=None,
            action="bootstrap",
        ),
    )

    def daemon_offline(*_args, **_kwargs):
        raise DeploymentError("Docker daemon is offline")

    monkeypatch.setattr(runner, "run", daemon_offline)
    report = controller.execute("status")
    checks = report["results"][0]["checks"]

    assert next(check for check in checks if check["name"] == "lifecycle_journal")["status"] == "passed"
    assert next(check for check in checks if check["name"] == "compose_status")["status"] == "failed"
    assert next(check for check in checks if check["name"] == "dr_services")["status"] == "failed"


def test_status_marks_exited_or_unhealthy_services_failed(tmp_path):
    inventory, values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]

    class UnhealthyRunner(_LifecycleRunner):
        def run(self, command, **kwargs):
            command_list = list(command)
            if command_list[-3:] == ["ps", "--format", "json"]:
                self.commands.append(command_list)
                self.call_options.append(kwargs)
                names = (
                    ("postgres-primary", "postgres-standby", "backup-scheduler")
                    if "--profile" in command_list
                    else ("redis", "emqx", "backend", "nginx")
                )
                services = [{"Service": name, "State": "running", "Health": "healthy"} for name in names]
                services[-1]["State"] = "exited"
                services[-1]["Health"] = "unhealthy"
                return CommandResult(stdout=json.dumps(services), stderr="", returncode=0)
            return super().run(command_list, **kwargs)

    runner = UnhealthyRunner()
    controller = FleetController(inventory, runner=runner)
    manager = LifecycleManager(controller)
    manager._write_state(
        target,
        manager._verified_state(
            target,
            manager._release(target, values),
            previous=None,
            action="bootstrap",
        ),
    )

    report = controller.execute("status")
    checks = report["results"][0]["checks"]

    assert next(check for check in checks if check["name"] == "compose_status")["status"] == "failed"
    assert next(check for check in checks if check["name"] == "dr_services")["status"] == "failed"


def test_lifecycle_rejects_context_alias_resource_collisions(tmp_path):
    dr = _lifecycle_dr_config(tmp_path)
    targets = []
    for index in (1, 2):
        env_path = tmp_path / f"alias-{index}.env"
        _write_environment(env_path)
        targets.append(
            {
                "name": f"alias-{index}",
                "docker_context": f"context-alias-{index}",
                "env_file": str(env_path),
                "project_name": "shared-application",
                "dr": {
                    "mode": "local",
                    "compose_file": str(dr.compose_file),
                    "project_name": f"dr-{index}",
                    "secret_directory": str(tmp_path / f"secrets-{index}"),
                    "canonical_runtime_image": dr.canonical_runtime_image,
                    "final_runtime_image": dr.final_runtime_image,
                    "schema_application_image": dr.schema_application_image,
                    "repository_volume": f"repository-{index}",
                },
            }
        )
    inventory = load_inventory(_write_inventory(tmp_path, targets))

    with pytest.raises(DeploymentError, match="same Docker engine.*shared-application"):
        FleetController(inventory, runner=_LifecycleRunner()).execute("bootstrap")


def test_context_aliases_share_the_same_daemon_lock(tmp_path):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    lock_names = []

    for context in ("alias-one", "alias-two"):
        with manager._target_lock(replace(target, docker_context=context), "upgrade"):
            lock_command = next(
                command
                for command in reversed(runner.commands)
                if " container run " in f" {' '.join(command)} " and "com.dcim.lifecycle.lock=true" in command
            )
            lock_names.append(lock_command[lock_command.index("--name") + 1])

    assert lock_names[0] == lock_names[1]


def test_daemon_lock_renews_during_long_running_action(tmp_path, monkeypatch):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]
    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))
    monkeypatch.setattr(lifecycle_module, "LOCK_HEARTBEAT_INTERVAL_SECONDS", 0.005)

    with manager._target_lock(target, "upgrade"):
        time.sleep(0.03)

    assert any(
        " container exec " in f" {' '.join(command)} " and lifecycle_module.LOCK_HEARTBEAT_PATH in command
        for command in runner.commands
    )


def test_daemon_lock_fails_when_heartbeat_cannot_be_renewed(tmp_path, monkeypatch):
    inventory, _values, _env_path = _lifecycle_inventory(tmp_path)
    target = inventory.targets[0]

    runner = _LifecycleRunner()
    manager = LifecycleManager(FleetController(inventory, runner=runner))

    def fail_renewal(_target, _name, _stop, errors):
        errors.append(DeploymentError("heartbeat failed"))

    monkeypatch.setattr(manager, "_renew_daemon_lock", fail_renewal)

    with pytest.raises(DeploymentError, match="lock renewal failed"):
        with manager._target_lock(target, "upgrade"):
            pass


@pytest.mark.skipif(deploy_module.os.name != "nt", reason="Windows ACL only")
def test_environment_file_acl_is_restricted_before_secrets_are_read(tmp_path, monkeypatch):
    env_path = tmp_path / "protected.env"
    _write_environment(env_path)
    calls = []

    def successful_acl(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    deploy_module._PROTECTED_ENVIRONMENT_PATHS.discard(env_path.resolve())
    monkeypatch.setattr(deploy_module.subprocess, "run", successful_acl)
    assert parse_environment(env_path)["SECRET_KEY"] == "s" * 64
    assert calls
    assert "SetAccessRuleProtection($true, $false)" in calls[0][0][-1]

    rejected_path = tmp_path / "rejected.env"
    _write_environment(rejected_path)
    deploy_module._PROTECTED_ENVIRONMENT_PATHS.discard(rejected_path.resolve())
    monkeypatch.setattr(
        deploy_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, "", "restricted DACL verification failed"),
    )
    with pytest.raises(DeploymentError, match="cannot restrict Windows ACL"):
        parse_environment(rejected_path)
