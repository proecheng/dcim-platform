"""
用户通知联系方式模型
Story 34.1 — 多渠道告警通知
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from app.core.database import Base


class UserNotificationContact(Base):
    """用户通知联系方式（EAV模式）"""
    __tablename__ = "user_notification_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    channel_type = Column(String(20), nullable=False, comment="渠道类型: sms|im|voice|email")
    platform = Column(String(20), nullable=True, comment="平台: dingtalk|wecom|null")
    contact_value = Column(String(200), nullable=False, comment="联系方式值")
    is_enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    __table_args__ = (
        Index("ix_unc_user_id", "user_id"),
    )
