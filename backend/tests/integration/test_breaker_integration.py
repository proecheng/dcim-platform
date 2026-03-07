"""
断路器保护动作集成测试 - Story 25.4
测试场景: 断路器配置、过流告警、动作判定
"""
import pytest
import time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.models.energy import PowerDevice
from app.models.alarm import Alarm
from app.models.point import Point
from app.models.diagnosis import BreakerProfile
from app.services.diagnosis.breaker_service import check_breaker_action


@pytest.mark.asyncio
async def test_breaker_normal_action_c_curve(async_db: AsyncSession):
    """
    测试场景: C 型断路器正常保护动作
    验证: 过流 5 倍，动作时间在 1.3-15s 范围内
    """
    # 创建测试点位
    point = Point(
        point_code="POINT-BREAKER-001",
        point_name="Breaker Test Point",
        point_type="AI_CURRENT",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BREAKER-001",
        device_name="Test Breaker",
        device_type="BREAKER",
        is_enabled=True,
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 创建断路器配置 (C 型, 63A)
    breaker_profile = BreakerProfile(
        breaker_device_id=device.id,
        trip_curve_type="C",
        rated_current=63.0
    )
    async_db.add(breaker_profile)
    await async_db.commit()

    # 创建过流告警 (315A = 5 倍额定电流)
    alarm_time = datetime.now() - timedelta(seconds=8)  # 8 秒前触发
    alarm = Alarm(
        alarm_no=f"ALM-BREAKER-{int(time.time() * 1000)}",
        point_id=point.id,
        alarm_type="threshold",
        alarm_level="critical",
        alarm_message="过流告警",
        trigger_value=315.0,
        created_at=alarm_time
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 调用断路器判定
    result = await check_breaker_action(alarm, async_db)

    # 验证判定结果
    assert result.action_type == "保护正常动作"
    assert result.confidence == 0.95
    assert result.overload_ratio == pytest.approx(5.0, rel=0.01)
    assert 1.3 <= result.expected_time_range[0] <= 15.0
    assert 1.3 <= result.expected_time_range[1] <= 15.0
    assert 7.0 <= result.actual_time <= 9.0  # 约 8 秒


@pytest.mark.asyncio
async def test_breaker_too_fast_action(async_db: AsyncSession):
    """
    测试场景: 断路器动作过快，可能误动作
    验证: 动作时间 < 预期最小时间
    """
    # 创建测试点位
    point = Point(
        point_code="POINT-BREAKER-002",
        point_name="Breaker Test Point 2",
        point_type="AI_CURRENT",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BREAKER-002",
        device_name="Test Breaker 2",
        device_type="BREAKER",
        is_enabled=True,
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 创建断路器配置 (C 型, 63A)
    breaker_profile = BreakerProfile(
        breaker_device_id=device.id,
        trip_curve_type="C",
        rated_current=63.0
    )
    async_db.add(breaker_profile)
    await async_db.commit()

    # 创建过流告警 (315A = 5 倍)，动作时间 0.5 秒（< 1.3s 最小时间）
    alarm_time = datetime.now() - timedelta(seconds=0.5)
    alarm = Alarm(
        alarm_no=f"ALM-BREAKER-{int(time.time() * 1000)}",
        point_id=point.id,
        alarm_type="threshold",
        alarm_level="critical",
        alarm_message="过流告警",
        trigger_value=315.0,
        created_at=alarm_time
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 调用断路器判定
    result = await check_breaker_action(alarm, async_db)

    # 验证判定结果
    assert result.action_type == "动作过快，可能误动作"
    assert result.confidence == 0.7
    assert result.actual_time < result.expected_time_range[0]


@pytest.mark.asyncio
async def test_breaker_too_slow_action(async_db: AsyncSession):
    """
    测试场景: 断路器动作过慢，可能老化
    验证: 动作时间 > 预期最大时间 且 < 最大时间 × 2
    """
    # 创建测试点位
    point = Point(
        point_code="POINT-BREAKER-003",
        point_name="Breaker Test Point 3",
        point_type="AI_CURRENT",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BREAKER-003",
        device_name="Test Breaker 3",
        device_type="BREAKER",
        is_enabled=True,
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 创建断路器配置 (C 型, 63A)
    breaker_profile = BreakerProfile(
        breaker_device_id=device.id,
        trip_curve_type="C",
        rated_current=63.0
    )
    async_db.add(breaker_profile)
    await async_db.commit()

    # 创建过流告警 (315A = 5 倍)，动作时间 20 秒（> 15s 最大时间）
    alarm_time = datetime.now() - timedelta(seconds=20)
    alarm = Alarm(
        alarm_no=f"ALM-BREAKER-{int(time.time() * 1000)}",
        point_id=point.id,
        alarm_type="threshold",
        alarm_level="critical",
        alarm_message="过流告警",
        trigger_value=315.0,
        created_at=alarm_time
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 调用断路器判定
    result = await check_breaker_action(alarm, async_db)

    # 验证判定结果
    assert result.action_type == "动作过慢，断路器老化"
    assert result.confidence == 0.8
    assert result.actual_time > result.expected_time_range[1]


@pytest.mark.asyncio
async def test_breaker_failure_no_action(async_db: AsyncSession):
    """
    测试场景: 断路器故障，未动作
    验证: 动作时间 > 预期最大时间 × 2
    """
    # 创建测试点位
    point = Point(
        point_code="POINT-BREAKER-004",
        point_name="Breaker Test Point 4",
        point_type="AI_CURRENT",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BREAKER-004",
        device_name="Test Breaker 4",
        device_type="BREAKER",
        is_enabled=True,
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 创建断路器配置 (C 型, 63A)
    breaker_profile = BreakerProfile(
        breaker_device_id=device.id,
        trip_curve_type="C",
        rated_current=63.0
    )
    async_db.add(breaker_profile)
    await async_db.commit()

    # 创建过流告警 (315A = 5 倍)，动作时间 35 秒（> 15s × 2）
    alarm_time = datetime.now() - timedelta(seconds=35)
    alarm = Alarm(
        alarm_no=f"ALM-BREAKER-{int(time.time() * 1000)}",
        point_id=point.id,
        alarm_type="threshold",
        alarm_level="critical",
        alarm_message="过流告警",
        trigger_value=315.0,
        created_at=alarm_time
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 调用断路器判定
    result = await check_breaker_action(alarm, async_db)

    # 验证判定结果
    assert result.action_type == "断路器故障，未动作"
    assert result.confidence == 0.9
    assert result.actual_time > result.expected_time_range[1] * 2


@pytest.mark.asyncio
async def test_breaker_api_integration(client: AsyncClient, async_db: AsyncSession, admin_user):
    """
    测试场景: 通过 API 配置断路器并验证判定
    验证: API 配置 → 数据库更新 → 断路器判定生效
    """
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试点位
    point = Point(
        point_code="POINT-BREAKER-005",
        point_name="Breaker Test Point 5",
        point_type="AI_CURRENT",
        unit="A"
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    # 创建配电设备
    device = PowerDevice(
        device_code="BREAKER-005",
        device_name="Test Breaker 5",
        device_type="BREAKER",
        is_enabled=True,
        current_point_id=point.id
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 通过 API 创建断路器配置
    response = await client.post(
        "/api/v1/diagnosis/breaker-profiles",
        headers=headers,
        json={
            "breaker_device_id": device.id,
            "trip_curve_type": "B",
            "rated_current": 32.0
        }
    )
    assert response.status_code == 201

    # 创建过流告警 (96A = 3 倍)
    alarm_time = datetime.now() - timedelta(seconds=10)
    alarm = Alarm(
        alarm_no=f"ALM-BREAKER-{int(time.time() * 1000)}",
        point_id=point.id,
        alarm_type="threshold",
        alarm_level="critical",
        alarm_message="过流告警",
        trigger_value=96.0,
        created_at=alarm_time
    )
    async_db.add(alarm)
    await async_db.commit()
    await async_db.refresh(alarm)

    # 验证断路器判定生效
    result = await check_breaker_action(alarm, async_db)
    assert result.action_type == "保护正常动作"
    assert result.overload_ratio == pytest.approx(3.0, rel=0.01)
