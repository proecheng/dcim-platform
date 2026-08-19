from datetime import datetime, timedelta, timezone

import pytest

from app.services.slo_evidence import EvidenceValidationError, calculate_availability, calculate_mttr


UTC = timezone.utc


def _timestamp(minute: int) -> str:
    return (datetime(2026, 8, 18, tzinfo=UTC) + timedelta(minutes=minute)).isoformat().replace("+00:00", "Z")


def test_availability_counts_missing_telemetry_as_bad_and_only_preapproved_maintenance_is_excluded():
    samples = [
        {"timestamp_utc": _timestamp(0), "readiness_passed": True, "critical_e2e_passed": True, "telemetry_present": True},
        {"timestamp_utc": _timestamp(1), "readiness_passed": True, "critical_e2e_passed": True, "telemetry_present": True},
        {"timestamp_utc": _timestamp(2), "readiness_passed": True, "critical_e2e_passed": True, "telemetry_present": True},
        {"timestamp_utc": _timestamp(3), "readiness_passed": False, "critical_e2e_passed": True, "telemetry_present": True},
        {"timestamp_utc": _timestamp(4), "readiness_passed": False, "critical_e2e_passed": False, "telemetry_present": False},
        {
            "timestamp_utc": _timestamp(5),
            "readiness_passed": False,
            "critical_e2e_passed": False,
            "telemetry_present": True,
            "maintenance_id": "MW-1",
        },
    ]
    maintenance_windows = [{
        "maintenance_id": "MW-1",
        "subject": "service",
        "approved_at_utc": _timestamp(-1),
        "started_at_utc": _timestamp(5),
        "ended_at_utc": _timestamp(6),
        "approved_by": "change-manager",
        "change_id": "CHG-1",
    }]

    result = calculate_availability(samples, maintenance_windows=maintenance_windows)

    assert result["total_minutes"] == 6
    assert result["excluded_minutes"] == 1
    assert result["eligible_minutes"] == 5
    assert result["good_minutes"] == 3
    assert result["bad_minutes"] == 2
    assert result["missing_minutes"] == 1
    assert result["observed_availability_percent"] == 60.0
    assert result["window_error_budget_minutes"] == 0.025
    assert result["error_budget_consumed_percent"] == 8000.0
    assert result["annual_error_budget_minutes"] == 2628
    assert result["annual_slo_proven"] is False


def test_unapproved_or_late_maintenance_cannot_remove_bad_time():
    sample = {
        "timestamp_utc": _timestamp(1),
        "readiness_passed": False,
        "critical_e2e_passed": False,
        "telemetry_present": True,
        "maintenance_id": "MW-LATE",
    }
    maintenance_windows = [{
        "maintenance_id": "MW-LATE",
        "subject": "service",
        "approved_at_utc": _timestamp(2),
        "started_at_utc": _timestamp(1),
        "ended_at_utc": _timestamp(2),
        "approved_by": "change-manager",
        "change_id": "CHG-2",
    }]
    result = calculate_availability([sample], maintenance_windows=maintenance_windows)
    assert result["excluded_minutes"] == 0
    assert result["bad_minutes"] == 1


def test_self_reported_maintenance_flags_are_not_trusted():
    sample = {
        "timestamp_utc": _timestamp(1),
        "readiness_passed": False,
        "critical_e2e_passed": False,
        "telemetry_present": True,
        "maintenance_excluded": True,
        "maintenance_approved_at_utc": _timestamp(-1),
    }
    result = calculate_availability([sample])
    assert result["excluded_minutes"] == 0
    assert result["bad_minutes"] == 1


def test_availability_rejects_duplicate_or_reversed_timestamps():
    duplicate = [
        {"timestamp_utc": _timestamp(0), "readiness_passed": True, "critical_e2e_passed": True, "telemetry_present": True},
        {"timestamp_utc": _timestamp(0), "readiness_passed": True, "critical_e2e_passed": True, "telemetry_present": True},
    ]
    with pytest.raises(EvidenceValidationError, match="strictly increasing"):
        calculate_availability(duplicate)


def test_mttr_starts_at_alert_and_requires_three_consecutive_joint_recoveries():
    incidents = [
        {
            "incident_id": "INC-1",
            "severity": "critical",
            "alert_fired_at_utc": _timestamp(0),
            "alert_fired_monotonic_seconds": 100.0,
            "recovery_checks": [
                {"timestamp_utc": _timestamp(1), "monotonic_seconds": 160.0, "readiness_passed": True, "critical_e2e_passed": True},
                {"timestamp_utc": _timestamp(2), "monotonic_seconds": 220.0, "readiness_passed": False, "critical_e2e_passed": True},
                {"timestamp_utc": _timestamp(3), "monotonic_seconds": 280.0, "readiness_passed": True, "critical_e2e_passed": True},
                {"timestamp_utc": _timestamp(4), "monotonic_seconds": 340.0, "readiness_passed": True, "critical_e2e_passed": True},
                {"timestamp_utc": _timestamp(5), "monotonic_seconds": 400.0, "readiness_passed": True, "critical_e2e_passed": True},
            ],
        }
    ]

    result = calculate_mttr(incidents)

    assert result["resolved_incidents"] == 1
    assert result["unresolved_incidents"] == 0
    assert result["mean_mttr_seconds"] == 300.0
    assert result["incidents"][0]["resolved_at_utc"] == _timestamp(5)
    assert result["incidents"][0]["recovery_confirmation_count"] == 3


def test_mttr_keeps_unresolved_incidents_open_and_rejects_reversed_monotonic_time():
    unresolved = {
        "incident_id": "INC-2",
        "severity": "critical",
        "alert_fired_at_utc": _timestamp(0),
        "alert_fired_monotonic_seconds": 100.0,
        "recovery_checks": [
            {"timestamp_utc": _timestamp(1), "monotonic_seconds": 160.0, "readiness_passed": True, "critical_e2e_passed": True}
        ],
    }
    result = calculate_mttr([unresolved])
    assert result["resolved_incidents"] == 0
    assert result["unresolved_incidents"] == 1
    assert result["mean_mttr_seconds"] is None

    invalid = {**unresolved, "recovery_checks": [{"timestamp_utc": _timestamp(1), "monotonic_seconds": 99.0, "readiness_passed": True, "critical_e2e_passed": True}]}
    with pytest.raises(EvidenceValidationError, match="monotonic"):
        calculate_mttr([invalid])


def test_mttr_rejects_recovery_checks_less_than_thirty_seconds_apart():
    incident = {
        "incident_id": "INC-FAST",
        "severity": "critical",
        "alert_fired_at_utc": _timestamp(0),
        "alert_fired_monotonic_seconds": 100.0,
        "recovery_checks": [
            {
                "timestamp_utc": (datetime(2026, 8, 18, tzinfo=UTC) + timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
                "monotonic_seconds": 110.0,
                "readiness_passed": True,
                "critical_e2e_passed": True,
            }
        ],
    }
    with pytest.raises(EvidenceValidationError, match="30 seconds"):
        calculate_mttr([incident])
