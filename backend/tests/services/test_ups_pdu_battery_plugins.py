"""UPS/PDU/Battery 劣化分析插件测试 — Story 36.5

18 个测试:
  1.  UPS 插件注册表
  2.  PDU 插件注册表
  3.  Battery 插件注册表
  4.  UPS full data（电压+效率+切换+温度）
  5.  UPS partial data（仅电压）
  6.  UPS minimal data（无数据）
  7.  UPS 电压分段标准差趋势
  8.  PDU full data（负载+电压+THD+温升）
  9.  PDU partial data（仅负载+电压）
  10. PDU minimal data（无数据）
  11. PDU 零负载保护
  12. Battery full data（SOH+内阻+温度）
  13. Battery partial data（仅 SOH）
  14. Battery minimal data（无数据）
  15. Battery SOH → score 非线性映射
  16. Battery 无 SOH 仅内阻
  17. Analyzer 路由 UPS/PDU/BATTERY 到正确插件
  18. 共享 _linear_regression_slope 兼容导入
"""

import pytest
from datetime import datetime, timedelta

from app.models.device import Device
from app.models.point import Point
from app.models.diagnosis import BatterySOHRecord
from app.services.predictive_maintenance.base import DegradationResult
from app.services.predictive_maintenance.registry import (
    DEGRADATION_PLUGIN_REGISTRY,
    get_degradation_plugin,
)
from app.services.predictive_maintenance.ups_plugin import UPSDegradationPlugin
from app.services.predictive_maintenance.pdu_plugin import PDUDegradationPlugin
from app.services.predictive_maintenance.battery_plugin import BatteryDegradationPlugin
from app.services.predictive_maintenance.analyzer import DegradationAnalyzer


# ==================== Helpers ====================

def _make_trend_data(days: int = 30, base_value: float = 220.0, slope: float = 0.0):
    """生成趋势数据：[(day_offset, value), ...]"""
    return [(float(d) / 24.0, base_value + slope * d / 24.0) for d in range(days * 24)]


def _make_voltage_data(days: int = 30, base: float = 220.0, noise_growth: float = 0.0):
    """生成电压数据，noise_growth 控制标准差增长速率"""
    import random
    random.seed(123)
    data = []
    for h in range(days * 24):
        day = h / 24.0
        noise_scale = 0.5 + noise_growth * day
        v = base + random.gauss(0, noise_scale)
        data.append((day, v))
    return data


# ==================== 1-3. 插件注册表 ====================

@pytest.mark.asyncio
async def test_ups_plugin_registered():
    """UPS 插件已注册"""
    assert "ups" in DEGRADATION_PLUGIN_REGISTRY
    assert get_degradation_plugin("ups") is UPSDegradationPlugin


@pytest.mark.asyncio
async def test_pdu_plugin_registered():
    """PDU 插件已注册"""
    assert "pdu" in DEGRADATION_PLUGIN_REGISTRY
    assert get_degradation_plugin("pdu") is PDUDegradationPlugin


@pytest.mark.asyncio
async def test_battery_plugin_registered():
    """Battery 插件已注册"""
    assert "battery" in DEGRADATION_PLUGIN_REGISTRY
    assert get_degradation_plugin("battery") is BatteryDegradationPlugin


# ==================== 4-7. UPS 插件测试 ====================

@pytest.mark.asyncio
async def test_ups_plugin_full_data():
    """UPS full data: 电压+效率+切换+温度 → data_sufficiency='full'"""
    plugin = UPSDegradationPlugin()
    point_history = {
        "output_voltage": _make_voltage_data(days=30, base=220.0, noise_growth=0.01),
        "efficiency": _make_trend_data(days=30, base_value=95.0, slope=-0.01),
        "transfer_count": [(float(d), 1.0 if d % 200 == 0 else 0.0) for d in range(30 * 24)],
        "temperature": _make_trend_data(days=30, base_value=35.0, slope=0.005),
    }

    result = await plugin.analyze(device_id=1, point_history=point_history, window_days=30)

    assert isinstance(result, DegradationResult)
    assert result.device_id == 1
    assert 0 <= result.score <= 100
    assert result.confidence > 0
    assert result.data_sufficiency == "full"
    assert result.detail is not None
    assert "voltage_stability" in result.detail


