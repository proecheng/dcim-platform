"""Story 39.3 空仓库初始化与当前发布 schema 引导测试。"""

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SCHEMA_SHA256 = "81cdd3d0d4d3a4ad5edc128981e383bcfff5f37bc1b9d30f491c1598fc1be6b3"


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _load_bootstrap_module():
    path = REPO_ROOT / "scripts/story_39_3_schema_bootstrap.py"
    spec = importlib.util.spec_from_file_location("story_39_3_schema_bootstrap", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_primary_init_creates_and_checks_stanza_before_entrypoint_returns():
    init_script = _text("deploy/postgres-backup/init-primary.sh")

    stanza_create = '/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" stanza-create'
    repository_check = '/usr/local/bin/pgbackrest-wrapper --stanza="$stanza" check'
    assert stanza_create in init_script
    assert repository_check in init_script
    assert init_script.index(stanza_create) < init_script.index(repository_check)

    schema_gate = _text("deploy/postgres-backup/Dockerfile.schema-gate")
    assert (
        "COPY deploy/postgres-backup/init-primary.sh /docker-entrypoint-initdb.d/20-dcim-replication.sh" in schema_gate
    )
    assert "chmod 0755 /docker-entrypoint-initdb.d/20-dcim-replication.sh" in schema_gate
    assert "bash -n /docker-entrypoint-initdb.d/20-dcim-replication.sh" in schema_gate


def test_schema_bootstrap_contract_is_fail_closed_and_ordered():
    bootstrap = _text("scripts/story_39_3_schema_bootstrap.py")

    for required in (
        "com.dcim.story",
        "com.docker.compose.project",
        "com.dcim.dr.role",
        "com.dcim.dr.site",
        "@sha256:",
        "expected-schema-tables.txt",
        EXPECTED_SCHEMA_SHA256,
        "canonical-schema.dump",
        "canonical-schema-manifest.json",
        "artifact_sha256",
        "catalog_sha256",
        "pg_restore",
        "--single-transaction",
        "pg_get_constraintdef",
        "information_schema.columns",
        "20260707_0100",
        "timescaledb_information.hypertables",
        "timescaledb_information.jobs",
        "schema-bootstrap-last-run.json",
        "subprocess.run",
        "FAULT_TREE_HMAC_KEY",
    ):
        assert required in bootstrap

    assert bootstrap.index("validate_isolation") < bootstrap.index("restore_canonical_schema")
    assert bootstrap.index("validate_application_metadata") < bootstrap.index("restore_canonical_schema")
    assert bootstrap.index("require_empty_database") < bootstrap.index("restore_canonical_schema")
    assert "Base.metadata.create_all" not in bootstrap
    assert 'arguments=["stamp"' not in bootstrap
    assert "shell=True" not in bootstrap


def test_schema_bootstrap_rejects_mutable_application_image():
    bootstrap = _load_bootstrap_module()

    with pytest.raises(bootstrap.BootstrapError, match="immutable") as exc_info:
        bootstrap.validate_image_reference("ghcr.io/proecheng/dcim-platform/backend:latest")

    assert exc_info.value.code == "mutable_application_image"


def test_schema_bootstrap_rejects_manifest_hash_mismatch(tmp_path):
    bootstrap = _load_bootstrap_module()
    manifest = tmp_path / "expected-schema-tables.txt"
    approved = _text("deploy/postgres-backup/expected-schema-tables.txt")
    manifest.write_text(approved.replace("users\n", "users_tampered\n"), encoding="utf-8")

    with pytest.raises(bootstrap.BootstrapError, match="hash") as exc_info:
        bootstrap.load_expected_schema(manifest, EXPECTED_SCHEMA_SHA256)

    assert exc_info.value.code == "schema_manifest_hash_mismatch"


def test_schema_bootstrap_rejects_non_empty_database():
    bootstrap = _load_bootstrap_module()

    with pytest.raises(bootstrap.BootstrapError, match="empty") as exc_info:
        bootstrap.require_empty_database(1)

    assert exc_info.value.code == "database_not_empty"


def test_schema_bootstrap_rejects_isolation_label_mismatch():
    bootstrap = _load_bootstrap_module()

    container_labels = {
        "com.dcim.story": "39.3",
        "com.docker.compose.project": "dcim-story-39-3-full",
        "com.dcim.dr.role": "primary",
    }
    network_labels = {
        "com.dcim.story": "39.3",
        "com.docker.compose.project": "another-project",
        "com.dcim.dr.site": "primary",
    }

    with pytest.raises(bootstrap.BootstrapError, match="project") as exc_info:
        bootstrap.validate_isolation_labels(
            "dcim-story-39-3-full",
            container_labels,
            network_labels,
        )

    assert exc_info.value.code == "isolation_label_invalid"


def test_canonical_manifest_binds_dump_hash_and_release_provenance(tmp_path):
    bootstrap = _load_bootstrap_module()
    dump = tmp_path / "canonical-schema.dump"
    dump.write_bytes(b"canonical")
    application_image = "example.invalid/backend@sha256:" + ("a" * 64)
    manifest = tmp_path / "canonical-schema-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact": dump.name,
                "artifact_sha256": bootstrap.file_sha256(dump),
                "catalog_sha256": "b" * 64,
                "alembic_head": bootstrap.RELEASE_HEAD,
                "source_revision": bootstrap.SOURCE_REVISION,
                "application_image": application_image,
                "runtime_image": "example.invalid/postgres@sha256:" + ("c" * 64),
                "table_count": bootstrap.EXPECTED_TABLE_COUNT,
                "table_names_sha256": bootstrap.EXPECTED_SCHEMA_SHA256,
            }
        ),
        encoding="utf-8",
    )

    payload = bootstrap.load_canonical_manifest(manifest, dump, application_image)
    assert payload["artifact_sha256"] == bootstrap.file_sha256(dump)

    dump.write_bytes(b"tampered")
    with pytest.raises(bootstrap.BootstrapError) as exc_info:
        bootstrap.load_canonical_manifest(manifest, dump, application_image)
    assert exc_info.value.code == "canonical_artifact_hash_mismatch"


