"""
Story 25.3: UPS电池SOH预测服务单元测试
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

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


@pytest.mark.asyncio
class TestGetRatedParameters:
    """测试额定参数查询"""

    async def test_get_rated_parameters_success(self, db_session):
        """测试成功获取额定参数"""
        from app.models.config import SystemConfig
        import json

        # 创建测试配置
        config = SystemConfig(
            config_group="diagnosis",
            config_key="ups_rated_params",
            config_value=json.dumps({
                "rated_resistance_mohm": 50.0,
                "rated_cycle_count": 1200
            }),
            value_type="json",
            description="Test config",
            is_editable=True
        )
        db_session.add(config)
        await db_session.commit()

        # 测试查询
        result = await get_rated_parameters(device_id=1)
        assert result is not None
        assert result["rated_resistance_mohm"] == 50.0
        assert result["rated_cycle_count"] == 1200

    async def test_get_rated_parameters_not_found(self, db_session):
        """测试配置不存在"""
        result = await get_rated_parameters(device_id=1)
        assert result is None


@pytest.mark.asyncio
class TestGetSOHWeights:
    """测试 SOH 权重配置查询"""

    async def test_get_soh_weights_existing(self, db_session):
        """测试获取已存在的权重配置"""
        from app.models.config import SystemConfig
        import json

        # 创建测试配置
        config = SystemConfig(
            config_group="diagnosis",
            config_key="soh_weights",
            config_value=json.dumps({"w_r": 0.7, "w_c": 0.3, "version": "v1.1"}),
            value_type="json",
            description="Test weights",
            is_editable=True
        )
        db_session.add(config)
        await db_session.commit()

        # 测试查询
        result = await get_soh_weights()
        assert result["w_r"] == 0.7
        assert result["w_c"] == 0.3
        assert result["version"] == "v1.1"

    async def test_get_soh_weights_auto_initialize(self, db_session):
        """测试自动初始化默认权重"""
        result = await get_soh_weights()
        assert result["w_r"] == 0.6
        assert result["w_c"] == 0.4
        assert result["version"] == "v1.0"


@pytest.mark.asyncio
class TestGetLatestSOH:
    """测试最新 SOH 查询"""

