from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.load_shift import FeasibilityAnalysisRequest, ShiftPeriodType
from app.services.load_shift.algorithms.benefit_calculator import BenefitCalculator


@pytest.mark.asyncio
async def test_calculate_benefits_uses_normalized_period_price_rows():
    calculator = BenefitCalculator(None)
    calculator._load_devices = AsyncMock(return_value=[SimpleNamespace(rated_power=50.0)])
    calculator._load_pricing = AsyncMock(
        return_value={
            ShiftPeriodType.SHARP: 1.2,
            ShiftPeriodType.VALLEY: 0.3,
        }
    )
    request = FeasibilityAnalysisRequest(
        shift_date=date.today(),
        shift_from_period=ShiftPeriodType.SHARP,
        shift_to_period=ShiftPeriodType.VALLEY,
        target_shift_power=50.0,
        selected_devices=[],
    )

    result = await calculator.calculate_benefits(request, [])

    assert result.cost_saving == pytest.approx(45.0)
    assert result.benefit_details["from_period_price"] == pytest.approx(1.2)
    assert result.benefit_details["to_period_price"] == pytest.approx(0.3)
