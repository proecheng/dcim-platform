"""
Story 34.5 — 通知渠道升级测试
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notification.dispatcher import (
    NotificationDispatcher,
    check_channel_escalations,
    _escalate_single_alarm,
)


# ==================== check_channel_escalations 测试 ====================


class TestCheckChannelEscalations:

    async def test_no_active_alarms_returns_zero(self):
        """无活动告警返回 0"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await check_channel_escalations(mock_session)
        assert result == 0

    async def test_acknowledged_alarm_not_queried(self):
        """已确认告警不在查询结果中（WHERE status='active'）"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # 模拟查询只返回 active 告警，acknowledged 不会出现
        mock_result.all.return_value = [(1, "critical", 100)]
        mock_session.execute = AsyncMock(return_value=mock_result)

        # 验证 check_channel_escalations 传递的查询包含 status='active' 条件
        with patch(
            "app.services.notification.dispatcher._escalate_single_alarm",
            new_callable=AsyncMock,
            return_value=0,
        ):
            await check_channel_escalations(mock_session)

        # 验证 execute 被调用，且查询的 WHERE 子句编译后包含 status = 'active'
        call_args = mock_session.execute.call_args
        query = call_args[0][0]
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        assert "status" in compiled and "active" in compiled

    async def test_single_alarm_exception_isolated(self):
        """单个告警异常不影响其他告警"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (1, "critical", 100),
            (2, "major", 200),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        call_count = 0

        async def mock_escalate(session, dispatcher, alarm_id, alarm_level, point_id, now):
            nonlocal call_count
            call_count += 1
            if alarm_id == 1:
                raise RuntimeError("模拟异常")
            return 1

        with patch(
            "app.services.notification.dispatcher._escalate_single_alarm",
            side_effect=mock_escalate,
        ):
            result = await check_channel_escalations(mock_session)

        assert call_count == 2
        assert result == 1  # 告警2成功，告警1异常返回0


# ==================== _escalate_single_alarm 测试 ====================


