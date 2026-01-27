"""
运维管理模型
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from ..core.database import Base


# ==================== 枚举定义 ====================

class WorkOrderStatus(str, PyEnum):
    """工单状态枚举"""
    pending = "待处理"
    assigned = "已派单"
    processing = "处理中"
    completed = "已完成"
    closed = "已关闭"
    cancelled = "已取消"


class WorkOrderType(str, PyEnum):
    """工单类型枚举"""
    fault = "故障报修"
    maintenance = "日常维护"
    inspection = "巡检任务"
    change = "变更请求"
    other = "其他"


class WorkOrderPriority(str, PyEnum):
    """工单优先级枚举"""
    critical = "紧急"
    high = "高"
    medium = "中"
    low = "低"


class InspectionStatus(str, PyEnum):
    """巡检状态枚举"""
    pending = "待巡检"
    in_progress = "巡检中"
    completed = "已完成"
    overdue = "已逾期"


# ==================== 工单模型 ====================

class WorkOrder(Base):
    """工单表"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(50), unique=True, nullable=False, comment="工单编号")
    title = Column(String(200), nullable=False, comment="工单标题")
    description = Column(Text, comment="工单描述")
    order_type = Column(Enum(WorkOrderType), default=WorkOrderType.other, comment="工单类型")
    priority = Column(Enum(WorkOrderPriority), default=WorkOrderPriority.medium, comment="优先级")
    status = Column(Enum(WorkOrderStatus), default=WorkOrderStatus.pending, comment="工单状态")
    device_id = Column(Integer, comment="关联设备ID")
    device_name = Column(String(100), comment="设备名称")
    location = Column(String(200), comment="位置")
    reporter = Column(String(100), comment="报修人")
    reporter_phone = Column(String(50), comment="报修人电话")
    assignee = Column(String(100), comment="处理人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    assigned_at = Column(DateTime, comment="派单时间")
    started_at = Column(DateTime, comment="开始处理时间")
    completed_at = Column(DateTime, comment="完成时间")
    closed_at = Column(DateTime, comment="关闭时间")
    deadline = Column(DateTime, comment="截止时间")
    solution = Column(Text, comment="解决方案")
    root_cause = Column(Text, comment="根本原因")
    remarks = Column(Text, comment="备注")
    satisfaction = Column(Integer, comment="满意度(1-5)")
    feedback = Column(Text, comment="反馈")

    # 关系
    logs = relationship("WorkOrderLog", back_populates="work_order", cascade="all, delete-orphan")


class WorkOrderLog(Base):
    """工单日志表"""
    __tablename__ = "work_order_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, comment="工单ID")
    action = Column(String(50), comment="操作类型")
    content = Column(Text, comment="操作内容")
    operator = Column(String(100), comment="操作人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    work_order = relationship("WorkOrder", back_populates="logs")


# ==================== 巡检计划模型 ====================

class InspectionPlan(Base):
    """巡检计划表"""
    __tablename__ = "inspection_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="计划名称")
    description = Column(Text, comment="计划描述")
    frequency = Column(String(50), comment="巡检频率(daily/weekly/monthly)")
    location = Column(String(200), comment="巡检位置")
    check_items = Column(Text, comment="检查项目(JSON字符串)")
    assignee = Column(String(100), comment="负责人")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    tasks = relationship("InspectionTask", back_populates="plan", cascade="all, delete-orphan")


class InspectionTask(Base):
    """巡检任务表"""
    __tablename__ = "inspection_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("inspection_plans.id"), comment="巡检计划ID")
    task_no = Column(String(50), unique=True, nullable=False, comment="任务编号")
    status = Column(Enum(InspectionStatus), default=InspectionStatus.pending, comment="任务状态")
    assignee = Column(String(100), comment="执行人")
    scheduled_date = Column(DateTime, comment="计划执行日期")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    result = Column(Text, comment="巡检结果(JSON)")
    abnormal_count = Column(Integer, default=0, comment="异常数量")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    plan = relationship("InspectionPlan", back_populates="tasks")


# ==================== 知识库模型 ====================

class KnowledgeBase(Base):
    """知识库表"""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="标题")
    category = Column(String(100), comment="分类")
    content = Column(Text, comment="内容")
    tags = Column(String(500), comment="标签")
    view_count = Column(Integer, default=0, comment="查看次数")
    is_published = Column(Boolean, default=False, comment="是否发布")
    author = Column(String(100), comment="作者")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
