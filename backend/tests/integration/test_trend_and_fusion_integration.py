"""
趋势分析与多传感器融合集成测试
Story 25.7: 趋势分析与多传感器融合
"""

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import TrendWarning, SensorFusionRecord
from app.models.point import Point
from app.models.topology_config import CoolingZone
from app.services.diagnosis.sensor_fusion_service import SensorFusionService
from app.services.diagnosis.trend_analysis_service import TrendAnalysisService


@pytest.mark.integration
class TestTrendAnalysisIntegration:
    """趋势分析集成测试"""

    @pytest.mark.asyncio
    async def test_complete_trend_analysis_flow(self, async_db: AsyncSession):
        """测试完整的趋势分析流程"""
        # 1. 创建测试点位
        point = Point(
            point_code="T-TEST-01",
            point_name="测试温度点位",
            unit="℃",
            point_type="AI",
            is_enabled=True,
        )
        async_db.add(point)
        await async_db.commit()
        await async_db.refresh(point)

        # 2. 创建趋势分析服务
        trend_service = TrendAnalysisService(async_db, redis=None)

        # 3. 模拟数据不足场景
        warning = await trend_service.analyze_point_trend(point.id)
        assert warning is None  # 数据不足应返回 None

        # 4. 验证点位信息查询
        point_info = await trend_service._get_point_info(point.id)
        assert point_info is not None
        assert point_info.id == point.id

        # 5. 验证阈值读取
        threshold = await trend_service._get_trend_threshold("℃")
        assert threshold > 0

    @pytest.mark.asyncio
    async def test_trend_warning_persistence(self, async_db: AsyncSession):
        """测试趋势预警持久化"""
        # 1. 创建测试点位
        point = Point(
            point_code="T-TEST-02",
            point_name="测试温度点位2",
            unit="℃",
            point_type="AI",
            is_enabled=True,
        )
        async_db.add(point)
        await async_db.commit()
        await async_db.refresh(point)

        # 2. 创建趋势预警
        warning = TrendWarning(
            point_id=point.id,
            trend_type="上升",
            start_value=25.0,
            end_value=26.5,
            total_change=1.5,
            message="测试预警",
            level="info",
            detected_at=datetime.now(),
        )
        async_db.add(warning)
        await async_db.commit()

        # 3. 查询验证
        result = await async_db.execute(select(TrendWarning).where(TrendWarning.point_id == point.id))
        saved_warning = result.scalar_one()

        assert saved_warning.trend_type == "上升"
        assert saved_warning.total_change == 1.5
        assert saved_warning.acknowledged is False

    @pytest.mark.asyncio
    async def test_trend_warning_acknowledgement(self, async_db: AsyncSession):
        """测试趋势预警确认"""
        # 1. 创建测试点位和预警
        point = Point(
            point_code="T-TEST-03",
            point_name="测试温度点位3",
            unit="℃",
            point_type="AI",
            is_enabled=True,
        )
        async_db.add(point)
        await async_db.commit()
        await async_db.refresh(point)

        warning = TrendWarning(
            point_id=point.id,
            trend_type="下降",
            start_value=26.0,
            end_value=24.5,
            total_change=1.5,
            message="测试预警",
            level="info",
            detected_at=datetime.now(),
        )
        async_db.add(warning)
        await async_db.commit()
        await async_db.refresh(warning)

        # 2. 确认预警
        warning.acknowledged = True
        warning.acknowledged_by = 1
        warning.acknowledged_at = datetime.now()
        await async_db.commit()

        # 3. 验证确认状态
        result = await async_db.execute(select(TrendWarning).where(TrendWarning.id == warning.id))
        updated_warning = result.scalar_one()

        assert updated_warning.acknowledged is True
        assert updated_warning.acknowledged_by == 1
        assert updated_warning.acknowledged_at is not None


