"""
控制与日志模型
"""
from datetime import datetime, date
from sqlalchemy import String, DateTime, Float, Integer, Text, ForeignKey, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


class ControlCommand(Base):
    """控制指令表"""
    __tablename__ = "control_commands"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    point_id: Mapped[int] = mapped_column(ForeignKey("points.id"), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    executed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, executing, success, failed
    result_message: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class License(Base):
    """系统授权表"""
    __tablename__ = "license"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    license_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    license_type: Mapped[str] = mapped_column(String(20), nullable=False)  # basic, standard, enterprise, unlimited
    max_points: Mapped[int] = mapped_column(Integer, nullable=False)
    expire_date: Mapped[date] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=True)  # point, alarm, user, threshold
    target_id: Mapped[int] = mapped_column(Integer, nullable=True)
    old_value: Mapped[str] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
