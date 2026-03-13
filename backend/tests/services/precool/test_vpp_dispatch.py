"""
VPP 调控指令服务测试

Story 33.2: VppDispatchService 单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, time

from app.services.precool.vpp_dispatch import VppDispatchService


# ==================== 速率限制测试 ====================


class TestRateLimit:
    """速率限制测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_under_limit(self):
        """未超限时放行"""
        svc = VppDispatchService()
        with patch("app.services.precool.vpp_dispatch.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=5)
            mock_redis.set_json = AsyncMock()
            result = await svc.check_rate_limit()
            assert result is True
            mock_redis.set_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_at_limit(self):
        """达到限制时拒绝"""
        svc = VppDispatchService()
        with patch("app.services.precool.vpp_dispatch.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=12)
            result = await svc.check_rate_limit()
            assert result is False

    @pytest.mark.asyncio
    async def test_rate_limit_redis_unavailable(self):
        """Redis 不可用时降级放行"""
        svc = VppDispatchService()
        with patch("app.services.precool.vpp_dispatch.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(side_effect=Exception("连接失败"))
            result = await svc.check_rate_limit()
            assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_none_count(self):
        """计数为 None（首次）时放行"""
        svc = VppDispatchService()
        with patch("app.services.precool.vpp_dispatch.redis_service") as mock_redis:
            mock_redis.get_json = AsyncMock(return_value=None)
            mock_redis.set_json = AsyncMock()
            result = await svc.check_rate_limit()
            assert result is True
            # 应设置为 1
            call_args = mock_redis.set_json.call_args
            assert call_args[0][1] == 1


# ==================== 指令验证与处理测试 ====================


def _make_mock_session():
    """创建模拟的异步 session"""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_capacity(down_kw=50.0, up_kw=30.0):
    """创建模拟容量数据"""
    return {
        "down_adjustable_kw": down_kw,
        "up_adjustable_kw": up_kw,
        "down_adjustable_thermal_kw": down_kw * 3.5,
        "up_adjustable_thermal_kw": up_kw * 3.5,
        "T_current": 23.0,
        "headroom_down": 4.0,
        "headroom_up": 5.0,
        "response_window_hours": 1.0,
        "zones": [],
    }


class TestValidateAndExecute:
    """validate_and_execute 测试"""

    @pytest.mark.asyncio
    async def test_accept_down_adjust(self):
        """正常 down_adjust 指令被接受"""
        svc = VppDispatchService()
        request = {
            "command_type": "down_adjust",
            "target_power_kw": 30.0,
            "duration_minutes": 60,
            "priority": 1,
        }
        mock_session = _make_mock_session()
        # 无冲突计划
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "app.services.precool.vpp_capacity.vpp_capacity_service.calculate_capacity",
                new_callable=AsyncMock,
                return_value=_make_capacity(down_kw=50.0),
            ):
                result = await svc.validate_and_execute(request)

        assert result["status"] == "accepted"
        assert result["accepted_power_kw"] == 30.0

    @pytest.mark.asyncio
    async def test_reject_exceeds_capacity(self):
        """请求功率超过可调容量时拒绝"""
        svc = VppDispatchService()
        request = {
            "command_type": "down_adjust",
            "target_power_kw": 100.0,
            "duration_minutes": 60,
        }
        mock_session = _make_mock_session()

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "app.services.precool.vpp_capacity.vpp_capacity_service.calculate_capacity",
                new_callable=AsyncMock,
                return_value=_make_capacity(down_kw=50.0),
            ):
                result = await svc.validate_and_execute(request)

        assert result["status"] == "rejected"
        assert "超过可调容量" in result["reject_reason"]
        assert result["max_adjustable_kw"] == 50.0

    @pytest.mark.asyncio
    async def test_reject_negative_power(self):
        """target_power_kw <= 0 时拒绝"""
        svc = VppDispatchService()
        request = {
            "command_type": "up_adjust",
            "target_power_kw": -5.0,
            "duration_minutes": 30,
        }
        mock_session = _make_mock_session()

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.validate_and_execute(request)

        assert result["status"] == "rejected"
        assert "大于 0" in result["reject_reason"]

    @pytest.mark.asyncio
    async def test_reject_zero_duration(self):
        """duration_minutes <= 0 时拒绝"""
        svc = VppDispatchService()
        request = {
            "command_type": "down_adjust",
            "target_power_kw": 10.0,
            "duration_minutes": 0,
        }
        mock_session = _make_mock_session()

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.validate_and_execute(request)

        assert result["status"] == "rejected"
        assert "大于 0" in result["reject_reason"]

    @pytest.mark.asyncio
    async def test_accept_up_adjust(self):
        """正常 up_adjust 指令被接受"""
        svc = VppDispatchService()
        request = {
            "command_type": "up_adjust",
            "target_power_kw": 20.0,
            "duration_minutes": 30,
        }
        mock_session = _make_mock_session()

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "app.services.precool.vpp_capacity.vpp_capacity_service.calculate_capacity",
                new_callable=AsyncMock,
                return_value=_make_capacity(up_kw=30.0),
            ):
                result = await svc.validate_and_execute(request)

        assert result["status"] == "accepted"
        assert result["accepted_power_kw"] == 20.0

    @pytest.mark.asyncio
    async def test_capacity_calculation_failure(self):
        """容量计算失败时拒绝"""
        svc = VppDispatchService()
        request = {
            "command_type": "down_adjust",
            "target_power_kw": 10.0,
            "duration_minutes": 60,
        }
        mock_session = _make_mock_session()

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch(
                "app.services.precool.vpp_capacity.vpp_capacity_service.calculate_capacity",
                new_callable=AsyncMock,
                side_effect=Exception("数据库连接失败"),
            ):
                result = await svc.validate_and_execute(request)

        assert result["status"] == "rejected"
        assert "容量计算失败" in result["reject_reason"]


