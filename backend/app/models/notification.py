"""
系统通知模型 - Story 24.8
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean

from ..core.database import Base


class SystemNotification(Base):
    """系统内通知表"""

    __tablename__ = "system_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, nullable=False, comment="通知内容")
    notification_type = Column(String(50), nullable=False, comment="通知类型")
    target_role = Column(String(20), nullable=False, comment="目标角色: admin/operator/viewer")
    data = Column(JSON, nullable=True, comment="附加数据")
    is_read = Column(Boolean, default=False, comment="是否已读")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
