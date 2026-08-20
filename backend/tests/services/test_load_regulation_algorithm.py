from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.energy import LoadRegulationConfig, PowerDevice
from app.models.point import Point, PointRealtime
from app.services.device_control_service import ControlAction, ControlInterface, ControlResult
from app.services.load_regulation import LoadRegulationService


async def _create_config(async_db, *, point_source: str | None = None, is_auto: bool = False):
    point_id = None
    if point_source is not None:
        point = Point(
            point_code=f"REG-POWER-{point_source}-{datetime.now().timestamp()}",
            point_name="调节算法功率",
            point_type="AI",
            unit="kW",
            is_enabled=True,
        )
        async_db.add(point)
        await async_db.flush()
        point_id = point.id
        async_db.add(
            PointRealtime(
                point_id=point.id,
                value=40.0,
                quality=0,
                status="normal",
                source=point_source,
                updated_at=datetime.now(),
            )
        )

    device = PowerDevice(
        device_code=f"REG-DEVICE-{datetime.now().timestamp()}",
        device_name="调节算法空调",
        device_type="HVAC",
        rated_power=50.0,
        power_point_id=point_id,
        is_enabled=True,
    )
    async_db.add(device)
    await async_db.flush()
    config = LoadRegulationConfig(
        device_id=device.id,
        regulation_type="temperature",
        min_value=20.0,
        max_value=28.0,
        current_value=24.0,
        default_value=24.0,
        step_size=0.5,
        unit="°C",
        power_factor=-3.0,
        base_power=50.0,
        power_curve=[
            {"value": 24.0, "power_ratio": 0.8},
            {"value": 26.0, "power_ratio": 0.6},
            {"value": 28.0, "power_ratio": 0.5},
        ],
        is_enabled=True,
        is_auto=is_auto,
    )
    async_db.add(config)
    await async_db.commit()
    return device, config


@pytest.mark.asyncio
async def test_simulation_uses_realtime_power_and_curve(async_db):
    _, config = await _create_config(async_db, point_source="mqtt")

    result = await LoadRegulationService(async_db).simulate_regulation(config.id, 26.0)

    assert result is not None
    assert result.data_sufficient is True
    assert result.current_power == pytest.approx(40.0)
    assert result.estimated_power == pytest.approx(30.0)
    assert result.power_change == pytest.approx(-10.0)
    assert result.calculation_method == "实时功率×功率曲线插值"


@pytest.mark.asyncio
async def test_simulation_rejects_demo_power_as_measured_evidence(async_db):
    _, config = await _create_config(async_db, point_source="demo")

    result = await LoadRegulationService(async_db).simulate_regulation(config.id, 26.0)

    assert result is not None
    assert result.data_sufficient is False
    assert result.current_power is None
    assert result.estimated_power is None
    assert result.power_change is None
    assert "不能作为真实节能量依据" in (result.warning or "")


@pytest.mark.asyncio
async def test_recommendation_has_no_fake_saving_without_measured_power(async_db):
    _, config = await _create_config(async_db)

    recommendations = await LoadRegulationService(async_db).get_recommendations()
    recommendation = next(item for item in recommendations if item.config_id == config.id)

    assert recommendation.data_sufficient is False
    assert recommendation.power_saving is None
    assert "待实时功率接入后评估" in recommendation.reason


@pytest.mark.asyncio
async def test_apply_pending_does_not_update_current_value_or_claim_saving(async_db):
    device, config = await _create_config(async_db, point_source="mqtt")
    action = ControlAction(
        device_id=device.id,
        device_name=device.device_name,
        action_type="temperature",
        current_value=24.0,
        target_value=26.0,
        unit="°C",
        interface=ControlInterface.MANUAL,
        result=ControlResult.PENDING,
        message="需要人工操作",
        executed_at=datetime.now(),
    )

    with patch(
        "app.services.load_regulation.DeviceControlService.control_device_regulation",
        new_callable=AsyncMock,
        return_value=action,
    ):
        result = await LoadRegulationService(async_db).apply_regulation(config.id, 26.0)

    await async_db.refresh(config)
    assert result is not None
    assert result.status == "pending"
    assert result.power_saved is None
    assert config.current_value == pytest.approx(24.0)


@pytest.mark.asyncio
async def test_apply_uses_requested_config_when_device_type_has_duplicates(async_db):
    device, config = await _create_config(async_db, point_source="mqtt")
    duplicate = LoadRegulationConfig(
        device_id=device.id,
        regulation_type=config.regulation_type,
        min_value=20.0,
        max_value=24.0,
        current_value=22.0,
        default_value=22.0,
        step_size=0.5,
        unit="°C",
        power_factor=-1.0,
        base_power=50.0,
        is_enabled=True,
        is_auto=False,
    )
    async_db.add(duplicate)
    await async_db.commit()

    result = await LoadRegulationService(async_db).apply_regulation(config.id, 26.0)

    assert result is not None
    assert result.config_id == config.id
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_simulation_validates_range_and_step(async_db):
    _, config = await _create_config(async_db, point_source="mqtt")
    service = LoadRegulationService(async_db)

    with pytest.raises(ValueError, match="范围内"):
        await service.simulate_regulation(config.id, 29.0)
    with pytest.raises(ValueError, match="步长"):
        await service.simulate_regulation(config.id, 25.2)
