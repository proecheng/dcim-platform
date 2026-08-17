from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.vpp_calculator import VPPCalculator


def _result_with_scalars(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.mark.anyio
async def test_transfer_potential_does_not_invent_missing_prices():
    db = AsyncMock()
    empty_loads = _result_with_scalars([])
    empty_prices = _result_with_scalars([])
    empty_config = MagicMock()
    empty_config.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(side_effect=[empty_loads, empty_prices, empty_config])

    result = await VPPCalculator(db).calc_transfer_potential()

    assert result["transferable_load"]["value"] == 0
    assert result["price_spread"]["value"] is None
    assert result["annual_transfer_benefit"]["value"] is None
    assert result["data_source"]["price_data_sufficient"] is False


@pytest.mark.anyio
async def test_zero_benefit_has_no_payback_period_or_default_investment():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result_with_scalars([]))

    result = await VPPCalculator(db).calc_roi(0)

    assert result["total_investment"]["value"] is None
    assert result["payback_period"]["value"] is None
    assert result["roi"]["value"] is None


@pytest.mark.anyio
async def test_full_analysis_reports_missing_inputs_instead_of_zero_conclusions():
    calculator = VPPCalculator(AsyncMock())
    calculator.calc_load_metrics = AsyncMock(
        return_value={"error": "无负荷数据", "data_source": {"data_points": 0}}
    )
    calculator.calc_transfer_potential = AsyncMock(
        return_value={
            "transferable_load": {"value": 0},
            "annual_transfer_benefit": {"value": None},
            "data_source": {"adjustable_loads_count": 0, "price_data_sufficient": False},
        }
    )
    calculator.calc_demand_optimization = AsyncMock(
        return_value={"demand_optimization_benefit": {"value": None}}
    )
    calculator.calc_vpp_revenue = AsyncMock(return_value={"total_vpp_revenue": {"value": 0}})
    calculator.calc_roi = AsyncMock(
        return_value={
            "total_investment": {"value": None},
            "payback_period": {"value": None},
            "roi": {"value": None},
        }
    )
    calculator.calc_cost_structure = AsyncMock(return_value={"error": "无电费数据"})
    calculator.calc_average_price = AsyncMock(return_value={"value": None})
    calculator.calc_fluctuation_rate = AsyncMock(return_value={"value": None})
    calculator.calc_peak_ratio = AsyncMock(return_value={"value": None})
    calculator.calc_valley_ratio = AsyncMock(return_value={"value": None})

    result = await calculator.generate_full_analysis(
        ["2026-08"],
        __import__("datetime").date(2026, 8, 1),
        __import__("datetime").date(2026, 8, 16),
    )

    assert result["data_sufficient"] is False
    assert result["summary"]["annual_total_benefit"]["value"] is None
    assert "所选日期范围无负荷曲线" in result["warnings"]
    assert "缺少峰、谷电价配置" in result["warnings"]
