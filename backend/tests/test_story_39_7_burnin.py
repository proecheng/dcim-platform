import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.story_39_7_burnin import (  # noqa: E402
    E2E_OFFSETS_SECONDS,
    BurnInError,
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
