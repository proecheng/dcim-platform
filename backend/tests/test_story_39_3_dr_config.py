"""Story 39.3 灾备拓扑与安全配置契约测试。"""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_IMAGE = (
    "public.ecr.aws/docker/library/postgres:16.15-bookworm"
    "@sha256:60f4761b9035e0b8d5218f701a8c3382f641bf12b1604822574cf5be3baeb537"
)
VERSIONED_IMAGE = "dcim-postgres:16.15-ts2.29.1-pgb2.59.0"
DR_IMAGE_REFERENCE = (
    "${DCIM_POSTGRES_IMAGE_REPOSITORY:?DCIM_POSTGRES_IMAGE_REPOSITORY is required}"
    "@sha256:${DCIM_POSTGRES_IMAGE_DIGEST:?DCIM_POSTGRES_IMAGE_DIGEST is required}"
)
SCHEMA_GATE_BASE = (
    "dcim-postgres:16.15-ts2.29.1-pgb2.59.0@sha256:e6ca69c005bfba5b30dbb91c58a181874e2c833e0a311ad3998f32d4b497f3e4"
)


def _yaml(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_postgres_image_sources_are_immutable_and_versioned():
    compose = _yaml("docker-compose.yml")
    postgres = compose["services"]["postgres"]

    assert postgres["image"] == VERSIONED_IMAGE
    assert postgres["build"]["dockerfile"] == "deploy/postgres-backup/Dockerfile"
    assert "latest" not in postgres["image"].lower()

    dockerfile = _text("deploy/postgres-backup/Dockerfile")
    assert not dockerfile.startswith("# syntax=")
    assert f"ARG POSTGRES_BASE_IMAGE={BASE_IMAGE}" in dockerfile
    assert dockerfile.count("FROM ${POSTGRES_BASE_IMAGE}") == 2
    assert "TIMESCALEDB_VERSION=2.29.1" in dockerfile
    assert "APACHE_ONLY" not in dockerfile
    assert "PGBACKREST_VERSION=2.59.0" in dockerfile
    assert "B0054B6D399268E8ABFE4C64DB846EC843AE93A1CBBA5D5F1811E9198F666212" in dockerfile
    assert "faaf8faa14a6392279654ee216a493fcd07b0c513af4b55fe34faec062cb8875" in dockerfile

    versions = _yaml("deploy/postgres-backup/versions.yaml")
    assert versions["postgresql"]["version"] == "16.15"
    assert versions["postgresql"]["base_image"] == BASE_IMAGE
    assert versions["timescaledb"]["version"] == "2.29.1"
    assert versions["pgbackrest"]["version"] == "2.59.0"
    assert versions["release_image"]["require_digest"] is True


def test_postgres_image_build_sources_are_configurable_in_both_stages():
    dockerfile = _text("deploy/postgres-backup/Dockerfile")

    assert "ARG DEBIAN_MIRROR=http://deb.debian.org/debian" in dockerfile
    assert "ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security" in dockerfile
    assert "ARG PGDG_MIRROR=http://apt.postgresql.org/pub/repos/apt" in dockerfile
    assert dockerfile.count("ARG DEBIAN_MIRROR") == 3
    assert dockerfile.count("ARG DEBIAN_SECURITY_MIRROR") == 3
    assert dockerfile.count("ARG PGDG_MIRROR") == 3
    assert dockerfile.count("sed -ri") == 2
    assert dockerfile.count("${DEBIAN_MIRROR}") == 2
    assert dockerfile.count("${DEBIAN_SECURITY_MIRROR}") == 2
    assert dockerfile.count("${PGDG_MIRROR}") == 2
    assert (
        "ARG PGBACKREST_SOURCE_URL=https://github.com/pgbackrest/pgbackrest/releases/download/release/"
        "2.59.0/pgbackrest-2.59.0.tar.gz"
    ) in dockerfile
    assert '"${PGBACKREST_SOURCE_URL}"' in dockerfile
    assert "--retry-all-errors" in dockerfile


def test_postgres_root_build_context_only_includes_the_dr_image_sources():
    dockerignore = _text(".dockerignore").splitlines()

    assert dockerignore[0] == "**"
    assert "!deploy/" in dockerignore
    assert "!deploy/postgres-backup/" in dockerignore
    assert "!deploy/postgres-backup/**" in dockerignore
    assert not any("secret" in line.lower() for line in dockerignore if line.startswith("!"))


def test_schema_gate_refresh_is_pinned_and_only_replaces_validator_inputs():
    dockerfile = _text("deploy/postgres-backup/Dockerfile.schema-gate")

    assert f"ARG DCIM_POSTGRES_RUNTIME_BASE={SCHEMA_GATE_BASE}" in dockerfile
    assert "FROM ${DCIM_POSTGRES_RUNTIME_BASE}" in dockerfile
    assert "COPY deploy/postgres-backup/restore-validate.sh /usr/local/bin/restore-validate.sh" in dockerfile
    assert (
        "COPY deploy/postgres-backup/expected-schema-tables.txt "
        "/usr/local/share/dcim-dr/expected-schema-tables.txt" in dockerfile
    )
    assert "bash -n /usr/local/bin/restore-validate.sh" in dockerfile


def test_dr_compose_separates_roles_networks_and_volumes():
    dr = _yaml("deploy/dr/docker-compose.dr.yml")
    services = dr["services"]
    required = {"postgres-primary", "postgres-standby", "backup-scheduler", "postgres-restore"}
    assert required.issubset(services)

    for name in required:
        image = services[name]["image"]
        assert image == DR_IMAGE_REFERENCE
        assert "latest" not in image.lower()

    assert services["postgres-primary"]["environment"]["DCIM_DR_INIT_ENABLED"] == "true"

    primary_volumes = "\n".join(services["postgres-primary"]["volumes"])
    standby_volumes = "\n".join(services["postgres-standby"]["volumes"])
    restore_volumes = "\n".join(services["postgres-restore"]["volumes"])
    scheduler_volumes = "\n".join(services["backup-scheduler"]["volumes"])

    assert "postgres-primary-data:/var/lib/postgresql/data" in primary_volumes
    assert "postgres-standby-data:/var/lib/postgresql/data" in standby_volumes
    assert "postgres-restore-data:/var/lib/postgresql/data" in restore_volumes
    assert "pgbackrest-repository:/var/lib/pgbackrest" in scheduler_volumes
    assert "postgres-primary-data" not in restore_volumes
    assert "postgres-standby-data" not in restore_volumes
    assert "/var/lib/pgbackrest:ro" in restore_volumes

    assert set(services["postgres-primary"]["networks"]) == {
        "primary-site",
        "replication-transit",
        "database-client",
    }
    assert services["postgres-primary"]["networks"]["database-client"]["aliases"] == ["postgres-writer"]
    assert set(services["postgres-standby"]["networks"]) == {"standby-site", "replication-transit"}
    assert "restore-isolated" in services["postgres-restore"]["networks"]
    assert dr["networks"]["database-client"]["internal"] is True
    assert dr["networks"]["database-client"]["labels"]["com.dcim.dr.role"] == "stable-endpoint"


def test_postgres_wal_replication_and_status_contract_is_bounded():
    config = _text("deploy/postgres-backup/postgresql-primary.conf")
    assert "wal_level = replica" in config
    assert "archive_mode = on" in config
    assert "pgbackrest-wrapper --stanza=dcim archive-push %p" in config
    assert "archive_timeout = 60s" in config
    assert "max_replication_slots = 4" in config
    assert "max_slot_wal_keep_size = 10GB" in config
    assert "wal_log_hints = on" in config
    assert "full_page_writes = on" in config

    status_sql = _text("deploy/postgres-backup/postgres-status.sql")
    assert "pg_stat_archiver" in status_sql
    assert "pg_stat_replication" in status_sql
    assert "pg_replication_slots" in status_sql
    assert "pg_wal_lsn_diff" in status_sql


def test_dr_credentials_are_secret_files_and_fail_closed():
    dr = _yaml("deploy/dr/docker-compose.dr.yml")
    secret_definitions = dr["secrets"]
    expected = {"postgres_password", "replication_password", "pgbackrest_cipher_pass", "fence_token"}
    assert expected.issubset(secret_definitions)
    for name in expected:
        assert secret_definitions[name]["file"].startswith("${")
        assert ":?" in secret_definitions[name]["file"]

    rendered = _text("deploy/dr/docker-compose.dr.yml")
    assert "POSTGRES_PASSWORD_FILE" in rendered
    assert "REPLICATION_PASSWORD_FILE" in rendered
    assert "PGBACKREST_REPO1_CIPHER_PASS_FILE" in rendered
    assert "FENCE_TOKEN_FILE" in rendered
    assert "POSTGRES_PASSWORD:" not in rendered
    assert "REPLICATION_PASSWORD:" not in rendered
    assert "PGBACKREST_REPO1_CIPHER_PASS:" not in rendered

    validator = _text("deploy/postgres-backup/validate-secrets.sh")
    assert "placeholder" in validator
    assert "required" in validator
    assert "chmod" not in validator

    wrapper = _text("deploy/postgres-backup/pgbackrest-wrapper")
    assert "PGBACKREST_PG1_USER" in wrapper
    assert "POSTGRES_USER" in wrapper
    assert "unset PGBACKREST_REPO1_CIPHER_PASS_FILE" in wrapper


def test_dr_initialization_is_opt_in_for_the_default_compose_stack():
    init_script = _text("deploy/postgres-backup/init-primary.sh")
    opt_in_guard = init_script.index("dr_init_enabled=${DCIM_DR_INIT_ENABLED:-false}")
    disabled_exit = init_script.index("false)\n        exit 0")
    secret_requirement = init_script.index("REPLICATION_PASSWORD_FILE is required")

    assert opt_in_guard < disabled_exit < secret_requirement

    dr = _yaml("deploy/dr/docker-compose.dr.yml")
    assert dr["services"]["postgres-primary"]["environment"]["DCIM_DR_INIT_ENABLED"] == "true"

    env_example = _text(".env.example")
    assert "DCIM_POSTGRES_IMAGE_REPOSITORY=" in env_example
    assert "DCIM_POSTGRES_IMAGE_DIGEST=" in env_example
    assert "DCIM_POSTGRES_IMAGE=" not in env_example


def test_promotion_contract_requires_fencing_and_safe_rejoin():
    runbook = _text("deploy/dr/README.md").lower()
    assert "fence" in runbook
    assert "promotion" in runbook
    assert "pg_rewind" in runbook
    assert "full rebuild" in runbook
    assert "automatic failover" in runbook
    assert "@sha256" in runbook
