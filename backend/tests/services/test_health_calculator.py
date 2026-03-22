"""DeviceHealthScoreCalculator 测试 — Story 36.2

10 个测试覆盖 AC #1~#5:
  5.1  HVAC 权重加权合并
  5.2  UPS/Battery 权重
  5.3  minimal data_sufficiency 降级
  5.4  动态权重配置
  5.5  告警评分计算
  5.6  维保评分计算
  5.7  calculate_all_health_scores 批量
  5.8  battery_soh_service 兼容
  5.9  score_to_level 边界值
  5.10 评分≤40 日志标记
"""

import pytest
from datetime import datetime, timedelta

from app.models.device import Device
from app.models.point import Point
from app.models.alarm import Alarm
from app.models.operation import WorkOrder, WorkOrderStatus
from app.models.config import SystemConfig
from app.models.report import DeviceHealthScore
from app.services.predictive_maintenance.base import DegradationResult
from app.services.predictive_maintenance.health_calculator import (
    DeviceHealthScoreCalculator,
    _calc_alarm_score,
    _calc_maintenance_score,
    _score_to_level,
    WEIGHT_CONFIG,
    MINIMAL_WEIGHTS,
)


# ==================== Helpers ====================

async def _make_device(db, device_type="AC", code_suffix="001"):
    """创建测试设备"""
    device = Device(
        device_code=f"HC-{device_type}-{code_suffix}",
        device_name=f"测试{device_type}设备{code_suffix}",
        device_type=device_type,
        area_code="A1",
    )
    db.add(device)
    await db.flush()
    return device


async def _make_point(db, device_id, suffix="return_temp"):
    """创建测试点位"""
    p = Point(
        point_code=f"HC-POINT-{device_id}_{suffix}",
        point_name=f"测试{suffix}",
        point_type="AI",
        device_id=device_id,
        device_type="AC",
    )
    db.add(p)
    await db.flush()
    return p


async def _make_alarms(db, point_id, count=5):
    """创建测试告警"""
    now = datetime.now()
    for i in range(count):
        alarm = Alarm(
            alarm_no=f"ALM-HC-{point_id}-{i}",
            point_id=point_id,
            alarm_level="minor",
            alarm_message=f"测试告警{i}",
            created_at=now - timedelta(days=i),
        )
        db.add(alarm)
    await db.flush()


async def _make_work_order(db, device_id, days_ago=15):
    """创建已完成工单"""
    wo = WorkOrder(
        order_no=f"WO-HC-{device_id}-{days_ago}",
        title=f"维保工单-{device_id}",
        device_id=device_id,
        status=WorkOrderStatus.completed,
        completed_at=datetime.now() - timedelta(days=days_ago),
    )
    db.add(wo)
    await db.flush()
    return wo


# ==================== 5.1 HVAC 权重加权合并 ====================

@pytest.mark.asyncio
async def test_hvac_weighted_merge(async_db):
    """AC#1: HVAC 劣化40%+告警30%+维保30%"""
    calculator = DeviceHealthScoreCalculator(async_db)
    dr = DegradationResult(
        device_id=1, score=70.0, confidence=0.8,
        available_points=3, total_points=5, data_sufficiency="full"
    )
    weights = WEIGHT_CONFIG["hvac"]
    score, level, factors = calculator.calculate(dr, alarm_count=3, days_since_maintenance=50, plugin_key="hvac", weights=weights)

    # 劣化70*0.4 + 告警70*0.3 + 维保85*0.3 = 28+21+25.5 = 74.5
    assert abs(score - 74.5) < 0.2
    assert level == "关注"
    assert factors["degradation"]["weight"] == 0.4
    assert factors["alarm"]["weight"] == 0.3
    assert factors["maintenance"]["weight"] == 0.3


# ==================== 5.2 UPS/Battery 权重 ====================

