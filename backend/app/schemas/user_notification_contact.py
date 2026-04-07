"""
用户通知联系方式 Schema
Story 34.1 — 多渠道告警通知
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

VALID_CHANNEL_TYPES = {"sms", "im", "voice", "email"}
VALID_PLATFORMS = {"dingtalk", "wecom"}


def validate_contact_value(channel_type: str, contact_value: str) -> None:
    """独立校验函数，供 Create schema 和 API 层 Update 共用"""
    if channel_type in ("sms", "voice"):
        if not PHONE_PATTERN.match(contact_value):
            raise ValueError("sms/voice 渠道的联系方式必须为有效中国手机号（11位数字，1开头）")
    if channel_type == "email":
        if not EMAIL_PATTERN.match(contact_value):
            raise ValueError("email 渠道的联系方式必须为有效邮箱格式")


class NotificationContactCreate(BaseModel):
    channel_type: str = Field(..., pattern="^(sms|im|voice|email)$")
    platform: Optional[str] = Field(None, pattern="^(dingtalk|wecom)$")
    contact_value: str = Field(..., min_length=1, max_length=200)
    is_enabled: bool = True

    @model_validator(mode="after")
    def validate_all(self):
        # platform 校验
        if self.channel_type == "im" and not self.platform:
            raise ValueError("im 渠道必须指定 platform (dingtalk/wecom)")
        if self.channel_type != "im" and self.platform:
            raise ValueError("非 im 渠道不应指定 platform")
        # contact_value 格式校验
        validate_contact_value(self.channel_type, self.contact_value)
        return self


class NotificationContactUpdate(BaseModel):
    """更新时 contact_value 格式校验在 API 层执行（需从 DB 读取 channel_type）"""

    contact_value: Optional[str] = Field(None, min_length=1, max_length=200)
    is_enabled: Optional[bool] = None


class NotificationContactInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    channel_type: str
    platform: Optional[str] = None
    contact_value: str
    is_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ImportFromProfileResponse(BaseModel):
    """从账户信息导入的返回值"""

    created: list[NotificationContactInfo] = []
    skipped: int = 0