@pytest.mark.integration
class TestSensorFusionIntegration:
    """多传感器融合集成测试"""

    @pytest.mark.asyncio
    async def test_complete_sensor_fusion_flow(self, async_db: AsyncSession):
        """测试完整的多传感器融合流程"""
        # 1. 创建融合服务
        fusion_service = SensorFusionService(async_db)

        # 2. 测试温度标准差计算（无传感器场景）
        result = await fusion_service.calculate_temperature_variance(999)

        assert result.sensor_count == 0
        assert result.is_evidence is False

        # 3. 测试压差传感器检测（无传感器场景）
        pressure_result = await fusion_service.check_differential_pressure(999)

        assert pressure_result is None

    @pytest.mark.asyncio
    async def test_fusion_record_persistence(self, async_db: AsyncSession):
        """测试融合记录持久化"""
        from app.services.diagnosis.sensor_fusion_service import SensorFusionResult

        # 1. 创建融合服务与关联制冷区域
        fusion_service = SensorFusionService(async_db)
        zone = CoolingZone(zone_code="TEST-FUSION-ZONE", zone_name="测试融合区域")
        async_db.add(zone)
        await async_db.flush()

        # 2. 创建融合结果
        fusion_result = SensorFusionResult(
            zone_id=zone.id,
            sensor_count=3,
            std_dev=6.5,
            evidence_type="airflow_uneven",
            is_evidence=True,
            probability=0.85,
            message="测试融合记录",
        )

        # 3. 保存融合记录
        await fusion_service.save_fusion_record(fusion_result)

        # 4. 查询验证
        result = await async_db.execute(select(SensorFusionRecord).where(SensorFusionRecord.zone_id == zone.id))
        records = result.scalars().all()

        assert len(records) > 0
        latest_record = records[-1]
        assert latest_record.sensor_count == 3
        assert latest_record.std_dev == 6.5
        assert latest_record.is_evidence is True


@pytest.mark.integration
class TestDiagnosisEngineIntegration:
    """诊断引擎集成测试"""

    @pytest.mark.asyncio
    async def test_fault_tree_integration(self, async_db: AsyncSession):
        """测试故障树集成多传感器融合和趋势预警"""
        # 注意：此测试需要完整的故障树数据，这里仅测试服务可用性

        # 1. 创建融合服务
        fusion_service = SensorFusionService(async_db)

        # 2. 测试融合服务可调用
        result = await fusion_service.calculate_temperature_variance(1)
        assert result is not None

        # 3. 创建趋势分析服务
        trend_service = TrendAnalysisService(async_db, redis=None)

        # 4. 测试趋势服务可调用
        warnings = await trend_service.get_recent_warnings(zone_id=1, hours=24)
        assert isinstance(warnings, list)

    @pytest.mark.asyncio
    async def test_evidence_collection_with_fusion(self, async_db: AsyncSession):
        """测试证据收集集成融合数据"""
        # 此测试验证融合服务和趋势服务可以被故障树引擎调用
        # 实际的故障树推理需要完整的故障树数据和告警事件

        from app.services.diagnosis.sensor_fusion_service import get_sensor_fusion_service
        from app.services.diagnosis.trend_analysis_service import get_trend_analysis_service

        # 1. 获取服务实例
        fusion_service = get_sensor_fusion_service(async_db)
        trend_service = get_trend_analysis_service(async_db, redis=None)

        assert fusion_service is not None
        assert trend_service is not None

        # 2. 验证服务方法可调用
        temp_variance = await fusion_service.calculate_temperature_variance(1)
        assert temp_variance is not None

        await fusion_service.check_differential_pressure(1)
        # pressure_check 可能为 None（无传感器）

        recent_warnings = await trend_service.get_recent_warnings(zone_id=1, hours=24)
        assert isinstance(recent_warnings, list)


@pytest.mark.integration
class TestScheduledTaskIntegration:
    """定时任务集成测试"""

    @pytest.mark.asyncio
    async def test_trend_analysis_task_execution(self, async_db: AsyncSession):
        """测试趋势分析定时任务执行"""
        # 模拟定时任务执行流程

        # 1. 查询所有启用的温湿度点位
        result = await async_db.execute(
            select(Point).where(
                Point.is_enabled.is_(True),
                (Point.unit.like("%℃%")) | (Point.unit.like("%°C%")) | (Point.unit.like("%RH%")),
            )
        )
        points = result.scalars().all()

        # 2. 创建趋势分析服务
        trend_service = TrendAnalysisService(async_db, redis=None)

        # 3. 对每个点位执行趋势分析
        warnings = []
        for point in points[:5]:  # 限制测试数量
            warning = await trend_service.analyze_point_trend(point.id)
            if warning:
                warnings.append(warning)
                async_db.add(warning)

        await async_db.commit()

        # 4. 验证任务执行成功（无异常）
        assert True  # 如果执行到这里说明没有抛出异常
