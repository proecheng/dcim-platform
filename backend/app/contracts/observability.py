"""Story 39.7 observability thresholds without runtime dependencies."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservabilityThresholds:
    evidence_window_seconds: int = 72 * 60 * 60
    critical_e2e_runs: int = 12
    minimum_e2e_spacing_seconds: int = 5 * 60 * 60
    monitoring_gap_seconds: int = 5 * 60
    error_warning_percent: float = 0.5
    error_critical_percent: float = 1.0
    resource_warning_percent: float = 80.0
    resource_critical_percent: float = 90.0
    resource_recovery_percent: float = 75.0
    resource_sustain_seconds: int = 5 * 60
    backup_warning_age_seconds: int = 26 * 60 * 60
    backup_critical_age_seconds: int = 36 * 60 * 60
    gateway_warning_failures: int = 3
    gateway_heartbeat_critical_seconds: int = 5 * 60
    recovery_evaluations: int = 3
    annual_slo_percent: float = 99.5
    annual_error_budget_minutes: int = 2_628


D39_03 = ObservabilityThresholds()
