"""约束检查器专项测试（算力中心特殊约束）"""

from datetime import date

import pytest

from app.models.energy import PowerDevice
from app.models.load_shift import ShiftConstraint
from app.schemas.load_shift import ConstraintType, FeasibilityAnalysisRequest, ShiftPeriodType
from app.services.load_shift.algorithms.constraint_checker import ConstraintChecker


def _new_device(
    code: str,
    name: str,
    dtype: str,
    rated_power: float,
    avg_load_rate: float,
) -> PowerDevice:
    return PowerDevice(
        device_code=code,
        device_name=name,
        device_type=dtype,
        rated_power=rated_power,
        avg_load_rate=avg_load_rate,
        is_enabled=True,
    )


def _new_request(target_shift_power: float) -> FeasibilityAnalysisRequest:
    return FeasibilityAnalysisRequest(
        shift_date=date.today(),
        shift_from_period=ShiftPeriodType.PEAK,
        shift_to_period=ShiftPeriodType.VALLEY,
        target_shift_power=target_shift_power,
        selected_devices=[],
    )


@pytest.mark.asyncio
async def test_datacenter_max_transfer_power_exceeded(async_db):
    """目标功率超过算力中心最大可转移上限时，应返回建议值。"""
    # 负载分布：IT=700, cooling=200, other=100, total=1000
    it = _new_device("IT-001", "IT1", "IT_SERVER", 700, 100)
    cooling = _new_device("AC-001", "AC1", "AC", 200, 100)
    other = _new_device("L-001", "LIGHT", "LIGHTING", 100, 100)
    async_db.add_all([it, cooling, other])

    constraint = ShiftConstraint(
        constraint_name="算力中心占比约束",
        constraint_type=ConstraintType.DATACENTER_LOAD,
        constraint_params={
            "it_load_ratio_min": 0.6,
            "it_load_ratio_max": 0.8,
            "cooling_ratio": 0.2,
            "other_ratio": 0.1,
            "cooling_transferable_ratio": 0.4,
            "other_transferable_ratio": 0.6,
        },
        is_enabled=True,
    )
    async_db.add(constraint)
    await async_db.flush()

    # 上限 = 1000 * (0.2*0.4 + 0.1*0.6) = 140
    request = _new_request(200)
    checker = ConstraintChecker(async_db)
    result = await checker.check_all_constraints(request, [cooling.id])

    assert result.is_valid is False
    violations = [v for v in result.violated_constraints if v.get("violation_type") == "max_transfer_power_exceeded"]
    assert len(violations) == 1
    assert abs(float(violations[0]["suggested_max_shift_power"]) - 140.0) < 0.01


@pytest.mark.asyncio
async def test_datacenter_it_ratio_out_of_range(async_db):
    """IT占比超出范围时，应给出 IT 占比违例。"""
    # IT=900, cooling=100 -> IT ratio = 0.9
    it = _new_device("IT-002", "IT2", "IT_SERVER", 900, 100)
    cooling = _new_device("AC-002", "AC2", "AC", 100, 100)
    async_db.add_all([it, cooling])

    constraint = ShiftConstraint(
        constraint_name="IT占比约束",
        constraint_type=ConstraintType.DATACENTER_LOAD,
        constraint_params={
            "it_load_ratio_min": 0.6,
            "it_load_ratio_max": 0.8,
            "cooling_ratio": 0.1,
            "other_ratio": 0.0,
            "cooling_transferable_ratio": 0.4,
            "other_transferable_ratio": 0.6,
        },
        is_enabled=True,
    )
    async_db.add(constraint)
    await async_db.flush()

    request = _new_request(10)
    checker = ConstraintChecker(async_db)
    result = await checker.check_all_constraints(request, [cooling.id])

    assert result.is_valid is False
    violations = [v for v in result.violated_constraints if v.get("violation_type") == "it_load_ratio_out_of_range"]
    assert len(violations) == 1
    assert 0.89 < float(violations[0]["current_value"]) < 0.91


@pytest.mark.asyncio
async def test_ups_capacity_exceeded_with_suggested_power(async_db):
    """UPS容量超限时，应返回上限与建议功率。"""
    # 总负载估算: IT 100 + AC 100 + UPS 100 = 300
    it = _new_device("IT-003", "IT3", "IT_SERVER", 200, 50)
    cooling = _new_device("AC-003", "AC3", "AC", 200, 50)
    ups = _new_device("UPS-001", "UPS1", "UPS", 500, 20)
    async_db.add_all([it, cooling, ups])

    constraint = ShiftConstraint(
        constraint_name="UPS容量约束",
        constraint_type=ConstraintType.UPS_CAPACITY,
        constraint_params={
            "safety_factor": 0.8,
            "reject_on_exceed": True,
            "auto_adjust": True,
        },
        is_enabled=True,
    )
    async_db.add(constraint)
    await async_db.flush()

    # 允许上限 = 500 * 0.8 = 400；目标150 -> projected=450 超限；建议=100
    request = _new_request(150)
    checker = ConstraintChecker(async_db)
    result = await checker.check_all_constraints(request, [cooling.id])

    assert result.is_valid is False
    violations = [v for v in result.violated_constraints if v.get("violation_type") == "ups_capacity_exceeded"]
    assert len(violations) == 1
    assert abs(float(violations[0]["limit_value"]) - 400.0) < 0.01
    assert abs(float(violations[0]["suggested_max_shift_power"]) - 100.0) < 0.01
