"""Device shift-ratio recommendation tests."""

import pytest

from sqlalchemy import select

from app.models.energy import DeviceShiftConfig, LoadRegulationConfig, PowerDevice
from app.services.device_config_generator import DeviceConfigAutoGenerator
from app.services.device_regulation_service import DeviceRegulationService


@pytest.mark.asyncio
async def test_ratio_recommendations_use_cooling_subtype_and_controls(async_db):
    devices = [
        PowerDevice(
            device_code="ROW-AC-001",
            device_name="行级空调01",
            device_type="AC",
            load_subtype="row_ac",
            controllable_params=["temperature_setpoint", "fan_speed", "cooling_output"],
            rated_power=30,
            is_enabled=True,
        ),
        PowerDevice(
            device_code="CHW-AHU-001",
            device_name="冷冻水末端01",
            device_type="HVAC",
            load_subtype="chilled_water_terminal",
            controllable_params=["supply_air_temperature", "chilled_water_valve", "fan_speed"],
            rated_power=80,
            is_enabled=True,
        ),
        PowerDevice(
            device_code="TES-001",
            device_name="蓄冷罐01",
            device_type="HVAC",
            load_subtype="thermal_storage",
            controllable_params=["storage_charge", "storage_discharge", "storage_soc", "pump_frequency"],
            thermal_storage_config={
                "capacity_kwh": 2000,
                "max_discharge_kw": 800,
                "equivalent_cop": 4,
                "discharge_efficiency": 0.9,
                "usable_soc_min": 0.15,
                "usable_soc_max": 0.9,
            },
            rated_power=200,
            is_enabled=True,
        ),
    ]
    async_db.add_all(devices)
    await async_db.commit()

    result = await DeviceRegulationService(async_db).get_ratio_recommendations(days=30)
    by_code = {item["device_code"]: item for item in result["recommendations"]}

    assert by_code["ROW-AC-001"]["load_subtype"] == "row_ac"
    assert by_code["CHW-AHU-001"]["load_subtype"] == "chilled_water_terminal"
    assert by_code["TES-001"]["load_subtype"] == "thermal_storage"
    assert by_code["ROW-AC-001"]["recommended_ratio"] != by_code["CHW-AHU-001"]["recommended_ratio"]
    assert by_code["TES-001"]["recommended_ratio"] > by_code["ROW-AC-001"]["recommended_ratio"]
    assert "thermal_storage" in by_code["TES-001"]["calculation_details"]["constraints"]
    strategy = by_code["TES-001"]["calculation_details"]["cooling_strategy"]
    assert strategy["strategy_type"] == "thermal_storage"
    assert {"storage_charge", "storage_discharge"} <= {step["phase"] for step in strategy["steps"]}
    assert any("P_e" in formula["expression"] for formula in strategy["formulas"])


@pytest.mark.asyncio
async def test_thermal_storage_limit_converts_cooling_kw_to_electric_kw(async_db):
    storage = PowerDevice(
        device_code="TES-COP-001",
        device_name="蓄冷罐COP校验",
        device_type="HVAC",
        load_subtype="thermal_storage",
        controllable_params=["storage_charge", "storage_discharge", "storage_soc"],
        thermal_storage_config={
            "capacity_kwh": 1000,
            "max_discharge_kw": 400,
            "equivalent_cop": 4,
            "discharge_efficiency": 0.9,
            "auxiliary_power_kw": 10,
            "usable_soc_min": 0.1,
            "usable_soc_max": 0.9,
        },
        rated_power=200,
        is_enabled=True,
    )
    async_db.add(storage)
    await async_db.commit()

    result = await DeviceRegulationService(async_db).get_ratio_recommendations(days=30)
    rec = next(item for item in result["recommendations"] if item["device_code"] == "TES-COP-001")
    storage_constraint = rec["calculation_details"]["constraints"]["thermal_storage"]["max_ratio"]

    # min(400 kWth, 1000*0.8/2 h) * 0.9 / COP 4 - 10 kW aux = 80 kWe.
    assert storage_constraint == 0.4


@pytest.mark.asyncio
async def test_water_cooled_chiller_recommendation_includes_dispatch_steps(async_db):
    chiller = PowerDevice(
        device_code="WCH-001",
        device_name="大型水冷冷机01",
        device_type="CHILLER",
        load_subtype="water_cooled_chiller",
        controllable_params=[
            "chilled_water_supply_temperature",
            "compressor_frequency",
            "pump_frequency",
            "flow_rate",
        ],
        rated_power=500,
        is_enabled=True,
    )
    async_db.add(chiller)
    await async_db.commit()

    result = await DeviceRegulationService(async_db).get_ratio_recommendations(days=30)
    rec = next(item for item in result["recommendations"] if item["device_code"] == "WCH-001")
    strategy = rec["calculation_details"]["cooling_strategy"]

    phases = {step["phase"] for step in strategy["steps"]}
    assert "valley_charge_or_precool" in phases
    assert "peak_chw_reset" in phases
    assert "pump_vfd_reset" in phases
    assert any("DeltaP" in formula["expression"] for formula in strategy["formulas"])


@pytest.mark.asyncio
async def test_thermal_storage_config_generator_uses_storage_template(async_db):
    storage = PowerDevice(
        device_code="TES-GEN-001",
        device_name="蓄冷罐配置生成",
        device_type="HVAC",
        load_subtype="thermal_storage",
        controllable_params=["storage_charge", "storage_discharge", "storage_soc", "pump_frequency"],
        thermal_storage_config={
            "capacity_kwh": 2000,
            "max_discharge_kw": 800,
            "max_charge_kw": 600,
            "usable_soc_min": 0.15,
            "usable_soc_max": 0.9,
        },
        rated_power=220,
        is_enabled=True,
    )
    async_db.add(storage)
    await async_db.commit()
    await async_db.refresh(storage)

    result = await DeviceConfigAutoGenerator(async_db).generate_configs_for_device(storage)
    await async_db.commit()

    assert result["shift_config_created"] is True
    assert result["regulation_config_created"] is True

    shift_result = await async_db.execute(select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == storage.id))
    shift_config = shift_result.scalar_one()
    assert shift_config.shiftable_power_ratio >= 0.6
    assert shift_config.forbidden_shift_hours == []
    assert shift_config.max_shift_duration == 6.0

    reg_result = await async_db.execute(select(LoadRegulationConfig).where(LoadRegulationConfig.device_id == storage.id))
    reg_config = reg_result.scalar_one()
    assert reg_config.regulation_type == "load"
    assert reg_config.unit == "%SOC"