def test_empty_database_guard_covers_non_table_objects():
    bootstrap = _load_bootstrap_module()
    occupancy = {
        "public_relations": 0,
        "public_functions": 1,
        "public_types": 0,
        "user_schemas": 0,
        "non_builtin_extensions": 0,
    }

    with pytest.raises(bootstrap.BootstrapError) as exc_info:
        bootstrap.require_empty_database(occupancy)
    assert exc_info.value.code == "database_not_empty"


def test_committed_canonical_artifact_matches_manifest():
    bootstrap = _load_bootstrap_module()
    dump = REPO_ROOT / "deploy/postgres-backup/canonical-schema.dump"
    manifest = json.loads(_text("deploy/postgres-backup/canonical-schema-manifest.json"))

    assert dump.stat().st_size > 1_000_000
    assert bootstrap.file_sha256(dump) == manifest["artifact_sha256"]


def test_canonical_artifact_cleanup_uses_root_for_sticky_tmp(tmp_path):
    bootstrap = _load_bootstrap_module()

    class Runner:
        def __init__(self):
            self.calls = []

        def run(self, step, argv, **_kwargs):
            self.calls.append((step, argv))
            return ""

        def try_run(self, step, argv, **_kwargs):
            self.calls.append((step, argv))
            return True, ""

    runner = Runner()
    bootstrap.restore_canonical_schema(
        runner,
        dump_path=tmp_path / "canonical-schema.dump",
        container="validated-primary",
        database="dcim",
        database_user="dcim",
    )

    cleanup = runner.calls[-1]
    assert cleanup == (
        "remove_canonical_schema_copy",
        [
            "docker",
            "exec",
            "validated-primary",
            "rm",
            "-f",
            bootstrap.CANONICAL_CONTAINER_PATH,
        ],
    )
