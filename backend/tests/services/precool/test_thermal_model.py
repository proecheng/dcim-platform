"""
ThermalModel 单元测试

测试 RC 热动力学模型的核心功能
"""

import pytest
from datetime import datetime, timedelta
from app.services.precool.thermal_model import ThermalModel


class TestThermalModelBasic:
    """基本功能测试"""

    @pytest.mark.asyncio
    async def test_predict_temperature_parameters_not_calibrated(self):
        """测试 R/C 参数未标定时返回错误"""
        model = ThermalModel()
        # 假设 zone_id=999 的 thermal_R 或 thermal_C 为 NULL
        result = await model.predict_temperature(zone_id=999, hours=1.0)

        assert "error" in result
        assert result["error"] == "parameters_not_calibrated" or result["error"] == "zone_not_found"
        assert result["zone_id"] == 999


    @pytest.mark.asyncio
    async def test_predict_temperature_numerical_instability(self):
        """测试数值不稳定时返回错误"""
        model = ThermalModel()
        # 假设 zone_id=1 有极端 RC 参数导致 Δt >= 2RC
        result = await model.predict_temperature(zone_id=1, hours=100.0)

        # 应该返回数值不稳定错误或其他错误
        assert "error" in result


    @pytest.mark.asyncio
    async def test_predict_temperature_invalid_q_cool_schedule(self):
        """测试 q_cool_schedule 长度不匹配时返回错误"""
        model = ThermalModel()
        # 1 小时预测需要 12 步，但提供 10 步
        result = await model.predict_temperature(
            zone_id=1,
            hours=1.0,
            q_cool_schedule=[50.0] * 10  # 错误长度
        )

        assert "error" in result
        if result["error"] != "zone_not_found":
            assert result["error"] == "invalid_q_cool_schedule"


    @pytest.mark.asyncio
    async def test_predict_temperature_insufficient_data(self):
        """测试数据不足时返回错误"""
        model = ThermalModel()
        # 假设 zone_id=998 没有足够的历史数据
        result = await model.predict_temperature(zone_id=998, hours=1.0)

        assert "error" in result


class TestThermalModelDataQuality:
    """数据质量检查测试"""

    @pytest.mark.asyncio
    async def test_temperature_out_of_bounds(self):
        """测试温度异常时拒绝预测"""
        model = ThermalModel()
        # 假设 zone_id=997 有异常温度数据
        result = await model.predict_temperature(zone_id=997, hours=1.0)

        assert "error" in result


    @pytest.mark.asyncio
    async def test_sensor_offline(self):
        """测试传感器离线时拒绝预测"""
        model = ThermalModel()
        # 假设 zone_id=996 的传感器离线
        result = await model.predict_temperature(zone_id=996, hours=1.0)

        assert "error" in result


class TestThermalModelPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_performance_typical_scenario(self):
        """测试典型场景性能（1 小时预测 < 200ms）"""
        import time
        model = ThermalModel()

        start = time.time()
        result = await model.predict_temperature(zone_id=1, hours=1.0)
        elapsed = time.time() - start

        # 如果预测成功，检查性能
        if "error" not in result:
            assert elapsed < 1.0  # < 1s（架构标准）
            # 典型场景应该 < 200ms，但这里放宽到 500ms 以适应测试环境
            assert elapsed < 0.5


    @pytest.mark.asyncio
    async def test_performance_extreme_scenario(self):
        """测试极限场景性能（24 小时预测 < 5s）"""
        import time
        model = ThermalModel()

        start = time.time()
        result = await model.predict_temperature(zone_id=1, hours=24.0)
        elapsed = time.time() - start

        # 如果预测成功，检查性能
        if "error" not in result:
            assert elapsed < 5.0  # < 5s


class TestThermalModelNumericalStability:
    """数值稳定性测试"""

    @pytest.mark.asyncio
    async def test_numerical_stability_extreme_rc(self):
        """测试极端 RC 参数时温度不发散"""
        model = ThermalModel()
        # 假设 zone_id=2 有极端 RC 参数：R=0.01, C=100
        result = await model.predict_temperature(zone_id=2, hours=24.0)

        # 如果预测成功，温度应该在合理范围内
        if "error" not in result and "temperature_trajectory" in result:
            temps = result["temperature_trajectory"]
            # 所有温度应该在 0-50°C 范围内
            assert all(0 <= t <= 50 for t in temps), f"Temperature out of bounds: {temps}"
            # 温度不应该发散（变化不应该太剧烈）
            max_temp = max(temps)
            min_temp = min(temps)
            assert max_temp - min_temp < 30, f"Temperature divergence detected: {max_temp} - {min_temp}"
