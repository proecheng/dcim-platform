"""
运维管理数据模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.operation import (
    WorkOrderStatus,
    WorkOrderType,
    WorkOrderPriority,
    InspectionStatus
)


# ==================== 工单 Schemas ====================

class WorkOrderBase(BaseModel):
    """工单基础模型"""
    title: str = Field(..., description="工单标题")
    description: Optional[str] = Field(None, description="工单描述")
    order_type: Optional[WorkOrderType] = Field(WorkOrderType.other, description="工单类型")
    priority: Optional[WorkOrderPriority] = Field(WorkOrderPriority.medium, description="优先级")
    device_id: Optional[int] = Field(None, description="关联设备ID")
    device_name: Optional[str] = Field(None, description="设备名称")
    location: Optional[str] = Field(None, description="位置")
    reporter: Optional[str] = Field(None, description="报修人")
    reporter_phone: Optional[str] = Field(None, description="报修人电话")
    deadline: Optional[datetime] = Field(None, description="截止时间")


class WorkOrderCreate(WorkOrderBase):
    """创建工单"""
    pass


class WorkOrderUpdate(BaseModel):
    """更新工单"""
    title: Optional[str] = Field(None, description="工单标题")
    description: Optional[str] = Field(None, description="工单描述")
    order_type: Optional[WorkOrderType] = Field(None, description="工单类型")
    priority: Optional[WorkOrderPriority] = Field(None, description="优先级")
    device_id: Optional[int] = Field(None, description="关联设备ID")
    device_name: Optional[str] = Field(None, description="设备名称")
    location: Optional[str] = Field(None, description="位置")
    reporter: Optional[str] = Field(None, description="报修人")
    reporter_phone: Optional[str] = Field(None, description="报修人电话")
    deadline: Optional[datetime] = Field(None, description="截止时间")
    status: Optional[WorkOrderStatus] = Field(None, description="工单状态")
    assignee: Optional[str] = Field(None, description="处理人")
    solution: Optional[str] = Field(None, description="解决方案")
    root_cause: Optional[str] = Field(None, description="根本原因")
    remarks: Optional[str] = Field(None, description="备注")


class WorkOrderResponse(WorkOrderBase):
    """工单响应"""
    id: int = Field(..., description="ID")
    order_no: str = Field(..., description="工单编号")
    status: WorkOrderStatus = Field(WorkOrderStatus.pending, description="工单状态")
    assignee: Optional[str] = Field(None, description="处理人")
    created_at: datetime = Field(..., description="创建时间")
    assigned_at: Optional[datetime] = Field(None, description="派单时间")
    started_at: Optional[datetime] = Field(None, description="开始处理时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    solution: Optional[str] = Field(None, description="解决方案")
    root_cause: Optional[str] = Field(None, description="根本原因")

    class Config:
        from_attributes = True


# ==================== 工单日志 Schemas ====================

class WorkOrderLogResponse(BaseModel):
    """工单日志响应"""
    id: int = Field(..., description="ID")
    order_id: int = Field(..., description="工单ID")
    action: Optional[str] = Field(None, description="操作类型")
    content: Optional[str] = Field(None, description="操作内容")
    operator: Optional[str] = Field(None, description="操作人")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ==================== 巡检计划 Schemas ====================

class InspectionPlanBase(BaseModel):
    """巡检计划基础模型"""
    name: str = Field(..., description="计划名称")
    description: Optional[str] = Field(None, description="计划描述")
    frequency: Optional[str] = Field(None, description="巡检频率(daily/weekly/monthly)")
    location: Optional[str] = Field(None, description="巡检位置")
    check_items: Optional[str] = Field(None, description="检查项目(JSON字符串)")
    assignee: Optional[str] = Field(None, description="负责人")
    is_active: Optional[bool] = Field(True, description="是否启用")


class InspectionPlanCreate(InspectionPlanBase):
    """创建巡检计划"""
    pass


class InspectionPlanUpdate(BaseModel):
    """更新巡检计划"""
    name: Optional[str] = Field(None, description="计划名称")
    description: Optional[str] = Field(None, description="计划描述")
    frequency: Optional[str] = Field(None, description="巡检频率(daily/weekly/monthly)")
    location: Optional[str] = Field(None, description="巡检位置")
    check_items: Optional[str] = Field(None, description="检查项目(JSON字符串)")
    assignee: Optional[str] = Field(None, description="负责人")
    is_active: Optional[bool] = Field(None, description="是否启用")


class InspectionPlanResponse(InspectionPlanBase):
    """巡检计划响应"""
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 巡检任务 Schemas ====================

class InspectionTaskBase(BaseModel):
    """巡检任务基础模型"""
    plan_id: Optional[int] = Field(None, description="巡检计划ID")
    assignee: Optional[str] = Field(None, description="执行人")
    scheduled_date: Optional[datetime] = Field(None, description="计划执行日期")


class InspectionTaskCreate(InspectionTaskBase):
    """创建巡检任务"""
    pass


class InspectionTaskUpdate(BaseModel):
    """更新巡检任务"""
    status: Optional[InspectionStatus] = Field(None, description="任务状态")
    assignee: Optional[str] = Field(None, description="执行人")
    result: Optional[str] = Field(None, description="巡检结果(JSON)")
    abnormal_count: Optional[int] = Field(None, description="异常数量")
    remarks: Optional[str] = Field(None, description="备注")


class InspectionTaskResponse(InspectionTaskBase):
    """巡检任务响应"""
    id: int = Field(..., description="ID")
    task_no: str = Field(..., description="任务编号")
    status: InspectionStatus = Field(InspectionStatus.pending, description="任务状态")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    result: Optional[str] = Field(None, description="巡检结果(JSON)")
    abnormal_count: Optional[int] = Field(0, description="异常数量")
    remarks: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ==================== 知识库 Schemas ====================

class KnowledgeBaseSchema(BaseModel):
    """知识库基础模型"""
    title: str = Field(..., description="标题")
    category: Optional[str] = Field(None, description="分类")
    content: Optional[str] = Field(None, description="内容")
    tags: Optional[str] = Field(None, description="标签")
    is_published: Optional[bool] = Field(False, description="是否发布")
    author: Optional[str] = Field(None, description="作者")


class KnowledgeCreate(KnowledgeBaseSchema):
    """创建知识库条目"""
    pass


class KnowledgeUpdate(BaseModel):
    """更新知识库条目"""
    title: Optional[str] = Field(None, description="标题")
    category: Optional[str] = Field(None, description="分类")
    content: Optional[str] = Field(None, description="内容")
    tags: Optional[str] = Field(None, description="标签")
    is_published: Optional[bool] = Field(None, description="是否发布")
    author: Optional[str] = Field(None, description="作者")


class KnowledgeResponse(KnowledgeBaseSchema):
    """知识库条目响应"""
    id: int = Field(..., description="ID")
    view_count: int = Field(0, description="查看次数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 运维统计 Schemas ====================

class OperationStatistics(BaseModel):
    """运维统计信息"""
    total_orders: int = Field(0, description="工单总数")
    pending_orders: int = Field(0, description="待处理工单数")
    processing_orders: int = Field(0, description="处理中工单数")
    completed_orders: int = Field(0, description="已完成工单数")
    overdue_inspections: int = Field(0, description="逾期巡检数")
    knowledge_count: int = Field(0, description="知识库条目数")
