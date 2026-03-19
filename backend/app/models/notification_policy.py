"""
Story 34.3: 通知策略配置 — NotificationPolicy ORM 模型
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)

from app.core.database import Base


class NotificationPolicy(Base):
    __tablename__ = "notification_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="策略名称")
    site_id = Column(
        Integer,
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=True,
        comment="站点ID, NULL=全局默认",
    )
    alarm_level = Column(
        String(20), nullable=False, comment="告警级别: critical|major|minor|info"
    )
    time_range_start = Column(
        String(5), nullable=True, comment="时段开始 HH:MM, NULL=全天"
    )
    time_range_end = Column(
        String(5), nullable=True, comment="时段结束 HH:MM"
    )
    channels = Column(JSON, nullable=False, comment='渠道组合: ["im","sms"]')
    notify_user_ids = Column(JSON, nullable=False, comment="通知对象: [1,2,3]")
    channel_escalation_enabled = Column(
        Boolean, default=False, nullable=False, comment="是否启用渠道升级"
    )
    escalation_timeout_minutes = Column(
        Integer, default=5, nullable=False, comment="渠道升级超时(分钟)"
    )
    escalation_channel_order = Column(
        JSON, nullable=True, comment='升级顺序: ["im","sms","voice"]'
    )
    is_enabled = Column(
        Boolean, default=True, nullable=False, comment="是否启用"
    )
    is_default = Column(
        Boolean, default=False, nullable=False, comment="是否为系统默认(不可删除)"
    )
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )

    __table_args__ = (
        Index("ix_np_site_level", "site_id", "alarm_level"),
    )
