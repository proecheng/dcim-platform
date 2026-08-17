from datetime import datetime

import pytest

from app.services.analysis_plugins.base import AnalysisContext, DeviceData, PowerData
from app.services.analysis_plugins.equipment_efficiency import EquipmentEfficiencyPlugin
from app.services.analysis_plugins.power_factor import PowerFactorPlugin


@pytest.mark.anyio
async def test_power_factor_zero_benefit_has_no_payback_period():
    context = AnalysisContext(
        power_data=[
            PowerData(
                timestamp=datetime.now(),
                device_id="ups-1",
                device_name="UPS 1",
                device_type="UPS",
                voltage=380,
                current=100,
                active_power=50,
                reactive_power=20,
                apparent_power=55,
                power_factor=0.93,
                frequency=50,
                load_rate=50,
            )
        ]
    )

    results = await PowerFactorPlugin().analyze(context)

    assert results
    assert results[0].estimated_cost_saving == 0
    assert results[0].payback_period is None
    assert "无法估算" in results[0].detail


@pytest.mark.anyio
async def test_equipment_efficiency_skips_devices_without_observed_load():
    context = AnalysisContext(
        device_data=[
            DeviceData(
                device_id="ups-1",
                device_name="UPS 1",
                device_type="UPS",
                rated_power=100,
                current_power=0,
                efficiency=95,
                running_hours=100,
                location="A1",
            )
        ]
    )

    results = await EquipmentEfficiencyPlugin().analyze(context)

    assert results == []
