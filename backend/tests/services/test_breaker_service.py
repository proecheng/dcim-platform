"""
测试断路器保护判定服务 - Story 25.4
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diagnosis.breaker_service import (
    interpolate_trip_time,
    check_breaker_action,
    BREAKER_CURVES
)
from app.models.alarm import Alarm
from app.models.energy import PowerDevice
from app.models.diagnosis import BreakerProfile
from app.models import Point


@pytest.mark.parametrize("curve_type,overload_ratio,expected_min,expected_max", [
    ("B", 3.0, 3.0, 45.0),  # 边界：最小倍数
    ("B", 5.0, 0.04, 0.1),  # 边界：最大倍数
    ("B", 4.0, 1.52, 22.55),  # 插值：中间值
    ("C", 5.0, 1.3, 15.0),  # C 曲线最小倍数
    ("C", 7.5, 0.67, 7.55),  # C 曲线插值
    ("D", 10.0, 1.0, 8.0),  # D 曲线最小倍数
    ("D", 30.0, 0.52, 4.04),  # D 曲线插值
])
def test_interpolate_trip_time(curve_type, overload_ratio, expected_min, expected_max):
    """测试脱扣时间插值计算"""
    min_time, max_time = interpolate_trip_time(curve_type, overload_ratio)

    assert abs(min_time - expected_min) < 0.01
    assert abs(max_time - expected_max) < 0.01


def test_interpolate_trip_time_below_minimum():
    """测试过载倍数小于最小值"""
    min_time, max_time = interpolate_trip_time("B", 2.0)  # 小于 3.0

    # 应返回最小倍数对应的时间
    assert min_time == 3.0
    assert max_time == 45.0


def test_interpolate_trip_time_above_maximum():
    """测试过载倍数大于最大值"""
    min_time, max_time = interpolate_trip_time("B", 10.0)  # 大于 5.0

    # 应返回最大倍数对应的时间
    assert min_time == 0.04
    assert max_time == 0.1


def test_interpolate_trip_time_invalid_curve():
    """测试无效曲线类型"""
    with pytest.raises(ValueError, match="不支持的曲线类型"):
        interpolate_trip_time("X", 5.0)


@pytest.mark.asyncio
async def test_check_breaker_action_normal(async_db: AsyncSession):
    """测试断路器正常动作"""
    # 创建点位
    point = Point(
        point_code="PT-CURRENT-1",
        point_name="Current-1",
        point_type="AI",
        device_id=1
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BRK-001",
        device_name="Breaker-1",
        device_type="Breaker",
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 创建断路器配置
    profile = BreakerProfile(
        breaker_device_id=device.id,
        trip_curve_type="C",
        rated_current=100.0
    )
    async_db.add(profile)
    await async_db.commit()

    # 创建告警（过载 6 倍，预期时间 1.3-15s）
    alarm = Alarm(
        alarm_no="ALM-001",
        point_id=point.id,
        trigger_value=600.0,  # 6 倍过载
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now() - timedelta(seconds=5)  # 5 秒前触发
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 检查断路器动作
    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "保护正常动作"
    assert result.confidence == 0.95
    assert result.overload_ratio == 6.0
    # C型曲线 6倍过载的插值结果 (5倍→1.3-15s, 10倍→0.04-0.1s, 6倍插值)
    assert 1.0 <= result.expected_time_range[0] <= 1.5
    assert 7.0 <= result.expected_time_range[1] <= 15.0
    assert 4.5 <= result.actual_time <= 5.5  # 允许一定误差


@pytest.mark.asyncio
async def test_check_breaker_action_too_fast(async_db: AsyncSession):
    """测试断路器动作过快（可能误动作）"""
    point = Point(point_code="PT-CURRENT-2", point_name="Current-2", point_type="AI", device_id=1)
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    device = PowerDevice(device_code="BRK-002", device_name="Breaker-2", device_type="Breaker", current_point_id=point.id)
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    profile = BreakerProfile(breaker_device_id=device.id, trip_curve_type="B", rated_current=50.0)
    async_db.add(profile)
    await async_db.commit()

    # 过载 4 倍，预期时间约 1.52-22.55s，但实际 0.5s 就动作了
    alarm = Alarm(
        alarm_no="ALM-002",
        point_id=point.id,
        trigger_value=200.0,
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now() - timedelta(seconds=0.5)
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "动作过快，可能误动作"
    assert result.confidence == 0.7


@pytest.mark.asyncio
async def test_check_breaker_action_too_slow(async_db: AsyncSession):
    """测试断路器动作过慢（老化）"""
    point = Point(point_code="PT-CURRENT-3", point_name="Current-3", point_type="AI", device_id=1)
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    device = PowerDevice(device_code="BRK-003", device_name="Breaker-3", device_type="Breaker", current_point_id=point.id)
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    profile = BreakerProfile(breaker_device_id=device.id, trip_curve_type="C", rated_current=100.0)
    async_db.add(profile)
    await async_db.commit()

    # 过载 10 倍，预期时间 0.04-0.1s，但实际 0.15s 才动作
    alarm = Alarm(
        alarm_no="ALM-003",
        point_id=point.id,
        trigger_value=1000.0,
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now() - timedelta(seconds=0.15)
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "动作过慢，断路器老化"
    assert result.confidence == 0.8


@pytest.mark.asyncio
async def test_check_breaker_action_failure(async_db: AsyncSession):
    """测试断路器故障（未动作）"""
    point = Point(point_code="PT-CURRENT-4", point_name="Current-4", point_type="AI", device_id=1)
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    device = PowerDevice(device_code="BRK-004", device_name="Breaker-4", device_type="Breaker", current_point_id=point.id)
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    profile = BreakerProfile(breaker_device_id=device.id, trip_curve_type="D", rated_current=200.0)
    async_db.add(profile)
    await async_db.commit()

    # 过载 50 倍，预期时间 0.04-0.1s，但实际 1s 还未动作
    alarm = Alarm(
        alarm_no="ALM-004",
        point_id=point.id,
        trigger_value=10000.0,
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now() - timedelta(seconds=1.0)
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "断路器故障，未动作"
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_check_breaker_action_no_device(async_db: AsyncSession):
    """测试点位未关联设备"""
    point = Point(point_code="PT-CURRENT-5", point_name="Current-5", point_type="AI", device_id=1)
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    alarm = Alarm(
        alarm_no="ALM-005",
        point_id=point.id,
        trigger_value=500.0,
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now()
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "no_breaker_config"
    assert result.confidence == 0.0
    assert "未关联到配电设备" in result.explanation


@pytest.mark.asyncio
async def test_check_breaker_action_no_profile(async_db: AsyncSession):
    """测试设备未配置断路器特性"""
    point = Point(point_code="PT-CURRENT-6", point_name="Current-6", point_type="AI", device_id=1)
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    device = PowerDevice(device_code="BRK-006", device_name="Breaker-6", device_type="Breaker", current_point_id=point.id)
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    alarm = Alarm(
        alarm_no="ALM-006",
        point_id=point.id,
        trigger_value=500.0,
        alarm_message="过流告警", alarm_level="critical",
        created_at=datetime.now()
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    result = await check_breaker_action(alarm, async_db)

    assert result.action_type == "no_breaker_config"
    assert "未配置断路器特性" in result.explanation
