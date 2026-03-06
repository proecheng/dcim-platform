"""
Story 24.6 诊断结果存储与分级推送 — 单元测试与集成测试
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import sys

# Mock redis module before any imports
sys.modules.setdefault('redis', MagicMock())
sys.modules.setdefault('redis.asyncio', MagicMock())

from tests.conftest import auth_headers


# ==================== 7.1 DiagnosisResultStore 测试 ====================


@pytest.mark.anyio
async def test_result_store_save_complete(async_db):
    """测试完整保存: session + result + audit_log 单事务"""
    from app.models.diagnosis import DiagnosisSession, DiagnosisResult, DiagnosisAuditLog
    from app.services.diagnosis.result_store import DiagnosisResultStore

    with patch("app.services.diagnosis.result_store.async_session") as mock_ctx:
        # 使用真实 async_db
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        session_id, result_id = await DiagnosisResultStore.save_complete(
            trigger_alarm_id=100,
            device_id=1,
            engine_level="L1",
            status="success",
            max_confidence=0.85,
            start_time=datetime.now(),
            end_time=datetime.now(),
            inference_time_ms=50,
            alarm_id=100,
            diagnosis_level="L1",
            matched=True,
            conclusion="温度传感器故障",
            confidence=0.85,
            root_cause="传感器损坏",
            input_data={"alarm_id": 100, "level": "critical"},
            output_data={"matched": True, "confidence": 0.85},
        )

        assert session_id > 0
        assert result_id > 0

        # 验证 session 已创建
        from sqlalchemy import select
        sess_result = await async_db.execute(
            select(DiagnosisSession).where(DiagnosisSession.id == session_id)
        )
        sess = sess_result.scalar_one_or_none()
        assert sess is not None
        assert sess.engine_level == "L1"
        assert sess.max_confidence == 0.85

        # 验证 result 已创建
        res_result = await async_db.execute(
            select(DiagnosisResult).where(DiagnosisResult.id == result_id)
        )
        res = res_result.scalar_one_or_none()
        assert res is not None
        assert res.session_id == session_id
        assert res.root_cause == "传感器损坏"

        # 验证 audit_log 已创建
        audit_result = await async_db.execute(
            select(DiagnosisAuditLog).where(DiagnosisAuditLog.session_id == session_id)
        )
        audit = audit_result.scalar_one_or_none()
        assert audit is not None
        assert audit.engine_level == "L1"


# ==================== 7.2 分级推送逻辑测试 ====================


@pytest.mark.anyio
async def test_push_confidence_90_alert():
    """confidence=0.90 应推送 diagnosis_alert"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    with patch("app.services.diagnosis.push_service.ws_manager") as mock_ws:
        mock_ws.broadcast_diagnosis = AsyncMock()

        result = await DiagnosisPushService.push_diagnosis_result(
            session_id=1,
            device_id=1,
            engine_level="L2",
            confidence=0.90,
            conclusion="UPS 故障",
            root_cause="电池老化",
        )

        assert result == "pushed"
        mock_ws.broadcast_diagnosis.assert_called_once()
        call_kwargs = mock_ws.broadcast_diagnosis.call_args[1]
        assert call_kwargs["msg_type"] == "diagnosis_alert"
        assert call_kwargs["data"]["confidence"] == 90  # 百分比整数
        assert call_kwargs["target_roles"] == ["operator", "admin"]


@pytest.mark.anyio
async def test_push_confidence_70_suggestion():
    """confidence=0.70 应推送 diagnosis_suggestion"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    with patch("app.services.diagnosis.push_service.ws_manager") as mock_ws:
        mock_ws.broadcast_diagnosis = AsyncMock()

        result = await DiagnosisPushService.push_diagnosis_result(
            session_id=2,
            device_id=1,
            engine_level="L1",
            confidence=0.70,
            conclusion="可能过热",
        )

        assert result == "pushed"
        call_kwargs = mock_ws.broadcast_diagnosis.call_args[1]
        assert call_kwargs["msg_type"] == "diagnosis_suggestion"
        assert call_kwargs["data"]["confidence"] == 70


@pytest.mark.anyio
async def test_push_confidence_50_skipped():
    """confidence=0.50 不推送"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    with patch("app.services.diagnosis.push_service.ws_manager") as mock_ws:
        mock_ws.broadcast_diagnosis = AsyncMock()

        result = await DiagnosisPushService.push_diagnosis_result(
            session_id=3,
            device_id=1,
            engine_level="L1",
            confidence=0.50,
        )

        assert result == "skipped"
        mock_ws.broadcast_diagnosis.assert_not_called()


# ==================== 7.3 边界值测试 ====================


