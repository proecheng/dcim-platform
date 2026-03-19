"""
通知渠道适配器
Story 34.2 — 通知渠道适配器框架
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from app.schemas.notification import AlarmNotificationContext

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    success: bool
    error_message: Optional[str] = None


class NotificationAdapter(ABC):
    """通知渠道适配器基类"""

    @abstractmethod
    async def send(
        self,
        contact_value: str,
        subject: str,
        content: str,
        context: Optional[AlarmNotificationContext],
    ) -> NotificationResult: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def is_enabled(self) -> bool: ...


class EmailNotificationAdapter(NotificationAdapter):
    """邮件适配器 — 包装现有 EmailService 单例"""

    def __init__(self, email_svc):
        self._email_svc = email_svc

    def is_enabled(self) -> bool:
        return self._email_svc.is_available

    async def send(self, contact_value, subject, content, context):
        try:
            success = await asyncio.wait_for(
                self._email_svc.send_html_email([contact_value], subject, content),
                timeout=45,
            )
            if success:
                return NotificationResult(success=True)
            return NotificationResult(success=False, error_message="邮件发送返回 False")
        except asyncio.TimeoutError:
            return NotificationResult(success=False, error_message="邮件发送超时(45s)")
        except Exception as e:
            return NotificationResult(success=False, error_message=str(e))

    async def health_check(self) -> bool:
        return self._email_svc.is_available


class ImAdapter(NotificationAdapter):
    """钉钉 Webhook 适配器 — httpx.AsyncClient 原生异步"""

    def __init__(self):
        self._webhook_url: Optional[str] = None
        self._secret: Optional[str] = None

    async def load_config(self):
        """从 SystemConfig 加载钉钉配置"""
        from sqlalchemy import select
        from app.core.database import async_session
        from app.models.config import SystemConfig

        try:
            async with async_session() as session:
                for key in (
                    "notification.im.dingtalk.webhook_url",
                    "notification.im.dingtalk.secret",
                ):
                    result = await session.execute(
                        select(SystemConfig).where(SystemConfig.key == key)
                    )
                    cfg = result.scalar_one_or_none()
                    if cfg and cfg.value:
                        if "webhook_url" in key:
                            self._webhook_url = cfg.value
                        else:
                            self._secret = cfg.value
        except Exception as e:
            logger.warning("加载钉钉配置失败: %s", e)

    def is_enabled(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, contact_value, subject, content, context):
        import httpx

        url = self._webhook_url
        if self._secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{self._secret}"
            hmac_code = hmac.new(
                self._secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": subject, "text": content},
            "at": {"atMobiles": [contact_value] if contact_value else []},
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                data = resp.json()
                if data.get("errcode") == 0:
                    return NotificationResult(success=True)
                return NotificationResult(
                    success=False, error_message=f"钉钉API错误: {data}"
                )
        except Exception as e:
            return NotificationResult(success=False, error_message=str(e))

    async def health_check(self) -> bool:
        return self.is_enabled()


class SmsAdapter(NotificationAdapter):
    """短信适配器 — V4.3.1 交付，当前为桩实现"""

    async def send(self, contact_value, subject, content, context):
        return NotificationResult(
            success=False, error_message="SMS adapter not implemented"
        )

    async def health_check(self):
        return False

    def is_enabled(self):
        return False


class VoiceCallAdapter(NotificationAdapter):
    """语音电话适配器 — V4.3.1 交付，当前为桩实现"""

    async def send(self, contact_value, subject, content, context):
        return NotificationResult(
            success=False, error_message="Voice adapter not implemented"
        )

    async def health_check(self):
        return False

    def is_enabled(self):
        return False


# ==================== 适配器注册表 ====================

ADAPTER_REGISTRY: dict[str, NotificationAdapter] = {}


async def init_adapters():
    """初始化并注册所有适配器 — 在 main.py lifespan 启动时调用"""
    from app.services.email_service import email_service

    ADAPTER_REGISTRY["email"] = EmailNotificationAdapter(email_service)

    im_adapter = ImAdapter()
    await im_adapter.load_config()
    ADAPTER_REGISTRY["im"] = im_adapter

    ADAPTER_REGISTRY["sms"] = SmsAdapter()
    ADAPTER_REGISTRY["voice"] = VoiceCallAdapter()

    enabled = [k for k, v in ADAPTER_REGISTRY.items() if v.is_enabled()]
    logger.info("通知适配器已初始化: 启用=%s", enabled)
