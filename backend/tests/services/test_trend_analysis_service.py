"""
趋势分析服务单元测试
Story 25.7: 趋势分析与多传感器融合
"""

import pytest
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
    return TrendAnalysisService(mock_db, redis=mock_redis)


def _make_point(id=1, point_name="T-01", unit="℃"):
    """创建模拟的 Point 对象"""
    point = MagicMock(spec=Point)
    point.id = id
    point.point_name = point_name
    point.unit = unit
    point.is_enabled = True
    return point


class TestAnalyzePointTrend:
    """测试 analyze_point_trend 方法"""

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_none(self, trend_service, mock_db):
        """测试数据不足时返回 None"""
        point = _make_point(id=1, point_name="T-01", unit="℃")

        # 调用顺序：1. _get_point_info -> scalar_one_or_none, 2. 数据查询 -> fetchall
        point_result = MagicMock()
        point_result.scalar_one_or_none.return_value = point

        data_result = MagicMock()
        data_result.fetchall.return_value = [
            MagicMock(avg_value=25.0, sample_count=15),
            MagicMock(avg_value=25.5, sample_count=12),
            MagicMock(avg_value=26.0, sample_count=10),
        ]

        mock_db.execute = AsyncMock(side_effect=[point_result, data_result])

        result = await trend_service.analyze_point_trend(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_trend_returns_none(self, trend_service, mock_db):
        """测试无明显趋势时返回 None"""
        point = _make_point(id=1, point_name="T-01", unit="℃")

        # 调用顺序：1. point_info, 2. data, 3. threshold
        point_result = MagicMock()
        point_result.scalar_one_or_none.return_value = point

        data_result = MagicMock()
        data_result.fetchall.return_value = [
            MagicMock(avg_value=25.0, sample_count=15),
            MagicMock(avg_value=25.1, sample_count=12),
            MagicMock(avg_value=24.9, sample_count=14),
            MagicMock(avg_value=25.0, sample_count=13),
            MagicMock(avg_value=25.1, sample_count=11),
            MagicMock(avg_value=25.0, sample_count=16),
            MagicMock(avg_value=25.1, sample_count=10),
        ]

        threshold_result = MagicMock()
        threshold_result.fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=[point_result, data_result, threshold_result])

        result = await trend_service.analyze_point_trend(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_increasing_trend_generates_warning(self, trend_service, mock_db):
        """测试上升趋势生成预警"""
        point = _make_point(id=1, point_name="T-01", unit="℃")

        # 调用顺序：1. point_info, 2. data, 3. threshold
        point_result = MagicMock()
        point_result.scalar_one_or_none.return_value = point

        data_result = MagicMock()
        data_result.fetchall.return_value = [
            MagicMock(avg_value=24.0, sample_count=15),
            MagicMock(avg_value=24.5, sample_count=12),
            MagicMock(avg_value=25.0, sample_count=14),
            MagicMock(avg_value=25.5, sample_count=13),
            MagicMock(avg_value=26.0, sample_count=11),
            MagicMock(avg_value=26.5, sample_count=16),
            MagicMock(avg_value=27.0, sample_count=10),
        ]

        threshold_result = MagicMock()
        threshold_result.fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=[point_result, data_result, threshold_result])

        result = await trend_service.analyze_point_trend(1)

        assert result is not None
        assert isinstance(result, TrendWarning)
        assert result.trend_type == "上升"
        assert result.point_id == 1
        assert result.total_change > 0.5  # 超过阈值

    @pytest.mark.asyncio
    async def test_decreasing_trend_generates_warning(self, trend_service, mock_db):
        """测试下降趋势生成预警"""
        point = _make_point(id=1, point_name="T-01", unit="℃")

        # 调用顺序：1. point_info, 2. data, 3. threshold
        point_result = MagicMock()
        point_result.scalar_one_or_none.return_value = point

        data_result = MagicMock()
        data_result.fetchall.return_value = [
            MagicMock(avg_value=27.0, sample_count=15),
            MagicMock(avg_value=26.5, sample_count=12),
            MagicMock(avg_value=26.0, sample_count=14),
            MagicMock(avg_value=25.5, sample_count=13),
            MagicMock(avg_value=25.0, sample_count=11),
            MagicMock(avg_value=24.5, sample_count=16),
            MagicMock(avg_value=24.0, sample_count=10),
        ]

        threshold_result = MagicMock()
        threshold_result.fetchone.return_value = MagicMock(config_value="0.5")

        mock_db.execute = AsyncMock(side_effect=[point_result, data_result, threshold_result])

        result = await trend_service.analyze_point_trend(1)

        assert result is not None
        assert isinstance(result, TrendWarning)
        assert result.trend_type == "下降"
        assert result.point_id == 1

    @pytest.mark.asyncio
    async def test_humidity_uses_history_aggregation(self, trend_service, mock_db):
        """测试湿度点位使用统一的历史数据聚合"""
        point = _make_point(id=2, point_name="H-01", unit="%RH")

        point_result = MagicMock()
        point_result.scalar_one_or_none.return_value = point

        data_result = MagicMock()
        data_result.fetchall.return_value = [
            MagicMock(avg_value=50.0, sample_count=15),
            MagicMock(avg_value=51.0, sample_count=12),
            MagicMock(avg_value=52.0, sample_count=14),
        ]

        mock_db.execute = AsyncMock(side_effect=[point_result, data_result])

        await trend_service.analyze_point_trend(2)

        # 验证使用了规范化历史表（在第二次 execute 调用中）
        assert mock_db.execute.call_count >= 2
        second_call_args = mock_db.execute.call_args_list[1]
        query_text = str(second_call_args[0][0])
        assert "point_history" in query_text

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

        with patch.object(trend_service, "_create_system_alarm", new_callable=AsyncMock) as mock_alarm:
            await trend_service._check_continuous_insufficient_data(1, 2)

            mock_alarm.assert_called_once()
            assert "连续 3 小时数据不足" in mock_alarm.call_args[1]["message"]


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
