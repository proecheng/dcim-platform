"""Story 39.3 迁移与应用回滚契约测试。"""

import importlib.util
from pathlib import Path
import sys

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _load_drill_module():
    path = REPO_ROOT / "scripts/story_39_3_migration_drill.py"
    spec = importlib.util.spec_from_file_location("story_39_3_migration_drill", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_migration_inventory_is_explicit_and_fail_closed():
    contract = _yaml("deploy/postgres-backup/migration-rollback-contract.yaml")
    release = contract["release_migration"]

    assert contract["schema_version"] == 1
    assert release["revision"] == "20260707_0100"
    assert release["down_revision"] == "20260322_0200"
    assert release["classification"] == "conditionally_reversible"
    assert release["migration_file"] == ("backend/alembic/versions/20260707_0100_power_device_flexibility_fields.py")
    assert release["write_freeze_required"] is True
    assert release["named_restore_point_required"] is True
    assert release["fallback"] == "pitr"
    assert release["downgrade_sequence"] == ["20260322_0200", "20260707_0100"]

    invariant = release["reversibility_invariant"]
    assert invariant["id"] == "new_flexibility_columns_are_empty"
    assert invariant["expected"] == 0
    for column in (
        "load_subtype",
        "controllable_params",
        "thermal_storage_config",
        "flexibility_factor",
    ):
        assert column in invariant["sql"]

    compatibility = contract["application_compatibility"]
    assert compatibility["previous_source_revision"] == "4dfac2df0d80141bd8044f8ccf9ed26de3cd6933"
    assert compatibility["current_source_revision"] == "436a8e778037bf6fcf9140b757e9584e669ad33b"
    assert compatibility["required_secret_files"] == ["FAULT_TREE_HMAC_KEY"]
    assert compatibility["previous_image_schema"] == "20260322_0200"
    assert compatibility["current_image_schema"] == "20260707_0100"


def test_irreversible_boundaries_require_pitr_not_alembic_downgrade():
    contract = _yaml("deploy/postgres-backup/migration-rollback-contract.yaml")
    boundaries = {item["revision"]: item for item in contract["irreversible_boundaries"]}

    assert boundaries["a001_full_schema"]["recovery"] == "pitr"
    assert "empty downgrade" in boundaries["a001_full_schema"]["reason"]
    assert boundaries["a002_timescaledb_hypertable"]["recovery"] == "pitr"
    assert "hypertable" in boundaries["a002_timescaledb_hypertable"]["reason"]


def test_migration_drill_requires_freeze_restore_point_and_immutable_images():
    drill = _text("scripts/story_39_3_migration_drill.py")

    for required in (
        "MIGRATION_WRITE_FREEZE_TOKEN",
        "MIGRATION_RESTORE_POINT",
        "CURRENT_APP_IMAGE",
        "PREVIOUS_APP_IMAGE",
        "FAULT_TREE_HMAC_KEY",
        "org.opencontainers.image.revision",
        "application_image_provenance_mismatch",
        "@sha256:",
        "com.dcim.story",
        "com.dcim.dr.role",
        'inspect_labels(runner, "volume"',
        "restore-socket",
        "pg_create_restore_point",
        "new_flexibility_columns_are_empty",
        "alembic current",
        "alembic downgrade",
        "alembic upgrade",
        "migration_invariant_changed",
        "alembic_not_at_head",
        "timescaledb_objects_missing",
        "previous_app_incompatible",
        "validate_previous_app_schema",
        "validate_current_app_schema",
        "migration-last-run.json",
        "subprocess.run",
    ):
        assert required in drill

    assert drill.index("pg_create_restore_point") < drill.index("alembic downgrade")
    assert drill.index("new_flexibility_columns_are_empty") < drill.index("alembic downgrade")
    assert "shell=True" not in drill


def test_database_runtime_image_does_not_absorb_application_migration_stack():
    dockerfile = _text("deploy/postgres-backup/Dockerfile")
    assert "story_39_3_migration_drill.py" not in dockerfile
    assert "alembic" not in dockerfile.lower()


def test_application_image_revision_label_is_fail_closed():
    drill = _load_drill_module()
    image = "example.invalid/backend@sha256:" + ("c" * 64)

    class LabelRunner:
        def __init__(self, revision):
            self.revision = revision

        def run(self, _step, _argv, **_kwargs):
            return '{"org.opencontainers.image.revision":"' + self.revision + '"}'

    expected = "4dfac2df0d80141bd8044f8ccf9ed26de3cd6933"
    drill.validate_image(LabelRunner(expected), "previous_app", image, expected)

    with pytest.raises(drill.DrillError, match="source revision") as error:
        drill.validate_image(LabelRunner("wrong"), "previous_app", image, expected)
    assert error.value.code == "application_image_provenance_mismatch"


def test_migration_drill_uses_explicit_database_role_for_psql(monkeypatch, tmp_path):
    drill = _load_drill_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "story_39_3_migration_drill.py",
            "--project",
            "dcim-story-39-3-full",
            "--postgres-container",
            "postgres-restore",
            "--network",
            "restore-isolated",
            "--socket-volume",
            "restore-socket-volume",
            "--database-url-file",
            str(tmp_path / "database-url"),
            "--write-freeze-token-file",
            str(tmp_path / "freeze-token"),
            "--fault-tree-hmac-key-file",
            str(tmp_path / "fault-tree-hmac-key"),
            "--output-dir",
            str(tmp_path),
        ],
    )

    args = drill.parse_args()
    assert args.database_user == "dcim"
    assert args.socket_volume == "restore-socket-volume"

    class RecordingRunner:
        def __init__(self):
            self.argv = None

        def run(self, _step, argv, **_kwargs):
            self.argv = argv
            return "1"

    runner = RecordingRunner()
    drill.psql(runner, "postgres-restore", "dcim", args.database_user, "probe", "SELECT 1;")

    assert runner.argv is not None
    assert runner.argv[runner.argv.index("--user") + 1] == "postgres"
    assert runner.argv[runner.argv.index("--username") + 1] == "dcim"