@pytest.mark.asyncio
async def test_battery_weighted_merge(async_db):
    """AC#2: Battery SOH 50%+告警20%+维保30%"""
    calculator = DeviceHealthScoreCalculator(async_db)
    dr = DegradationResult(
        device_id=1, score=85.0, confidence=0.8,
        available_points=1, total_points=1, data_sufficiency="partial"
    )
    weights = WEIGHT_CONFIG["battery"]
    score, level, factors = calculator.calculate(dr, alarm_count=0, days_since_maintenance=20, plugin_key="battery", weights=weights)

    # SOH 85*0.5 + 告警100*0.2 + 维保100*0.3 = 42.5+20+30 = 92.5
    assert abs(score - 92.5) < 0.2
    assert level == "健康"
    assert factors["degradation"]["weight"] == 0.5


# ==================== 5.3 minimal data_sufficiency 降级 ====================

@pytest.mark.asyncio
async def test_minimal_data_sufficiency_degradation(async_db):
    """AC#3: minimal 时劣化权重归零，仅告警50%+维保50%"""
    calculator = DeviceHealthScoreCalculator(async_db)
    dr = DegradationResult(
        device_id=1, score=20.0, confidence=0.0,  # 劣化评分很低但应被忽略
        available_points=0, total_points=5, data_sufficiency="minimal"
    )
    weights = WEIGHT_CONFIG["hvac"]
    score, level, factors = calculator.calculate(dr, alarm_count=0, days_since_maintenance=10, plugin_key="hvac", weights=weights)

    # 劣化 0 + 告警100*0.5 + 维保100*0.5 = 100
    assert abs(score - 100.0) < 0.2
    assert level == "健康"
    assert factors["degradation"]["weight"] == 0  # minimal 权重


# ==================== 5.4 动态权重配置 ====================

@pytest.mark.asyncio
async def test_dynamic_weight_config(async_db):
    """AC#4: SystemConfig 覆盖默认权重"""
    # 写入自定义权重到 SystemConfig
    cfg = SystemConfig(
        config_group="predictive_maintenance",
        config_key="weights.hvac",
        config_value='{"degradation": 0.6, "alarm": 0.2, "maintenance": 0.2}',
        value_type="json",
    )
    async_db.add(cfg)
    await async_db.flush()

    calculator = DeviceHealthScoreCalculator(async_db)
    loaded = await calculator._load_weight_config("hvac")

    assert loaded["degradation"] == 0.6
    assert loaded["alarm"] == 0.2
    assert loaded["maintenance"] == 0.2


# ==================== 5.5 告警评分计算 ====================

@pytest.mark.asyncio
async def test_alarm_score_mapping():
    """告警频次 → 评分映射"""
    assert _calc_alarm_score(0) == 100.0
    assert _calc_alarm_score(1) == 85.0
    assert _calc_alarm_score(2) == 85.0
    assert _calc_alarm_score(3) == 70.0
    assert _calc_alarm_score(5) == 70.0
    assert _calc_alarm_score(6) == 50.0
    assert _calc_alarm_score(10) == 50.0
    assert _calc_alarm_score(11) == 30.0
    assert _calc_alarm_score(20) == 30.0
    assert _calc_alarm_score(21) == 10.0
    assert _calc_alarm_score(100) == 10.0


# ==================== 5.6 维保评分计算 ====================

@pytest.mark.asyncio
async def test_maintenance_score_mapping():
    """距最后维保天数 → 评分映射"""
    assert _calc_maintenance_score(0) == 100.0
    assert _calc_maintenance_score(30) == 100.0
    assert _calc_maintenance_score(31) == 85.0
    assert _calc_maintenance_score(90) == 85.0
    assert _calc_maintenance_score(91) == 70.0
    assert _calc_maintenance_score(180) == 70.0
    assert _calc_maintenance_score(181) == 50.0
    assert _calc_maintenance_score(365) == 50.0
    assert _calc_maintenance_score(366) == 30.0
    assert _calc_maintenance_score(None) == 50.0  # 无维保记录


# ==================== 5.7 批量计算 ====================

