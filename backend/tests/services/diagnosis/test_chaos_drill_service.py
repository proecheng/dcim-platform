"""
灾难恢复演练服务测试 - Story 26.7
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.diagnosis.chaos_drill_service import (
    ChaosDrillService,
    VALID_SCENARIOS,
    DEFAULT_SCHEDULE,
)
from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState
from app.models.config import SystemConfig
from app.models.report import ReportRecord
from app.services.diagnosis.fallback_store import DiagnosisFallbackStore


@pytest.fixture
def mock_db():
    """模拟异步数据库 session"""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def breaker():
    """创建测试用 CircuitBreaker"""
    return CircuitBreaker(
        error_threshold=0.3,
        window_size=10,
        consecutive_failures_threshold=3,
        cooldown_seconds=30,
    )


@pytest.fixture
def service(mock_db):
    """创建测试用 ChaosDrillService"""
    return ChaosDrillService(mock_db)


@pytest.fixture(autouse=True)
def reset_drill_state():
    """每个测试前后重置演练状态"""
    ChaosDrillService.is_drill_active = False
    ChaosDrillService._current_drill_id = None
    ChaosDrillService._stop_requested = False
    ChaosDrillService._drill_lock = None
    yield
    ChaosDrillService.is_drill_active = False
    ChaosDrillService._current_drill_id = None
    ChaosDrillService._stop_requested = False
    ChaosDrillService._drill_lock = None


# ---- 1. 获取默认演练计划 ----

@pytest.mark.asyncio
async def test_get_default_schedule(service, mock_db):
    """获取默认演练计划"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    schedule = await service.get_drill_schedule()

    assert schedule["enabled"] is False
    assert schedule["cron_expression"] == "0 2 * * 0"
    assert schedule["window_minutes"] == 120
    assert "circuit_breaker_degradation" in schedule["scenarios"]
    assert "db_timeout_fallback" in schedule["scenarios"]
    assert schedule["confirmed"] is False


# ---- 2. 更新演练计划 ----

@pytest.mark.asyncio
async def test_update_schedule(service, mock_db):
    """更新演练计划"""
    # get_drill_schedule 的 mock
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    schedule = await service.update_drill_schedule({
        "enabled": True,
        "cron_expression": "0 3 * * 1",
        "scenarios": ["circuit_breaker_degradation"],
    })

    assert schedule["enabled"] is True
    assert schedule["cron_expression"] == "0 3 * * 1"
    assert schedule["scenarios"] == ["circuit_breaker_degradation"]
    # 更新后 confirmed 应重置
    assert schedule["confirmed"] is False


# ---- 3. 确认演练计划 ----

@pytest.mark.asyncio
async def test_confirm_schedule(service, mock_db):
    """确认演练计划"""
    config = MagicMock()
    config.config_value = json.dumps({**DEFAULT_SCHEDULE, "enabled": True})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = config
    mock_db.execute.return_value = mock_result

    schedule = await service.confirm_drill_schedule(user_id=1)

    assert schedule["confirmed"] is True
    assert schedule["confirmed_by"] == 1
    assert schedule["confirmed_at"] is not None


# ---- 4. 触发演练 - 熔断降级场景 ----

@pytest.mark.asyncio
async def test_circuit_breaker_scenario(service, breaker):
    """熔断降级场景验证"""
    result = await service._run_circuit_breaker_scenario(breaker)

    assert result["name"] == "circuit_breaker_degradation"
    assert result["status"] == "passed"
    assert result["details"]["breaker_state_before"] == "CLOSED"
    assert result["details"]["breaker_forced_to"] == "OPEN"
    assert result["details"]["degradation_detected"] is True
    assert result["details"]["l1_fallback_working"] is True
    assert result["details"]["breaker_restored_to"] == "CLOSED"
    assert "recovery_seconds" in result


# ---- 5. 触发演练 - DB 超时场景 ----

@pytest.mark.asyncio
async def test_db_timeout_scenario_with_redis(service):
    """DB 超时场景 - Redis 可用时验证完整链路"""
    mock_redis = MagicMock()
    mock_redis.exists = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    with patch.object(
        DiagnosisFallbackStore, "save_to_redis",
        new_callable=AsyncMock,
        return_value="diagnosis:pending:test-key",
    ):
        import app.core.redis_lock as rl
        original_fn = getattr(rl, "get_redis_client", None)
        rl.get_redis_client = AsyncMock(return_value=mock_redis)
        try:
            result = await service._run_db_timeout_scenario()
        finally:
            if original_fn:
                rl.get_redis_client = original_fn

    assert result["name"] == "db_timeout_fallback"
    assert result["status"] == "passed"
    assert result["details"]["redis_fallback_working"] is True
    assert result["details"]["data_integrity_check"] is True
    assert result["details"]["fault_cleared"] is True


