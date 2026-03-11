"""
精度监控服务测试

Story 29.5: 模型精度验证与记录
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.precool.accuracy_monitor import (
    backfill_actual_temperatures,
    run_daily_accuracy_report,
    _check_consecutive_errors,
    _query_actual_temperature,
    MAE_EXCELLENT_1H,
    MAE_ACCEPTABLE_3H,
    MAX_DEVIATION_SAFE,
    CONSECUTIVE_ERROR_THRESHOLD,
    CONSECUTIVE_ERROR_COUNT,
    SENTINEL_VALUE,
    BACKFILL_BATCH_SIZE,
    DAILY_MAE_1H_WARNING,
    DAILY_MAE_3H_WARNING,
)


def _make_async_session_ctx(mock_session):
    """创建 async_session 上下文管理器 mock"""
    mock_ctx = MagicMock()
    mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


_UNSET = object()


def _make_sync_result(scalars_all=None, scalar_val=_UNSET, all_val=None):
    """创建 SQLAlchemy Result mock（all/scalar/scalars 都是同步方法）"""
    result = MagicMock()
    if scalars_all is not None:
        result.scalars.return_value.all.return_value = scalars_all
    if scalar_val is not _UNSET:
        result.scalar.return_value = scalar_val
    if all_val is not None:
        result.all.return_value = all_val
    return result


class TestConstants:
    """常量定义测试"""

    def test_mae_thresholds(self):
        assert MAE_EXCELLENT_1H == 1.0
        assert MAE_ACCEPTABLE_3H == 2.0
        assert MAX_DEVIATION_SAFE == 3.0

    def test_consecutive_error_config(self):
        assert CONSECUTIVE_ERROR_THRESHOLD == 2.0
        assert CONSECUTIVE_ERROR_COUNT == 3

    def test_sentinel_value(self):
        assert SENTINEL_VALUE == -999.0

    def test_backfill_batch_size(self):
        assert BACKFILL_BATCH_SIZE == 100

    def test_daily_warning_thresholds(self):
        assert DAILY_MAE_1H_WARNING == 1.5
        assert DAILY_MAE_3H_WARNING == 3.0


class TestBackfillActualTemperatures:
    """回填实际温度测试"""

    @pytest.mark.asyncio
    async def test_backfill_no_pending_logs(self):
        """无待回填记录时安全退出"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)):
            await backfill_actual_temperatures()

    @pytest.mark.asyncio
    async def test_backfill_skips_unexpired(self):
        """预测时间窗口未到期的记录应跳过"""
        mock_log = MagicMock()
        mock_log.created_at = datetime.now()
        mock_log.prediction_horizon_min = 60
        mock_log.actual_temp = None
        mock_log.cooling_zone_id = 1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[mock_log])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)):
            await backfill_actual_temperatures()
            assert mock_log.actual_temp is None

    @pytest.mark.asyncio
    async def test_backfill_sets_sentinel_after_timeout(self):
        """超时 1 小时后标记哨兵值"""
        mock_log = MagicMock()
        mock_log.created_at = datetime.now() - timedelta(hours=2)
        mock_log.prediction_horizon_min = 30
        mock_log.actual_temp = None
        mock_log.cooling_zone_id = 1
        mock_log.predicted_temp = 25.0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[mock_log])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)), \
             patch("app.services.precool.accuracy_monitor._query_actual_temperature",
                   new_callable=AsyncMock, return_value=None):
            await backfill_actual_temperatures()
            assert mock_log.actual_temp == SENTINEL_VALUE
            assert mock_log.deviation is None

    @pytest.mark.asyncio
    async def test_backfill_fills_actual_temp(self):
        """成功回填实际温度和偏差"""
        mock_log = MagicMock()
        mock_log.created_at = datetime.now() - timedelta(hours=2)
        mock_log.prediction_horizon_min = 30
        mock_log.actual_temp = None
        mock_log.cooling_zone_id = 1
        mock_log.predicted_temp = 25.0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[mock_log])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)), \
             patch("app.services.precool.accuracy_monitor._query_actual_temperature",
                   new_callable=AsyncMock, return_value=26.5), \
             patch("app.services.precool.accuracy_monitor._check_consecutive_errors",
                   new_callable=AsyncMock):
            await backfill_actual_temperatures()
            assert mock_log.actual_temp == 26.5
            assert mock_log.deviation == 1.5

    @pytest.mark.asyncio
    async def test_backfill_exception_handled(self):
        """回填过程中异常不应传播"""
        with patch("app.services.precool.accuracy_monitor.async_session",
                   side_effect=Exception("DB error")):
            await backfill_actual_temperatures()


