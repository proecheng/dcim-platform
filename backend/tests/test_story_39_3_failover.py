"""Story 39.3 受控 failover/failback 契约测试。"""

import importlib.util
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    with (REPO_ROOT / path).open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def _load_drill_module():
    path = REPO_ROOT / "scripts/story_39_3_failover_drill.py"
    spec = importlib.util.spec_from_file_location("story_39_3_failover_drill", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failover_contract_matches_d39_01_and_separates_evidence_classes():
    contract = _yaml("deploy/postgres-backup/failover-contract.yaml")

    assert contract["schema_version"] == 1
    assert contract["stable_endpoint"]["hostname"] == "postgres-writer"
    assert contract["stable_endpoint"]["probe_table"] == "story_39_3_failover_probe"

    scenarios = contract["scenarios"]
    assert scenarios["planned_switchover"]["rpo_seconds_max"] == 0
    assert scenarios["planned_switchover"]["rto_seconds_max"] == 900
    assert scenarios["unexpected_primary_failure"]["rpo_seconds_max"] == 60
    assert scenarios["unexpected_primary_failure"]["rto_seconds_max"] == 1800
    assert scenarios["site_restore"]["rpo_seconds_max"] == 300
    assert scenarios["site_restore"]["rto_seconds_max"] == 14400

    evidence = contract["evidence_classification"]
    assert evidence["same_host"] == "mechanism-only"
    assert evidence["independent_failure_domain_required"] is True
    assert evidence["same_host_may_claim_formal_pass"] is False

    rejoin = contract["old_primary_rejoin"]
    assert set(rejoin["allowed_methods"]) == {"pg_rewind", "full_rebuild"}
    assert rejoin["untreated_old_primary_allowed"] is False


def test_standby_can_follow_a_promoted_peer_and_archive_after_promotion():
    entrypoint = _text("deploy/postgres-backup/standby-entrypoint.sh")
    compose = _yaml("deploy/dr/docker-compose.dr.yml")

    for required in (
        "PRIMARY_HOST",
        "PRIMARY_PORT",
        "REPLICATION_SLOT",
        'host="$primary_host"',
        '--host="$primary_host"',
        '--port="$primary_port"',
        '--slot="$replication_slot"',
    ):
        assert required in entrypoint

    standby_mounts = compose["services"]["postgres-standby"]["volumes"]
    repository_mount = next(item for item in standby_mounts if item.startswith("pgbackrest-repository:"))
    assert not repository_mount.endswith(":ro")


def test_failover_drill_is_fenced_timeline_driven_and_fail_closed():
    drill = _text("scripts/story_39_3_failover_drill.py")

    for required in (
        "postgres-writer",
        "story_39_3_failover_probe",
        "time.monotonic",
        "pg_last_wal_replay_lsn",
        "pg_current_wal_lsn",
        "pg_is_in_recovery",
        "pg_promote",
        "docker",
        "network",
        "disconnect",
        "--alias",
        "postgres-writer",
        "old_primary_rejoin_refused",
        "full_rebuild",
        "missing_commit_count",
        "latest_missing_commit_age_seconds",
        "mechanism-only",
        "independent_failure_domain_required",
        "failover-last-run.json",
        "PowerDevice",
        "application_readiness_and_critical_write",
    ):
        assert required in drill

    assert "shell=True" not in drill
    assert drill.index("verify_fence") < drill.index("pg_promote")


def test_rpo_calculation_counts_missing_acknowledged_commits_and_age():
    drill = _load_drill_module()
    result = drill.calculate_rpo(
        acknowledged=[
            {"sequence": 1, "committed_at": "2026-08-15T00:00:00Z"},
            {"sequence": 2, "committed_at": "2026-08-15T00:00:01Z"},
            {"sequence": 3, "committed_at": "2026-08-15T00:00:02Z"},
        ],
        recovered_sequences={1, 3},
        recovered_at="2026-08-15T00:00:05Z",
    )

    assert result["missing_commit_count"] == 1
    assert result["missing_sequences"] == [2]
    assert result["latest_missing_commit_age_seconds"] == 4.0


def test_same_host_cannot_claim_formal_or_spoof_independent_evidence(tmp_path):
    drill = _load_drill_module()
    contract = _yaml("deploy/postgres-backup/failover-contract.yaml")

    same_host = drill.classify_evidence(failure_domain="same-host", attestation=None, contract=contract)
    assert same_host["class"] == "mechanism-only"
    assert same_host["formal_pass_allowed"] is False

    attestation = tmp_path / "failure-domain.yaml"
    attestation.write_text(
        "primary_failure_domain: site-a\nstandby_failure_domain: site-b\nindependent_failure_domain_required: true\n",
        encoding="utf-8",
    )
    with pytest.raises(drill.DrillError) as exc_info:
        drill.classify_evidence(
            failure_domain="independent",
            attestation=attestation,
            contract=contract,
        )

    assert exc_info.value.code == "independent_failure_domain_unsupported"
