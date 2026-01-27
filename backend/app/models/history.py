"""
历史数据模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Index

from ..core.database import Base


class PointHistory(Base):
    """点位历史数据表"""
    __tablename__ = "point_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    value = Column(Float, nullable=False, comment="数值")
    quality = Column(Integer, default=0, comment="数据质量: 0=好 1=不确定 2=坏")
    min_value = Column(Float, comment="周期内最小值")
    max_value = Column(Float, comment="周期内最大值")
    avg_value = Column(Float, comment="周期内平均值")
    recorded_at = Column(DateTime, default=datetime.now, comment="记录时间")

    __table_args__ = (
        Index("idx_history_point_time", "point_id", "recorded_at"),
        Index("idx_history_time", "recorded_at"),
    )


class PointHistoryArchive(Base):
    """历史数据归档表（聚合数据）"""
    __tablename__ = "point_history_archive"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    archive_type = Column(String(20), comment="归档类型: hourly/daily/monthly")
    value_min = Column(Float, comment="最小值")
    value_max = Column(Float, comment="最大值")
    value_avg = Column(Float, comment="平均值")
    value_sum = Column(Float, comment="累计值")
    sample_count = Column(Integer, comment="采样数量")
    recorded_at = Column(DateTime, comment="记录时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class PointChangeLog(Base):
    """点位变化记录表（DI点位）"""
    __tablename__ = "point_change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    old_value = Column(Float, comment="旧值")
    new_value = Column(Float, comment="新值")
    change_type = Column(String(20), comment="变化类型: normal/alarm/recover")
    changed_at = Column(DateTime, default=datetime.now, comment="变化时间")