@pytest.mark.asyncio
async def test_calculate_all_health_scores(async_db):
    """AC#1-#5: 多设备类型混合批量计算"""
    # 创建不同类型设备
    ac = await _make_device(async_db, "AC", "B01")
    ups = await _make_device(async_db, "UPS", "B02")
    th = await _make_device(async_db, "TH", "B03")  # 不支持的类型

    # AC 设备添加告警和工单
    pt = await _make_point(async_db, ac.id, "return_temp")
    await _make_alarms(async_db, pt.id, count=3)
    await _make_work_order(async_db, ac.id, days_ago=45)

    calculator = DeviceHealthScoreCalculator(async_db)
    count = await calculator.calculate_all_health_scores()

    # AC + UPS 应被计算（TH 不在 DEVICE_TYPE_MAP 中）
    assert count == 2

    # 验证 DeviceHealthScore 记录
    from sqlalchemy import select
    result = await async_db.execute(
        select(DeviceHealthScore).where(DeviceHealthScore.device_id == ac.id)
    )
    record = result.scalar_one()
    assert record.score > 0
    assert record.health_level in ("健康", "关注", "预警", "危险")
    assert record.alarm_count == 3
    assert record.score_factors is not None
    assert record.data_sufficiency is not None


# ==================== 5.8 battery_soh_service 兼容 ====================

@pytest.mark.asyncio
async def test_battery_soh_service_compatibility(async_db):
    """AC#2: battery_soh_service update_device_health_score 正确写入"""
    device = await _make_device(async_db, "UPS", "SOH01")

    # 模拟通过 calculator 直接计算（不通过 battery_soh_service 因为它创建自己的 session）
    calculator = DeviceHealthScoreCalculator(async_db)
    dr = DegradationResult(
        device_id=device.id,
        score=75.0,  # SOH 75%
        confidence=0.8,
        available_points=1,
        total_points=1,
        data_sufficiency="partial",
        primary_concern="battery_soh",
    )

    weights = await calculator._load_weight_config("battery")
    score, health_level, score_factors = calculator.calculate(
        dr, alarm_count=0, days_since_maintenance=None, plugin_key="battery", weights=weights
    )

    await calculator._upsert_health_score(
        device=device,
        score=score,
        health_level=health_level,
        alarm_count=0,
        days_since=None,
        last_maint=None,
        score_factors=score_factors,
        data_sufficiency="partial",
        degradation_score=75.0,
    )
    await async_db.flush()

    # 验证写入
    from sqlalchemy import select
    result = await async_db.execute(
        select(DeviceHealthScore).where(DeviceHealthScore.device_id == device.id)
    )
    record = result.scalar_one()
    assert record.degradation_score == 75.0
    assert record.data_sufficiency == "partial"
    assert record.score > 0


# ==================== 5.9 score_to_level 边界值 ====================

@pytest.mark.asyncio
async def test_score_to_level_boundaries():
    """边界值验证：使用 >= 逻辑"""
    assert _score_to_level(100) == "健康"
    assert _score_to_level(80) == "健康"    # 边界：80 应为"健康"
    assert _score_to_level(79.9) == "关注"
    assert _score_to_level(60) == "关注"    # 边界：60 应为"关注"
    assert _score_to_level(59.9) == "预警"
    assert _score_to_level(40) == "预警"    # 边界：40 应为"预警"
    assert _score_to_level(39.9) == "危险"
    assert _score_to_level(0) == "危险"


# ==================== 5.10 评分≤40 日志标记 ====================

@pytest.mark.asyncio
async def test_low_score_logging(async_db, caplog):
    """AC#5: score≤40 日志 warning 标记"""
    import logging
    caplog.set_level(logging.WARNING)

    device = await _make_device(async_db, "AC", "LOG01")

    # 创建大量告警让评分降低
    pt = await _make_point(async_db, device.id, "return_temp")
    await _make_alarms(async_db, pt.id, count=25)  # >20 告警 → 告警评分 10

    # 创建过期维保（>365天前）
    await _make_work_order(async_db, device.id, days_ago=400)

    calculator = DeviceHealthScoreCalculator(async_db)
    await calculator.calculate_all_health_scores()

    # 验证 warning 日志
    warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    health_warnings = [m for m in warning_messages if "健康度预警" in m]
    assert len(health_warnings) > 0, "score≤40 应有 warning 日志"