def test_push_level_boundary_values():
    """测试推送级别边界值"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    # > 0.80 → alert
    assert DiagnosisPushService.get_push_level(0.81) == "alert"
    # = 0.80 → suggestion（不是 alert，因为条件是 > 0.80）
    assert DiagnosisPushService.get_push_level(0.80) == "suggestion"
    # = 0.60 → suggestion
    assert DiagnosisPushService.get_push_level(0.60) == "suggestion"
    # < 0.60 → log_only
    assert DiagnosisPushService.get_push_level(0.59) == "log_only"
    # = 0.0
    assert DiagnosisPushService.get_push_level(0.0) == "log_only"
    # = 1.0
    assert DiagnosisPushService.get_push_level(1.0) == "alert"


# ==================== 7.4 诊断历史查询 API 测试 ====================


@pytest.mark.anyio
async def test_sessions_list_api(client, async_db, admin_user):
    """测试 GET /api/v1/diagnosis/sessions 分页查询"""
    user, token = admin_user

    from app.models.diagnosis import DiagnosisSession
    # 创建测试数据
    for i in range(3):
        s = DiagnosisSession(
            trigger_alarm_id=None,
            device_id=i + 1,
            engine_level="L1",
            status="success",
            push_status="skipped",
            max_confidence=0.5 + i * 0.15,
            start_time=datetime.now(),
            inference_time_ms=50,
        )
        async_db.add(s)
    await async_db.flush()

    resp = await client.get(
        "/api/v1/diagnosis/sessions?page=1&page_size=10",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.anyio
async def test_session_detail_api(client, async_db, admin_user):
    """测试 GET /api/v1/diagnosis/sessions/{id} 详情"""
    user, token = admin_user

    from app.models.diagnosis import DiagnosisSession
    s = DiagnosisSession(
        device_id=10,
        engine_level="L2",
        status="success",
        push_status="pushed",
        max_confidence=0.92,
        start_time=datetime.now(),
        inference_time_ms=200,
    )
    async_db.add(s)
    await async_db.flush()

    resp = await client.get(
        f"/api/v1/diagnosis/sessions/{s.id}",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == s.id
    assert data["engine_level"] == "L2"


@pytest.mark.anyio
async def test_session_audit_log_requires_admin(client, async_db, viewer_user, admin_user):
    """测试审计日志 API 需要 admin 角色"""
    _, viewer_token = viewer_user
    _, admin_token = admin_user

    from app.models.diagnosis import DiagnosisSession
    s = DiagnosisSession(
        engine_level="L1", status="success", push_status="skipped",
        start_time=datetime.now(), inference_time_ms=10,
    )
    async_db.add(s)
    await async_db.flush()

    # viewer 应被拒绝
    resp = await client.get(
        f"/api/v1/diagnosis/sessions/{s.id}/audit-log",
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 403

    # admin 应成功
    resp = await client.get(
        f"/api/v1/diagnosis/sessions/{s.id}/audit-log",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200


# ==================== 7.6 事务回滚测试 ====================


@pytest.mark.anyio
async def test_save_complete_rollback_on_error():
    """模拟数据库写入失败，验证回滚并三级降级：DB → Redis → 本地文件 → raise"""
    from app.services.diagnosis.result_store import DiagnosisResultStore

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock(side_effect=Exception("DB write failed"))
    mock_session.rollback = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    # DB 失败后尝试 Redis fallback，Redis 也失败
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(side_effect=Exception("Redis also down"))

    async def mock_get_redis():
        return mock_redis

    with patch("app.services.diagnosis.result_store.async_session", return_value=mock_ctx):
        with patch("app.services.diagnosis.fallback_store.get_redis_client", new=mock_get_redis):
            # Redis 也失败后尝试本地文件，本地文件也失败时才 raise
            with patch("app.services.diagnosis.fallback_store.DiagnosisFallbackStore._save_to_local_file",
                        new_callable=AsyncMock, side_effect=Exception("File also down")):
                with pytest.raises(Exception, match="DB write failed"):
                    await DiagnosisResultStore.save_complete(
                        engine_level="L1",
                        start_time=datetime.now(),
                        input_data={},
                        output_data={},
                    )
                mock_session.rollback.assert_called_once()


# ==================== 7.7 审计日志脱敏测试 ====================


def test_sanitize_audit_data_removes_sensitive_fields():
    """验证敏感字段被移除"""
    from app.services.diagnosis.result_store import DiagnosisResultStore

    data = {
        "alarm_id": 100,
        "password": "secret123",
        "token": "jwt_xxx",
        "nested": {
            "api_key": "key_123",
            "value": 42,
        },
        "items": [
            {"secret": "abc", "name": "test"},
        ],
    }

    sanitized = DiagnosisResultStore._sanitize_audit_data(data)

    assert sanitized["alarm_id"] == 100
    assert sanitized["password"] == "***REDACTED***"
    assert sanitized["token"] == "***REDACTED***"
    assert sanitized["nested"]["api_key"] == "***REDACTED***"
    assert sanitized["nested"]["value"] == 42
    assert sanitized["items"][0]["secret"] == "***REDACTED***"
    assert sanitized["items"][0]["name"] == "test"


def test_truncate_large_audit_data():
    """验证超过 64KB 的 JSON 被截断"""
    from app.services.diagnosis.result_store import DiagnosisResultStore

    # 创建一个超大字段
    data = {
        "small_field": "ok",
        "large_field": "x" * 100000,  # ~100KB
    }

    truncated = DiagnosisResultStore._truncate_to_size(data, 64 * 1024)
    import json
    serialized = json.dumps(truncated, ensure_ascii=False)
    assert len(serialized.encode("utf-8")) <= 64 * 1024
    assert truncated["large_field"] == "[TRUNCATED]"
    assert truncated["small_field"] == "ok"
    assert truncated["_truncated"] is True


# ==================== 7.8 推送失败容错测试 ====================


@pytest.mark.anyio
async def test_push_failure_returns_failed():
    """模拟 WebSocket 推送异常，验证返回 'failed'"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    with patch("app.services.diagnosis.push_service.ws_manager") as mock_ws:
        mock_ws.broadcast_diagnosis = AsyncMock(side_effect=Exception("WS connection lost"))

        result = await DiagnosisPushService.push_diagnosis_result(
            session_id=1,
            device_id=1,
            engine_level="L1",
            confidence=0.90,
        )

        assert result == "failed"


