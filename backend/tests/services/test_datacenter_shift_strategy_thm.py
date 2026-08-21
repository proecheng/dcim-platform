"""
THM (Temperature Headroom Method) 单元测试

测试 Story 29.3 的 THM 方法实现
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.datacenter_shift_strategy import (
    _calculate_shiftable_power_thm,
    _calculate_temperature_rise_rate,
    _get_thm_config,
    _get_zone_supply_temperature,
    calculate_shiftable_power_for_zone,
)


def _db_result(*, scalar=None, one=None, rows=None):
    result = MagicMock()
    result.scalar.return_value = scalar
    result.scalar_one_or_none.return_value = one
    result.all.return_value = [] if rows is None else rows
    return result


def _session(*results):
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


THM_CONFIG = {
    "thm_safety_factor": 0.8,
    "thm_absolute_max_ratio": 0.6,
    "thm_min_headroom_celsius": 2.0,
}


class TestTHMBasic:
    """THM 方法基本功能测试"""

    @pytest.mark.asyncio
    async def test_thm_method_when_not_calibrated(self):
        """测试未校准时使用 THM 方法"""
        session = _session(_db_result(one=None))
        thm_result = {"zone_id": 999, "shiftable_ratio": 0.2, "method": "THM"}

        with (
            patch(
                "app.services.precool.constraints.check_all_constraints",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.datacenter_shift_strategy._calculate_shiftable_power_thm",
                new_callable=AsyncMock,
                return_value=thm_result,
            ) as calculate_thm,
        ):
            result = await calculate_shiftable_power_for_zone(zone_id=999, session=session)

        assert result == thm_result
        calculate_thm.assert_awaited_once_with(999, session)

    @pytest.mark.asyncio
    async def test_thm_formula_division_by_zero_protection(self):
        """测试 THM 公式除零保护（T_supply = T_max）"""
        session = _session(_db_result(scalar=24.0))

        with (
            patch(
                "app.services.datacenter_shift_strategy._get_thm_config",
                new_callable=AsyncMock,
                return_value=THM_CONFIG,
            ),
            patch(
                "app.services.datacenter_shift_strategy._get_zone_supply_temperature",
                new_callable=AsyncMock,
                return_value=27.0,
            ),
        ):
            result = await _calculate_shiftable_power_thm(1, session)

        assert result["error"] == "invalid_supply_temp"
        assert result["zone_id"] == 1

    @pytest.mark.asyncio
    async def test_temperature_headroom_red_line(self):
        """测试温度裕度红线（headroom < 2.0°C 时 ratio = 0）"""
        session = _session(_db_result(scalar=26.0))

        with (
            patch(
                "app.services.datacenter_shift_strategy._get_thm_config",
                new_callable=AsyncMock,
                return_value=THM_CONFIG,
            ),
            patch(
                "app.services.datacenter_shift_strategy._get_zone_supply_temperature",
                new_callable=AsyncMock,
                return_value=12.0,
            ),
        ):
            result = await _calculate_shiftable_power_thm(1, session)

        assert result["shiftable_ratio"] == 0.0
        assert result["headroom_celsius"] == 1.0
        assert result["method"] == "THM"


class TestTHMConfig:
    """SystemConfig 配置项测试"""

    @pytest.mark.asyncio
    async def test_config_default_fallback(self):
        """测试配置项不存在时使用默认值"""
        session = _session(*[_db_result(one=None) for _ in range(3)])

        assert await _get_thm_config(session) == THM_CONFIG
        assert session.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_config_range_validation(self):
        """测试配置项范围校验（超出范围时使用边界值）"""
        low_session = _session(
            _db_result(one=SimpleNamespace(config_value="0.1")),
            _db_result(one=SimpleNamespace(config_value="0.2")),
            _db_result(one=SimpleNamespace(config_value="0.5")),
        )
        high_session = _session(
            _db_result(one=SimpleNamespace(config_value="1.1")),
            _db_result(one=SimpleNamespace(config_value="1.2")),
            _db_result(one=SimpleNamespace(config_value="4.0")),
        )

        assert await _get_thm_config(low_session) == {
            "thm_safety_factor": 0.7,
            "thm_absolute_max_ratio": 0.4,
            "thm_min_headroom_celsius": 1.0,
        }
        assert await _get_thm_config(high_session) == {
            "thm_safety_factor": 0.9,
            "thm_absolute_max_ratio": 0.8,
            "thm_min_headroom_celsius": 3.0,
        }

    @pytest.mark.asyncio
    async def test_configured_values_are_used(self):
        """测试数据库中的有效配置值会进入算法，而不是静默回退默认值"""
        session = _session(
            _db_result(one=SimpleNamespace(config_value="0.85")),
            _db_result(one=SimpleNamespace(config_value="0.7")),
            _db_result(one=SimpleNamespace(config_value="2.5")),
        )

        assert await _get_thm_config(session) == {
            "thm_safety_factor": 0.85,
            "thm_absolute_max_ratio": 0.7,
            "thm_min_headroom_celsius": 2.5,
        }


class TestTemperatureRiseRate:
    """温升速率计算测试"""

    @pytest.mark.asyncio
    async def test_linear_regression_accuracy(self):
        """测试线性回归计算准确性（给定已知斜率的数据）"""
        # 手动构造已知斜率的数据
        # 斜率 = 0.5°C/h，初始温度 = 20°C
        # 测试数据：0h=20°C, 0.5h=20.25°C, 1h=20.5°C
        start = datetime(2026, 1, 1, 0, 0)
        rows = [(start + timedelta(minutes=5 * i), 20.0 + 0.5 * (5 * i / 60)) for i in range(12)]
        session = _session(_db_result(rows=rows))

        result = await _calculate_temperature_rise_rate(1, session)

        assert result == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_insufficient_data_conservative_estimate(self):
        """测试数据不足时使用保守估计 0.5°C/h"""
        start = datetime(2026, 1, 1, 0, 0)
        rows = [(start + timedelta(minutes=5 * i), 20.0) for i in range(11)]
        session = _session(_db_result(rows=rows))

        assert await _calculate_temperature_rise_rate(1, session) == 0.5

    @pytest.mark.asyncio
    async def test_outlier_filtering(self):
        """测试异常点过滤（相邻点变化 > 3°C）"""
        start = datetime(2026, 1, 1, 0, 0)
        rows = [(start + timedelta(minutes=5 * i), 20.0 + 0.25 * (5 * i / 60)) for i in range(12)]
        rows[6] = (rows[6][0], rows[6][1] + 10.0)
        session = _session(_db_result(rows=rows))

        result = await _calculate_temperature_rise_rate(1, session)

        assert result == pytest.approx(0.25)

    @pytest.mark.asyncio
    async def test_abnormal_value_filtering(self):
        """测试异常值过滤（回归后温升速率 > 2°C/h 或 < -1°C/h）"""
        start = datetime(2026, 1, 1, 0, 0)
        rows = [(start + timedelta(minutes=5 * i), 20.0 + 3.0 * (5 * i / 60)) for i in range(12)]
        session = _session(_db_result(rows=rows))

        assert await _calculate_temperature_rise_rate(1, session) == 0.5

    @pytest.mark.asyncio
    async def test_division_by_zero_protection(self):
        """测试除零保护（温升速率 ≤ 0 时跳过热缓冲时间校验）"""
        session = _session(_db_result(scalar=24.0))

        with (
            patch(
                "app.services.datacenter_shift_strategy._get_thm_config",
                new_callable=AsyncMock,
                return_value=THM_CONFIG,
            ),
            patch(
                "app.services.datacenter_shift_strategy._get_zone_supply_temperature",
                new_callable=AsyncMock,
                return_value=12.0,
            ),
            patch(
                "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
                new_callable=AsyncMock,
                return_value=0.0,
            ),
        ):
            result = await _calculate_shiftable_power_thm(1, session)

        assert result["shiftable_ratio"] == pytest.approx(0.16)


class TestThermalBufferTime:
    """热缓冲时间校验测试"""

    @pytest.mark.asyncio
    async def test_thermal_buffer_below_threshold(self):
        """测试热缓冲时间 < 30 分钟时 ratio = 0"""
        session = _session(_db_result(scalar=26.6))
        config = {**THM_CONFIG, "thm_min_headroom_celsius": 0.1}

        with (
            patch(
                "app.services.datacenter_shift_strategy._get_thm_config",
                new_callable=AsyncMock,
                return_value=config,
            ),
            patch(
                "app.services.datacenter_shift_strategy._get_zone_supply_temperature",
                new_callable=AsyncMock,
                return_value=12.0,
            ),
            patch(
                "app.services.datacenter_shift_strategy._calculate_temperature_rise_rate",
                new_callable=AsyncMock,
                return_value=1.0,
            ),
        ):
            result = await _calculate_shiftable_power_thm(1, session)

        assert result["shiftable_ratio"] == 0.0
        assert result["headroom_celsius"] == pytest.approx(0.4)


class TestModeSwitching:
    """模式切换测试"""

    @pytest.mark.asyncio
    async def test_switch_to_tcl_when_calibrated(self):
        """测试 RC 校准后使用 TCL 模式"""
        thermal_parameter = SimpleNamespace(is_active=True)
        session = _session(_db_result(one=thermal_parameter))
        tcl_result = {"zone_id": 1, "shiftable_ratio": 0.15, "method": "TCL"}

        with (
            patch(
                "app.services.precool.constraints.check_all_constraints",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.datacenter_shift_strategy._calculate_shiftable_power_tcl",
                new_callable=AsyncMock,
                return_value=tcl_result,
            ) as calculate_tcl,
        ):
            result = await calculate_shiftable_power_for_zone(1, session)

        assert result == tcl_result
        calculate_tcl.assert_awaited_once_with(1, session)


class TestDataQuality:
    """数据质量检查测试"""

    @pytest.mark.asyncio
    async def test_sensor_offline_rejection(self):
        """测试传感器离线时拒绝转移"""
        session = _session(_db_result(scalar=None), _db_result(scalar=None))

        with patch(
            "app.services.datacenter_shift_strategy._get_thm_config",
            new_callable=AsyncMock,
            return_value=THM_CONFIG,
        ):
            result = await _calculate_shiftable_power_thm(1, session)

        assert result["error"] == "sensor_offline"
        assert result["zone_id"] == 1


class TestTSupplyCalculation:
    """T_supply 平均值计算测试"""

    @pytest.mark.asyncio
    async def test_partial_unit_data(self):
        """测试部分 Unit 有数据、部分无数据时的平均值计算"""
        point_with_data = SimpleNamespace(id=10)
        point_without_data = SimpleNamespace(id=20)
        session = _session(
            _db_result(rows=[(SimpleNamespace(), point_with_data), (SimpleNamespace(), point_without_data)]),
            _db_result(rows=[(12.0,), (14.0,)]),
            _db_result(rows=[]),
        )

        assert await _get_zone_supply_temperature(1, session) == 13.0
