"""
通知记录模型
Story 34.2 — 通知渠道适配器框架
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text
from app.core.database import Base


class NotificationRecord(Base):
    """通知发送记录"""

    __tablename__ = "notification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True, comment="关联告警")
    policy_id = Column(Integer, nullable=True, comment="触发策略ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="通知对象")
    channel_type = Column(String(20), nullable=False, comment="渠道类型: sms|im|voice|email")
    platform = Column(String(20), nullable=True, comment="平台: dingtalk|wecom|null")
    contact_value = Column(String(200), nullable=False, comment="实际发送的联系方式")
    content_summary = Column(String(500), nullable=True, comment="发送内容摘要")
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending|sent|failed|retrying")
    retry_count = Column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries = Column(Integer, nullable=False, default=3, comment="最大重试次数")
    sent_at = Column(DateTime, nullable=True, comment="发送成功时间")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("ix_nr_alarm_id", "alarm_id"),
        Index("ix_nr_status", "status"),
        Index("ix_nr_created_at", "created_at"),
    )