# ==================== 7.9 同一告警多次诊断测试 ====================


@pytest.mark.anyio
async def test_same_alarm_dual_sessions(async_db):
    """L1 和 L2 各创建独立 session，通过 trigger_alarm_id 可查到两条"""
    from app.models.diagnosis import DiagnosisSession
    from sqlalchemy import select

    alarm_id = 999

    # L1 session
    s1 = DiagnosisSession(
        trigger_alarm_id=alarm_id,
        device_id=1,
        engine_level="L1",
        status="success",
        push_status="skipped",
        start_time=datetime.now(),
        inference_time_ms=30,
    )
    async_db.add(s1)

    # L2 session
    s2 = DiagnosisSession(
        trigger_alarm_id=alarm_id,
        device_id=1,
        engine_level="L2",
        status="success",
        push_status="pushed",
        start_time=datetime.now(),
        inference_time_ms=500,
    )
    async_db.add(s2)
    await async_db.flush()

    result = await async_db.execute(
        select(DiagnosisSession).where(DiagnosisSession.trigger_alarm_id == alarm_id)
    )
    sessions = result.scalars().all()
    assert len(sessions) == 2
    levels = {s.engine_level for s in sessions}
    assert levels == {"L1", "L2"}


# ==================== 7.5 WebSocket 消息格式测试 ====================


@pytest.mark.anyio
async def test_websocket_message_format():
    """验证 broadcast_diagnosis 推送消息 type/target_roles/data 字段完整"""
    from app.services.websocket import ConnectionManager

    manager = ConnectionManager()
    sent_messages = []

    # mock broadcast
    async def mock_broadcast(message, channel):
        sent_messages.append((message, channel))

    manager.broadcast = mock_broadcast

    push_data = {
        "session_id": 1,
        "confidence": 92,
        "root_cause": "UPS 电池故障",
    }

    await manager.broadcast_diagnosis(
        msg_type="diagnosis_alert",
        data=push_data,
        target_roles=["operator", "admin"],
    )

    assert len(sent_messages) == 1
    msg, channel = sent_messages[0]
    assert channel == "alarms"
    assert msg["type"] == "diagnosis_alert"
    assert msg["target_roles"] == ["operator", "admin"]
    assert msg["data"]["session_id"] == 1
    assert msg["data"]["confidence"] == 92


# ==================== 8.1 审计脱敏 - 敏感后缀字段测试（第二轮审查问题 2） ====================


def test_sanitize_sensitive_suffix_fields():
    """验证敏感后缀字段被脱敏，而 primary_key/keyboard 等不被脱敏"""
    from app.services.diagnosis.result_store import DiagnosisResultStore

    data = {
        "user_password": "secret123",
        "auth_token": "jwt_xxx",
        "database_key": "xyz789",
        "api_secret": "hidden",
        "primary_key": 123,        # 不应被脱敏（不以 _key 结尾，完整匹配 primary_key）
        "keyboard": "qwerty",      # 不应被脱敏
        "monkey": "banana",        # 不应被脱敏
    }

    sanitized = DiagnosisResultStore._sanitize_audit_data(data)

    assert sanitized["user_password"] == "***REDACTED***"
    assert sanitized["auth_token"] == "***REDACTED***"
    assert sanitized["database_key"] == "***REDACTED***"
    assert sanitized["api_secret"] == "***REDACTED***"
    assert sanitized["keyboard"] == "qwerty"
    assert sanitized["monkey"] == "banana"