def test_run_app_injects_secret_by_environment_name_only():
    drill = _load_drill_module()

    class RecordingRunner:
        def __init__(self):
            self.argv = None
            self.env = None

        def run(self, _step, argv, **kwargs):
            self.argv = argv
            self.env = kwargs["env"]
            return "ok"

    runner = RecordingRunner()
    secret = "a" * 64
    drill.run_app(
        runner,
        step="probe",
        image="example.invalid/backend@sha256:" + ("b" * 64),
        network="restore-isolated",
        socket_volume="restore-socket-volume",
        database_url="postgresql+asyncpg://dcim:secret@postgres-restore:5432/dcim",
        runtime_environment={"FAULT_TREE_HMAC_KEY": secret},
        entrypoint="python",
        arguments=["-c", "print('ok')"],
        failure_code="probe_failed",
    )

    assert runner.argv is not None
    assert runner.env is not None
    assert runner.env["FAULT_TREE_HMAC_KEY"] == secret
    assert runner.argv.count("--env") == 2
    assert "DATABASE_URL" in runner.argv
    assert "FAULT_TREE_HMAC_KEY" in runner.argv
    assert "type=volume,src=restore-socket-volume,dst=/var/run/postgresql,readonly" in runner.argv
    assert secret not in runner.argv


def test_named_secret_can_be_loaded_from_dotenv_without_exposing_other_values(tmp_path):
    drill = _load_drill_module()
    secret = "b" * 64
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"OTHER_SECRET=do-not-use\nFAULT_TREE_HMAC_KEY='{secret}'\n",
        encoding="utf-8",
    )

    assert (
        drill.load_secret_file(
            dotenv,
            "application_secret_missing",
            drill.FAULT_TREE_HMAC_KEY,
            environment_name=drill.FAULT_TREE_HMAC_KEY,
        )
        == secret
    )
