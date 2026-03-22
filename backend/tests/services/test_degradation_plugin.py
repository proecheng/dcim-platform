"""劣化分析插件框架测试 — Story 36.1

10 个测试覆盖 AC #1~#7:
  5.1  插件注册表
  5.2  HVAC full data
  5.3  HVAC partial data
  5.4  HVAC minimal data
  5.5  可配置窗口
  5.6  analyze_all_devices 设备类型过滤
  5.7  _fetch_point_history 降级
  5.8  archive_hourly 聚合
  5.9  archive_hourly 幂等
  5.10 线性回归斜率
"""

import pytest
from datetime import datetime, timedelta

from app.models.device import Device
from app.models.point import Point
from app.models.history import PointHistory, PointHistoryArchive
from app.services.predictive_maintenance.base import DegradationPlugin, DegradationResult
from app.services.predictive_maintenance.registry import (
    DEGRADATION_PLUGIN_REGISTRY,
    register_degradation_plugin,
    get_degradation_plugin,
    list_degradation_plugins,
)
from app.services.predictive_maintenance.hvac_plugin import (
    HVACDegradationPlugin,
    _linear_regression_slope,
)
from app.services.predictive_maintenance.analyzer import DegradationAnalyzer
from app.services.predictive_maintenance.archiver import archive_hourly


# ==================== Helpers ====================

def _make_trend_data(days: int = 30, base_value: float = 24.0, slope: float = 0.0):
    """生成模拟温度趋势数据：[(day_offset, value), ...]"""
    return [(float(d), base_value + slope * d) for d in range(days * 24)]


def _make_toggle_data(days: int = 30, toggle_rate: float = 0.05):
    """生成模拟压缩机启停数据"""
    import random
    random.seed(42)
    data = []
    state = 1.0
    for d in range(days * 24):
        if random.random() < toggle_rate:
            state = 1.0 - state
        data.append((float(d) / 24.0, state))
    return data


async def _seed_device_and_points(db, device_type="AC", point_suffixes=None):
    """创建测试设备和点位，返回 (device, points_dict)"""
    device = Device(
        device_code=f"TEST-{device_type}-001",
        device_name=f"测试{device_type}设备",
        device_type=device_type,
        area_code="A1",
    )
    db.add(device)
    await db.flush()

    points = {}
    if point_suffixes:
        for suffix in point_suffixes:
            p = Point(
                point_code=f"TEST-{device_type}-001_{suffix}",
                point_name=f"测试{suffix}",
                point_type="AI",
                device_id=device.id,
                device_type=device_type,
            )
            db.add(p)
            await db.flush()
            points[suffix] = p

    return device, points


async def _seed_point_history(db, point_id, hours=720, base_value=24.0, slope=0.0):
    """生成测试 PointHistory 数据"""
    now = datetime.now()
    for h in range(hours):
        ts = now - timedelta(hours=hours - h)
        value = base_value + slope * (h / 24.0)
        ph = PointHistory(
            point_id=point_id,
            value=value,
            quality=0,
            recorded_at=ts,
        )
        db.add(ph)
    await db.flush()


async def _seed_archive_data(db, point_id, hours=720, base_value=24.0, slope=0.0):
    """生成测试 PointHistoryArchive(hourly) 数据"""
    now = datetime.now()
    for h in range(hours):
        ts = now - timedelta(hours=hours - h)
        ts = ts.replace(minute=0, second=0, microsecond=0)
        value = base_value + slope * (h / 24.0)
        archive = PointHistoryArchive(
            point_id=point_id,
            archive_type="hourly",
            value_min=value - 0.5,
            value_max=value + 0.5,
            value_avg=value,
            value_sum=value * 12,
            sample_count=12,
            recorded_at=ts,
        )
        db.add(archive)
    await db.flush()


# ==================== 5.1 插件注册表测试 ====================

@pytest.mark.asyncio
async def test_plugin_registry():
    """AC#1: 插件注册表 — 注册/获取/列举"""
    # hvac 插件应已通过 __init__.py 自动注册
    assert "hvac" in DEGRADATION_PLUGIN_REGISTRY
    assert get_degradation_plugin("hvac") is HVACDegradationPlugin
    assert "hvac" in list_degradation_plugins()

    # 不存在的插件返回 None
    assert get_degradation_plugin("nonexistent") is None

    # 测试装饰器注册新插件
    @register_degradation_plugin("test_device")
    class TestPlugin(DegradationPlugin):
        def get_device_type(self): return "test_device"
        def get_required_points(self): return []
        def get_optional_points(self): return []
        async def analyze(self, device_id, point_history, window_days=30):
            return DegradationResult(device_id=device_id, score=100, confidence=0,
                                    available_points=0, total_points=0)

    assert get_degradation_plugin("test_device") is TestPlugin
    assert "test_device" in list_degradation_plugins()

    # 清理
    del DEGRADATION_PLUGIN_REGISTRY["test_device"]


