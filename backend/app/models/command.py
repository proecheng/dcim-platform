"""
控制命令分级确认模型
Story 9-6: 控制命令分级确认
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON

from ..core.database import Base


class CommandApproval(Base):
    """命令审批工单表"""
    __tablename__ = "command_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command_type = Column(String(50), nullable=False, comment="命令类型标识")
    risk_level = Column(String(20), nullable=False, comment="风险等级: normal/critical")
    target_device_id = Column(Integer, nullable=False, comment="目标设备ID")
    target_device_name = Column(String(100), nullable=False, comment="目标设备名称")
    command_content = Column(JSON, comment="命令内容（参数）")
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="发起人ID")
    requester_name = Column(String(50), nullable=False, comment="发起人用户名")
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="审批人ID")
    approver_name = Column(String(50), nullable=True, comment="审批人用户名")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected/cancelled/timeout")
    reject_reason = Column(Text, nullable=True, comment="驳回原因")
    timeout_minutes = Column(Integer, default=30, comment="超时时间(分钟)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    approved_at = Column(DateTime, nullable=True, comment="审批时间")
    executed_at = Column(DateTime, nullable=True, comment="执行时间")
    expired_at = Column(DateTime, nullable=False, comment="过期时间")


class CommandAuditLog(Base):
    """命令审计日志表"""
    __tablename__ = "command_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command_type = Column(String(50), nullable=False, comment="命令类型")
    risk_level = Column(String(20), nullable=False, comment="风险等级")
    target_device_id = Column(Integer, nullable=False, comment="目标设备ID")
    target_device_name = Column(String(100), nullable=False, comment="目标设备名称")
    command_content = Column(JSON, comment="命令内容")
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="操作人ID")
    operator_name = Column(String(50), nullable=False, comment="操作人用户名")
    approval_id = Column(Integer, ForeignKey("command_approvals.id"), nullable=True, comment="关联审批ID")
    result = Column(String(20), nullable=False, comment="结果: success/failed/cancelled/timeout/pending")
    result_message = Column(Text, nullable=True, comment="结果描述")
    created_at = Column(DateTime, default=datetime.now, comment="记录时间")
