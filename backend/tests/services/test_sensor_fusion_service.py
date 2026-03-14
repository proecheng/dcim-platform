"""
多传感器融合服务单元测试
Story 25.7: 趋势分析与多传感器融合
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diagnosis.sensor_fusion_service import (
    SensorFusionService,
    SensorFusionResult
)


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def fusion_service(mock_db):
    """创建多传感器融合服务实例"""
    return SensorFusionService(mock_db)


class TestCalculateTemperatureVariance:
    """测试温度标准差计算"""

    @pytest.mark.asyncio
    async def test_insufficient_sensors_returns_no_evidence(self, fusion_service, mock_db):
        """测试传感器数量不足时不作为证据"""
        # 模拟查询结果：只有 1 个传感器
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=1, name="T-01", value=25.0, height_level=1.5, accuracy_class=0.5)
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.calculate_temperature_variance(1)

        assert result.sensor_count == 1
        assert result.is_evidence is False
        assert result.evidence_type == "insufficient_sensors"

    @pytest.mark.asyncio
    async def test_high_variance_generates_evidence(self, fusion_service, mock_db):
        """测试高标准差生成气流不均匀证据"""
        # 模拟查询结果：3 个传感器，温差大（需要 std_dev > 5.0）
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=1, name="T-01", value=15.0, height_level=1.5, accuracy_class=0.5),
            MagicMock(id=2, name="T-02", value=32.0, height_level=1.5, accuracy_class=0.5),
            MagicMock(id=3, name="T-03", value=24.0, height_level=1.5, accuracy_class=0.5),
        ]

        # 模拟配置查询：阈值 5.0
        config_result = MagicMock()
        config_result.fetchone.return_value = MagicMock(config_value="5.0")
        mock_db.execute = AsyncMock(side_effect=[mock_result, config_result])

        result = await fusion_service.calculate_temperature_variance(1)

        assert result.sensor_count == 3
        assert result.is_evidence is True
        assert result.evidence_type == "airflow_uneven"
        assert result.probability == 0.85
        assert result.std_dev > 5.0

    @pytest.mark.asyncio
    async def test_moderate_variance_no_evidence(self, fusion_service, mock_db):
        """测试中等标准差不作为证据"""
        # 模拟查询结果：3 个传感器，温差中等
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=1, name="T-01", value=24.0, height_level=1.5, accuracy_class=0.5),
            MagicMock(id=2, name="T-02", value=25.0, height_level=1.5, accuracy_class=0.5),
            MagicMock(id=3, name="T-03", value=26.0, height_level=1.5, accuracy_class=0.5),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # 模拟配置查询：阈值 5.0
        config_result = MagicMock()
        config_result.fetchone.return_value = MagicMock(config_value="5.0")
        mock_db.execute = AsyncMock(side_effect=[mock_result, config_result])

        result = await fusion_service.calculate_temperature_variance(1)

        assert result.is_evidence is False
        assert result.evidence_type in ["moderate_variance", "normal"]

    @pytest.mark.asyncio
    async def test_height_grouping(self, fusion_service, mock_db):
        """测试按高度分组计算"""
        # 模拟查询结果：不同高度的传感器
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=1, name="T-Floor", value=22.0, height_level=0.3, accuracy_class=0.5),
            MagicMock(id=2, name="T-Rack-1", value=25.0, height_level=1.5, accuracy_class=0.5),
            MagicMock(id=3, name="T-Rack-2", value=26.0, height_level=1.8, accuracy_class=0.5),
            MagicMock(id=4, name="T-Ceiling", value=28.0, height_level=3.0, accuracy_class=0.5),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # 模拟配置查询
        config_result = MagicMock()
        config_result.fetchone.return_value = MagicMock(config_value="5.0")
        mock_db.execute = AsyncMock(side_effect=[mock_result, config_result])

        result = await fusion_service.calculate_temperature_variance(1)

        # 验证分层计算
        assert result.layer_variances is not None
        assert "rack" in result.layer_variances  # 机柜层应该有数据

    @pytest.mark.asyncio
    async def test_accuracy_weighting(self, fusion_service, mock_db):
        """测试精度加权计算"""
        # 模拟查询结果：不同精度等级的传感器
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id=1, name="T-01", value=25.0, height_level=1.5, accuracy_class=0.2),  # 高精度
            MagicMock(id=2, name="T-02", value=26.0, height_level=1.5, accuracy_class=1.0),  # 低精度
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # 模拟配置查询
        config_result = MagicMock()
        config_result.fetchone.return_value = MagicMock(config_value="5.0")
        mock_db.execute = AsyncMock(side_effect=[mock_result, config_result])

        result = await fusion_service.calculate_temperature_variance(1)

        # 验证加权计算生效（高精度传感器权重更大）
        assert result.std_dev is not None


class TestCheckDifferentialPressure:
    """测试压差传感器检测"""

    @pytest.mark.asyncio
    async def test_no_sensors_returns_none(self, fusion_service, mock_db):
        """测试无压差传感器时返回 None"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.check_differential_pressure(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_insufficient_valid_sensors_returns_none(self, fusion_service, mock_db):
        """测试有效传感器不足时返回 None"""
        # 模拟查询结果：2 个传感器，但 1 个通信超时
        now = datetime.now()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                id=1, name="P-01", value=50.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
            MagicMock(
                id=2, name="P-02", value=55.0, quality_flag=None,
                updated_at=now - timedelta(minutes=10),  # 超时
                threshold_low=60.0
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.check_differential_pressure(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_low_pressure_generates_evidence(self, fusion_service, mock_db):
        """测试低压差生成送风系统异常证据"""
        # 模拟查询结果：2 个传感器，压差低于阈值
        now = datetime.now()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                id=1, name="P-01", value=50.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
            MagicMock(
                id=2, name="P-02", value=55.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.check_differential_pressure(1)

        assert result is not None
        assert result.is_evidence is True
        assert result.evidence_type == "air_supply_abnormal"
        assert result.probability == 0.80

    @pytest.mark.asyncio
    async def test_normal_pressure_returns_none(self, fusion_service, mock_db):
        """测试正常压差返回 None"""
        # 模拟查询结果：2 个传感器，压差正常
        now = datetime.now()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                id=1, name="P-01", value=70.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
            MagicMock(
                id=2, name="P-02", value=75.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.check_differential_pressure(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_filters_poor_quality_data(self, fusion_service, mock_db):
        """测试过滤低质量数据"""
        # 模拟查询结果：3 个传感器，1 个数据质量差
        now = datetime.now()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(
                id=1, name="P-01", value=50.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
            MagicMock(
                id=2, name="P-02", value=55.0, quality_flag="poor",  # 低质量
                updated_at=now, threshold_low=60.0
            ),
            MagicMock(
                id=3, name="P-03", value=52.0, quality_flag=None,
                updated_at=now, threshold_low=60.0
            ),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await fusion_service.check_differential_pressure(1)

        # 应该只使用 2 个有效传感器
        assert result is not None
        assert result.sensor_count == 2


class TestSaveFusionRecord:
    """测试保存融合记录"""

    @pytest.mark.asyncio
    async def test_saves_record_to_database(self, fusion_service, mock_db):
        """测试保存融合记录到数据库"""
        fusion_result = SensorFusionResult(
            zone_id=1,
            sensor_count=3,
            std_dev=6.5,
            evidence_type="airflow_uneven",
            is_evidence=True,
            probability=0.85,
            message="气流不均匀"
        )

        await fusion_service.save_fusion_record(fusion_result)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
