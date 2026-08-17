from datetime import datetime

import pytest

from app.services.feedback_learning import FeedbackLearner
from app.services.forecasting import generate_demo_forecast
from app.services.optimizer import MILPOptimizer, PricingConfig, run_day_ahead_optimization


def test_heuristic_resolves_default_demand_target(monkeypatch):
    monkeypatch.setattr("app.services.optimizer.PULP_AVAILABLE", False)
    optimizer = MILPOptimizer(pricing=PricingConfig(declared_demand=800.0))

    result = optimizer.optimize([500.0] * 96)

    assert result["status"] == "success"
    assert result["demand_target"] == pytest.approx(800.0)


def test_demo_forecast_is_deterministic_and_labeled():
    target = datetime(2026, 8, 17)

    first = generate_demo_forecast(target)
    second = generate_demo_forecast(target)

    assert first == second
    assert first["data_source"] == "demo_scenario"
    assert first["data_sufficient"] is False
    assert "情景模拟" in first["warning"]


def test_optimization_propagates_data_source_and_default_target():
    forecast = generate_demo_forecast(datetime(2026, 8, 17))

    result = run_day_ahead_optimization(
        forecast_data=forecast,
        pricing_config={"declared_demand": 800.0, "demand_price": 40.0},
        storage_config=None,
    )

    assert result["demand_target"] == pytest.approx(800.0)
    assert result["data_source"] == "demo_scenario"
    assert result["data_sufficient"] is False
    assert result["warning"] == forecast["warning"]


def test_feedback_report_does_not_recommend_from_zero_samples():
    report = FeedbackLearner().generate_report(datetime(2026, 8, 1), datetime(2026, 8, 16))

    assert report.recommendations == [
        "暂无真实调度执行和预测反馈数据，暂不能评估成功率、需量利用率或节省达成率"
    ]