# ==================== 5.2 HVAC Full Data 测试 ====================

@pytest.mark.asyncio
async def test_hvac_plugin_full_data():
    """AC#2: 30天完整数据 → score + confidence + trend_factors, data_sufficiency='full'"""
    plugin = HVACDegradationPlugin()

    # 构造完整数据（必需+2个可选）
    point_history = {
        "return_temp": _make_trend_data(days=30, base_value=24.0, slope=0.02),
        "compressor1_status": _make_toggle_data(days=30, toggle_rate=0.05),
        "cop": [(float(d), 3.5 - 0.002 * d) for d in range(30 * 24)],
    }

    result = await plugin.analyze(device_id=1, point_history=point_history, window_days=30)

    assert isinstance(result, DegradationResult)
    assert result.device_id == 1
    assert 0 <= result.score <= 100
    assert 0 < result.confidence <= 1.0
    assert result.data_sufficiency == "full"
    assert "return_temp_slope_per_month" in result.trend_factors
    assert result.detail is not None
    assert "return_temp" in result.detail


# ==================== 5.3 HVAC Partial Data 测试 ====================

@pytest.mark.asyncio
async def test_hvac_plugin_partial_data():
    """AC#3: 仅回风温度数据 → data_sufficiency='partial', confidence 降低"""
    plugin = HVACDegradationPlugin()

    point_history = {
        "return_temp": _make_trend_data(days=30, base_value=24.0, slope=0.01),
    }

    result = await plugin.analyze(device_id=2, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert result.confidence < 0.8  # confidence 应低于 full data 情况
    assert result.score > 0
    assert result.detail is not None


# ==================== 5.4 HVAC Minimal Data 测试 ====================

@pytest.mark.asyncio
async def test_hvac_plugin_minimal_data():
    """AC#4: 无数据 → score=100, confidence=0, data_sufficiency='minimal'"""
    plugin = HVACDegradationPlugin()

    # 空数据
    result = await plugin.analyze(device_id=3, point_history={}, window_days=30)

    assert result.score == 100.0
    assert result.confidence == 0.0
    assert result.data_sufficiency == "minimal"
    assert result.available_points == 0

    # 有 key 但空列表
    result2 = await plugin.analyze(
        device_id=4,
        point_history={"return_temp": [], "cop": []},
        window_days=30,
    )
    assert result2.score == 100.0
    assert result2.confidence == 0.0
    assert result2.data_sufficiency == "minimal"


# ==================== 5.5 可配置窗口测试 ====================

@pytest.mark.asyncio
async def test_hvac_plugin_configurable_window():
    """AC#5: window_days=60 使用60天窗口"""
    plugin = HVACDegradationPlugin()

    # 60天数据
    point_history = {
        "return_temp": _make_trend_data(days=60, base_value=24.0, slope=0.01),
        "compressor1_status": _make_toggle_data(days=60, toggle_rate=0.05),
        "cop": [(float(d), 3.5 - 0.001 * d) for d in range(60 * 24)],
    }

    result = await plugin.analyze(device_id=5, point_history=point_history, window_days=60)

    assert result.data_sufficiency == "full"
    assert result.confidence > 0


# ==================== 5.6 Analyzer analyze_all_devices 测试 ====================

@pytest.mark.asyncio
async def test_analyzer_device_type_filter(async_db):
    """AC#7: 仅分析 UPS/AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR/PDU，跳过 TH/DOOR 等"""
    # 创建各类设备
    for dt in ["AC", "PRECISION_AC_INDOOR", "UPS", "PDU", "TH", "DOOR", "SMOKE", "WATER"]:
        d = Device(
            device_code=f"FILTER-{dt}-001",
            device_name=f"设备{dt}",
            device_type=dt,
            area_code="A1",
        )
        async_db.add(d)
    await async_db.flush()

    analyzer = DegradationAnalyzer(async_db, window_days=30)
    results = await analyzer.analyze_all_devices()

    # 所有结果的设备都应在 DEVICE_TYPE_MAP 中
    # 由于无历史数据，结果可能为空或全是 minimal
    # 但不应有 TH/DOOR/SMOKE/WATER 设备被分析
    from app.services.predictive_maintenance.config import DEVICE_TYPE_MAP
    analyzed_device_ids = {r.device_id for r in results}

    # 查询哪些设备被分析了
    from sqlalchemy import select
    for dt in ["TH", "DOOR", "SMOKE", "WATER"]:
        sensor_result = await async_db.execute(
            select(Device).where(Device.device_code == f"FILTER-{dt}-001")
        )
        sensor = sensor_result.scalar_one_or_none()
        if sensor:
            assert sensor.id not in analyzed_device_ids, f"{dt} 设备不应参与劣化分析"


# ==================== 5.7 _fetch_point_history 降级测试 ====================

@pytest.mark.asyncio
async def test_fetch_point_history_fallback(async_db):
    """AC: PointHistoryArchive 无数据时降级到 PointHistory"""
    device, points = await _seed_device_and_points(
        async_db, "AC", ["return_temp"]
    )
    # 只在 PointHistory 中写数据（不写 Archive）
    await _seed_point_history(
        async_db, points["return_temp"].id, hours=48, base_value=24.0
    )

    analyzer = DegradationAnalyzer(async_db, window_days=30)
    history = await analyzer._fetch_point_history(
        device.id, ["return_temp"]
    )

    assert "return_temp" in history
    assert len(history["return_temp"]) > 0  # 降级后应有数据


# ==================== 5.8 archive_hourly 聚合测试 ====================

@pytest.mark.asyncio
async def test_archive_hourly_aggregation(async_db):
    """AC#6: 正确聚合 min/max/avg/sum/count 写入 PointHistoryArchive"""
    device, points = await _seed_device_and_points(
        async_db, "AC", ["return_temp"]
    )
    point_id = points["return_temp"].id

    # 写入上一小时的 PointHistory 数据
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    values = [23.0, 24.0, 25.0, 26.0, 27.0]
    for i, v in enumerate(values):
        ph = PointHistory(
            point_id=point_id,
            value=v,
            quality=0,
            recorded_at=hour_start + timedelta(minutes=i * 10),
        )
        async_db.add(ph)
    await async_db.flush()

    # 执行归档
    created = await archive_hourly(async_db)
    assert created == 1

    # 验证归档数据
    from sqlalchemy import select
    result = await async_db.execute(
        select(PointHistoryArchive).where(
            PointHistoryArchive.point_id == point_id,
            PointHistoryArchive.archive_type == "hourly",
        )
    )
    archive = result.scalar_one()

    assert archive.value_min == 23.0
    assert archive.value_max == 27.0
    assert abs(archive.value_avg - 25.0) < 0.01
    assert archive.sample_count == 5


# ==================== 5.9 archive_hourly 幂等测试 ====================

@pytest.mark.asyncio
async def test_archive_hourly_idempotent(async_db):
    """AC#6: 重复执行不产生重复记录"""
    device, points = await _seed_device_and_points(
        async_db, "AC", ["return_temp"]
    )
    point_id = points["return_temp"].id

    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    for i in range(5):
        ph = PointHistory(
            point_id=point_id,
            value=24.0 + i,
            quality=0,
            recorded_at=hour_start + timedelta(minutes=i * 10),
        )
        async_db.add(ph)
    await async_db.flush()

    # 第一次归档
    created1 = await archive_hourly(async_db)
    assert created1 == 1

    # 第二次归档（幂等）
    created2 = await archive_hourly(async_db)
    assert created2 == 0

    # 验证只有一条归档记录
    from sqlalchemy import select, func
    count_result = await async_db.execute(
        select(func.count(PointHistoryArchive.id)).where(
            PointHistoryArchive.point_id == point_id,
            PointHistoryArchive.archive_type == "hourly",
        )
    )
    assert count_result.scalar() == 1


# ==================== 5.10 线性回归斜率测试 ====================

@pytest.mark.asyncio
async def test_linear_regression_slope():
    """验证线性回归斜率计算准确性"""
    # 完美线性：y = 2x + 1，斜率应为 2.0
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]
    values = [1.0, 3.0, 5.0, 7.0, 9.0]
    slope = _linear_regression_slope(timestamps, values)
    assert abs(slope - 2.0) < 0.001

    # 水平线：斜率应为 0.0
    values_flat = [5.0, 5.0, 5.0, 5.0, 5.0]
    slope_flat = _linear_regression_slope(timestamps, values_flat)
    assert abs(slope_flat) < 0.001

    # 下降趋势：y = -0.5x + 10
    values_down = [10.0, 9.5, 9.0, 8.5, 8.0]
    slope_down = _linear_regression_slope(timestamps, values_down)
    assert abs(slope_down - (-0.5)) < 0.001

    # 单点：返回 0
    assert _linear_regression_slope([0.0], [5.0]) == 0.0

    # 空列表：返回 0
    assert _linear_regression_slope([], []) == 0.0

    # 所有 timestamp 相同（denominator=0）
    assert _linear_regression_slope([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) == 0.0
