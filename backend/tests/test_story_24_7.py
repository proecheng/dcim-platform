"""
Story 24.7 熔断降级机制 -- 单元测试与集成测试
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import sys

# Mock redis module before any imports
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()

from tests.conftest import auth_headers


# ==================== 6.1 熔断触发测试 ====================


@pytest.mark.anyio
async def test_breaker_trip_on_consecutive_failures():
    """模拟连续失败，验证 CLOSED -> OPEN"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(consecutive_failures_threshold=3)

    assert breaker.state == BreakerState.CLOSED

    # 3 次连续失败（低流量模式，窗口内 <5 次请求）
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.CLOSED

    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN


# ==================== 6.2 错误率计算测试 ====================


@pytest.mark.anyio
async def test_breaker_trip_on_error_rate():
    """滑动窗口内 >10% 错误率触发熔断"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(
        error_threshold=0.10,
        window_size=5,  # 修正：使用 window_size 替代 min_requests
        consecutive_failures_threshold=100,  # 禁用连续失败触发
    )

    # 5 次请求，1 次失败 = 20% > 10%
    await breaker.record_success()
    await breaker.record_success()
    await breaker.record_success()
    await breaker.record_success()
    await breaker.record_failure()

    assert breaker.state == BreakerState.OPEN
    assert breaker.error_rate > 0.10


# ==================== 6.3 低流量模式测试 ====================


@pytest.mark.anyio
async def test_breaker_low_traffic_mode():
    """连续 3 次失败触发熔断（快速熔断）"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(
        window_size=10,  # 修正：使用 window_size
        consecutive_failures_threshold=3,
    )

    # 连续 3 次失败触发快速熔断
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.CLOSED

    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN


# ==================== 6.4 自动恢复测试 ====================


@pytest.mark.anyio
async def test_breaker_auto_recovery():
    """OPEN -> 30s -> HALF_OPEN -> 试探成功 -> CLOSED"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    current_time = 1000.0

    def mock_time():
        return current_time

    breaker = CircuitBreaker(
        consecutive_failures_threshold=3,
        cooldown_seconds=30,
        time_func=mock_time,
    )

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # 冷却期未到，请求应降级
    current_time = 1020.0  # +20s < 30s
    allowed, degraded = await breaker.allow_request("L2")
    assert allowed is True
    assert degraded is True
    assert breaker.state == BreakerState.OPEN

    # 冷却期已到，转 HALF_OPEN
    current_time = 1031.0  # +31s > 30s
    allowed, degraded = await breaker.allow_request("L2")
    assert allowed is True
    assert degraded is False
    assert breaker.state == BreakerState.HALF_OPEN

    # 试探成功 -> CLOSED
    await breaker.record_success()
    assert breaker.state == BreakerState.CLOSED


# ==================== 6.5 试探失败测试 ====================


@pytest.mark.anyio
async def test_breaker_probe_failure():
    """HALF_OPEN -> 试探失败 -> 回到 OPEN"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    current_time = 1000.0

    def mock_time():
        return current_time

    breaker = CircuitBreaker(
        consecutive_failures_threshold=3,
        cooldown_seconds=30,
        time_func=mock_time,
    )

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # 冷却期后转 HALF_OPEN
    current_time = 1031.0
    await breaker.allow_request("L2")
    assert breaker.state == BreakerState.HALF_OPEN

    # 试探失败 -> 回到 OPEN
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN


# ==================== 6.6 降级路由测试 ====================


