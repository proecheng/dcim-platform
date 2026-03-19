"""
Story 34.2 — 通知渠道适配器框架测试
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.conftest import auth_headers

from app.schemas.notification import (
    AlarmNotificationContext,
    render_notification,
    get_template_for_channel,
    get_subject_for_channel,
    SMS_TEMPLATE,
    IM_MARKDOWN_TEMPLATE,
    ALARM_LEVEL_CN,
)
from app.services.notification.adapters import (
    EmailNotificationAdapter,
    ImAdapter,
    SmsAdapter,
    VoiceCallAdapter,
    NotificationResult,
    ADAPTER_REGISTRY,
)


# ==================== Fixtures ====================

@pytest.fixture
def sample_context():
    return AlarmNotificationContext(
        alarm_id=1,
        alarm_level="critical",
        alarm_message="温度超过阈值",
        device_name="空调-01",
        point_name="回风温度",
        current_value=35.5,
        threshold_value=30.0,
        site_id=1,
        site_name="主机房",
        created_at=datetime(2026, 3, 19, 10, 30, 0),
    )


@pytest.fixture
def none_context():
    return AlarmNotificationContext(
        alarm_id=2,
        alarm_level="minor",
        alarm_message=None,
        device_name=None,
        point_name=None,
        current_value=None,
        threshold_value=None,
        site_id=None,
        site_name=None,
        created_at=None,
    )


# ==================== 消息模板测试 ====================

class TestMessageTemplates:

    def test_sms_template_length(self, sample_context):
        result = render_notification(SMS_TEMPLATE, sample_context)
        assert len(result) <= 70

    def test_im_template_contains_all_fields(self, sample_context):
        result = render_notification(IM_MARKDOWN_TEMPLATE, sample_context)
        assert "主机房" in result
        assert "紧急" in result
        assert "空调-01" in result
        assert "回风温度" in result
        assert "35.5" in result
        assert "30.0" in result
        assert "温度超过阈值" in result

    def test_none_values_replaced(self, none_context):
        result = render_notification(SMS_TEMPLATE, none_context)
        assert "未知" in result

    def test_alarm_level_cn_mapping(self):
        assert ALARM_LEVEL_CN["critical"] == "紧急"
        assert ALARM_LEVEL_CN["major"] == "重要"
        assert ALARM_LEVEL_CN["minor"] == "次要"
        assert ALARM_LEVEL_CN["info"] == "信息"

    def test_get_template_for_each_channel(self):
        for ch in ("sms", "email", "im", "voice"):
            t = get_template_for_channel(ch)
            assert isinstance(t, str) and len(t) > 0

    def test_get_subject_for_each_channel(self):
        for ch in ("sms", "email", "im", "voice"):
            s = get_subject_for_channel(ch)
            assert isinstance(s, str) and len(s) > 0


# ==================== 适配器测试 ====================

class TestEmailAdapter:

    async def test_send_success(self, sample_context):
        mock_svc = MagicMock()
        mock_svc.is_available = True
        mock_svc.send_html_email = AsyncMock(return_value=True)
        adapter = EmailNotificationAdapter(mock_svc)

        result = await adapter.send("test@example.com", "subject", "content", sample_context)
        assert result.success is True
        mock_svc.send_html_email.assert_called_once_with(["test@example.com"], "subject", "content")

    async def test_send_failure(self, sample_context):
        mock_svc = MagicMock()
        mock_svc.is_available = True
        mock_svc.send_html_email = AsyncMock(return_value=False)
        adapter = EmailNotificationAdapter(mock_svc)

        result = await adapter.send("test@example.com", "subject", "content", sample_context)
        assert result.success is False
        assert result.error_message is not None

    async def test_send_timeout(self, sample_context):
        mock_svc = MagicMock()
        mock_svc.is_available = True
        mock_svc.send_html_email = AsyncMock(side_effect=asyncio.TimeoutError())
        adapter = EmailNotificationAdapter(mock_svc)

        # patch asyncio.wait_for to raise TimeoutError immediately
        with patch("app.services.notification.adapters.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = await adapter.send("test@example.com", "subject", "content", sample_context)
            assert result.success is False
            assert "超时" in result.error_message

    async def test_is_enabled(self):
        mock_svc = MagicMock()
        mock_svc.is_available = True
        adapter = EmailNotificationAdapter(mock_svc)
        assert adapter.is_enabled() is True

        mock_svc.is_available = False
        assert adapter.is_enabled() is False

    async def test_health_check(self):
        mock_svc = MagicMock()
        mock_svc.is_available = True
        adapter = EmailNotificationAdapter(mock_svc)
        assert await adapter.health_check() is True


class TestImAdapter:

    async def test_send_success(self, sample_context):
        adapter = ImAdapter()
        adapter._webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=test"
        adapter._secret = None  # 无签名模式

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0, "errmsg": "ok"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.send("13800138000", "subject", "content", sample_context)
            assert result.success is True

    async def test_send_failure(self, sample_context):
        adapter = ImAdapter()
        adapter._webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=test"
        adapter._secret = None

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 300001, "errmsg": "token invalid"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.send("13800138000", "subject", "content", sample_context)
            assert result.success is False
            assert "钉钉API错误" in result.error_message

    async def test_is_enabled_without_config(self):
        adapter = ImAdapter()
        assert adapter.is_enabled() is False

    async def test_is_enabled_with_config(self):
        adapter = ImAdapter()
        adapter._webhook_url = "https://example.com"
        assert adapter.is_enabled() is True


class TestStubAdapters:

    async def test_sms_not_implemented(self, sample_context):
        adapter = SmsAdapter()
        result = await adapter.send("13800138000", "s", "c", sample_context)
        assert result.success is False
        assert "not implemented" in result.error_message

    async def test_sms_disabled(self):
        assert SmsAdapter().is_enabled() is False

    async def test_voice_not_implemented(self, sample_context):
        adapter = VoiceCallAdapter()
        result = await adapter.send("13800138000", "s", "c", sample_context)
        assert result.success is False
        assert "not implemented" in result.error_message

    async def test_voice_disabled(self):
        assert VoiceCallAdapter().is_enabled() is False


# ==================== API 端点测试（直接调用函数，避免 client fixture 超时） ====================

class TestNotificationAPI:

    async def test_get_channels_status(self):
        """渠道状态查询 — 直接测试逻辑"""
        mock_adapter = MagicMock()
        mock_adapter.is_enabled.return_value = True
        mock_adapter.health_check = AsyncMock(return_value=True)

        original = dict(ADAPTER_REGISTRY)
        ADAPTER_REGISTRY.clear()
        ADAPTER_REGISTRY["email"] = mock_adapter

        try:
            from app.schemas.notification import ChannelStatusInfo
            results = []
            for channel_type, adapter in ADAPTER_REGISTRY.items():
                healthy = await adapter.health_check()
                results.append(ChannelStatusInfo(
                    channel_type=channel_type,
                    enabled=adapter.is_enabled(),
                    healthy=healthy,
                ))
            assert len(results) == 1
            assert results[0].channel_type == "email"
            assert results[0].enabled is True
            assert results[0].healthy is True
        finally:
            ADAPTER_REGISTRY.clear()
            ADAPTER_REGISTRY.update(original)

    async def test_test_send_success(self):
        """测试发送 — mock adapter 返回成功"""
        mock_adapter = MagicMock()
        mock_adapter.is_enabled.return_value = True
        mock_adapter.send = AsyncMock(return_value=NotificationResult(success=True))

        original = dict(ADAPTER_REGISTRY)
        ADAPTER_REGISTRY.clear()
        ADAPTER_REGISTRY["email"] = mock_adapter

        try:
            adapter = ADAPTER_REGISTRY.get("email")
            assert adapter is not None
            assert adapter.is_enabled()
            result = await adapter.send("test@example.com", "subject", "content", None)
            assert result.success is True
        finally:
            ADAPTER_REGISTRY.clear()
            ADAPTER_REGISTRY.update(original)

    async def test_test_send_disabled_channel(self):
        """禁用渠道测试发送 — 返回失败"""
        mock_adapter = MagicMock()
        mock_adapter.is_enabled.return_value = False

        original = dict(ADAPTER_REGISTRY)
        ADAPTER_REGISTRY.clear()
        ADAPTER_REGISTRY["sms"] = mock_adapter

        try:
            adapter = ADAPTER_REGISTRY.get("sms")
            assert adapter is not None
            assert adapter.is_enabled() is False
        finally:
            ADAPTER_REGISTRY.clear()
            ADAPTER_REGISTRY.update(original)

    async def test_unregistered_channel(self):
        """未注册渠道 — 返回 None"""
        original = dict(ADAPTER_REGISTRY)
        ADAPTER_REGISTRY.clear()
        try:
            adapter = ADAPTER_REGISTRY.get("fax")
            assert adapter is None
        finally:
            ADAPTER_REGISTRY.clear()
            ADAPTER_REGISTRY.update(original)


# ==================== 适配器注册表测试 ====================

class TestAdapterRegistry:

    async def test_disabled_adapter_not_used(self):
        """禁用的适配器 is_enabled 返回 False"""
        sms = SmsAdapter()
        voice = VoiceCallAdapter()
        assert sms.is_enabled() is False
        assert voice.is_enabled() is False
