"""
联动策略模型
Story 9-1: 联动引擎核心框架
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..core.database import Base


class LinkagePolicy(Base):
    """联动策略表"""

    __tablename__ = "linkage_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="策略名称")
    description = Column(Text, nullable=True, comment="策略描述")
    trigger_type = Column(String(50), nullable=False, comment="触发类型: alarm.triggered/alarm.resolved等")
    trigger_condition = Column(JSON, comment="触发条件")
    priority = Column(String(20), default="normal", comment="优先级: fire_signal/critical/normal")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_system = Column(Boolean, default=False, comment="是否系统内置策略")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    actions = relationship("LinkageAction", backref="policy", lazy="selectin", cascade="all, delete-orphan")


class LinkageAction(Base):
    """联动动作表"""

    __tablename__ = "linkage_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("linkage_policies.id"), nullable=False, comment="策略ID")
    action_type = Column(String(50), nullable=False, comment="动作类型: ALARM_NOTIFY/WEBHOOK等")
    action_config = Column(JSON, comment="动作配置")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    timeout_seconds = Column(Integer, default=3, comment="超时时间(秒)")
    retry_count = Column(Integer, default=0, comment="重试次数")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class LinkageExecution(Base):
    """联动执行记录表"""

    __tablename__ = "linkage_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("linkage_policies.id"), nullable=False, comment="策略ID")
    event_id = Column(String(36), nullable=False, comment="事件ID")
    trigger_source = Column(String(200), comment="触发来源")
    trigger_event = Column(JSON, comment="触发事件快照")
    status = Column(String(20), default="executing", comment="状态: executing/completed/partial_failure/failed")
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    total_duration_ms = Column(Integer, nullable=True, comment="总耗时(毫秒)")

    # 关系
    logs = relationship("LinkageLog", backref="execution", lazy="selectin", cascade="all, delete-orphan")


class LinkageLog(Base):
    """联动执行日志表"""

    __tablename__ = "linkage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("linkage_executions.id"), nullable=False, comment="执行记录ID")
    action_id = Column(Integer, nullable=True, comment="动作ID")
    action_type = Column(String(50), comment="动作类型")
    action_config = Column(JSON, comment="动作配置快照")
    status = Column(String(20), nullable=False, comment="状态: success/failed/timeout/skipped")
    error_message = Column(Text, nullable=True, comment="错误信息")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    duration_ms = Column(Integer, nullable=True, comment="耗时(毫秒)")


class LinkageRecovery(Base):
    """联动恢复记录表 — Story 9-4"""

    __tablename__ = "linkage_recoveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("linkage_executions.id"), nullable=False, comment="关联执行记录ID")
    operator = Column(String(50), nullable=False, comment="操作人")
    mode = Column(String(20), default="auto", comment="恢复模式: auto(一键)/manual(逐项)")
    status = Column(String(20), default="executing", comment="状态: executing/completed/partial_recovery/failed")
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    total_duration_ms = Column(Integer, nullable=True, comment="总耗时(毫秒)")

    # 关系
    logs = relationship("LinkageRecoveryLog", backref="recovery", lazy="selectin", cascade="all, delete-orphan")


class LinkageRecoveryLog(Base):
    """联动恢复步骤日志表 — Story 9-4"""

    __tablename__ = "linkage_recovery_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recovery_id = Column(Integer, ForeignKey("linkage_recoveries.id"), nullable=False, comment="恢复记录ID")
    step_order = Column(Integer, default=0, comment="恢复步骤顺序")
    action_type = Column(String(50), comment="动作类型")
    target_type = Column(String(50), comment="目标设备类型")
    recovery_command = Column(String(50), comment="恢复命令")
    action_config = Column(JSON, comment="恢复动作配置")
    status = Column(String(20), default="pending", comment="状态: pending/executing/success/failed/skipped")
    error_message = Column(Text, nullable=True, comment="错误信息")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    duration_ms = Column(Integer, nullable=True, comment="耗时(毫秒)")
