"""
Story 25.3: UPS电池SOH预测服务单元测试
"""
import pytest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager

from app.services.diagnosis.battery_soh_service import (
    clip,
    get_rated_parameters,
    get_soh_weights,
    get_latest_soh,
    get_latest_soh_record,
    get_point_latest_value,
    _get_point_id_by_type,
    calculate_soh,
)


class TestClipFunction:
    """测试 clip 工具函数"""

    def test_clip_within_range(self):
        assert clip(50.0, 0.0, 100.0) == 50.0

    def test_clip_below_min(self):
        assert clip(-10.0, 0.0, 100.0) == 0.0

    def test_clip_above_max(self):
        assert clip(150.0, 0.0, 100.0) == 100.0

    def test_clip_at_boundaries(self):
        assert clip(0.0, 0.0, 100.0) == 0.0
        assert clip(100.0, 0.0, 100.0) == 100.0


def _mock_async_session(mock_db):
    """创建模拟的 async_session 上下文管理器"""
    @asynccontextmanager
    async def _session():
        yield mock_db
    return _session


@pytest.mark.asyncio
class TestGetRatedParameters:
    """测试额定参数查询"""

    async def test_get_rated_parameters_success(self):
        """测试成功获取额定参数"""
        # Mock 数据库返回配置
        mock_config = MagicMock()
        mock_config.config_value = json.dumps({
            "rated_resistance_mohm": 50.0,
            "rated_cycle_count": 1200
        })

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_rated_parameters(device_id=1)

        assert result is not None
        assert result["rated_resistance_mohm"] == 50.0
        assert result["rated_cycle_count"] == 1200

    async def test_get_rated_parameters_not_found(self):
        """测试配置不存在"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_rated_parameters(device_id=1)

        assert result is None


@pytest.mark.asyncio
class TestGetSOHWeights:
    """测试 SOH 权重配置查询"""

    async def test_get_soh_weights_existing(self):
        """测试获取已存在的权重配置"""
        mock_config = MagicMock()
        mock_config.config_value = json.dumps({"w_r": 0.7, "w_c": 0.3, "version": "v1.1"})

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_config
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_soh_weights()

        assert result["w_r"] == 0.7
        assert result["w_c"] == 0.3
        assert result["version"] == "v1.1"

    async def test_get_soh_weights_auto_initialize(self):
        """测试自动初始化默认权重"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_soh_weights()

        assert result["w_r"] == 0.6
        assert result["w_c"] == 0.4
        assert result["version"] == "v1.0"


@pytest.mark.asyncio
class TestGetLatestSOH:
    """测试最新 SOH 查询"""

    async def test_get_latest_soh_no_record(self):
        """测试无记录时返回 None"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_latest_soh(device_id=1)

        assert result is None

    async def test_get_latest_soh_record_found(self):
        """测试有记录时返回 SOH 值"""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 85.5
        mock_db.execute.return_value = mock_result

        with patch("app.services.diagnosis.battery_soh_service.async_session", _mock_async_session(mock_db)):
            result = await get_latest_soh(device_id=1)

        assert result == 85.5
