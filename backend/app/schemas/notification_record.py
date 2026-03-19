"""
通知记录查询 Schema
Story 34.7 — 通知管理前端
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationRecordInfo(BaseModel):
    id: int
    alarm_id: Optional[int] = None
    alarm_level: Optional[str] = None  # 来自 JOIN Alarm 表
    user_id: Optional[int] = None
    policy_id: Optional[int] = None
    channel_type: str
    platform: Optional[str] = None
    contact_value: str
    content_summary: Optional[str] = None
    status: str
    retry_count: int = 0
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