@pytest.mark.anyio
async def test_degraded_routing():
    """OPEN 状态下 L2 请求自动降级"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(consecutive_failures_threshold=3)

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # L2 请求应降级
    allowed, degraded = await breaker.allow_request("L2")
    assert allowed is True
    assert degraded is True

    # L3 请求也应降级
    allowed, degraded = await breaker.allow_request("L3")
    assert allowed is True
    assert degraded is True


# ==================== 6.7 健康检查 API 测试 ====================


@pytest.mark.anyio
async def test_health_api(client, admin_user):
    """验证健康检查 API 返回数据完整性"""
    _, token = admin_user

    from app.services.diagnosis.circuit_breaker import CircuitBreaker

    mock_scheduler = MagicMock()
    mock_scheduler.circuit_breaker = CircuitBreaker()

    with patch("app.services.diagnosis.scheduler.get_scheduler", new_callable=AsyncMock, return_value=mock_scheduler):
        resp = await client.get(
            "/api/v1/diagnosis/health",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] in ("CLOSED", "UNKNOWN")
        assert "error_rate" in data


# ==================== 6.8 Redis 降级写入测试 ====================


@pytest.mark.anyio
async def test_fallback_save_to_redis():
    """模拟 DB 不可用，验证写入 Redis"""
    mock_client = AsyncMock()
    mock_client.set = AsyncMock()

    async def mock_get_redis_client():
        return mock_client

    with patch("app.services.diagnosis.fallback_store.get_redis_client", new=mock_get_redis_client):
        from app.services.diagnosis.fallback_store import DiagnosisFallbackStore

        key = await DiagnosisFallbackStore.save_to_redis({
            "engine_level": "L1",
            "start_time": datetime.now().isoformat(),
            "status": "success",
        })

        assert key.startswith("diagnosis:pending:")
        mock_client.set.assert_called_once()
        # 验证 TTL 参数
        call_args = mock_client.set.call_args
        assert call_args[1]["ex"] == 3600


# ==================== 6.9 pending 恢复测试 ====================


@pytest.mark.anyio
async def test_recover_pending():
    """验证 Redis 中的 pending 数据成功恢复到 DB"""
    now = datetime.now()
    test_data = {
        "_version": "1.0",  # 添加版本号
        "engine_level": "L1",
        "start_time": now.isoformat(),
        "end_time": now.isoformat(),
        "status": "success",
        "input_data": {},
        "output_data": {},
    }

    mock_client = AsyncMock()
    # 模拟 scan_iter 返回 1 个 key
    async def mock_scan_iter(*args, **kwargs):
        yield "diagnosis:pending:test-uuid"
    mock_client.scan_iter = mock_scan_iter
    mock_client.get = AsyncMock(return_value=json.dumps(test_data))
    mock_client.delete = AsyncMock()
    mock_client.set = AsyncMock(return_value=True)  # 添加分布式锁 mock

    async def mock_get_redis_client():
        return mock_client

    with patch("app.services.diagnosis.fallback_store.get_redis_client", new=mock_get_redis_client):
        from app.services.diagnosis.fallback_store import DiagnosisFallbackStore

        with patch("app.services.diagnosis.result_store.DiagnosisResultStore.save_complete", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = (1, 1)
            result = await DiagnosisFallbackStore.recover_pending()

            # 修正：返回值现在是 dict
            assert result["success"] == 1
            assert result["failed"] == 0
            assert result["skipped"] == 0
            mock_save.assert_called_once()
            mock_client.delete.assert_called()  # 会被调用两次：删除数据 key 和释放锁

            # 验证 datetime 字段被还原
            call_kwargs = mock_save.call_args[1]
            assert isinstance(call_kwargs["start_time"], datetime)
            assert isinstance(call_kwargs["end_time"], datetime)


# ==================== 6.10 状态变更告警测试 ====================


@pytest.mark.anyio
async def test_state_change_alert():
    """验证 WebSocket 推送消息格式"""
    state_changes = []

    async def mock_callback(data):
        state_changes.append(data)

    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(
        consecutive_failures_threshold=3,
        on_state_change=mock_callback,
    )

    # 触发 CLOSED -> OPEN
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()

    assert len(state_changes) == 1
    change = state_changes[0]
    assert change["state"] == "OPEN"
    assert change["previous_state"] == "CLOSED"
    assert change["reason"] == "consecutive_failures"
    assert "timestamp" in change


# ==================== 6.11 L1 请求不受熔断影响测试 ====================


@pytest.mark.anyio
async def test_l1_bypasses_breaker():
    """OPEN 状态下 L1 请求正常执行，不降级"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(consecutive_failures_threshold=3)

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # L1 请求不受影响
    allowed, degraded = await breaker.allow_request("L1")
    assert allowed is True
    assert degraded is False


# ==================== 6.12 datetime 序列化/反序列化测试 ====================


@pytest.mark.anyio
async def test_datetime_round_trip():
    """Redis fallback 的 datetime 字段 round-trip 正确性"""
    original_time = datetime(2026, 3, 6, 12, 30, 45)
    test_data = {
        "engine_level": "L1",
        "start_time": original_time.isoformat(),
        "end_time": None,
        "status": "success",
        "input_data": {},
        "output_data": {},
    }

    # 序列化
    serialized = json.dumps(test_data, default=str)
    # 反序列化
    deserialized = json.loads(serialized)

    # datetime 字段还原
    for dt_field in ("start_time", "end_time"):
        val = deserialized.get(dt_field)
        if isinstance(val, str) and val != "None":
            deserialized[dt_field] = datetime.fromisoformat(val)
        elif val == "None" or val is None:
            deserialized[dt_field] = None

    assert deserialized["start_time"] == original_time
    assert deserialized["end_time"] is None


# ==================== 6.13 时间 mock 测试 ====================