# ---- 6. 触发演练 - 全部场景 ----

@pytest.mark.asyncio
async def test_execute_drill_all_scenarios(service, breaker, mock_db):
    """执行所有演练场景"""
    # C20 修复: _generate_drill_report 使用独立 async_session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(service, "_run_db_timeout_scenario") as mock_db_scenario, \
         patch("app.core.database.async_session", return_value=mock_session_cm):
        mock_db_scenario.return_value = {
            "name": "db_timeout_fallback",
            "status": "passed",
            "details": {},
            "recovery_seconds": 0.5,
        }

        await service._execute_drill(
            drill_id="drill-test",
            scenarios=["circuit_breaker_degradation", "db_timeout_fallback"],
            breaker=breaker,
        )

        # 演练完成后状态应该恢复
        assert ChaosDrillService.is_drill_active is False
        assert ChaosDrillService._current_drill_id is None

        # 应生成报告
        mock_db.add.assert_called_once()
        added_report = mock_db.add.call_args[0][0]
        assert isinstance(added_report, ReportRecord)
        assert added_report.report_type == "diagnosis_drill"


# ---- 7. 终止演练 ----

@pytest.mark.asyncio
async def test_stop_drill(service, breaker):
    """终止演练"""
    ChaosDrillService.is_drill_active = True
    ChaosDrillService._current_drill_id = "drill-test-123"

    drill_id = await service.stop_drill(breaker=breaker)

    assert drill_id == "drill-test-123"
    assert ChaosDrillService._stop_requested is True


@pytest.mark.asyncio
async def test_stop_drill_no_active(service):
    """终止演练 - 无活跃演练"""
    with pytest.raises(ValueError, match="当前没有正在执行的演练"):
        await service.stop_drill()


# ---- 8. 演练报告生成 ----

@pytest.mark.asyncio
async def test_generate_drill_report(service, mock_db):
    """演练报告生成"""
    now = datetime.now(timezone.utc)
    scenarios = [
        {"name": "circuit_breaker_degradation", "status": "passed"},
        {"name": "db_timeout_fallback", "status": "passed"},
    ]

    # C20 修复后 _generate_drill_report 使用独立 async_session，需要 patch
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.core.database.async_session", return_value=mock_session_cm):
        await service._generate_drill_report(
            drill_id="drill-test",
            start_time=now,
            end_time=now,
            duration_seconds=5.0,
            scenario_results=scenarios,
        )

    mock_db.add.assert_called_once()
    report = mock_db.add.call_args[0][0]
    assert report.report_type == "diagnosis_drill"
    assert report.status == "completed"

    data = json.loads(report.report_data)
    assert data["overall_status"] == "passed"
    assert data["summary"] == "2/2 个场景通过"


# ---- 9. 查询演练历史 ----

@pytest.mark.asyncio
async def test_get_drill_history(service, mock_db):
    """查询演练历史"""
    # count query
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 3

    # data query
    mock_data_result = MagicMock()
    mock_data_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [mock_count_result, mock_data_result]

    result = await service.get_drill_history(page=1, page_size=10)

    assert result["total"] == 3
    assert result["items"] == []


# ---- 10. 并发演练保护 ----

@pytest.mark.asyncio
async def test_concurrent_drill_protection(service, breaker, mock_db):
    """并发演练保护"""
    ChaosDrillService.is_drill_active = True

    with pytest.raises(ValueError, match="已有演练正在执行"):
        await service.trigger_drill(scenarios=["circuit_breaker_degradation"], breaker=breaker)


# ---- 11. 场景超时保护 ----

@pytest.mark.asyncio
async def test_scenario_timeout(service, mock_db):
    """场景超时保护"""
    async def slow_scenario(*args, **kwargs):
        await asyncio.sleep(999)
        return {"name": "test", "status": "passed"}

    # C20 修复: _generate_drill_report 使用独立 async_session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(service, "_run_scenario", side_effect=slow_scenario), \
         patch("app.services.diagnosis.chaos_drill_service.SCENARIO_TIMEOUT", 0.1), \
         patch("app.core.database.async_session", return_value=mock_session_cm):
        await service._execute_drill(
            drill_id="drill-timeout",
            scenarios=["circuit_breaker_degradation"],
            breaker=None,
        )

    # 应生成超时报告
    report = mock_db.add.call_args[0][0]
    data = json.loads(report.report_data)
    assert data["scenarios"][0]["status"] == "timeout"


# ---- 12. 演练标志正确设置/清除 ----

