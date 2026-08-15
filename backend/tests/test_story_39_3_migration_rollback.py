"""Story 39.3 迁移与应用回滚契约测试。"""

import importlib.util
import json
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
        "alembic_current",
        "alembic_downgrade",
        "alembic_upgrade",
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

    assert drill.index("pg_create_restore_point") < drill.index("alembic_downgrade")
    assert drill.index("new_flexibility_columns_are_empty") < drill.index("alembic_downgrade")
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
            "--migration-database-url-file",
            str(tmp_path / "migration-database-url"),
            "--write-freeze-token-file",
            str(tmp_path / "freeze-token"),
            "--fault-tree-hmac-key-file",
            str(tmp_path / "fault-tree-hmac-key"),
            "--output-dir",
            str(tmp_path),
            "--pitr-evidence-file",
            str(tmp_path / "pitr-evidence.json"),
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
            self.calls = []
            self.env = None

        def run(self, _step, argv, **kwargs):
            self.calls.append(argv)
            if "env" in kwargs:
                self.env = kwargs["env"]
            return "ok"

        def try_run(self, _step, _argv, **_kwargs):
            return True, ""

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

    assert runner.calls
    assert runner.env is not None
    assert runner.env["FAULT_TREE_HMAC_KEY"] == secret
    create_argv = runner.calls[0]
    assert create_argv.count("--env") == 2
    assert "DATABASE_URL" in create_argv
    assert "FAULT_TREE_HMAC_KEY" in create_argv
    assert "type=volume,src=restore-socket-volume,dst=/var/run/postgresql,readonly" in create_argv
    assert secret not in create_argv


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


def test_database_urls_are_bound_to_validated_restore_socket():
    drill = _load_drill_module()
    application_url = "postgresql+asyncpg://dcim:secret@/dcim?host=%2Fvar%2Frun%2Fpostgresql"

    assert (
        drill.validate_socket_database_url(
            application_url,
            expected_database="dcim",
            expected_user="dcim",
            name="application database URL",
        )
        == application_url
    )
    with pytest.raises(drill.DrillError) as tcp_error:
        drill.validate_socket_database_url(
            "postgresql+asyncpg://dcim:secret@postgres-restore:5432/dcim",
            expected_database="dcim",
            expected_user="dcim",
            name="application database URL",
        )
    assert tcp_error.value.code == "database_url_target_invalid"

    with pytest.raises(drill.DrillError) as role_error:
        drill.validate_socket_database_url(
            application_url,
            expected_database="dcim",
            expected_user="postgres",
            name="migration database URL",
        )
    assert role_error.value.code == "database_url_target_invalid"


def test_database_native_fence_disables_login_and_terminates_sessions():
    drill = _load_drill_module()

    class RecordingRunner:
        def __init__(self):
            self.commands = []

        def run(self, step, argv, **_kwargs):
            self.commands.append((step, argv))
            return "0" if step == "verify_application_sessions_fenced" else ""

    runner = RecordingRunner()
    drill.set_application_login(
        runner,
        "postgres-restore",
        "dcim",
        "postgres",
        "dcim",
        False,
    )

    sql = [argv[argv.index("--command") + 1] for _, argv in runner.commands]
    assert 'ALTER ROLE "dcim" NOLOGIN' in sql[0]
    assert "pg_terminate_backend" in sql[1]
    assert "pg_stat_activity" in sql[2]


def test_application_and_schema_probes_use_runtime_metadata_and_business_dml():
    drill = _load_drill_module()

    assert "Base.metadata.tables" in drill.APP_IMAGE_SCHEMA_PROBE
    assert "ScriptDirectory" in drill.APP_IMAGE_SCHEMA_PROBE
    assert "models.glob" not in drill.APP_IMAGE_SCHEMA_PROBE
    assert "update(PowerDevice)" in drill.APP_PROBE
    assert "transaction.rollback" in drill.APP_PROBE
    assert "TEMP TABLE" not in drill.APP_PROBE
    assert "information_schema.columns" in drill.DATABASE_FINGERPRINT_PROBE
    assert "pg_get_constraintdef" in drill.DATABASE_FINGERPRINT_PROBE


def test_pitr_evidence_is_bound_to_restore_point_and_fingerprints(tmp_path):
    drill = _load_drill_module()
    database_fingerprint = {"alembic_revision": "head", "catalog": {}, "data": {}}
    timescaledb_fingerprint = {"hypertables": [{}], "jobs": [{}, {}]}
    evidence = tmp_path / "pitr-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "pass",
                "isolated_restore": True,
                "restore_target_type": "name",
                "restore_target_value": "story_39_3_test",
                "restore_lsn": "0/123",
                "alembic_head": "head",
                "repository_check": "pass",
                "pg_amcheck": "pass",
                "rpo_missing_commit_count": 0,
                "rto_seconds": 30,
                "database_fingerprint": database_fingerprint,
                "timescaledb_fingerprint": timescaledb_fingerprint,
            }
        ),
        encoding="utf-8",
    )

    payload = drill.wait_for_pitr_evidence(
        evidence,
        restore_point="story_39_3_test",
        restore_lsn="0/123",
        expected_head="head",
        expected_database_fingerprint=database_fingerprint,
        expected_timescaledb_fingerprint=timescaledb_fingerprint,
        created_after=evidence.stat().st_mtime - 1,
        timeout=1,
        poll_interval=0.01,
    )
    assert payload["status"] == "pass"
