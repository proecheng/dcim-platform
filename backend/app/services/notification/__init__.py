"""
通知服务包
Story 34.2 — 通知渠道适配器框架
"""

from .adapters import (
    ADAPTER_REGISTRY,
    EmailNotificationAdapter,
    ImAdapter,
    NotificationAdapter,
    NotificationResult,
    SmsAdapter,
    VoiceCallAdapter,
    init_adapters,
)
from .dispatcher import NotificationDispatcher, notification_dispatcher

__all__ = [
    "ADAPTER_REGISTRY",
    "EmailNotificationAdapter",
    "ImAdapter",
    "NotificationAdapter",
    "NotificationResult",
    "SmsAdapter",
    "VoiceCallAdapter",
    "init_adapters",
    "NotificationDispatcher",
    "notification_dispatcher",
]
