from app.services.drift_detection import _generate_resolved_diagnosis


def test_auto_resolved_diagnosis_matches_current_deviation():
    diagnosis = _generate_resolved_diagnosis(0.47, automatic=True)

    assert "0.5σ" in diagnosis
    assert "自动解除" in diagnosis
    assert "持续偏离" not in diagnosis


def test_manual_resolved_diagnosis_does_not_claim_automatic_recovery():
    diagnosis = _generate_resolved_diagnosis(3.2, automatic=False)

    assert "人工解除" in diagnosis
    assert "自动解除" not in diagnosis
