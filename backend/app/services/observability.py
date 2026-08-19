"""Story 39.7 SLO observability, alert evaluation, and evidence inputs."""

from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.observability import D39_03, ObservabilityThresholds
from ..core.config import get_settings
from ..core.redis import redis_service
from ..middleware.metrics import metrics_collector
from ..models.gateway import DataSource, Gateway
from ..mqtt import mqtt_service
from ..services.websocket import ws_manager


UTC = timezone.utc
OWNER = "proecheng"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if math.isfinite(converted) else None


def _nested_number(value: Mapping[str, Any], *keys: str) -> float | None:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return _number(current)


def read_backup_status(status_dir: str | os.PathLike[str] | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Read the atomic Story 39.3 status snapshot without trusting its contents."""
    directory = Path(status_dir or os.getenv("BACKUP_STATUS_DIR", "/var/lib/dcim-dr-status"))
    path = directory / "backup-status.json"
    base = {"available": False, "path": "backup-status.json"}
    if not path.is_file() or path.is_symlink():
        return {**base, "status": "missing", "error": "backup status is not available"}
    try:
        if path.stat().st_size > 1_048_576:
            raise ValueError("backup status exceeds size limit")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {**base, "status": "malformed", "error": str(exc)}
    if not isinstance(payload, dict):
        return {**base, "status": "malformed", "error": "backup status must be an object"}

    captured_at = _parse_utc(payload.get("captured_at_utc"))
    current = now or _utc_now()
    heartbeat_path = directory / "scheduler-heartbeat"
    if not heartbeat_path.is_file() or heartbeat_path.is_symlink():
        return {**base, "status": "scheduler_missing", "error": "backup scheduler heartbeat is not available"}
    try:
        scheduler_at = _parse_utc(heartbeat_path.read_text(encoding="utf-8").strip())
    except OSError as exc:
        return {**base, "status": "scheduler_missing", "error": str(exc)}
    if scheduler_at is None or scheduler_at > current + timedelta(seconds=30):
        return {**base, "status": "malformed", "error": "backup scheduler heartbeat is invalid or in the future"}
    scheduler_freshness = (current - scheduler_at).total_seconds()
    if scheduler_freshness > D39_03.monitoring_gap_seconds:
        return {
            **base,
            "status": "scheduler_stale",
            "scheduler_freshness_seconds": scheduler_freshness,
            "error": "backup scheduler heartbeat is stale",
        }
    age = _number(payload.get("backup_age_seconds"))
    if age is None and isinstance(payload.get("backup_age_seconds"), type(None)):
        age = None
    status = payload.get("status")
    if status not in {"ok", "failed", "initializing"}:
        return {**base, "status": "malformed", "error": "backup status contains an unsupported state"}
    if age is not None and age < 0:
        return {**base, "status": "malformed", "error": "backup age cannot be negative"}
    if captured_at is None or age is None and status == "ok":
        return {**base, "status": "malformed", "error": "backup status lacks valid timestamp or age"}
    if captured_at and captured_at > current + timedelta(seconds=30):
        return {**base, "status": "malformed", "error": "backup status timestamp is in the future"}
    if captured_at and age is not None:
        age += max(0.0, (current - captured_at).total_seconds())
    result = {
        **base,
        "available": True,
        "status": status,
        "backup_age_seconds": age,
        "captured_at_utc": _utc_iso(captured_at),
        "scheduler_heartbeat_at_utc": _utc_iso(scheduler_at),
        "scheduler_freshness_seconds": scheduler_freshness,
        "last_run_status": payload.get("last_run_status"),
        "failure_code": payload.get("failure_code"),
        "retention_full_count": payload.get("retention_full_count"),
        "retention_window_full_count": payload.get("retention_window_full_count"),
    }
    return result


@dataclass
class _AlertLifecycle:
    first_observed_at: datetime | None = None
    fired_at: datetime | None = None
    resolved_at: datetime | None = None
    recovery_count: int = 0
    last_state: str = "ok"
    active_severity: str | None = None
    pending_severity: str | None = None
    warning_since: datetime | None = None
    critical_since: datetime | None = None
    last_recovery_at: datetime | None = None


class AlertEvaluator:
    """Deterministic process-local D39-03 alert lifecycle evaluator."""

    def __init__(self, *, thresholds: ObservabilityThresholds = D39_03) -> None:
        self.thresholds = thresholds
        self._lifecycles: dict[str, _AlertLifecycle] = {}
        self._last_sample_id: str | None = None
        self._last_sample_at: datetime | None = None
        self.minimum_sample_interval_seconds = 30

    def _transition(
        self,
        rule_id: str,
        severity: str | None,
        observed_value: Any,
        threshold: Any,
        now: datetime,
        *,
        sustained_seconds: int = 0,
        runbook: str,
        accepted: bool,
    ) -> dict[str, Any]:
        lifecycle = self._lifecycles.setdefault(rule_id, _AlertLifecycle())
        if not accepted:
            return self._result(rule_id, lifecycle.last_state, observed_value, threshold, lifecycle, runbook, sustained_seconds)
        if severity is None:
            lifecycle.recovery_count = 0
            lifecycle.last_recovery_at = None
            lifecycle.warning_since = None
            lifecycle.critical_since = None
            lifecycle.pending_severity = None
            lifecycle.last_state = "unknown"
            return self._result(rule_id, "unknown", observed_value, threshold, lifecycle, runbook, sustained_seconds)

        if severity == "ok":
            lifecycle.warning_since = None
            lifecycle.critical_since = None
            lifecycle.pending_severity = None
            if lifecycle.active_severity or lifecycle.last_state in {"unknown", "recovering"}:
                lifecycle.recovery_count += 1
                lifecycle.last_recovery_at = now
                lifecycle.last_state = "ok" if lifecycle.recovery_count >= self.thresholds.recovery_evaluations else "recovering"
                if lifecycle.last_state == "ok":
                    lifecycle.resolved_at = now
                    lifecycle.first_observed_at = None
                    lifecycle.fired_at = None
                    lifecycle.active_severity = None
                    lifecycle.pending_severity = None
            else:
                lifecycle.last_state = "ok"
                lifecycle.recovery_count = 0
                lifecycle.last_recovery_at = None
            return self._result(rule_id, lifecycle.last_state, observed_value, threshold, lifecycle, runbook, sustained_seconds)

        lifecycle.recovery_count = 0
        lifecycle.last_recovery_at = None
        lifecycle.resolved_at = None
        rank = {"warning": 1, "critical": 2}
        active_rank = rank.get(lifecycle.active_severity or "", 0)
        requested_rank = rank[severity]
        if severity == "warning" and lifecycle.active_severity != "critical":
            lifecycle.critical_since = None
            lifecycle.pending_severity = None
        if lifecycle.active_severity and requested_rank <= active_rank:
            lifecycle.last_state = lifecycle.active_severity
            return self._result(
                rule_id, lifecycle.last_state, observed_value, threshold, lifecycle, runbook, sustained_seconds
            )

        if severity == "warning":
            lifecycle.warning_since = lifecycle.warning_since or now
            lifecycle.critical_since = None
        else:
            lifecycle.warning_since = lifecycle.warning_since or now
            lifecycle.critical_since = lifecycle.critical_since or now
        warning_elapsed = max(0.0, (now - lifecycle.warning_since).total_seconds())
        critical_elapsed = (
            max(0.0, (now - lifecycle.critical_since).total_seconds()) if lifecycle.critical_since else 0.0
        )
        warning_ready = not sustained_seconds or warning_elapsed >= sustained_seconds
        critical_ready = severity == "critical" and (not sustained_seconds or critical_elapsed >= sustained_seconds)
        if critical_ready:
            lifecycle.active_severity = "critical"
            lifecycle.first_observed_at = lifecycle.critical_since
            lifecycle.fired_at = now
            lifecycle.pending_severity = None
            lifecycle.last_state = "critical"
        elif warning_ready:
            if lifecycle.active_severity is None:
                lifecycle.active_severity = "warning"
                lifecycle.first_observed_at = lifecycle.warning_since
                lifecycle.fired_at = now
            lifecycle.pending_severity = "critical" if severity == "critical" else None
            lifecycle.last_state = lifecycle.active_severity
        else:
            lifecycle.pending_severity = severity
            lifecycle.last_state = lifecycle.active_severity or "pending"
        return self._result(rule_id, lifecycle.last_state, observed_value, threshold, lifecycle, runbook, sustained_seconds)

    @staticmethod
    def _result(
        rule_id: str,
        state: str,
        observed_value: Any,
        threshold: Any,
        lifecycle: _AlertLifecycle,
        runbook: str,
        sustained_seconds: int,
    ) -> dict[str, Any]:
        return {
            "rule_id": rule_id,
            "state": state,
            "severity": state if state in {"warning", "critical"} else None,
            "observed_value": observed_value,
            "threshold": threshold,
            "required_duration_seconds": sustained_seconds,
            "owner": OWNER,
            "runbook": runbook,
            "first_observed_at_utc": _utc_iso(lifecycle.first_observed_at),
            "fired_at_utc": _utc_iso(lifecycle.fired_at),
            "recovery_count": lifecycle.recovery_count,
            "resolved_at_utc": _utc_iso(lifecycle.resolved_at),
            "pending_severity": lifecycle.pending_severity,
            "pending_since_utc": _utc_iso(
                lifecycle.critical_since if lifecycle.pending_severity == "critical" else lifecycle.warning_since
            ),
        }

    def evaluate(
        self,
        snapshot: Mapping[str, Any],
        *,
        now: datetime | None = None,
        sample_id: str | None = None,
    ) -> dict[str, Any]:
        current = now or _utc_now()
        sample_key = sample_id or _utc_iso(current)
        accepted = True
        if sample_key == self._last_sample_id:
            accepted = False
        elif self._last_sample_at is not None and current <= self._last_sample_at:
            accepted = False
        elif sample_id is not None and self._last_sample_at is not None and (
            current - self._last_sample_at
        ).total_seconds() < self.minimum_sample_interval_seconds:
            accepted = False
        if accepted:
            self._last_sample_id = sample_key
            self._last_sample_at = current
        metrics = snapshot.get("metrics") if isinstance(snapshot.get("metrics"), Mapping) else {}
        rolling = metrics.get("rolling_window") if isinstance(metrics.get("rolling_window"), Mapping) else {}
        system = metrics.get("system") if isinstance(metrics.get("system"), Mapping) else {}
        rolling_requests = _number(rolling.get("requests"))
        rolling_errors = _number(rolling.get("errors"))
        if (
            rolling_requests is not None
            and rolling_errors is not None
            and rolling_requests >= 0
            and 0 <= rolling_errors <= rolling_requests
        ):
            error_rate = rolling_errors / rolling_requests * 100 if rolling_requests else 0.0
        else:
            error_rate = _number(rolling.get("error_rate_percent"))
        alerts: dict[str, dict[str, Any]] = {}

        if error_rate is None:
            error_severity = None
        elif error_rate > self.thresholds.error_critical_percent:
            error_severity = "critical"
        elif error_rate > self.thresholds.error_warning_percent:
            error_severity = "warning"
        else:
            error_severity = "ok"
        alerts["http_error_rate"] = self._transition(
            "http_error_rate",
            error_severity,
            error_rate,
            {"warning_percent": self.thresholds.error_warning_percent, "critical_percent": self.thresholds.error_critical_percent},
            current,
            runbook="slo/http-error-rate",
            accepted=accepted,
        )

        for rule_id, metric_key in (("cpu_usage", "cpu_percent"), ("memory_usage", "memory_percent"), ("disk_usage", "disk_usage_percent")):
            value = _number(system.get(metric_key))
            existing = self._lifecycles.get(rule_id)
            if value is None:
                severity = None
            elif value >= self.thresholds.resource_critical_percent:
                severity = "critical"
            elif value >= self.thresholds.resource_warning_percent:
                severity = "critical" if existing and existing.last_state == "critical" else "warning"
            elif value >= self.thresholds.resource_recovery_percent and existing and existing.last_state in {
                "warning",
                "critical",
                "recovering",
            }:
                severity = "critical" if existing.last_state == "critical" else "warning"
            else:
                severity = "ok"
            alerts[rule_id] = self._transition(
                rule_id,
                severity,
                value,
                {"warning_percent": self.thresholds.resource_warning_percent, "critical_percent": self.thresholds.resource_critical_percent},
                current,
                sustained_seconds=self.thresholds.resource_sustain_seconds,
                runbook=f"slo/{rule_id}",
                accepted=accepted,
            )

        backup = snapshot.get("backup") if isinstance(snapshot.get("backup"), Mapping) else {}
        backup_status = backup.get("status")
        backup_age = _number(backup.get("backup_age_seconds"))
        backup_freshness = _number(backup.get("scheduler_freshness_seconds"))
        if (
            backup_status != "ok"
            or backup.get("available") is False
            or backup.get("failure_code") not in {None, ""}
            or backup.get("last_run_status") == "failed"
            or backup_freshness is not None
            and backup_freshness > self.thresholds.monitoring_gap_seconds
        ):
            backup_severity = "critical"
        elif backup_age is None:
            backup_severity = None
        elif backup_age >= self.thresholds.backup_critical_age_seconds:
            backup_severity = "critical"
        elif backup_age >= self.thresholds.backup_warning_age_seconds:
            backup_severity = "warning"
        else:
            backup_severity = "ok"
        alerts["backup_age"] = self._transition(
            "backup_age",
            backup_severity,
            backup_age,
            {"warning_seconds": self.thresholds.backup_warning_age_seconds, "critical_seconds": self.thresholds.backup_critical_age_seconds},
            current,
            runbook="dr/backup-status",
            accepted=accepted,
        )

        dependencies = snapshot.get("dependencies") if isinstance(snapshot.get("dependencies"), Mapping) else {}
        required_dependencies = {"database", "redis", "mqtt", "websocket"}
        dependencies_valid = set(dependencies) == required_dependencies and all(
            isinstance(dependencies.get(name), Mapping)
            and dependencies[name].get("status") in {"ok", "disabled", "fail", "failed", "critical", "unknown", "unavailable", "degraded"}
            for name in required_dependencies
        )
        dependency_states = [dependencies[name].get("status") for name in required_dependencies] if dependencies_valid else []
        if not dependencies_valid:
            dependency_severity = None
        elif any(state in {"fail", "failed", "critical"} for state in dependency_states):
            dependency_severity = "critical"
        elif any(state in {"unknown", "unavailable", "degraded"} for state in dependency_states):
            dependency_severity = None
        else:
            dependency_severity = "ok"
        alerts["dependencies"] = self._transition(
            "dependencies",
            dependency_severity,
            dependencies,
            {"failed": "critical", "unknown": "fail_closed"},
            current,
            runbook="slo/dependencies",
            accepted=accepted,
        )

        backlog = snapshot.get("gateway_backlog") if isinstance(snapshot.get("gateway_backlog"), Mapping) else {}
        warning_count = _number(backlog.get("warning_datasources"))
        critical_count = _number(backlog.get("critical_datasources"))
        stale_gateways = _number(backlog.get("stale_gateways"))
        offline_gateways = _number(backlog.get("offline_gateways"))
        backlog_fields = ("warning_datasources", "critical_datasources", "stale_gateways", "offline_gateways")
        backlog_valid = backlog.get("available") is True and all(
            _number(backlog.get(field)) is not None and _number(backlog.get(field)) >= 0 for field in backlog_fields
        )
        if backlog.get("available") is False:
            backlog_severity = "critical"
        elif not backlog_valid:
            backlog_severity = None
        elif any(
            (value or 0) > 0 for value in (critical_count, stale_gateways, offline_gateways)
        ):
            backlog_severity = "critical"
        elif (warning_count or 0) > 0:
            backlog_severity = "warning"
        else:
            backlog_severity = "ok"
        alerts["gateway_backlog"] = self._transition(
            "gateway_backlog",
            backlog_severity,
            {"warning_datasources": warning_count, "critical_datasources": critical_count, "stale_gateways": stale_gateways, "offline_gateways": offline_gateways},
            {"warning_failures": self.thresholds.gateway_warning_failures, "heartbeat_critical_seconds": self.thresholds.gateway_heartbeat_critical_seconds},
            current,
            runbook="gateway/communication-backlog",
            accepted=accepted,
        )

        active = [alert for alert in alerts.values() if alert["state"] in {"warning", "critical", "unknown", "pending", "recovering"}]
        critical = any(alert["state"] == "critical" for alert in alerts.values())
        unknown = any(alert["state"] == "unknown" for alert in alerts.values())
        return {
            "evaluated_at_utc": _utc_iso(current),
            "sample_id": sample_key,
            "sample_accepted": accepted,
            "alerts": alerts,
            "active_alerts": active,
            "status": "critical" if critical else "unknown" if unknown else "degraded" if active else "healthy",
            "thresholds": {
                "owner": OWNER,
                "annual_slo_percent": self.thresholds.annual_slo_percent,
                "annual_error_budget_minutes": self.thresholds.annual_error_budget_minutes,
            },
        }

    def export_state(self) -> dict[str, Any]:
        return {
            "last_sample_id": self._last_sample_id,
            "last_sample_at_utc": _utc_iso(self._last_sample_at),
            "lifecycles": {
                rule_id: {
                    key: _utc_iso(value) if isinstance(value, datetime) else value
                    for key, value in vars(lifecycle).items()
                }
                for rule_id, lifecycle in self._lifecycles.items()
            },
        }

    def import_state(self, state: Mapping[str, Any]) -> None:
        self._last_sample_id = state.get("last_sample_id") if isinstance(state.get("last_sample_id"), str) else None
        self._last_sample_at = _parse_utc(state.get("last_sample_at_utc"))
        lifecycles = state.get("lifecycles")
        if not isinstance(lifecycles, Mapping):
            return
        datetime_fields = {
            "first_observed_at", "fired_at", "resolved_at", "warning_since", "critical_since", "last_recovery_at"
        }
        for rule_id, payload in lifecycles.items():
            if not isinstance(rule_id, str) or not isinstance(payload, Mapping):
                continue
            values = {
                key: _parse_utc(value) if key in datetime_fields else value
                for key, value in payload.items()
                if key in _AlertLifecycle.__dataclass_fields__
            }
            self._lifecycles[rule_id] = _AlertLifecycle(**values)


async def _dependency_snapshot(db: AsyncSession) -> dict[str, dict[str, Any]]:
    settings = get_settings()
    result: dict[str, dict[str, Any]] = {}
    try:
        await db.execute(text("SELECT 1"))
        result["database"] = {"status": "ok"}
    except Exception as exc:
        result["database"] = {"status": "fail", "error_type": type(exc).__name__}

    if not settings.redis_enabled:
        result["redis"] = {"status": "disabled"}
    elif not redis_service or not redis_service.is_available or getattr(redis_service, "_pool", None) is None:
        result["redis"] = {"status": "fail"}
    else:
        try:
            await redis_service._pool.ping()
            result["redis"] = {"status": "ok"}
        except Exception as exc:
            result["redis"] = {"status": "fail", "error_type": type(exc).__name__}

    if not settings.mqtt_enabled:
        result["mqtt"] = {"status": "disabled"}
    elif mqtt_service.is_connected:
        result["mqtt"] = {"status": "ok"}
    elif mqtt_service._running:
        result["mqtt"] = {"status": "fail"}
    else:
        result["mqtt"] = {"status": "unknown"}
    result["websocket"] = {"status": "ok", "connections": ws_manager.total_connections}
    return result


async def _gateway_backlog(db: AsyncSession, *, now: datetime) -> dict[str, Any]:
    result = {
        "available": True,
        "enabled_gateways": 0,
        "enabled_datasources": 0,
        "warning_datasources": 0,
        "critical_datasources": 0,
        "stale_gateways": 0,
        "offline_gateways": 0,
        "future_gateways": 0,
        "max_cpu_percent": None,
        "max_memory_percent": None,
        "max_disk_usage_percent": None,
    }
    try:
        gateway_rows = (await db.execute(select(Gateway).where(Gateway.is_enabled.is_(True)))).scalars().all()
        datasource_rows = (await db.execute(select(DataSource).where(DataSource.is_enabled.is_(True)))).scalars().all()
    except Exception as exc:
        return {**result, "available": False, "error_type": type(exc).__name__}

    result["enabled_gateways"] = len(gateway_rows)
    result["enabled_datasources"] = len(datasource_rows)
    for gateway in gateway_rows:
        for result_key, value in (
            ("max_cpu_percent", gateway.cpu_usage),
            ("max_memory_percent", gateway.memory_usage),
            ("max_disk_usage_percent", gateway.disk_usage),
        ):
            numeric = _number(value)
            if numeric is not None:
                result[result_key] = max(result[result_key] or 0.0, numeric)
        if str(gateway.status).lower() == "offline":
            result["offline_gateways"] += 1
        if gateway.last_heartbeat and gateway.last_heartbeat.tzinfo is None:
            heartbeat = gateway.last_heartbeat.replace(tzinfo=UTC)
        else:
            heartbeat = gateway.last_heartbeat
        heartbeat_age = (now - heartbeat.astimezone(UTC)).total_seconds() if heartbeat is not None else None
        if heartbeat_age is not None and heartbeat_age < -30:
            result["future_gateways"] += 1
            result["stale_gateways"] += 1
        elif heartbeat_age is None or heartbeat_age > D39_03.gateway_heartbeat_critical_seconds:
            result["stale_gateways"] += 1

    for datasource in datasource_rows:
        failures = int(datasource.consecutive_failures or 0)
        if failures >= int(datasource.retry_max_failures or 0) > 0 or str(datasource.status) in {"interrupted", "device_offline", "gateway_offline"}:
            result["critical_datasources"] += 1
        elif failures >= D39_03.gateway_warning_failures:
            result["warning_datasources"] += 1
    return result


def _system_resources() -> dict[str, Any]:
    resources: dict[str, Any] = {"cpu_percent": None, "memory_percent": None, "disk_usage_percent": None}
    try:
        import psutil

        process = psutil.Process()
        resources["cpu_percent"] = _number(process.cpu_percent())
        resources["memory_percent"] = _number(process.memory_percent())
    except (ImportError, OSError):
        pass
    try:
        total, used, _ = shutil.disk_usage(Path.cwd())
        resources["disk_usage_percent"] = round(used / total * 100, 2) if total else None
    except OSError:
        pass
    return resources


async def collect_observability_snapshot(
    db: AsyncSession,
    *,
    status_dir: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _utc_now()
    metrics = await metrics_collector.get_metrics()
    metrics.setdefault("system", {}).update(_system_resources())
    dependencies = await _dependency_snapshot(db)
    gateway_backlog = await _gateway_backlog(db, now=current)
    for key, resource_key in (("cpu_percent", "max_cpu_percent"), ("memory_percent", "max_memory_percent"), ("disk_usage_percent", "max_disk_usage_percent")):
        gateway_value = gateway_backlog.get(resource_key)
        if gateway_value is not None:
            metrics["system"][key] = max(metrics["system"].get(key) or 0.0, gateway_value)
    backup = read_backup_status(status_dir, now=current)
    snapshot: dict[str, Any] = {
        "captured_at_utc": _utc_iso(current),
        "metrics": metrics,
        "dependencies": dependencies,
        "backup": backup,
        "gateway_backlog": gateway_backlog,
        "availability": {
            "annual_slo_percent": D39_03.annual_slo_percent,
            "annual_error_budget_minutes": D39_03.annual_error_budget_minutes,
            "annual_slo_proven": False,
        },
    }
    return snapshot


class ObservabilityMonitor:
    """Single-process persistent sampler; HTTP readers never advance alert state."""

    def __init__(
        self,
        *,
        state_path: str | os.PathLike[str] | None = None,
        evaluator: AlertEvaluator | None = None,
    ) -> None:
        self.state_path = Path(
            state_path or os.getenv("OBSERVABILITY_STATE_PATH", "./artifacts/observability-state.json")
        )
        self.evaluator = evaluator or AlertEvaluator()
        self._snapshot: dict[str, Any] = {
            "captured_at_utc": None,
            "status": "unknown",
            "alerts": {},
            "active_alerts": [],
            "alert_evaluation": {"status": "unknown", "alerts": {}, "sample_accepted": False},
        }
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        if not self.state_path.is_file() or self.state_path.is_symlink():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        if not isinstance(payload, Mapping):
            return
        snapshot = payload.get("snapshot")
        evaluator_state = payload.get("evaluator")
        if isinstance(snapshot, Mapping):
            self._snapshot = dict(snapshot)
        if isinstance(evaluator_state, Mapping):
            self.evaluator.import_state(evaluator_state)

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        payload = {"snapshot": self._snapshot, "evaluator": self.evaluator.export_state()}
        temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.state_path)

    async def record_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        now: datetime | None = None,
        sample_id: str | None = None,
    ) -> dict[str, Any]:
        current = now or _utc_now()
        effective_sample_id = sample_id or _utc_iso(current)
        async with self._lock:
            evaluation = self.evaluator.evaluate(
                snapshot,
                now=current,
                sample_id=effective_sample_id,
            )
            if evaluation["sample_accepted"]:
                combined = dict(snapshot)
                combined.update(
                    {
                        "alerts": evaluation["alerts"],
                        "active_alerts": evaluation["active_alerts"],
                        "status": evaluation["status"],
                        "alert_evaluation": evaluation,
                    }
                )
                self._snapshot = combined
                self._persist()
            return dict(self._snapshot)

    async def get_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return json.loads(json.dumps(self._snapshot))


observability_monitor = ObservabilityMonitor()


async def run_observability_monitor(
    session_factory,
    *,
    interval_seconds: int = 30,
    monitor: ObservabilityMonitor = observability_monitor,
) -> None:
    while True:
        started_at = _utc_now()
        try:
            async with session_factory() as db:
                snapshot = await collect_observability_snapshot(db, now=started_at)
            await monitor.record_snapshot(
                snapshot,
                now=started_at,
                sample_id=_utc_iso(started_at),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            failure_snapshot = {
                "captured_at_utc": _utc_iso(started_at),
                "metrics": {},
                "dependencies": {},
                "backup": {"available": False, "status": "unavailable"},
                "gateway_backlog": {"available": False},
                "availability": {
                    "annual_slo_percent": D39_03.annual_slo_percent,
                    "annual_error_budget_minutes": D39_03.annual_error_budget_minutes,
                    "annual_slo_proven": False,
                },
            }
            await monitor.record_snapshot(
                failure_snapshot,
                now=started_at,
                sample_id=_utc_iso(started_at),
            )
        elapsed = (_utc_now() - started_at).total_seconds()
        await asyncio.sleep(max(0.0, interval_seconds - elapsed))