class TestEscalateSingleAlarm:

    def _make_dispatcher(self):
        return NotificationDispatcher()

    def _make_session(self, max_sent_at, sent_channels_list):
        """构建 mock session，按调用顺序返回不同结果"""
        mock_session = AsyncMock()
        call_idx = {"i": 0}

        async def mock_execute(*args, **kwargs):
            idx = call_idx["i"]
            call_idx["i"] += 1
            if idx == 0:
                # 第1次: MAX(sent_at)
                r = MagicMock()
                r.scalar.return_value = max_sent_at
                return r
            else:
                # 第2次: DISTINCT channel_type
                r = MagicMock()
                r.all.return_value = [(ch,) for ch in sent_channels_list]
                return r

        mock_session.execute = mock_execute
        return mock_session

    def _make_policy(self, escalation_enabled=True, timeout=5,
                     escalation_order=None, channels=None, user_ids=None):
        p = MagicMock()
        p.id = 1
        p.channel_escalation_enabled = escalation_enabled
        p.escalation_timeout_minutes = timeout
        p.escalation_channel_order = escalation_order or ["im", "sms", "voice"]
        p.channels = channels or ["im"]
        p.notify_user_ids = user_ids or [1, 2]
        return p

    async def test_no_sent_record_returns_zero(self):
        """无 sent 记录（max_sent_at=None）跳过"""
        d = self._make_dispatcher()
        mock_session = AsyncMock()

        # MAX(sent_at) 返回 None
        mock_max_result = MagicMock()
        mock_max_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_max_result)

        result = await _escalate_single_alarm(
            mock_session, d, 1, "critical", 100, datetime.now()
        )
        assert result == 0

    async def test_not_timed_out_returns_zero(self):
        """告警未超时不升级"""
        d = self._make_dispatcher()
        policy = self._make_policy(timeout=5)
        now = datetime.now()
        recent_sent = now - timedelta(minutes=2)

        mock_session = self._make_session(recent_sent, [])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch("app.services.ingest_pipeline._point_meta_cache", {100: {"site_id": 1}}):
                result = await _escalate_single_alarm(
                    mock_session, d, 1, "critical", 100, now
                )
        assert result == 0

    async def test_escalation_disabled_returns_zero(self):
        """策略未启用渠道升级，跳过"""
        d = self._make_dispatcher()
        policy = self._make_policy(escalation_enabled=False)
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)

        mock_session = self._make_session(old_sent, [])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch("app.services.ingest_pipeline._point_meta_cache", {100: {"site_id": 1}}):
                result = await _escalate_single_alarm(
                    mock_session, d, 1, "critical", 100, now
                )
        assert result == 0

    async def test_all_channels_exhausted_returns_zero(self):
        """所有渠道已用尽，返回 0"""
        d = self._make_dispatcher()
        policy = self._make_policy(escalation_order=["im", "sms"])
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)

        mock_session = self._make_session(old_sent, ["im", "sms"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch("app.services.ingest_pipeline._point_meta_cache", {100: {"site_id": 1}}):
                result = await _escalate_single_alarm(
                    mock_session, d, 1, "critical", 100, now
                )
        assert result == 0

    async def test_escalate_to_next_channel(self):
        """告警超时且有下一渠道，发送成功"""
        d = self._make_dispatcher()
        policy = self._make_policy(escalation_order=["im", "sms", "voice"], user_ids=[1])
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)
        mock_send = AsyncMock()

        mock_session = self._make_session(old_sent, ["im"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock,
                              return_value=[(1, "13800138000", None)]):
                with patch.object(d, "send_notification", mock_send):
                    with patch("app.services.ingest_pipeline._point_meta_cache",
                               {100: {"site_id": 1, "site_name": "站点1",
                                      "device_name": "空调1", "point_name": "温度"}}):
                        result = await _escalate_single_alarm(
                            mock_session, d, 1, "critical", 100, now
                        )

        assert result == 1
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "sms"

    async def test_json_string_escalation_order(self):
        """JSON 字符串 escalation_channel_order 正确反序列化"""
        d = self._make_dispatcher()
        policy = self._make_policy(user_ids=[1])
        policy.escalation_channel_order = '["im","sms","voice"]'
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)
        mock_send = AsyncMock()

        mock_session = self._make_session(old_sent, ["im"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock,
                              return_value=[(1, "user@test.com", None)]):
                with patch.object(d, "send_notification", mock_send):
                    with patch("app.services.ingest_pipeline._point_meta_cache",
                               {100: {"site_id": 1}}):
                        result = await _escalate_single_alarm(
                            mock_session, d, 1, "critical", 100, now
                        )
        assert result == 1

    async def test_no_contacts_returns_zero(self):
        """无联系方式时跳过"""
        d = self._make_dispatcher()
        policy = self._make_policy(user_ids=[1])
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)

        mock_session = self._make_session(old_sent, ["im"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock, return_value=[]):
                with patch("app.services.ingest_pipeline._point_meta_cache",
                           {100: {"site_id": 1}}):
                    result = await _escalate_single_alarm(
                        mock_session, d, 1, "critical", 100, now
                    )
        assert result == 0

    async def test_idempotent_no_duplicate_send(self):
        """幂等性：已发送渠道不重复发送，跳到 voice"""
        d = self._make_dispatcher()
        policy = self._make_policy(escalation_order=["im", "sms", "voice"], user_ids=[1])
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)
        mock_send = AsyncMock()

        mock_session = self._make_session(old_sent, ["im", "sms"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock,
                              return_value=[(1, "13800138000", None)]):
                with patch.object(d, "send_notification", mock_send):
                    with patch("app.services.ingest_pipeline._point_meta_cache",
                               {100: {"site_id": 1}}):
                        result = await _escalate_single_alarm(
                            mock_session, d, 1, "critical", 100, now
                        )

        assert result == 1
        assert mock_send.call_args[0][1] == "voice"

    async def test_max_sent_at_ensures_per_step_timeout(self):
        """MAX(sent_at) 确保每步升级间有完整超时窗口"""
        d = self._make_dispatcher()
        policy = self._make_policy(timeout=5, user_ids=[1])
        now = datetime.now()
        recent_sent = now - timedelta(minutes=3)

        mock_session = self._make_session(recent_sent, [])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch("app.services.ingest_pipeline._point_meta_cache",
                       {100: {"site_id": 1}}):
                result = await _escalate_single_alarm(
                    mock_session, d, 1, "critical", 100, now
                )
        assert result == 0

    async def test_context_includes_device_and_point_name(self):
        """context 包含 device_name/point_name 字段"""
        d = self._make_dispatcher()
        policy = self._make_policy(user_ids=[1])
        now = datetime.now()
        old_sent = now - timedelta(minutes=10)
        mock_send = AsyncMock()

        meta = {
            "site_id": 1, "site_name": "站点A",
            "device_name": "精密空调1", "point_name": "回风温度",
        }

        mock_session = self._make_session(old_sent, ["im"])

        with patch.object(d, "_match_policy", new_callable=AsyncMock, return_value=policy):
            with patch.object(d, "_get_user_contacts", new_callable=AsyncMock,
                              return_value=[(1, "user@test.com", None)]):
                with patch.object(d, "send_notification", mock_send):
                    with patch("app.services.ingest_pipeline._point_meta_cache",
                               {100: meta}):
                        result = await _escalate_single_alarm(
                            mock_session, d, 1, "critical", 100, now
                        )

        assert result == 1
        context = mock_send.call_args[0][0]
        assert context.device_name == "精密空调1"
        assert context.point_name == "回风温度"
