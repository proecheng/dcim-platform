import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.observability import AlertEvaluator, ObservabilityMonitor, _gateway_backlog, read_backup_status


def _snapshot(**overrides):
    snapshot = {
        "captured_at_utc": "2026-08-18T00:00:00Z",
        "metrics": {
            "rolling_window": {"requests": 1000, "errors": 0, "error_rate_percent": 0.0},
            "system": {"cpu_percent": 20.0, "memory_percent": 20.0, "disk_usage_percent": 20.0},
        },
        "dependencies": {
            "database": {"status": "ok"},
            "redis": {"status": "disabled"},
            "mqtt": {"status": "disabled"},
            "websocket": {"status": "ok"},
        },
        "backup": {"available": True, "status": "ok", "backup_age_seconds": 60, "scheduler_freshness_seconds": 0},
        "gateway_backlog": {
            "available": True,
            "enabled_datasources": 1,
            "warning_datasources": 0,
            "critical_datasources": 0,
            "stale_gateways": 0,
            "offline_gateways": 0,
        },
    }
    for key, value in overrides.items():
        snapshot[key] = value
    return snapshot


def _at(seconds: int) -> datetime:
    return datetime(2026, 8, 18, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_alert_evaluator_applies_exact_error_thresholds_and_recovery():
    evaluator = AlertEvaluator()
    warning = _snapshot(metrics={"rolling_window": {"requests": 200, "errors": 2, "error_rate_percent": 1.0}})
    assert evaluator.evaluate(warning, now=_at(0))["alerts"]["http_error_rate"]["state"] == "warning"

    critical = _snapshot(metrics={"rolling_window": {"requests": 100, "errors": 2, "error_rate_percent": 2.0}})
    assert evaluator.evaluate(critical, now=_at(1))["alerts"]["http_error_rate"]["state"] == "critical"

    for second in (31, 61):
        assert evaluator.evaluate(_snapshot(), now=_at(second))["alerts"]["http_error_rate"]["state"] == "recovering"
    resolved = evaluator.evaluate(_snapshot(), now=_at(91))["alerts"]["http_error_rate"]
    assert resolved["state"] == "ok"
    assert resolved["recovery_count"] == 3
    assert resolved["resolved_at_utc"] is not None


def test_error_alert_uses_exact_counts_instead_of_rounded_display_rate():
    evaluator = AlertEvaluator()
    snapshot = _snapshot(
        metrics={
            "rolling_window": {
                "requests": 100_000,
                "errors": 1_001,
                "error_rate_percent": 1.0,
            }
        }
    )
    result = evaluator.evaluate(snapshot, now=_at(0))["alerts"]["http_error_rate"]
    assert result["state"] == "critical"
    assert result["observed_value"] == pytest.approx(1.001)


def test_resource_alerts_are_pending_until_five_minutes_and_recover_three_times():
    evaluator = AlertEvaluator()
    high_cpu = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0, "error_rate_percent": 0.0}, "system": {"cpu_percent": 80.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    assert evaluator.evaluate(high_cpu, now=_at(0))["alerts"]["cpu_usage"]["state"] == "pending"
    assert evaluator.evaluate(high_cpu, now=_at(299))["alerts"]["cpu_usage"]["state"] == "pending"
    assert evaluator.evaluate(high_cpu, now=_at(300))["alerts"]["cpu_usage"]["state"] == "warning"

    critical_cpu = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0, "error_rate_percent": 0.0}, "system": {"cpu_percent": 90.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    escalation = evaluator.evaluate(critical_cpu, now=_at(600))["alerts"]["cpu_usage"]
    assert escalation["state"] == "warning"
    assert escalation["pending_severity"] == "critical"
    assert evaluator.evaluate(critical_cpu, now=_at(899))["alerts"]["cpu_usage"]["state"] == "warning"
    assert evaluator.evaluate(critical_cpu, now=_at(900))["alerts"]["cpu_usage"]["state"] == "critical"
    still_critical = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0, "error_rate_percent": 0.0}, "system": {"cpu_percent": 85.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    assert evaluator.evaluate(still_critical, now=_at(901))["alerts"]["cpu_usage"]["state"] == "critical"

    not_recovered = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0, "error_rate_percent": 0.0}, "system": {"cpu_percent": 79.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    assert evaluator.evaluate(not_recovered, now=_at(902))["alerts"]["cpu_usage"]["state"] == "critical"

    low_cpu = _snapshot()
    for second in (931, 961):
        assert evaluator.evaluate(low_cpu, now=_at(second))["alerts"]["cpu_usage"]["state"] == "recovering"
    assert evaluator.evaluate(low_cpu, now=_at(991))["alerts"]["cpu_usage"]["state"] == "ok"


def test_unknown_telemetry_does_not_erase_active_alert_and_requires_recovery():
    evaluator = AlertEvaluator()
    critical = _snapshot(metrics={"rolling_window": {"requests": 100, "errors": 2, "error_rate_percent": 2.0}})
    assert evaluator.evaluate(critical, now=_at(0))["alerts"]["http_error_rate"]["state"] == "critical"
    unknown = _snapshot(metrics={"rolling_window": {}})
    assert evaluator.evaluate(unknown, now=_at(1))["alerts"]["http_error_rate"]["state"] == "unknown"
    assert evaluator.evaluate(_snapshot(), now=_at(31))["alerts"]["http_error_rate"]["state"] == "recovering"
    assert evaluator.evaluate(_snapshot(), now=_at(61))["alerts"]["http_error_rate"]["state"] == "recovering"
    assert evaluator.evaluate(_snapshot(), now=_at(91))["alerts"]["http_error_rate"]["state"] == "ok"


def test_duplicate_or_too_frequent_samples_cannot_advance_recovery():
    evaluator = AlertEvaluator()
    critical = _snapshot(metrics={"rolling_window": {"requests": 100, "errors": 2}})
    evaluator.evaluate(critical, now=_at(0), sample_id="critical-1")

    first = evaluator.evaluate(_snapshot(), now=_at(30), sample_id="healthy-1")
    assert first["alerts"]["http_error_rate"]["recovery_count"] == 1
    duplicate = evaluator.evaluate(_snapshot(), now=_at(60), sample_id="healthy-1")
    assert duplicate["sample_accepted"] is False
    assert duplicate["alerts"]["http_error_rate"]["recovery_count"] == 1
    too_soon = evaluator.evaluate(_snapshot(), now=_at(59), sample_id="healthy-2")
    assert too_soon["sample_accepted"] is False
    assert too_soon["alerts"]["http_error_rate"]["recovery_count"] == 1


def test_unknown_sample_restarts_resource_sustain_timer():
    evaluator = AlertEvaluator()
    high_cpu = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0}, "system": {"cpu_percent": 80.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    assert evaluator.evaluate(high_cpu, now=_at(0))["alerts"]["cpu_usage"]["state"] == "pending"
    unknown = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0}, "system": {"cpu_percent": None, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    assert evaluator.evaluate(unknown, now=_at(240))["alerts"]["cpu_usage"]["state"] == "unknown"
    restarted = evaluator.evaluate(high_cpu, now=_at(300))["alerts"]["cpu_usage"]
    assert restarted["state"] == "pending"
    assert restarted["pending_since_utc"] == _at(300).isoformat().replace("+00:00", "Z")


def test_resource_warning_and_critical_sustain_timers_are_independent():
    evaluator = AlertEvaluator()
    warning_cpu = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0}, "system": {"cpu_percent": 80.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    critical_cpu = _snapshot(metrics={"rolling_window": {"requests": 10, "errors": 0}, "system": {"cpu_percent": 90.0, "memory_percent": 20.0, "disk_usage_percent": 20.0}})
    evaluator.evaluate(warning_cpu, now=_at(0))
    evaluator.evaluate(critical_cpu, now=_at(240))
    warning_fires = evaluator.evaluate(critical_cpu, now=_at(300))["alerts"]["cpu_usage"]
    assert warning_fires["state"] == "warning"
    assert warning_fires["pending_severity"] == "critical"
    assert evaluator.evaluate(critical_cpu, now=_at(540))["alerts"]["cpu_usage"]["state"] == "critical"


@pytest.mark.parametrize("overrides,rule_id", [
    ({"dependencies": {}}, "dependencies"),
    ({"dependencies": {"database": {"status": "ok"}}}, "dependencies"),
    ({"gateway_backlog": {"available": True}}, "gateway_backlog"),
])
def test_incomplete_snapshot_sections_fail_closed(overrides, rule_id):
    result = AlertEvaluator().evaluate(_snapshot(**overrides), now=_at(0))
    assert result["alerts"][rule_id]["state"] == "unknown"


def test_mqtt_health_requires_explicit_connected_state():
    from app.mqtt.client import MqttService

    service = MqttService()
    service._running = True
    service._client = object()
    assert service.is_connected is False
    service._connected = True
    assert service.is_connected is True
    service._running = False
    assert service.is_connected is False


def test_standard_compose_mounts_dr_status_read_only():
    import yaml

    compose_path = Path(__file__).resolve().parents[2] / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    backend = compose["services"]["backend"]
    assert backend["environment"]["BACKUP_STATUS_DIR"] == "/var/lib/dcim-dr-status"
    assert "dr-status:/var/lib/dcim-dr-status:ro" in backend["volumes"]
    assert compose["volumes"]["dr-status"]["external"] is True


def test_backend_image_runs_single_observability_evaluator_worker():
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    contents = dockerfile.read_text(encoding="utf-8")
    assert '"--workers", "1"' in contents
    assert '"--workers", "2"' not in contents


def test_backup_and_gateway_rules_use_exact_d39_03_boundaries():
    evaluator = AlertEvaluator()
    warning_backup = _snapshot(backup={"available": True, "status": "ok", "backup_age_seconds": 26 * 3600})
    assert evaluator.evaluate(warning_backup, now=_at(0))["alerts"]["backup_age"]["state"] == "warning"
    critical_backup = _snapshot(backup={"available": True, "status": "ok", "backup_age_seconds": 36 * 3600})
    assert evaluator.evaluate(critical_backup, now=_at(1))["alerts"]["backup_age"]["state"] == "critical"

    warning_gateway = _snapshot(
        gateway_backlog={"available": True, "warning_datasources": 1, "critical_datasources": 0, "stale_gateways": 0, "offline_gateways": 0}
    )
    assert evaluator.evaluate(warning_gateway, now=_at(2))["alerts"]["gateway_backlog"]["state"] == "warning"
    critical_gateway = _snapshot(
        gateway_backlog={"available": True, "warning_datasources": 0, "critical_datasources": 1, "stale_gateways": 0, "offline_gateways": 0}
    )
    assert evaluator.evaluate(critical_gateway, now=_at(3))["alerts"]["gateway_backlog"]["state"] == "critical"


def test_stale_backup_scheduler_fails_closed_even_when_backup_age_is_low():
    evaluator = AlertEvaluator()
    stale = _snapshot(
        backup={
            "status": "ok",
            "available": True,
            "backup_age_seconds": 60,
            "scheduler_freshness_seconds": 301,
        }
    )
    result = evaluator.evaluate(stale, now=_at(0))["alerts"]["backup_age"]
    assert result["state"] == "critical"


def test_unavailable_gateway_backlog_fails_closed():
    evaluator = AlertEvaluator()
    unavailable = _snapshot(
        gateway_backlog={
            "available": False,
            "warning_datasources": 0,
            "critical_datasources": 0,
            "stale_gateways": 0,
            "offline_gateways": 0,
        }
    )
    result = evaluator.evaluate(unavailable, now=_at(0))["alerts"]["gateway_backlog"]
    assert result["state"] == "critical"


def test_backup_status_reader_fails_closed_for_missing_and_malformed_files(tmp_path: Path):
    missing = read_backup_status(tmp_path)
    assert missing["status"] == "missing"
    assert missing["available"] is False

    (tmp_path / "backup-status.json").write_text("{bad", encoding="utf-8")
    malformed = read_backup_status(tmp_path)
    assert malformed["status"] == "malformed"
    assert malformed["available"] is False

    (tmp_path / "scheduler-heartbeat").write_text("2026-08-18T00:00:00Z\n", encoding="utf-8")
    (tmp_path / "backup-status.json").write_text(
        json.dumps({"status": "ok", "backup_age_seconds": 26 * 3600, "captured_at_utc": "2026-08-18T00:00:00Z"}),
        encoding="utf-8",
    )
    warning = read_backup_status(tmp_path, now=_at(60))
    assert warning["status"] == "ok"
    assert warning["backup_age_seconds"] == 26 * 3600 + 60
    assert warning["scheduler_freshness_seconds"] == 60

    (tmp_path / "backup-status.json").write_text(
        json.dumps({"status": "unexpected", "backup_age_seconds": 1, "captured_at_utc": "2026-08-18T00:00:00Z"}),
        encoding="utf-8",
    )
    unsupported = read_backup_status(tmp_path, now=_at(60))
    assert unsupported["status"] == "malformed"
    assert unsupported["available"] is False


def test_backup_reader_rejects_missing_stale_or_future_scheduler_heartbeat(tmp_path: Path):
    (tmp_path / "backup-status.json").write_text(
        json.dumps({"status": "ok", "backup_age_seconds": 60, "captured_at_utc": "2026-08-18T00:00:00Z"}),
        encoding="utf-8",
    )
    assert read_backup_status(tmp_path, now=_at(60))["status"] == "scheduler_missing"
    (tmp_path / "scheduler-heartbeat").write_text("2026-08-17T23:54:00Z\n", encoding="utf-8")
    assert read_backup_status(tmp_path, now=_at(60))["status"] == "scheduler_stale"
    (tmp_path / "scheduler-heartbeat").write_text("2026-08-18T00:02:00Z\n", encoding="utf-8")
    assert read_backup_status(tmp_path, now=_at(60))["status"] == "malformed"


@pytest.mark.anyio
async def test_future_gateway_heartbeat_fails_closed():
    gateway = SimpleNamespace(
        cpu_usage=1,
        memory_usage=1,
        disk_usage=1,
        status="online",
        last_heartbeat=_at(31),
    )
    gateway_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [gateway]))
    datasource_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[gateway_result, datasource_result]))

    result = await _gateway_backlog(db, now=_at(0))

    assert result["future_gateways"] == 1
    assert result["stale_gateways"] == 1