# ==================== 冲突检测测试 ====================


class TestConflictDetection:
    """冲突检测测试"""

    @pytest.mark.asyncio
    async def test_no_conflict_no_active_plans(self):
        """无执行中预冷计划时无冲突"""
        svc = VppDispatchService()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await svc._check_and_abort_conflicts(mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_conflict_aborts_plan(self):
        """有冲突时中止预冷计划"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = 42
        mock_plan.cooling_zone_id = 1
        mock_plan.status = "executing"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_plan]
        mock_session.execute.return_value = mock_result

        with patch(
            "app.services.precool.vpp_dispatch.precool_executor",
            create=True,
        ) as mock_exec:
            # 这里需要 patch 整个 import
            with patch(
                "app.services.precool.executor.precool_executor"
            ) as mock_exec2:
                mock_exec2.abort_plan_by_api = AsyncMock()
                # 使用更精确的 patch
                with patch.dict(
                    "sys.modules",
                    {
                        "app.services.precool.executor": MagicMock(
                            precool_executor=MagicMock(
                                abort_plan_by_api=AsyncMock()
                            )
                        )
                    },
                ):
                    result = await svc._check_and_abort_conflicts(mock_session)

        assert result == 42

    @pytest.mark.asyncio
    async def test_conflict_abort_failure_returns_none(self):
        """中止失败时返回 None（不阻塞指令处理）"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        mock_plan = MagicMock()
        mock_plan.id = 99
        mock_plan.cooling_zone_id = 2

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_plan]
        mock_session.execute.return_value = mock_result

        with patch.dict(
            "sys.modules",
            {
                "app.services.precool.executor": MagicMock(
                    precool_executor=MagicMock(
                        abort_plan_by_api=AsyncMock(
                            side_effect=Exception("abort 失败")
                        )
                    )
                )
            },
        ):
            result = await svc._check_and_abort_conflicts(mock_session)

        assert result is None


# ==================== 响应构建测试 ====================


