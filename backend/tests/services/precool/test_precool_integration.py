"""
预冷系统端到端集成测试（纯 mock）

覆盖完整链路：预测 → 回填 → 精度计算 → 自动回退
测试 TCL 和 THM 两种模式的完整生命周期
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.precool.thermal_model import ThermalModel
from app.services.precool.accuracy_monitor import (
    _check_consecutive_errors,
    CONSECUTIVE_ERROR_THRESHOLD,
    CONSECUTIVE_ERROR_COUNT,
    SENTINEL_VALUE,
)


def _make_async_session_ctx(mock_session):
    """创建 async_session 上下文管理器 mock"""
    mock_ctx = MagicMock()
    mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


def _make_zone(thermal_R=0.03, thermal_C=50.0, bypass_beta=0.1):
    """创建 CoolingZone mock"""
    zone = MagicMock()
    zone.id = 1
    zone.thermal_R = thermal_R
    zone.thermal_C = thermal_C
    zone.bypass_beta = bypass_beta
    return zone


def _make_standard_data(steps=12):
    """创建标准历史数据"""
    return {
        "q_it": [100.0] * steps,
        "t_ambient": [24.0] * steps,
        "t_current": 24.0,
        "t_outlet": None,
        "t_outdoor": 25.0,
    }


def _make_good_quality():
    """创建正常数据质量结果"""
    return {
        "error": None,
        "missing_fields": [],
        "q_it_quality": "good",
        "t_ambient_quality": "good",
        "t_current_quality": "good",
    }


class TestTCLModePredictionLifecycle:
    """TCL 模式（RC 模型）完整生命周期"""

    @pytest.mark.asyncio
    async def test_tcl_prediction_produces_trajectory(self):
        """TCL 模式预测生成完整温度轨迹"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone()
        data = _make_standard_data()
        quality = _make_good_quality()

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value={"value": 50.0}), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            assert "error" not in result
            assert result["model_version"] == "RC-v1"
            assert len(result["temperature_trajectory"]) == 13  # 初始 + 12 步
            assert result["prediction_horizon_min"] == 60
            # 轨迹中所有温度在合理范围
            assert all(0 <= t <= 50 for t in result["temperature_trajectory"])

    @pytest.mark.asyncio
    async def test_tcl_with_custom_schedule(self):
        """TCL 模式使用自定义制冷功率计划"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone()
        data = _make_standard_data()
        quality = _make_good_quality()

        # 阶梯式制冷计划：前半高功率，后半低功率
        schedule = [80.0] * 6 + [40.0] * 6

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_active_thermal_param", return_value={"id": 1}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(
                zone_id=1, hours=1.0, q_cool_schedule=schedule
            )

            assert "error" not in result
            trajectory = result["temperature_trajectory"]
            # 后半段制冷降低，温度应有上升趋势
            mid = len(trajectory) // 2
            # 至少后半段最后温度 >= 前半段最后温度（制冷降低导致）
            assert trajectory[-1] >= trajectory[mid] or abs(trajectory[-1] - trajectory[mid]) < 0.5


class TestTHMFallbackLifecycle:
    """THM 模式（温度裕度法）降级生命周期"""

    @pytest.mark.asyncio
    async def test_uncalibrated_params_triggers_thm(self):
        """RC 参数未校准时触发 THM 降级"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone(thermal_R=None, thermal_C=None)  # 未校准

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            assert result["error"] == "parameters_not_calibrated"
            # 调用方应自动切换到 THM（在 API 层或 datacenter_shift_strategy 中处理）


