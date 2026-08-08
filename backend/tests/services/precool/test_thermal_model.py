"""
ThermalModel 单元测试

测试 RC 热动力学模型的核心功能
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.precool.thermal_model import ThermalModel


@pytest.fixture
def model(monkeypatch):
    """创建不依赖外部数据库的热模型。"""

    @asynccontextmanager
    async def isolated_async_session():
        yield MagicMock()

    monkeypatch.setattr("app.services.precool.thermal_model.async_session", isolated_async_session)
    thermal_model = ThermalModel()
    thermal_model._dependencies_checked = True
    return thermal_model


def _zone(thermal_r=1.0, thermal_c=100.0):
    return SimpleNamespace(thermal_R=thermal_r, thermal_C=thermal_c, bypass_beta=0.1)


def _configure_successful_prediction(model, monkeypatch, thermal_r=1.0, thermal_c=100.0):
    monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone(thermal_r, thermal_c)}))
    monkeypatch.setattr(
        model,
        "_load_historical_data",
        AsyncMock(
            return_value={
                "q_it": [100.0] * 288,
                "t_ambient": [24.0] * 288,
                "t_current": 24.0,
                "t_outlet": 24.0,
                "t_outdoor": 20.0,
            }
        ),
    )
    monkeypatch.setattr(
        model,
        "_check_data_quality",
        AsyncMock(
            return_value={
                "error": None,
                "missing_fields": [],
                "q_it_quality": "good",
                "t_ambient_quality": "good",
                "t_current_quality": "good",
            }
        ),
    )
    monkeypatch.setattr(model, "_get_current_cooling", AsyncMock(return_value={"value": 20.0}))
    monkeypatch.setattr(model, "_get_active_thermal_param", AsyncMock(return_value={"id": 1}))
    monkeypatch.setattr(model, "_log_prediction", AsyncMock())


class TestThermalModelDependencies:
    """依赖表检查测试"""

    @pytest.mark.asyncio
    async def test_dependencies_available(self, async_db, monkeypatch):
        """测试内存数据库包含热模型依赖表"""

        @asynccontextmanager
        async def isolated_async_session():
            yield async_db

        monkeypatch.setattr("app.services.precool.thermal_model.async_session", isolated_async_session)

        result = await ThermalModel()._check_dependencies()

        assert result == {"success": True}


class TestThermalModelBasic:
    """基本功能测试"""

    @pytest.mark.asyncio
    async def test_predict_temperature_parameters_not_calibrated(self, model, monkeypatch):
        """测试 R/C 参数未标定时返回错误"""
        monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone(thermal_r=None)}))

        result = await model.predict_temperature(zone_id=999, hours=1.0)

        assert result["error"] == "parameters_not_calibrated"
        assert result["zone_id"] == 999

    @pytest.mark.asyncio
    async def test_predict_temperature_numerical_instability(self, model, monkeypatch):
        """测试数值不稳定时返回错误"""
        monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone(thermal_r=0.01, thermal_c=1.0)}))

        result = await model.predict_temperature(zone_id=1, hours=100.0)

        assert result["error"] == "numerical_instability"
        assert result["zone_id"] == 1

    @pytest.mark.asyncio
    async def test_predict_temperature_invalid_q_cool_schedule(self, model):
        """测试 q_cool_schedule 长度不匹配时返回错误"""
        # 1 小时预测需要 12 步，但提供 10 步
        result = await model.predict_temperature(
            zone_id=1,
            hours=1.0,
            q_cool_schedule=[50.0] * 10,  # 错误长度
        )

        assert result["error"] == "invalid_q_cool_schedule"
        assert result["zone_id"] == 1

    @pytest.mark.asyncio
    async def test_predict_temperature_insufficient_data(self, model, monkeypatch):
        """测试数据不足时返回错误"""
        monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone()}))
        monkeypatch.setattr(
            model,
            "_load_historical_data",
            AsyncMock(return_value={"error": "insufficient_data", "missing_fields": ["Q_IT"], "zone_id": 998}),
        )

        result = await model.predict_temperature(zone_id=998, hours=1.0)

        assert result["error"] == "insufficient_data"
        assert result["missing_fields"] == ["Q_IT"]


class TestThermalModelDataQuality:
    """数据质量检查测试"""

    @pytest.mark.asyncio
    async def test_temperature_out_of_bounds(self, model, monkeypatch):
        """测试温度异常时拒绝预测"""
        monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone()}))
        monkeypatch.setattr(
            model,
            "_load_historical_data",
            AsyncMock(
                return_value={
                    "q_it": [100.0] * 12,
                    "t_ambient": [24.0] * 12,
                    "t_current": 55.0,
                    "t_outlet": None,
                    "t_outdoor": None,
                }
            ),
        )

        result = await model.predict_temperature(zone_id=997, hours=1.0)

        assert result["error"] == "invalid_temperature"
        assert result["field"] == "T_current"
        assert result["value"] == 55.0

    @pytest.mark.asyncio
    async def test_sensor_offline(self, model, monkeypatch):
        """测试传感器离线时拒绝预测"""
        monkeypatch.setattr(model, "_get_zone", AsyncMock(return_value={"zone": _zone()}))
        monkeypatch.setattr(
            model,
            "_load_historical_data",
            AsyncMock(
                return_value={
                    "q_it": [100.0] * 12,
                    "t_ambient": [24.0] * 12,
                    "t_current": 24.0,
                    "t_outlet": None,
                    "t_outdoor": None,
                }
            ),
        )
        monkeypatch.setattr(
            model,
            "_get_latest_temp_timestamp",
            AsyncMock(return_value=datetime.now() - timedelta(hours=2)),
        )

        result = await model.predict_temperature(zone_id=996, hours=1.0)

        assert result["error"] == "sensor_offline"
        assert result["sensor"] == "inlet"


class TestThermalModelPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_performance_typical_scenario(self, model, monkeypatch):
        """测试典型场景性能（1 小时预测 < 200ms）"""
        _configure_successful_prediction(model, monkeypatch)

        start = time.time()
        result = await model.predict_temperature(zone_id=1, hours=1.0)
        elapsed = time.time() - start

        assert "error" not in result
        assert elapsed < 1.0  # < 1s（架构标准）
        # 典型场景应该 < 200ms，但这里放宽到 500ms 以适应测试环境
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_performance_extreme_scenario(self, model, monkeypatch):
        """测试极限场景性能（24 小时预测 < 5s）"""
        _configure_successful_prediction(model, monkeypatch)

        start = time.time()
        result = await model.predict_temperature(zone_id=1, hours=24.0)
        elapsed = time.time() - start

        assert "error" not in result
        assert elapsed < 5.0  # < 5s


class TestThermalModelNumericalStability:
    """数值稳定性测试"""

    @pytest.mark.asyncio
    async def test_numerical_stability_extreme_rc(self, model, monkeypatch):
        """测试极端 RC 参数时温度不发散"""
        _configure_successful_prediction(model, monkeypatch, thermal_r=0.01, thermal_c=100.0)

        result = await model.predict_temperature(zone_id=2, hours=24.0)

        assert "error" not in result
        temps = result["temperature_trajectory"]
        # 所有温度应该在 0-50°C 范围内
        assert all(0 <= t <= 50 for t in temps), f"Temperature out of bounds: {temps}"
        # 温度不应该发散（变化不应该太剧烈）
        max_temp = max(temps)
        min_temp = min(temps)
        assert max_temp - min_temp < 30, f"Temperature divergence detected: {max_temp} - {min_temp}"