class TestBuildResponse:
    """_build_response 测试"""

    def test_accepted_response(self):
        """接受指令的响应格式"""
        svc = VppDispatchService()
        dispatch = MagicMock()
        dispatch.dispatch_id = "test-uuid"
        dispatch.command_type = "down_adjust"
        dispatch.target_power_kw = 30.0
        dispatch.duration_minutes = 60
        dispatch.status = "accepted"
        dispatch.reject_reason = None
        dispatch.max_adjustable_kw = None
        dispatch.accepted_power_kw = 30.0
        dispatch.aborted_schedule_id = None

        result = svc._build_response(dispatch)
        assert result["dispatch_id"] == "test-uuid"
        assert result["status"] == "accepted"
        assert result["accepted_power_kw"] == 30.0
        assert result["reject_reason"] is None

    def test_rejected_response(self):
        """拒绝指令的响应格式"""
        svc = VppDispatchService()
        dispatch = MagicMock()
        dispatch.dispatch_id = "test-uuid-2"
        dispatch.command_type = "down_adjust"
        dispatch.target_power_kw = 100.0
        dispatch.duration_minutes = 60
        dispatch.status = "rejected"
        dispatch.reject_reason = "超过可调容量"
        dispatch.max_adjustable_kw = 50.0
        dispatch.accepted_power_kw = None
        dispatch.aborted_schedule_id = None

        result = svc._build_response(dispatch)
        assert result["status"] == "rejected"
        assert result["reject_reason"] == "超过可调容量"
        assert result["max_adjustable_kw"] == 50.0


# ==================== 列表查询与统计测试 (Story 33.3) ====================


class TestListDispatches:
    """list_dispatches 测试"""

    @pytest.mark.asyncio
    async def test_list_empty(self):
        """无指令时返回空列表"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        # count 查询
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # 列表查询
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[count_result, list_result]
        )

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.list_dispatches(1, 20, None)

        assert result["total"] == 0
        assert result["items"] == []
        assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_list_with_data(self):
        """有指令时返回列表"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        mock_dispatch = MagicMock()
        mock_dispatch.dispatch_id = "test-uuid"
        mock_dispatch.command_type = "down_adjust"
        mock_dispatch.target_power_kw = 30.0
        mock_dispatch.duration_minutes = 60
        mock_dispatch.status = "accepted"
        mock_dispatch.reject_reason = None
        mock_dispatch.max_adjustable_kw = None
        mock_dispatch.accepted_power_kw = 30.0
        mock_dispatch.aborted_schedule_id = None
        mock_dispatch.created_at = datetime(2026, 3, 14, 10, 0, 0)

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [mock_dispatch]

        mock_session.execute = AsyncMock(
            side_effect=[count_result, list_result]
        )

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.list_dispatches(1, 20, None)

        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["dispatch_id"] == "test-uuid"
        assert result["items"][0]["created_at"] is not None


class TestGetStatistics:
    """get_statistics 测试"""

    @pytest.mark.asyncio
    async def test_statistics_empty(self):
        """无数据时返回零值"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        empty_row = MagicMock()
        empty_row.count = 0
        empty_row.total_power = None

        daily_result = MagicMock()
        daily_result.first.return_value = empty_row

        monthly_result = MagicMock()
        monthly_result.first.return_value = empty_row

        mock_session.execute = AsyncMock(
            side_effect=[daily_result, monthly_result]
        )

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.get_statistics()

        assert result["daily"]["count"] == 0
        assert result["daily"]["total_power_kw"] == 0
        assert result["monthly"]["estimated_savings_yuan"] == 0

    @pytest.mark.asyncio
    async def test_statistics_with_data(self):
        """有数据时正确计算"""
        svc = VppDispatchService()
        mock_session = AsyncMock()

        daily_row = MagicMock()
        daily_row.count = 3
        daily_row.total_power = 90.0

        monthly_row = MagicMock()
        monthly_row.count = 25
        monthly_row.total_power = 750.0

        daily_result = MagicMock()
        daily_result.first.return_value = daily_row

        monthly_result = MagicMock()
        monthly_result.first.return_value = monthly_row

        mock_session.execute = AsyncMock(
            side_effect=[daily_result, monthly_result]
        )

        with patch(
            "app.services.precool.vpp_dispatch.async_session"
        ) as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await svc.get_statistics()

        assert result["daily"]["count"] == 3
        assert result["daily"]["total_power_kw"] == 90.0
        assert result["daily"]["estimated_savings_yuan"] == 45.0
        assert result["monthly"]["count"] == 25
        assert result["monthly"]["total_power_kw"] == 750.0
        assert result["monthly"]["estimated_savings_yuan"] == 375.0