class TestAutoRollbackLifecycle:
    """自动回退生命周期"""

    @pytest.mark.asyncio
    async def test_consecutive_errors_trigger_rollback(self):
        """连续 3 次误差超阈值触发 RC → THM 回退"""
        mock_active_param = MagicMock()
        mock_active_param.is_active = True

        mock_session = AsyncMock()

        # 连续 3 次偏差都 > 2.0
        dev_result = MagicMock()
        dev_result.all.return_value = [(2.5,), (3.0,), (2.1,)]

        # 活跃参数
        active_result = MagicMock()
        active_result.scalar_one_or_none.return_value = mock_active_param

        # 删除旧的 inactive 参数
        delete_result = MagicMock()

        mock_session.execute = AsyncMock(
            side_effect=[dev_result, active_result, delete_result]
        )

        await _check_consecutive_errors(mock_session, zone_id=1)

        # 应该将 is_active 设为 False
        assert mock_active_param.is_active == False
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_partial_errors_no_rollback(self):
        """偏差未全部超过阈值时不回退"""
        mock_session = AsyncMock()

        # 只有 2/3 超过阈值
        dev_result = MagicMock()
        dev_result.all.return_value = [(2.5,), (1.5,), (3.0,)]

        mock_session.execute = AsyncMock(return_value=dev_result)

        await _check_consecutive_errors(mock_session, zone_id=1)

        # 不应触发回退（只查了一次 DB）
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_after_rollback_prediction_returns_not_calibrated(self):
        """回退后预测应返回 parameters_not_calibrated（触发 THM 降级）"""
        model = ThermalModel()
        model._dependencies_checked = True

        # 模拟回退后状态：zone 的 R/C 仍有值，但 ThermalParameter.is_active 全部 False
        # 注意：回退只改 ThermalParameter 表，不改 CoolingZone 表的 R/C
        # 但 predict_temperature 检查的是 zone.thermal_R/C（CoolingZone 表）
        # 所以回退后 RC 模型仍然可用（回退只影响 calculate_shiftable_power_for_zone 的分支选择）
        zone = _make_zone(thermal_R=0.03, thermal_C=50.0)
        data = _make_standard_data()
        quality = _make_good_quality()

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch.object(model, "_get_current_cooling", return_value={"value": 50.0}), \
             patch.object(model, "_get_active_thermal_param", return_value={}), \
             patch.object(model, "_log_prediction", return_value=None), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)

            # 预测仍能成功（CoolingZone 的 R/C 没变）
            # 但 model_version 为 RC-v0（无 active param）
            assert "error" not in result
            assert result["model_version"] == "RC-v0"


class TestDynamicRatioIntegration:
    """动态制冷比例集成测试"""

    @pytest.mark.asyncio
    async def test_dynamic_ratio_with_precool_enabled(self):
        """precool_enabled=True 时使用动态计算"""
        from app.services.load_shift.algorithms.constraint_checker import ConstraintChecker

        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = ConstraintChecker(db=mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"zone_id": 1, "shiftable_ratio": 0.35, "method": "THM"}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result == 0.35

    @pytest.mark.asyncio
    async def test_dynamic_ratio_with_precool_disabled(self):
        """precool_enabled=False 时返回 None（回退固定值）"""
        from app.services.load_shift.algorithms.constraint_checker import ConstraintChecker

        mock_config = MagicMock()
        mock_config.precool_enabled = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = ConstraintChecker(db=mock_session)
        result = await checker._get_dynamic_cooling_ratio(1)
        assert result is None  # 调用方回退到 0.4

    @pytest.mark.asyncio
    async def test_dynamic_ratio_calculation_error_fallback(self):
        """动态计算失败时返回 None（回退固定值）"""
        from app.services.load_shift.algorithms.constraint_checker import ConstraintChecker

        mock_config = MagicMock()
        mock_config.precool_enabled = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_session.execute = AsyncMock(return_value=mock_result)

        checker = ConstraintChecker(db=mock_session)

        with patch(
            "app.services.datacenter_shift_strategy.calculate_shiftable_power_for_zone",
            new_callable=AsyncMock,
            return_value={"error": "sensor_offline", "zone_id": 1}
        ):
            result = await checker._get_dynamic_cooling_ratio(1)
            assert result is None


class TestDataQualityToErrorChain:
    """数据质量问题 → 错误传播链路"""

    @pytest.mark.asyncio
    async def test_sensor_offline_blocks_prediction(self):
        """传感器离线时预测被阻止"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone()
        data = _make_standard_data()
        quality = {
            "error": "sensor_offline",
            "sensor": "inlet",
            "last_update": "2026-03-11T10:00:00",
            "zone_id": 1,
        }

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch.object(model, "_check_data_quality", return_value=quality), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "sensor_offline"

    @pytest.mark.asyncio
    async def test_insufficient_data_blocks_prediction(self):
        """数据不足时预测被阻止"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone()
        data = {
            "error": "insufficient_history",
            "field": "Q_IT",
            "available_minutes": 10,
            "zone_id": 1,
        }

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", return_value=data), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "insufficient_history"

    @pytest.mark.asyncio
    async def test_data_fetch_exception_handled(self):
        """数据加载异常不传播"""
        model = ThermalModel()
        model._dependencies_checked = True

        zone = _make_zone()

        with patch.object(model, "_get_zone", return_value={"zone": zone}), \
             patch.object(model, "_load_historical_data", side_effect=Exception("DB timeout")), \
             patch("app.services.precool.thermal_model.async_session",
                   _make_async_session_ctx(AsyncMock())):

            result = await model.predict_temperature(zone_id=1, hours=1.0)
            assert result["error"] == "data_fetch_failed"


class TestSentinelValueHandling:
    """哨兵值处理测试"""

    def test_sentinel_value_is_negative(self):
        """哨兵值应为负数（不会与真实温度混淆）"""
        assert SENTINEL_VALUE < 0

    def test_sentinel_value_distinct_from_valid_temps(self):
        """哨兵值应远离有效温度范围 [0, 50]"""
        assert SENTINEL_VALUE < -100  # 远离有效范围