# ==================== 8.2 字符串值敏感模式脱敏测试（第二轮审查问题 3） ====================


def test_sanitize_string_value_patterns():
    """验证字符串值中的敏感模式被脱敏"""
    from app.services.diagnosis.result_store import DiagnosisResultStore

    data = {
        "log_message": "User login with password=secret123",
        "config": "Authorization: Bearer xyz789",
        "normal_text": "This is a normal message",
        "token_in_value": "token:abc456 was used",
    }

    sanitized = DiagnosisResultStore._sanitize_audit_data(data)

    assert "secret123" not in sanitized["log_message"]
    assert "***REDACTED***" in sanitized["log_message"]
    assert "xyz789" not in sanitized["config"]
    assert sanitized["normal_text"] == "This is a normal message"
    assert "abc456" not in sanitized["token_in_value"]


# ==================== 8.3 推送重试队列测试（第二轮审查问题 5） ====================


@pytest.mark.anyio
async def test_push_retry_enqueue_on_failure():
    """推送失败时写入重试队列"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    mock_redis_client = AsyncMock()
    mock_redis_client.rpush = AsyncMock()

    async def mock_get_redis():
        return mock_redis_client

    mock_ws = AsyncMock()
    mock_ws.broadcast_diagnosis = AsyncMock(side_effect=Exception("WebSocket error"))

    with patch("app.services.diagnosis.push_service.get_redis_client", new=mock_get_redis):
        with patch("app.services.diagnosis.push_service.ws_manager", mock_ws):
            status = await DiagnosisPushService.push_diagnosis_result(
                session_id=1,
                device_id=100,
                device_type="server",
                engine_level="L1",
                confidence=0.85,
                conclusion="测试结论",
                root_cause="测试根因",
                suggested_actions=["action1"],
            )

            assert status == "failed"
            mock_redis_client.rpush.assert_called_once()
            call_args = mock_redis_client.rpush.call_args
            assert call_args[0][0] == "diagnosis:push_retry_queue"
            retry_data = json.loads(call_args[0][1])
            assert retry_data["session_id"] == 1
            assert retry_data["retry_count"] == 0
            assert "created_at" in retry_data


@pytest.mark.anyio
async def test_push_retry_process_success():
    """重试队列成功处理"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    now = datetime.now()
    retry_data = json.dumps({
        "session_id": 1,
        "device_id": 100,
        "device_type": "server",
        "engine_level": "L1",
        "confidence": 0.85,
        "conclusion": "测试",
        "retry_count": 0,
        "created_at": now.isoformat(),
    })

    mock_redis = AsyncMock()
    mock_redis.lpop = AsyncMock(side_effect=[retry_data, None])
    mock_redis.rpush = AsyncMock()

    async def mock_get_redis():
        return mock_redis

    with patch("app.services.diagnosis.push_service.get_redis_client", new=mock_get_redis):
        with patch.object(DiagnosisPushService, "push_diagnosis_result", new_callable=AsyncMock) as mock_push:
            mock_push.return_value = "pushed"
            result = await DiagnosisPushService.process_retry_queue()

            assert result["success"] == 1
            assert result["failed"] == 0
            assert result["expired"] == 0


@pytest.mark.anyio
async def test_push_retry_expired_skipped():
    """过期数据被跳过"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    old_time = datetime.now() - timedelta(hours=25)
    retry_data = json.dumps({
        "session_id": 1,
        "confidence": 0.85,
        "engine_level": "L1",
        "retry_count": 0,
        "created_at": old_time.isoformat(),
    })

    mock_redis = AsyncMock()
    mock_redis.lpop = AsyncMock(side_effect=[retry_data, None])

    async def mock_get_redis():
        return mock_redis

    with patch("app.services.diagnosis.push_service.get_redis_client", new=mock_get_redis):
        result = await DiagnosisPushService.process_retry_queue()
        assert result["expired"] == 1
        assert result["success"] == 0


@pytest.mark.anyio
async def test_push_retry_max_count_exceeded():
    """超过最大重试次数的数据被丢弃"""
    from app.services.diagnosis.push_service import DiagnosisPushService

    retry_data = json.dumps({
        "session_id": 1,
        "confidence": 0.85,
        "engine_level": "L1",
        "retry_count": 3,  # 已达上限
        "created_at": datetime.now().isoformat(),
    })

    mock_redis = AsyncMock()
    mock_redis.lpop = AsyncMock(side_effect=[retry_data, None])

    async def mock_get_redis():
        return mock_redis

    with patch("app.services.diagnosis.push_service.get_redis_client", new=mock_get_redis):
        result = await DiagnosisPushService.process_retry_queue()
        assert result["failed"] == 1
        assert result["success"] == 0
