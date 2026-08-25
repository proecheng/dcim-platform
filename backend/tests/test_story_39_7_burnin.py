import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import scripts.story_39_7_burnin as burnin_module  # noqa: E402
from scripts.story_39_7_burnin import (  # noqa: E402
    E2E_OFFSETS_SECONDS,
    BurnInError,
    BurnInRunner,
    _parse_fleet_test,
    _playwright_summary,
)


UTC = timezone.utc


def _playwright_report(*, skipped=0, unexpected=0, flaky=0, retry=0):
    return {
        "stats": {
            "startTime": "2026-08-22T10:00:00.000Z",
            "duration": 1000,
            "expected": 1,
            "skipped": skipped,
            "unexpected": unexpected,
            "flaky": flaky,
        },
        "suites": [{"specs": [{"tests": [{"results": [{"status": "passed", "retry": retry}]}]}]}],
    }


def test_absolute_e2e_schedule_has_12_runs_spanning_72_hours():
    assert len(E2E_OFFSETS_SECONDS) == 12
    assert E2E_OFFSETS_SECONDS[0] == 0
    assert E2E_OFFSETS_SECONDS[-1] == 72 * 60 * 60
    assert all(
        current - previous >= 5 * 60 * 60 for previous, current in zip(E2E_OFFSETS_SECONDS, E2E_OFFSETS_SECONDS[1:])
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"skipped": 1},
        {"unexpected": 1},
        {"flaky": 1},
        {"retry": 1},
    ],
)
def test_playwright_summary_rejects_non_first_attempt_results(tmp_path, mutation):
    report_path = tmp_path / "e2e.json"
    report_path.write_text(json.dumps(_playwright_report(**mutation)), encoding="utf-8")
    assert _playwright_summary(report_path)["first_attempt_passed"] is False


def test_playwright_summary_accepts_clean_first_attempt(tmp_path):
    report_path = tmp_path / "e2e.json"
    report_path.write_text(json.dumps(_playwright_report()), encoding="utf-8")
    summary = _playwright_summary(report_path)
    assert summary["first_attempt_passed"] is True
    assert summary["maximum_retry"] == 0


def test_fleet_test_requires_unique_artifact_and_clean_playwright(tmp_path):
    artifact = tmp_path / "e2e.json"
    artifact.write_text(json.dumps(_playwright_report()), encoding="utf-8")
    report = {
        "summary": {"failed": 0},
        "results": [{"checks": [{"name": "critical_e2e", "artifact": str(artifact)}]}],
    }
    parsed_artifact, summary = _parse_fleet_test(json.dumps(report))
    assert parsed_artifact == artifact.resolve()
    assert summary["first_attempt_passed"] is True


def test_fleet_test_rejects_failed_target():
    with pytest.raises(BurnInError, match="failed target"):
        _parse_fleet_test(json.dumps({"summary": {"failed": 1}, "results": []}))


def test_test_clock_is_timezone_aware():
    assert datetime.now(UTC).utcoffset() is not None


def _runner_without_initialization():
    runner = object.__new__(BurnInRunner)
    runner.target = SimpleNamespace(
        docker_context="desktop-linux",
        project_name="test-project",
        env_file=Path("test.env"),
        compose_file=Path("compose.yml"),
    )
    return runner


def test_wait_for_service_health_handles_starting_then_healthy(monkeypatch):
    runner = _runner_without_initialization()
    states = iter(("starting", "healthy"))

    def fake_run(*_args, **_kwargs):
        health = next(states)
        return SimpleNamespace(stdout=json.dumps({"Service": "redis", "State": "running", "Health": health}))

    monkeypatch.setattr(burnin_module, "_run", fake_run)
    monkeypatch.setattr(burnin_module.time, "sleep", lambda _seconds: None)

    runner._wait_for_service_health("redis", 30)


def test_incident_drill_keeps_controlled_outage_active_through_recovery(monkeypatch):
    runner = _runner_without_initialization()
    runner.incident_active = threading.Event()
    runner.e2e_lock = threading.Lock()
    runner.failure = None
    runner.failure_lock = threading.Lock()
    readiness_checks = []
    e2e_checks = []
    evidence_writes = []

    runner._login_token = lambda: "token"
    runner._wait_for_dependency_alert = lambda _token: (datetime.now(UTC), 0.0)

    def wait_for_readiness(expected, _timeout_seconds):
        readiness_checks.append(expected)
        if expected:
            assert runner.incident_active.is_set()

    runner._wait_for_readiness = wait_for_readiness
    runner._wait_for_service_health = lambda _service, _timeout: (
        runner.incident_active.is_set() or pytest.fail("incident flag cleared early")
    )

    def fleet_test():
        assert runner.incident_active.is_set()
        e2e_checks.append(True)
        now = datetime.now(UTC)
        return Path("e2e.json"), {"first_attempt_passed": True}, now, now

    runner._fleet_test = fleet_test

    class Store:
        def set_incident(self, _incident, _alert):
            assert runner.incident_active.is_set()
            evidence_writes.append(True)

    runner.store = Store()
    runner._write_state = lambda _status: runner.incident_active.is_set() or pytest.fail("incident flag cleared early")
    monkeypatch.setattr(burnin_module, "_run", lambda *_args, **_kwargs: SimpleNamespace(stdout=""))
    monkeypatch.setattr(burnin_module.time, "sleep", lambda _seconds: None)

    runner._incident_drill()

    assert runner.failure is None
    assert readiness_checks == [False, True, True, True]
    assert len(e2e_checks) == 3
    assert evidence_writes == [True]
    assert not runner.incident_active.is_set()