@pytest.mark.asyncio
async def test_drill_flag_lifecycle(service, breaker, mock_db):
    """演练标志在执行期间正确设置和清除"""
    flag_during_drill = None

    original_run = service._run_circuit_breaker_scenario

    async def capture_flag(b):
        nonlocal flag_during_drill
        flag_during_drill = ChaosDrillService.is_drill_active
        return await original_run(b)

    # C20 修复: _generate_drill_report 使用独立 async_session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(service, "_run_circuit_breaker_scenario", side_effect=capture_flag), \
         patch("app.core.database.async_session", return_value=mock_session_cm):
        await service._execute_drill(
            drill_id="drill-flag",
            scenarios=["circuit_breaker_degradation"],
            breaker=breaker,
        )

    assert flag_during_drill is True
    assert ChaosDrillService.is_drill_active is False


# ---- 13. 熔断器状态恢复验证 ----

@pytest.mark.asyncio
async def test_breaker_recovery_on_error(service, breaker, mock_db):
    """异常时熔断器自动恢复"""
    async def failing_scenario(*args, **kwargs):
        await breaker.force_open()
        raise RuntimeError("模拟故障")

    # C20 修复: _generate_drill_report 使用独立 async_session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(service, "_run_scenario", side_effect=failing_scenario), \
         patch("app.core.database.async_session", return_value=mock_session_cm):
        await service._execute_drill(
            drill_id="drill-error",
            scenarios=["circuit_breaker_degradation"],
            breaker=breaker,
        )

    # 即使异常，熔断器也应恢复
    assert breaker.state == BreakerState.CLOSED


# ---- 14. 无效场景名称处理 ----

@pytest.mark.asyncio
async def test_invalid_scenario_name(service, mock_db):
    """无效场景名称"""
    with pytest.raises(ValueError, match="无效的演练场景"):
        await service.trigger_drill(scenarios=["nonexistent_scenario"])


@pytest.mark.asyncio
async def test_update_schedule_invalid_scenario(service, mock_db):
    """更新计划 - 无效场景名称"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="无效的演练场景"):
        await service.update_drill_schedule({"scenarios": ["bad_scenario"]})


# ---- 15. 未确认计划不执行 ----

@pytest.mark.asyncio
async def test_confirm_disabled_schedule_fails(service, mock_db):
    """未启用的计划不能确认"""
    config = MagicMock()
    config.config_value = json.dumps({**DEFAULT_SCHEDULE, "enabled": False})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = config
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="请先启用演练计划"):
        await service.confirm_drill_schedule(user_id=1)


# ---- 16. CircuitBreaker.force_open 方法 ----

@pytest.mark.asyncio
async def test_force_open(breaker):
    """force_open 正确切换状态"""
    assert breaker.state == BreakerState.CLOSED

    await breaker.force_open()

    assert breaker.state == BreakerState.OPEN
    assert breaker._last_trip_time is not None
    assert breaker._degraded_since is not None


# ---- 17. 熔断器已 OPEN 时跳过场景 ----

@pytest.mark.asyncio
async def test_breaker_already_open_skips(service, breaker):
    """熔断器已 OPEN 时跳过场景 1"""
    await breaker.force_open()

    result = await service._run_circuit_breaker_scenario(breaker)

    assert result["status"] == "skipped"
    assert result["details"]["reason"] == "breaker_already_open"


# ---- 18. 无 breaker 时跳过场景 ----

@pytest.mark.asyncio
async def test_no_breaker_skips_scenario(service):
    """无 CircuitBreaker 实例时跳过"""
    result = await service._run_circuit_breaker_scenario(None)

    assert result["status"] == "skipped"
    assert "不可用" in result["details"]["error"]


# ---- 19. 报告 overall_status 计算 ----

@pytest.mark.asyncio
async def test_report_partial_status(service, mock_db):
    """部分场景通过的报告状态"""
    now = datetime.now(timezone.utc)

    # C20 修复: _generate_drill_report 使用独立 async_session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.core.database.async_session", return_value=mock_session_cm):
        await service._generate_drill_report(
            drill_id="drill-partial",
            start_time=now,
            end_time=now,
            duration_seconds=10.0,
            scenario_results=[
                {"name": "s1", "status": "passed"},
                {"name": "s2", "status": "failed"},
            ],
        )

    report = mock_db.add.call_args[0][0]
    data = json.loads(report.report_data)
    assert data["overall_status"] == "failed"
    assert data["summary"] == "1/2 个场景通过"


# ---- 20. _ensure_lock 延迟初始化 ----

def test_ensure_lock():
    """_ensure_lock 延迟初始化"""
    ChaosDrillService._drill_lock = None
    ChaosDrillService._ensure_lock()
    assert ChaosDrillService._drill_lock is not None
    assert isinstance(ChaosDrillService._drill_lock, asyncio.Lock)
