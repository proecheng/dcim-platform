"""
传感器元数据服务单元测试
Story 25.5: 传感器元数据与精度加权
"""

import asyncio
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.diagnosis.sensor_metadata_service import (
    SensorMetadataCache,
    get_sensor_weight,
    check_calibration_status,
    check_expired_calibrations
)
from app.models.diagnosis import SensorMetadata, CalibrationStatus


class TestSensorMetadataCache:
    """传感器元数据缓存测试"""

    @pytest.fixture(autouse=True)
    async def setup_and_teardown(self):
        """每个测试前后清理缓存"""
        SensorMetadataCache._cache.clear()
        yield
        SensorMetadataCache._cache.clear()

    @pytest.mark.asyncio
    async def test_load_all_success(self, async_db):
        """测试全量加载成功"""
        # 准备测试数据
        metadata1 = SensorMetadata(
            point_id=1001,
            accuracy_class=0.2,
            calibration_date=date.today() - timedelta(days=100),
            calibration_interval_days=365
        )
        metadata2 = SensorMetadata(
            point_id=1002,
            accuracy_class=0.5,
            calibration_date=None,
            calibration_interval_days=365
        )

        # Mock 数据库查询
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [metadata1, metadata2]
        async_db.execute = AsyncMock(return_value=mock_result)

        # 执行加载
        await SensorMetadataCache.load_all(async_db)

        # 验证缓存
        assert len(SensorMetadataCache._cache) == 2
        assert SensorMetadataCache._cache[1001] == metadata1
        assert SensorMetadataCache._cache[1002] == metadata2

    @pytest.mark.asyncio
    async def test_load_all_empty(self, async_db):
        """测试加载空数据"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        async_db.execute = AsyncMock(return_value=mock_result)

        await SensorMetadataCache.load_all(async_db)

        assert len(SensorMetadataCache._cache) == 0

    @pytest.mark.asyncio
    async def test_load_all_exception_handling(self, async_db):
        """测试加载异常处理"""
        async_db.execute = AsyncMock(side_effect=Exception("Database error"))

        # 不应抛出异常
        await SensorMetadataCache.load_all(async_db)

        # 缓存应为空
        assert len(SensorMetadataCache._cache) == 0

    def test_get_existing_metadata(self):
        """测试获取已存在的元数据"""
        metadata = SensorMetadata(
            point_id=1001,
            accuracy_class=0.2,
            calibration_date=date.today(),
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1001] = metadata

        result = SensorMetadataCache.get(1001)

        assert result == metadata

    def test_get_nonexistent_metadata(self):
        """测试获取不存在的元数据"""
        result = SensorMetadataCache.get(9999)

        assert result is None


class TestGetSensorWeight:
    """传感器权重计算测试"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """每个测试前后清理缓存"""
        SensorMetadataCache._cache.clear()
        yield
        SensorMetadataCache._cache.clear()

    def test_weight_no_metadata(self):
        """测试无元数据时返回默认权重"""
        weight = get_sensor_weight(9999)

        assert weight == 0.85

    def test_weight_accuracy_02(self):
        """测试 0.2 级精度权重"""
        metadata = SensorMetadata(
            point_id=1001,
            accuracy_class=0.2,
            calibration_date=date.today() - timedelta(days=100),
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1001] = metadata

        weight = get_sensor_weight(1001)

        assert weight == 1.0

    def test_weight_accuracy_05(self):
        """测试 0.5 级精度权重"""
        metadata = SensorMetadata(
            point_id=1002,
            accuracy_class=0.5,
            calibration_date=date.today() - timedelta(days=100),
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1002] = metadata

        weight = get_sensor_weight(1002)

        assert weight == 0.9

    def test_weight_accuracy_10(self):
        """测试 1.0 级精度权重"""
        metadata = SensorMetadata(
            point_id=1003,
            accuracy_class=1.0,
            calibration_date=date.today() - timedelta(days=100),
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1003] = metadata

        weight = get_sensor_weight(1003)

        assert weight == 0.8

    def test_weight_not_calibrated(self):
        """测试未校准传感器（calibration_date=NULL）"""
        metadata = SensorMetadata(
            point_id=1004,
            accuracy_class=0.5,
            calibration_date=None,
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1004] = metadata

        weight = get_sensor_weight(1004)

        # 未校准时使用基础权重，不降级
        assert weight == 0.9

    def test_weight_calibration_expired(self):
        """测试校准过期时权重降级"""
        metadata = SensorMetadata(
            point_id=1005,
            accuracy_class=0.5,
            calibration_date=date.today() - timedelta(days=400),  # 过期 35 天
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1005] = metadata

        weight = get_sensor_weight(1005)

        # 过期时权重降级为基础权重 × 0.6
        assert weight == 0.9 * 0.6

    def test_weight_calibration_valid(self):
        """测试校准有效时使用基础权重"""
        metadata = SensorMetadata(
            point_id=1006,
            accuracy_class=0.2,
            calibration_date=date.today() - timedelta(days=100),
            calibration_interval_days=365
        )
        SensorMetadataCache._cache[1006] = metadata

        weight = get_sensor_weight(1006)

        assert weight == 1.0


class TestCheckCalibrationStatus:
    """校准状态检查测试"""

    @pytest.mark.asyncio
    async def test_status_no_metadata(self, async_db):
        """测试无元数据状态"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        async_db.execute = AsyncMock(return_value=mock_result)

        status = await check_calibration_status(1001, async_db)

        assert status["point_id"] == 1001
        assert status["status"] == CalibrationStatus.NO_METADATA.value
        assert status["expired_days"] is None
        assert status["calibration_date"] is None
        assert status["next_calibration_date"] is None

    @pytest.mark.asyncio
    async def test_status_not_calibrated(self, async_db):
        """测试未校准状态"""
        metadata = SensorMetadata(
            point_id=1002,
            accuracy_class=0.5,
            calibration_date=None,
            calibration_interval_days=365
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = metadata
        async_db.execute = AsyncMock(return_value=mock_result)

        status = await check_calibration_status(1002, async_db)

        assert status["point_id"] == 1002
        assert status["status"] == CalibrationStatus.NOT_CALIBRATED.value
        assert status["expired_days"] is None
        assert status["calibration_date"] is None
        assert status["next_calibration_date"] is None

    @pytest.mark.asyncio
    async def test_status_valid(self, async_db):
        """测试校准有效状态"""
        calibration_date = date.today() - timedelta(days=100)
        metadata = SensorMetadata(
            point_id=1003,
            accuracy_class=0.5,
            calibration_date=calibration_date,
            calibration_interval_days=365
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = metadata
        async_db.execute = AsyncMock(return_value=mock_result)

        status = await check_calibration_status(1003, async_db)

        assert status["point_id"] == 1003
        assert status["status"] == CalibrationStatus.VALID.value
        assert status["expired_days"] is None
        assert status["calibration_date"] == calibration_date
        assert status["next_calibration_date"] == calibration_date + timedelta(days=365)

    @pytest.mark.asyncio
    async def test_status_expired(self, async_db):
        """测试校准过期状态"""
        calibration_date = date.today() - timedelta(days=400)
        metadata = SensorMetadata(
            point_id=1004,
            accuracy_class=0.5,
            calibration_date=calibration_date,
            calibration_interval_days=365
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = metadata
        async_db.execute = AsyncMock(return_value=mock_result)

        status = await check_calibration_status(1004, async_db)

        assert status["point_id"] == 1004
        assert status["status"] == CalibrationStatus.EXPIRED.value
        assert status["expired_days"] == 35  # 400 - 365
        assert status["calibration_date"] == calibration_date
        assert status["next_calibration_date"] == calibration_date + timedelta(days=365)
