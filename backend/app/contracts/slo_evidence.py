"""Pure SLO and MTTR calculations shared by runtime tests and evidence validation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any, Iterable, Mapping

from .observability import D39_03


UTC = timezone.utc


class EvidenceValidationError(ValueError):
    """Raised when raw SLO evidence is malformed or internally inconsistent."""


def parse_utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceValidationError(f"{field_name} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceValidationError(f"{field_name} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvidenceValidationError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _finite_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise EvidenceValidationError(f"{field_name} must be a finite number")
    return float(value)


def _display_number(value: float, digits: int = 4) -> int | float:
    rounded = round(value, digits)
    return int(rounded) if rounded.is_integer() else rounded


def _approved_maintenance_windows(
    maintenance_windows: Iterable[Mapping[str, Any]] | None,
) -> dict[str, tuple[datetime, datetime]]:
    approved: dict[str, tuple[datetime, datetime]] = {}
    for index, window in enumerate(maintenance_windows or ()):
        maintenance_id = window.get("maintenance_id")
        if not isinstance(maintenance_id, str) or not maintenance_id.strip() or maintenance_id in approved:
            continue
        if window.get("subject") != "service":
            continue
        if not all(isinstance(window.get(field), str) and window[field].strip() for field in ("approved_by", "change_id")):
            continue
        try:
            approved_at = parse_utc(window.get("approved_at_utc"), f"maintenance_windows[{index}].approved_at_utc")
            started_at = parse_utc(window.get("started_at_utc"), f"maintenance_windows[{index}].started_at_utc")
            ended_at = parse_utc(window.get("ended_at_utc"), f"maintenance_windows[{index}].ended_at_utc")
        except EvidenceValidationError:
            continue
        if approved_at < started_at < ended_at:
            approved[maintenance_id] = (started_at, ended_at)
    return approved


def calculate_availability(
    samples: Iterable[Mapping[str, Any]],
    *,
    maintenance_windows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    total_minutes = 0.0
    excluded_minutes = 0.0
    eligible_minutes = 0.0
    good_minutes = 0.0
    missing_minutes = 0.0
    previous_timestamp: datetime | None = None
    approved_maintenance = _approved_maintenance_windows(maintenance_windows)

    for index, sample in enumerate(samples):
        timestamp = parse_utc(sample.get("timestamp_utc"), f"samples[{index}].timestamp_utc")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise EvidenceValidationError("availability sample timestamps must be strictly increasing")
        previous_timestamp = timestamp
        duration_seconds = _finite_number(sample.get("duration_seconds", 60), f"samples[{index}].duration_seconds")
        if duration_seconds <= 0:
            raise EvidenceValidationError("availability sample duration must be positive")
        minutes = duration_seconds / 60
        total_minutes += minutes

        excluded = False
        maintenance_id = sample.get("maintenance_id")
        if isinstance(maintenance_id, str) and maintenance_id in approved_maintenance:
            maintenance_start, maintenance_end = approved_maintenance[maintenance_id]
            sample_end = timestamp + timedelta(seconds=duration_seconds)
            excluded = maintenance_start <= timestamp and sample_end <= maintenance_end
        if excluded:
            excluded_minutes += minutes
            continue

        eligible_minutes += minutes
        telemetry_present = sample.get("telemetry_present") is True
        if not telemetry_present:
            missing_minutes += minutes
        if telemetry_present and sample.get("readiness_passed") is True and sample.get("critical_e2e_passed") is True:
            good_minutes += minutes

    bad_minutes = eligible_minutes - good_minutes
    availability = good_minutes / eligible_minutes * 100 if eligible_minutes else 0.0
    budget_fraction = (100 - D39_03.annual_slo_percent) / 100
    window_budget = eligible_minutes * budget_fraction
    consumed_percent = bad_minutes / window_budget * 100 if window_budget else 0.0
    return {
        "total_minutes": _display_number(total_minutes),
        "excluded_minutes": _display_number(excluded_minutes),
        "eligible_minutes": _display_number(eligible_minutes),
        "good_minutes": _display_number(good_minutes),
        "bad_minutes": _display_number(bad_minutes),
        "missing_minutes": _display_number(missing_minutes),
        "observed_availability_percent": round(availability, 4),
        "slo_target_percent": D39_03.annual_slo_percent,
        "window_error_budget_minutes": round(window_budget, 4),
        "error_budget_consumed_percent": round(consumed_percent, 4),
        "annual_error_budget_minutes": D39_03.annual_error_budget_minutes,
        "provisional_annual_budget_remaining_minutes": round(
            max(0.0, D39_03.annual_error_budget_minutes - bad_minutes), 4
        ),
        "annual_slo_proven": False,
    }


def calculate_mttr(incidents: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    resolved_durations: list[float] = []
    incident_ids: set[str] = set()

    for incident_index, incident in enumerate(incidents):
        incident_id = incident.get("incident_id")
        if not isinstance(incident_id, str) or not incident_id.strip():
            raise EvidenceValidationError(f"incidents[{incident_index}].incident_id is required")
        if incident_id in incident_ids:
            raise EvidenceValidationError(f"duplicate incident_id: {incident_id}")
        incident_ids.add(incident_id)
        if incident.get("severity") != "critical":
            raise EvidenceValidationError(f"incident {incident_id} is not critical")

        fired_at = parse_utc(incident.get("alert_fired_at_utc"), f"incident {incident_id}.alert_fired_at_utc")
        fired_monotonic = _finite_number(
            incident.get("alert_fired_monotonic_seconds"), f"incident {incident_id}.alert_fired_monotonic_seconds"
        )
        checks = incident.get("recovery_checks")
        if not isinstance(checks, list):
            raise EvidenceValidationError(f"incident {incident_id}.recovery_checks must be a list")

        previous_timestamp = fired_at
        previous_monotonic = fired_monotonic
        consecutive = 0
        resolved_at: datetime | None = None
        resolved_monotonic: float | None = None
        for check_index, check in enumerate(checks):
            if not isinstance(check, Mapping):
                raise EvidenceValidationError(f"incident {incident_id} recovery check must be an object")
            timestamp = parse_utc(
                check.get("timestamp_utc"), f"incident {incident_id}.recovery_checks[{check_index}].timestamp_utc"
            )
            monotonic = _finite_number(
                check.get("monotonic_seconds"),
                f"incident {incident_id}.recovery_checks[{check_index}].monotonic_seconds",
            )
            if timestamp <= previous_timestamp:
                raise EvidenceValidationError(f"incident {incident_id} recovery timestamps must be strictly increasing")
            if monotonic <= previous_monotonic:
                raise EvidenceValidationError(f"incident {incident_id} monotonic time must be strictly increasing")
            if (timestamp - previous_timestamp).total_seconds() < 30 or monotonic - previous_monotonic < 30:
                raise EvidenceValidationError(
                    f"incident {incident_id} recovery evaluations must be at least 30 seconds apart"
                )
            previous_timestamp = timestamp
            previous_monotonic = monotonic
            if check.get("readiness_passed") is True and check.get("critical_e2e_passed") is True:
                consecutive += 1
            else:
                consecutive = 0
            if consecutive == D39_03.recovery_evaluations:
                resolved_at = timestamp
                resolved_monotonic = monotonic
                break

        mttr_seconds: float | None = None
        if resolved_at is not None and resolved_monotonic is not None:
            mttr_seconds = resolved_monotonic - fired_monotonic
            utc_duration = (resolved_at - fired_at).total_seconds()
            if abs(mttr_seconds - utc_duration) > 5:
                raise EvidenceValidationError(f"incident {incident_id} UTC and monotonic durations disagree")
            resolved_durations.append(mttr_seconds)
        results.append(
            {
                "incident_id": incident_id,
                "alert_fired_at_utc": fired_at.isoformat().replace("+00:00", "Z"),
                "resolved_at_utc": resolved_at.isoformat().replace("+00:00", "Z") if resolved_at else None,
                "recovery_confirmation_count": D39_03.recovery_evaluations if resolved_at else consecutive,
                "mttr_seconds": mttr_seconds,
                "status": "resolved" if resolved_at else "unresolved",
            }
        )

    return {
        "incident_count": len(results),
        "resolved_incidents": len(resolved_durations),
        "unresolved_incidents": len(results) - len(resolved_durations),
        "mean_mttr_seconds": round(fmean(resolved_durations), 3) if resolved_durations else None,
        "incidents": results,
    }