@pytest.mark.asyncio
async def test_ups_plugin_partial_data():
    """UPS partial data: 仅电压 → data_sufficiency='partial'"""
    plugin = UPSDegradationPlugin()
    point_history = {
        "output_voltage": _make_voltage_data(days=30, base=220.0),
    }

    result = await plugin.analyze(device_id=2, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert result.score > 0
    assert result.available_points == 1


@pytest.mark.asyncio
async def test_ups_plugin_minimal_data():
    """UPS minimal data: 无数据 → score=100, confidence=0"""
    plugin = UPSDegradationPlugin()
    result = await plugin.analyze(device_id=3, point_history={}, window_days=30)

    assert result.score == 100.0
    assert result.confidence == 0.0
    assert result.data_sufficiency == "minimal"
    assert result.available_points == 0


@pytest.mark.asyncio
async def test_ups_voltage_stability_degradation():
    """UPS 电压标准差增大 → 劣化评分下降"""
    plugin = UPSDegradationPlugin()
    # 高噪声增长
    point_history = {
        "output_voltage": _make_voltage_data(days=30, base=220.0, noise_growth=0.1),
    }

    result = await plugin.analyze(device_id=4, point_history=point_history, window_days=30)

    assert result.score < 100
    assert "voltage_std_trend" in result.trend_factors


# ==================== 8-11. PDU 插件测试 ====================

@pytest.mark.asyncio
async def test_pdu_plugin_full_data():
    """PDU full data: 负载+电压+THD+温升 → data_sufficiency='full'"""
    plugin = PDUDegradationPlugin()
    point_history = {
        "load_percentage": _make_trend_data(days=30, base_value=60.0, slope=0.01),
        "voltage": _make_trend_data(days=30, base_value=220.0, slope=0.0),
        "thd": _make_trend_data(days=30, base_value=3.0, slope=0.005),
        "temperature_rise": _make_trend_data(days=30, base_value=15.0, slope=0.002),
    }

    result = await plugin.analyze(device_id=5, point_history=point_history, window_days=30)

    assert isinstance(result, DegradationResult)
    assert result.data_sufficiency == "full"
    assert result.confidence > 0
    assert "load_trend" in result.detail


@pytest.mark.asyncio
async def test_pdu_plugin_partial_data():
    """PDU partial data: 仅负载+电压 → data_sufficiency='partial'"""
    plugin = PDUDegradationPlugin()
    point_history = {
        "load_percentage": _make_trend_data(days=30, base_value=50.0),
        "voltage": _make_trend_data(days=30, base_value=220.0),
    }

    result = await plugin.analyze(device_id=6, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert result.available_points == 2


@pytest.mark.asyncio
async def test_pdu_plugin_minimal_data():
    """PDU minimal data: 无数据 → score=100, confidence=0"""
    plugin = PDUDegradationPlugin()
    result = await plugin.analyze(device_id=7, point_history={}, window_days=30)

    assert result.score == 100.0
    assert result.confidence == 0.0
    assert result.data_sufficiency == "minimal"


@pytest.mark.asyncio
async def test_pdu_zero_load_protection():
    """PDU 零负载保护: 均值 < 1% → partial, 不评分负载率"""
    plugin = PDUDegradationPlugin()
    point_history = {
        "load_percentage": [(float(d) / 24.0, 0.1) for d in range(30 * 24)],
        "voltage": _make_trend_data(days=30, base_value=220.0),
    }

    result = await plugin.analyze(device_id=8, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert result.detail["load_trend"]["status"] == "zero_load"


# ==================== 12-16. Battery 插件测试 ====================

@pytest.mark.asyncio
async def test_battery_plugin_full_data():
    """Battery full data: SOH+内阻+温度 → data_sufficiency='full'"""
    plugin = BatteryDegradationPlugin()
    point_history = {
        "soh_percent": [(float(d), 95.0 - 0.1 * d) for d in range(30)],
        "internal_resistance": _make_trend_data(days=30, base_value=5.0, slope=0.001),
        "temperature": _make_trend_data(days=30, base_value=25.0, slope=0.002),
    }

    result = await plugin.analyze(device_id=9, point_history=point_history, window_days=30)

    assert isinstance(result, DegradationResult)
    assert result.data_sufficiency == "full"
    assert result.confidence > 0
    assert "soh_percent" in result.trend_factors
    assert "soh" in result.detail


@pytest.mark.asyncio
async def test_battery_plugin_partial_soh_only():
    """Battery partial: 仅 SOH → partial"""
    plugin = BatteryDegradationPlugin()
    point_history = {
        "soh_percent": [(0.0, 85.0), (15.0, 83.0), (29.0, 80.0)],
    }

    result = await plugin.analyze(device_id=10, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert result.score <= 85  # SOH 80% 附近


@pytest.mark.asyncio
async def test_battery_plugin_minimal_data():
    """Battery minimal: 无数据 → score=100, confidence=0"""
    plugin = BatteryDegradationPlugin()
    result = await plugin.analyze(device_id=11, point_history={}, window_days=30)

    assert result.score == 100.0
    assert result.confidence == 0.0
    assert result.data_sufficiency == "minimal"


@pytest.mark.asyncio
async def test_battery_soh_score_mapping():
    """Battery SOH → score 非线性映射 + 边界 clamp"""
    assert BatteryDegradationPlugin._soh_to_score(100) == 100
    assert BatteryDegradationPlugin._soh_to_score(90) == 90
    assert BatteryDegradationPlugin._soh_to_score(80) == 80
    # 60% SOH → 40 分
    assert BatteryDegradationPlugin._soh_to_score(60) == 40
    # 40% SOH → 10 分
    assert BatteryDegradationPlugin._soh_to_score(40) == 10
    # 0% → 0
    assert BatteryDegradationPlugin._soh_to_score(0) == 0
    # SOH > 100 clamp
    assert BatteryDegradationPlugin._soh_to_score(105) == 100
    # SOH < 0 clamp
    assert BatteryDegradationPlugin._soh_to_score(-5) == 0


@pytest.mark.asyncio
async def test_battery_no_soh_with_resistance():
    """Battery: 无 SOH 但有内阻 → partial"""
    plugin = BatteryDegradationPlugin()
    point_history = {
        "internal_resistance": _make_trend_data(days=30, base_value=5.0, slope=0.01),
    }

    result = await plugin.analyze(device_id=12, point_history=point_history, window_days=30)

    assert result.data_sufficiency == "partial"
    assert "resistance_slope_per_month" in result.trend_factors
    assert result.detail["soh"]["status"] == "no_data"


# ==================== 17. Analyzer 路由测试 ====================

@pytest.mark.asyncio
async def test_analyzer_routes_ups_pdu_battery(async_db):
    """Analyzer 将 UPS/PDU/BATTERY 设备路由到正确插件"""
    devices = {}
    for dt in ["UPS", "PDU", "BATTERY", "TH"]:
        d = Device(
            device_code=f"ROUTE-{dt}-001",
            device_name=f"设备{dt}",
            device_type=dt,
            area_code="A1",
        )
        async_db.add(d)
        await async_db.flush()
        devices[dt] = d

    analyzer = DegradationAnalyzer(async_db, window_days=30)
    results = await analyzer.analyze_all_devices()

    analyzed_ids = {r.device_id for r in results}

    # TH 设备不应被分析
    assert devices["TH"].id not in analyzed_ids

    # UPS/PDU/BATTERY 设备应被分析（无数据返回 minimal 结果）
    for dt in ["UPS", "PDU", "BATTERY"]:
        assert devices[dt].id in analyzed_ids, f"{dt} 设备应参与劣化分析"


# ==================== 18. 共享方法兼容导入 ====================

@pytest.mark.asyncio
async def test_linear_regression_slope_import_compat():
    """_linear_regression_slope 可从 hvac_plugin 和 base 导入"""
    from app.services.predictive_maintenance.hvac_plugin import _linear_regression_slope as from_hvac
    from app.services.predictive_maintenance.base import _linear_regression_slope as from_base

    # 同一函数
    assert from_hvac is from_base

    # 功能正确
    assert abs(from_base([0.0, 1.0, 2.0], [1.0, 3.0, 5.0]) - 2.0) < 0.001