class TestCheckConsecutiveErrors:
    """连续误差检查测试"""

    @pytest.mark.asyncio
    async def test_insufficient_records_no_rollback(self):
        """不足 3 条记录时不触发回退"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(all_val=[(2.5,), (3.0,)])
        )

        await _check_consecutive_errors(mock_session, zone_id=1)
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_below_threshold_no_rollback(self):
        """偏差未全部超过阈值时不回退"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(all_val=[(2.5,), (1.5,), (3.0,)])
        )

        await _check_consecutive_errors(mock_session, zone_id=1)
        assert mock_session.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_all_exceed_triggers_rollback(self):
        """连续 3 条全部超过阈值触发回退"""
        mock_active_param = MagicMock()
        mock_active_param.is_active = True

        mock_session = AsyncMock()
        # 按顺序返回不同 mock 结果
        dev_result = _make_sync_result(all_val=[(2.5,), (3.0,), (2.1,)])
        active_result = MagicMock()
        active_result.scalar_one_or_none.return_value = mock_active_param
        delete_result = MagicMock()

        mock_session.execute = AsyncMock(
            side_effect=[dev_result, active_result, delete_result]
        )

        await _check_consecutive_errors(mock_session, zone_id=1)
        assert mock_active_param.is_active == False
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_active_param_idempotent(self):
        """已无 active 参数时幂等不操作"""
        mock_session = AsyncMock()
        dev_result = _make_sync_result(all_val=[(2.5,), (3.0,), (2.1,)])
        active_result = MagicMock()
        active_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[dev_result, active_result]
        )

        await _check_consecutive_errors(mock_session, zone_id=1)
        mock_session.commit.assert_not_awaited()


class TestDailyAccuracyReport:
    """每日精度统计测试"""

    @pytest.mark.asyncio
    async def test_daily_report_no_records(self):
        """无有效记录时正常退出"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)):
            await run_daily_accuracy_report()

    @pytest.mark.asyncio
    async def test_daily_report_computes_mae(self):
        """正确计算 MAE"""
        log1 = MagicMock()
        log1.cooling_zone_id = 1
        log1.deviation = 0.5
        log1.prediction_horizon_min = 30
        log1.actual_temp = 25.5

        log2 = MagicMock()
        log2.cooling_zone_id = 1
        log2.deviation = -1.0
        log2.prediction_horizon_min = 120
        log2.actual_temp = 24.0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[log1, log2])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)):
            await run_daily_accuracy_report()
            # mae_1h = 0.5 (只有 log1, horizon<=60)
            # mae_3h = (0.5 + 1.0) / 2 = 0.75 (两条都 <=180)

    @pytest.mark.asyncio
    async def test_daily_report_detects_degradation(self):
        """检测精度退化并记录错误日志"""
        log1 = MagicMock()
        log1.cooling_zone_id = 1
        log1.deviation = 2.0
        log1.prediction_horizon_min = 30
        log1.actual_temp = 27.0

        log2 = MagicMock()
        log2.cooling_zone_id = 1
        log2.deviation = -1.5
        log2.prediction_horizon_min = 50
        log2.actual_temp = 23.5

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalars_all=[log1, log2])
        )

        with patch("app.services.precool.accuracy_monitor.async_session",
                   _make_async_session_ctx(mock_session)), \
             patch("app.services.precool.accuracy_monitor.logger") as mock_logger:
            await run_daily_accuracy_report()
            # mae_1h = (2.0 + 1.5) / 2 = 1.75 > 1.5 → 退化
            mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_daily_report_exception_handled(self):
        """异常不应传播"""
        with patch("app.services.precool.accuracy_monitor.async_session",
                   side_effect=Exception("DB error")):
            await run_daily_accuracy_report()


class TestQueryActualTemperature:
    """查询实际温度测试"""

    @pytest.mark.asyncio
    async def test_returns_max_inlet_temp(self):
        """返回时间窗口内的最大进风温度"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalar_val=26.5)
        )

        result = await _query_actual_temperature(
            mock_session, cooling_zone_id=1, target_time=datetime.now()
        )
        assert result == 26.5

    @pytest.mark.asyncio
    async def test_returns_none_when_no_data(self):
        """无温度数据时返回 None"""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=_make_sync_result(scalar_val=None)
        )

        result = await _query_actual_temperature(
            mock_session, cooling_zone_id=1, target_time=datetime.now()
        )
        assert result is None