@pytest.mark.anyio
async def test_injectable_time_source():
    """使用可注入时间源测试冷却期"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    current_time = 0.0

    def mock_time():
        return current_time

    breaker = CircuitBreaker(
        consecutive_failures_threshold=3,
        cooldown_seconds=30,
        time_func=mock_time,
    )

    # 时间 0: 触发熔断
    current_time = 0.0
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # 时间 29: 仍在冷却期
    current_time = 29.0
    _, degraded = await breaker.allow_request("L2")
    assert degraded is True
    assert breaker.state == BreakerState.OPEN

    # 时间 30: 冷却期刚到
    current_time = 30.0
    _, degraded = await breaker.allow_request("L2")
    assert degraded is False
    assert breaker.state == BreakerState.HALF_OPEN


# ==================== 额外: HALF_OPEN 并发请求降级测试 ====================


@pytest.mark.anyio
async def test_half_open_concurrent_degraded():
    """HALF_OPEN 时只有第一个请求试探，其余降级"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    current_time = 1000.0

    def mock_time():
        return current_time

    breaker = CircuitBreaker(
        consecutive_failures_threshold=3,
        cooldown_seconds=30,
        time_func=mock_time,
    )

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()

    # 冷却后第一个请求试探放行
    current_time = 1031.0
    _, degraded1 = await breaker.allow_request("L2")
    assert degraded1 is False  # 试探
    assert breaker.state == BreakerState.HALF_OPEN

    # 第二个并发请求应降级
    _, degraded2 = await breaker.allow_request("L2")
    assert degraded2 is True


# ==================== 额外: 错误率未达阈值不触发 ====================


@pytest.mark.anyio
async def test_breaker_stays_closed_below_threshold():
    """错误率 <= 10% 时不触发熔断"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(
        error_threshold=0.10,
        window_size=10,  # 修正：使用 window_size
        consecutive_failures_threshold=100,  # 禁用连续失败触发
    )

    # 10 次请求，1 次失败 = 10% (不触发，因为条件是 >10%)
    for _ in range(9):
        await breaker.record_success()
    await breaker.record_failure()

    assert breaker.state == BreakerState.CLOSED


# ==================== 额外: reset 方法测试 ====================


@pytest.mark.anyio
async def test_breaker_reset():
    """reset 将熔断器恢复到初始状态"""
    from app.services.diagnosis.circuit_breaker import CircuitBreaker, BreakerState

    breaker = CircuitBreaker(consecutive_failures_threshold=3)

    # 触发熔断
    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()
    assert breaker.state == BreakerState.OPEN

    # P1-3 修复: 重置（异步调用）
    await breaker.reset()
    assert breaker.state == BreakerState.CLOSED
    assert breaker.consecutive_failures == 0
    assert breaker.total_in_window == 0


# ==================== 额外: DB 故障降级写入集成测试 ====================


@pytest.mark.anyio
async def test_result_store_fallback_to_redis():
    """save_complete DB 失败时降级到 Redis，返回 (None, None)"""
    mock_redis_client = AsyncMock()
    mock_redis_client.set = AsyncMock()

    async def mock_get_redis_client():
        return mock_redis_client

    with patch("app.services.diagnosis.fallback_store.get_redis_client", new=mock_get_redis_client):
        from app.services.diagnosis.result_store import DiagnosisResultStore

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock(side_effect=Exception("DB connection refused"))
        mock_session.rollback = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.diagnosis.result_store.async_session", return_value=mock_ctx):
            session_id, result_id = await DiagnosisResultStore.save_complete(
                engine_level="L1",
                start_time=datetime.now(),
                input_data={},
                output_data={},
            )

            assert session_id is None  # 修正：降级保存返回 (None, None)
            assert result_id is None  # 修正：降级保存返回 (None, None)
            mock_session.rollback.assert_called_once()
            mock_redis_client.set.assert_called_once()


# ==================== 额外: WebSocket 熔断告警消息格式测试 ====================


@pytest.mark.anyio
async def test_breaker_websocket_alert_format():
    """验证通过 alarms 通道推送 system_diagnosis_breaker 消息"""
    from app.services.websocket import ConnectionManager

    manager = ConnectionManager()
    sent_messages = []

    async def mock_broadcast(message, channel):
        sent_messages.append((message, channel))

    manager.broadcast = mock_broadcast

    await manager.broadcast_diagnosis(
        msg_type="system_diagnosis_breaker",
        data={
            "state": "OPEN",
            "previous_state": "CLOSED",
            "error_rate": 0.15,
            "reason": "error_rate_exceeded",
            "timestamp": "2026-03-06T12:00:00+00:00",
        },
        target_roles=["admin"],
    )

    assert len(sent_messages) == 1
    msg, channel = sent_messages[0]
    assert channel == "alarms"
    assert msg["type"] == "system_diagnosis_breaker"
    assert msg["target_roles"] == ["admin"]
    assert msg["data"]["state"] == "OPEN"
    assert msg["data"]["error_rate"] == 0.15