@pytest.mark.anyio
async def test_observability_endpoint_is_read_only_and_returns_snapshot_contract():
    from app.api.deps import enforce_inventory_authorization, require_admin
    from app.main import app
    from app.models.user import User

    user = User(id=1, username="viewer", role="viewer", is_active=True)
    snapshot = {"status": "degraded", "alerts": {}, "captured_at_utc": "2026-08-18T00:00:00Z"}

    async def override_admin():
        return user

    async def override_inventory_authorization():
        return None

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[enforce_inventory_authorization] = override_inventory_authorization
    try:
        with patch("app.api.v1.system_health.observability_monitor.get_snapshot", new=AsyncMock(return_value=snapshot)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/system/observability")
        assert response.status_code == 200
        assert response.json() == snapshot
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_monitor_persists_state_and_get_snapshot_does_not_evaluate(tmp_path: Path):
    monitor = ObservabilityMonitor(state_path=tmp_path / "state.json")
    critical = _snapshot(metrics={"rolling_window": {"requests": 100, "errors": 2}})
    await monitor.record_snapshot(critical, now=_at(0), sample_id="sample-1")
    before = await monitor.get_snapshot()
    after = await monitor.get_snapshot()
    assert after == before
    assert (tmp_path / "state.json").is_file()

    restored = ObservabilityMonitor(state_path=tmp_path / "state.json")
    restored_snapshot = await restored.get_snapshot()
    assert restored_snapshot["alerts"]["http_error_rate"]["state"] == "critical"
