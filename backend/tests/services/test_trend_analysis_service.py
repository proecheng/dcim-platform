"""
趋势分析服务单元测试
Story 25.7: 趋势分析与多传感器融合
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diagnosis.trend_analysis_service import TrendAnalysisService
from app.models.diagnosis import TrendWarning
from app.models.point import Point


@pytest.fixture
def mock_db():
    """模拟数据库会话"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_redis():
    """模拟 Redis 客户端"""
    redis = MagicMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def trend_service(mock_db, mock_redis):
    """创建趋势分析服务实例"""
    service = TrendAnalysisService(mock_db)
    service.redis = mock_redis
    return service


class TestAnalyzePointTrend:
    """测试 analyze_point_trend 方法"""

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_none(self, trend_service, mock_db):
        """测试数据不足时返回 None"""
        # 模拟点位信息
        point = Point(id=1, name="T-01", unit="℃", enabled=True)
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = point

        # 模拟查询结果：只有 3 天数据（不足 5 天）
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(avg_value=25.0, sample_count=15),
            MagicMock(avg_value=25.5, sample_count=12),
            MagicMock(avg_value=26.0, sample_count=10),
        ]
        mock_db.execute.return_value = mock_result

        result = await trend_service.analyze_point_trend(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_trend_returns_none(self, trend_service, mock_db):
        """测试无明显趋势时返回 None"""
        # 模拟点位信息
        point = Point(id=1, name="T-01", unit="℃", enabled=True)

        # 模拟查询结果：7 天数据，但无明显趋势（波动在容差范围内）
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(avg_value=25.0, sample_count=15),
            MagicMock(avg_value=25.1, sample_count=12),
            MagicMock(avg_value=24.9, sample_count=14),
            MagicMock(avg_value=25.0, sample_count=13),
            MagicMock(avg_value=25.1, sample_count=11),
            MagicMock(avg_value=25.0, sample_count=16),
            MagicMock(avg_value=25.1, sample_count=10),
        ]

        # 配置 mock_db.execute 返回不同结果
        execute_results = [mock_result, MagicMock()]
        execute_results[1].scalar_one_or_none.return_value = point
        execute_results[1].fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=execute_results)

        result = await trend_service.analyze_point_trend(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_increasing_trend_generates_warning(self, trend_service, mock_db):
        """测试上升趋势生成预警"""
        # 模拟点位信息
        point = Point(id=1, name="T-01", unit="℃", enabled=True)

        # 模拟查询结果：7 天数据，明显上升趋势
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(avg_value=25.0, sample_count=15),
            MagicMock(avg_value=25.2, sample_count=12),
            MagicMock(avg_value=25.4, sample_count=14),
            MagicMock(avg_value=25.6, sample_count=13),
            MagicMock(avg_value=25.8, sample_count=11),
            MagicMock(avg_value=26.0, sample_count=16),
            MagicMock(avg_value=26.2, sample_count=10),
        ]

        # 配置 mock_db.execute 返回不同结果
        execute_results = [mock_result, MagicMock(), MagicMock()]
        execute_results[1].scalar_one_or_none.return_value = point
        execute_results[2].fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=execute_results)

        result = await trend_service.analyze_point_trend(1)

        assert result is not None
        assert isinstance(result, TrendWarning)
        assert result.trend_type == "上升"
        assert result.point_id == 1
        assert result.total_change > 0.5  # 超过阈值

    @pytest.mark.asyncio
    async def test_decreasing_trend_generates_warning(self, trend_service, mock_db):
        """测试下降趋势生成预警"""
        # 模拟点位信息
        point = Point(id=1, name="T-01", unit="℃", enabled=True)

        # 模拟查询结果：7 天数据，明显下降趋势
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(avg_value=26.0, sample_count=15),
            MagicMock(avg_value=25.8, sample_count=12),
            MagicMock(avg_value=25.6, sample_count=14),
            MagicMock(avg_value=25.4, sample_count=13),
            MagicMock(avg_value=25.2, sample_count=11),
            MagicMock(avg_value=25.0, sample_count=16),
            MagicMock(avg_value=24.8, sample_count=10),
        ]

        # 配置 mock_db.execute 返回不同结果
        execute_results = [mock_result, MagicMock(), MagicMock()]
        execute_results[1].scalar_one_or_none.return_value = point
        execute_results[2].fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=execute_results)

        result = await trend_service.analyze_point_trend(1)

        assert result is not None
        assert isinstance(result, TrendWarning)
        assert result.trend_type == "下降"
        assert result.point_id == 1

    @pytest.mark.asyncio
    async def test_humidity_uses_correct_view(self, trend_service, mock_db):
        """测试湿度点位使用正确的视图"""
        # 模拟湿度点位
        point = Point(id=2, name="H-01", unit="%RH", enabled=True)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(avg_value=50.0, sample_count=15),
            MagicMock(avg_value=51.0, sample_count=12),
            MagicMock(avg_value=52.0, sample_count=14),
        ]

        execute_results = [mock_result, MagicMock()]
        execute_results[1].scalar_one_or_none.return_value = point

        mock_db.execute = AsyncMock(side_effect=execute_results)

        await trend_service.analyze_point_trend(2)

        # 验证使用了 humidity_7d_avg 视图
        call_args = mock_db.execute.call_args_list[0][0][0]
        assert "humidity_7d_avg" in str(call_args)

    @pytest.mark.asyncio
    async def test_point_not_found_returns_none(self, trend_service, mock_db):
        """测试点位不存在时返回 None"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await trend_service.analyze_point_trend(999)

        assert result is None


class TestContinuousInsufficientData:
    """测试连续数据不足检测"""

    @pytest.mark.asyncio
    async def test_redis_unavailable_skips_check(self, trend_service, mock_db):
        """测试 Redis 不可用时跳过检查"""
        trend_service.redis = None

        # 不应抛出异常
        await trend_service._check_continuous_insufficient_data(1, 2)

    @pytest.mark.asyncio
    async def test_creates_alarm_after_3_consecutive_failures(self, trend_service, mock_db, mock_redis):
        """测试连续 3 次数据不足后创建告警"""
        mock_redis.incr.return_value = 3

        with patch.object(trend_service, '_create_system_alarm', new_callable=AsyncMock) as mock_alarm:
            await trend_service._check_continuous_insufficient_data(1, 2)

            mock_alarm.assert_called_once()
            assert "连续 3 小时数据不足" in mock_alarm.call_args[1]['message']


class TestGetTrendThreshold:
    """测试趋势阈值读取"""

    @pytest.mark.asyncio
    async def test_temperature_threshold(self, trend_service, mock_db):
        """测试温度阈值读取"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(config_value="0.5")
        mock_db.execute = AsyncMock(return_value=mock_result)

        threshold = await trend_service._get_trend_threshold("℃")

        assert threshold == 0.5

    @pytest.mark.asyncio
    async def test_humidity_threshold(self, trend_service, mock_db):
        """测试湿度阈值读取"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(config_value="3.0")
        mock_db.execute = AsyncMock(return_value=mock_result)

        threshold = await trend_service._get_trend_threshold("%RH")

        assert threshold == 3.0

    @pytest.mark.asyncio
    async def test_default_threshold_when_config_missing(self, trend_service, mock_db):
        """测试配置缺失时使用默认阈值"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        threshold = await trend_service._get_trend_threshold("℃")

        assert threshold == 0.5  # 默认值
