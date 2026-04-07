"""
Story 34.3: 通知策略配置 — Pydantic Schema
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

VALID_CHANNELS = {"sms", "im", "voice", "email"}
VALID_ALARM_LEVELS = {"critical", "major", "minor", "info"}


class NotificationPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    site_id: Optional[int] = None
    alarm_level: str = Field(..., pattern="^(critical|major|minor|info)$")
    time_range_start: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    time_range_end: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    channels: list[str]
    notify_user_ids: list[int] = Field(default_factory=list)
    channel_escalation_enabled: bool = False
    escalation_timeout_minutes: int = Field(5, ge=1, le=60)
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: bool = True

    @model_validator(mode="after")
    def validate_all(self):
        # time_range 必须同时有值或同时为 None
        if (self.time_range_start is None) != (self.time_range_end is None):
            raise ValueError("time_range_start 和 time_range_end 必须同时提供或同时为空")
        # start == end 零长度时段
        if self.time_range_start is not None and self.time_range_start == self.time_range_end:
            raise ValueError("time_range_start 和 time_range_end 不能相同（零长度时段无效）")
        # channels 校验
        if not self.channels:
            raise ValueError("channels 不能为空")
        invalid = set(self.channels) - VALID_CHANNELS
        if invalid:
            raise ValueError(f"无效的渠道类型: {invalid}")
        self.channels = list(dict.fromkeys(self.channels))  # 去重保序
        # escalation 联动
        if self.channel_escalation_enabled:
            if not self.escalation_channel_order:
                raise ValueError("启用渠道升级时必须提供 escalation_channel_order")
            invalid_esc = set(self.escalation_channel_order) - VALID_CHANNELS
            if invalid_esc:
                raise ValueError(f"escalation_channel_order 包含无效渠道: {invalid_esc}")
        return self


class NotificationPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    time_range_start: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    time_range_end: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    channels: Optional[list[str]] = None
    notify_user_ids: Optional[list[int]] = None
    channel_escalation_enabled: Optional[bool] = None
    escalation_timeout_minutes: Optional[int] = Field(None, ge=1, le=60)
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: Optional[bool] = None

    @model_validator(mode="after")
    def validate_update_fields(self):
        # channels 值校验
        if self.channels is not None:
            if not self.channels:
                raise ValueError("channels 不能为空")
            invalid = set(self.channels) - VALID_CHANNELS
            if invalid:
                raise ValueError(f"无效的渠道类型: {invalid}")
            self.channels = list(dict.fromkeys(self.channels))  # 去重保序
        # escalation_channel_order 值校验
        if self.escalation_channel_order is not None:
            invalid_esc = set(self.escalation_channel_order) - VALID_CHANNELS
            if invalid_esc:
                raise ValueError(f"escalation_channel_order 包含无效渠道: {invalid_esc}")
        return self


class NotificationPolicyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    site_id: Optional[int] = None
    alarm_level: str
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    channels: list[str]
    notify_user_ids: list[int]
    channel_escalation_enabled: bool
    escalation_timeout_minutes: int
    escalation_channel_order: Optional[list[str]] = None
    is_enabled: bool
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
