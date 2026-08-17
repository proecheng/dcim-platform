import pytest

from app.api.v1.proposal import calculate_default_shift_effects


def test_default_shift_effects_follow_displayed_formula():
    result = calculate_default_shift_effects(
        total_power=1199.11,
        shift_hours=2,
        source_price=1.5,
        target_price=0.4,
    )

    assert result["price_diff"] == pytest.approx(1.1)
    assert result["daily_energy"] == pytest.approx(2398.22)
    assert result["daily_saving"] == pytest.approx(2638.042)
    assert result["annual_saving"] == pytest.approx(791412.6)


def test_default_shift_effects_never_returns_negative_savings():
    result = calculate_default_shift_effects(100, 2, 0.4, 1.5)

    assert result["price_diff"] == 0
    assert result["daily_saving"] == 0
    assert result["annual_saving"] == 0
