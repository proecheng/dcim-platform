"""
运维管理 API - v1
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.operation import (
    WorkOrder, WorkOrderLog, WorkOrderStatus, WorkOrderPriority,
    InspectionPlan, InspectionTask, InspectionStatus,
    KnowledgeBase
)
from ...schemas.operation import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderLogResponse,
    InspectionPlanCreate, InspectionPlanUpdate, InspectionPlanResponse,
    InspectionTaskCreate, InspectionTaskUpdate, InspectionTaskResponse,
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse,
    OperationStatistics
)

router = APIRouter(prefix="/operation", tags=["运维管理"])


# ==================== 辅助函数 ====================

async def _generate_order_no(db: AsyncSession, prefix: str) -> str:
    """
    生成订单/任务编号

    Args:
        db: 数据库会话
        prefix: 编号前缀 (WO 或 IT)

    Returns:
        格式化的编号 (如 WO-20240115-001)
    """
    today = datetime.now().strftime("%Y%m%d")

    if prefix == "WO":
        result = await db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.order_no.like(f"WO-{today}-%")
            )
        )
        count = result.scalar() or 0
    elif prefix == "IT":
        result = await db.execute(
            select(func.count(InspectionTask.id)).where(
                InspectionTask.task_no.like(f"IT-{today}-%")
            )
        )
        count = result.scalar() or 0
    else:
        count = 0

    return f"{prefix}-{today}-{count + 1:03d}"


# ==================== 请求体模型 ====================

class AssignRequest(BaseModel):
    """派单请求"""
    assignee: str = Field(..., description="处理人")


class CompleteWorkOrderRequest(BaseModel):
    """完成工单请求"""
    solution: Optional[str] = Field(None, description="解决方案")
    root_cause: Optional[str] = Field(None, description="根本原因")


class AddLogRequest(BaseModel):
    """添加日志请求"""
    action: str = Field(..., description="操作类型")
    content: str = Field(..., description="操作内容")
    operator: str = Field(..., description="操作人")


class CompleteTaskRequest(BaseModel):
    """完成巡检任务请求"""
    result: Optional[str] = Field(None, description="巡检结果(JSON)")
    abnormal_count: Optional[int] = Field(None, description="异常数量")


# ==================== 工单管理 ====================

@router.get("/workorders", response_model=List[WorkOrderResponse], summary="获取工单列表")
async def get_work_orders(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    status: Optional[WorkOrderStatus] = Query(None, description="工单状态过滤"),
    priority: Optional[WorkOrderPriority] = Query(None, description="优先级过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取工单列表（分页）
    """
    query = select(WorkOrder)

    if status:
        query = query.where(WorkOrder.status == status)
    if priority:
        query = query.where(WorkOrder.priority == priority)

    query = query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    return [WorkOrderResponse.model_validate(order) for order in orders]


@router.post("/workorders", response_model=WorkOrderResponse, summary="创建工单")
async def create_work_order(
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建工单
    """
    order_no = await _generate_order_no(db, "WO")
    order = WorkOrder(
        order_no=order_no,
        **data.model_dump()
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 添加创建日志
    log = WorkOrderLog(
        order_id=order.id,
        action="创建",
        content=f"工单 {order_no} 创建成功",
        operator="系统"
    )
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.get("/workorders/{id}", response_model=WorkOrderResponse, summary="获取工单详情")
async def get_work_order(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取工单详情
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    return WorkOrderResponse.model_validate(order)


@router.put("/workorders/{id}", response_model=WorkOrderResponse, summary="更新工单")
async def update_work_order(
    id: int,
    data: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新工单信息
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(order, key, value)

    await db.commit()
    await db.refresh(order)

    return WorkOrderResponse.model_validate(order)


@router.delete("/workorders/{id}", summary="删除工单")
async def delete_work_order(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除工单
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    await db.delete(order)
    await db.commit()

    return {"message": "操作成功"}


@router.post("/workorders/{id}/assign", response_model=WorkOrderResponse, summary="派单")
async def assign_work_order(
    id: int,
    data: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    派单给指定处理人
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    order.assignee = data.assignee
    order.assigned_at = datetime.now()
    order.status = WorkOrderStatus.assigned

    await db.commit()
    await db.refresh(order)

    # 添加派单日志
    log = WorkOrderLog(
        order_id=id,
        action="派单",
        content=f"工单已派发给 {data.assignee}",
        operator="系统"
    )
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/start", response_model=WorkOrderResponse, summary="开始处理工单")
async def start_work_order(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    开始处理工单
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    order.status = WorkOrderStatus.processing
    order.started_at = datetime.now()

    await db.commit()
    await db.refresh(order)

    # 添加开始处理日志
    log = WorkOrderLog(
        order_id=id,
        action="开始处理",
        content="工单开始处理",
        operator=order.assignee or "系统"
    )
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/complete", response_model=WorkOrderResponse, summary="完成工单")
async def complete_work_order(
    id: int,
    data: CompleteWorkOrderRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    完成工单
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    order.status = WorkOrderStatus.completed
    order.completed_at = datetime.now()
    if data.solution:
        order.solution = data.solution
    if data.root_cause:
        order.root_cause = data.root_cause

    await db.commit()
    await db.refresh(order)

    # 添加完成日志
    log = WorkOrderLog(
        order_id=id,
        action="完成",
        content="工单处理完成",
        operator=order.assignee or "系统"
    )
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.get("/workorders/{id}/logs", response_model=List[WorkOrderLogResponse], summary="获取工单日志")
async def get_work_order_logs(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取工单日志
    """
    # 检查工单是否存在
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    result = await db.execute(
        select(WorkOrderLog)
        .where(WorkOrderLog.order_id == id)
        .order_by(WorkOrderLog.created_at.desc())
    )
    logs = result.scalars().all()

    return [WorkOrderLogResponse.model_validate(log) for log in logs]


@router.post("/workorders/{id}/logs", response_model=WorkOrderLogResponse, summary="添加工单日志")
async def add_work_order_log(
    id: int,
    data: AddLogRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    添加工单日志
    """
    # 检查工单是否存在
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    log = WorkOrderLog(
        order_id=id,
        action=data.action,
        content=data.content,
        operator=data.operator
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return WorkOrderLogResponse.model_validate(log)


# ==================== 巡检计划管理 ====================

@router.get("/plans", response_model=List[InspectionPlanResponse], summary="获取巡检计划列表")
async def get_inspection_plans(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取巡检计划列表（分页）
    """
    query = select(InspectionPlan).offset(skip).limit(limit)
    result = await db.execute(query)
    plans = result.scalars().all()

    return [InspectionPlanResponse.model_validate(plan) for plan in plans]


@router.post("/plans", response_model=InspectionPlanResponse, summary="创建巡检计划")
async def create_inspection_plan(
    data: InspectionPlanCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建巡检计划
    """
    plan = InspectionPlan(**data.model_dump())

    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    return InspectionPlanResponse.model_validate(plan)


@router.get("/plans/{id}", response_model=InspectionPlanResponse, summary="获取巡检计划详情")
async def get_inspection_plan(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取巡检计划详情
    """
    result = await db.execute(select(InspectionPlan).where(InspectionPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="巡检计划不存在")

    return InspectionPlanResponse.model_validate(plan)


@router.put("/plans/{id}", response_model=InspectionPlanResponse, summary="更新巡检计划")
async def update_inspection_plan(
    id: int,
    data: InspectionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新巡检计划信息
    """
    result = await db.execute(select(InspectionPlan).where(InspectionPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="巡检计划不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(plan, key, value)

    plan.updated_at = datetime.now()
    await db.commit()
    await db.refresh(plan)

    return InspectionPlanResponse.model_validate(plan)


@router.delete("/plans/{id}", summary="删除巡检计划")
async def delete_inspection_plan(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除巡检计划
    """
    result = await db.execute(select(InspectionPlan).where(InspectionPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="巡检计划不存在")

    await db.delete(plan)
    await db.commit()

    return {"message": "操作成功"}


# ==================== 巡检任务管理 ====================

@router.get("/tasks", response_model=List[InspectionTaskResponse], summary="获取巡检任务列表")
async def get_inspection_tasks(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    status: Optional[InspectionStatus] = Query(None, description="任务状态过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取巡检任务列表（分页）
    """
    query = select(InspectionTask)

    if status:
        query = query.where(InspectionTask.status == status)

    query = query.order_by(InspectionTask.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return [InspectionTaskResponse.model_validate(task) for task in tasks]


@router.post("/tasks", response_model=InspectionTaskResponse, summary="创建巡检任务")
async def create_inspection_task(
    data: InspectionTaskCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建巡检任务
    """
    task_no = await _generate_order_no(db, "IT")
    task = InspectionTask(
        task_no=task_no,
        **data.model_dump()
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.get("/tasks/{id}", response_model=InspectionTaskResponse, summary="获取巡检任务详情")
async def get_inspection_task(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取巡检任务详情
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    return InspectionTaskResponse.model_validate(task)


@router.put("/tasks/{id}", response_model=InspectionTaskResponse, summary="更新巡检任务")
async def update_inspection_task(
    id: int,
    data: InspectionTaskUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新巡检任务信息
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(task, key, value)

    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.post("/tasks/{id}/start", response_model=InspectionTaskResponse, summary="开始巡检任务")
async def start_inspection_task(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    开始巡检任务
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    task.status = InspectionStatus.in_progress
    task.started_at = datetime.now()

    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.post("/tasks/{id}/complete", response_model=InspectionTaskResponse, summary="完成巡检任务")
async def complete_inspection_task(
    id: int,
    data: CompleteTaskRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    完成巡检任务
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    task.status = InspectionStatus.completed
    task.completed_at = datetime.now()
    if data.result:
        task.result = data.result
    if data.abnormal_count is not None:
        task.abnormal_count = data.abnormal_count

    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


# ==================== 知识库管理 ====================

@router.get("/knowledge", response_model=List[KnowledgeResponse], summary="获取知识库列表")
async def get_knowledge_list(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    category: Optional[str] = Query(None, description="分类过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取知识库列表（分页）
    """
    query = select(KnowledgeBase)

    if category:
        query = query.where(KnowledgeBase.category == category)

    query = query.order_by(KnowledgeBase.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    articles = result.scalars().all()

    return [KnowledgeResponse.model_validate(article) for article in articles]


@router.post("/knowledge", response_model=KnowledgeResponse, summary="创建知识库文章")
async def create_knowledge(
    data: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建知识库文章
    """
    article = KnowledgeBase(**data.model_dump())

    db.add(article)
    await db.commit()
    await db.refresh(article)

    return KnowledgeResponse.model_validate(article)


@router.get("/knowledge/{id}", response_model=KnowledgeResponse, summary="获取知识库文章详情")
async def get_knowledge(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    根据ID获取知识库文章详情，并增加查看次数
    """
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == id))
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="知识库文章不存在")

    # 增加查看次数
    article.view_count = (article.view_count or 0) + 1
    await db.commit()
    await db.refresh(article)

    return KnowledgeResponse.model_validate(article)


@router.put("/knowledge/{id}", response_model=KnowledgeResponse, summary="更新知识库文章")
async def update_knowledge(
    id: int,
    data: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新知识库文章信息
    """
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == id))
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="知识库文章不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(article, key, value)

    article.updated_at = datetime.now()
    await db.commit()
    await db.refresh(article)

    return KnowledgeResponse.model_validate(article)


@router.delete("/knowledge/{id}", summary="删除知识库文章")
async def delete_knowledge(
    id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除知识库文章
    """
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == id))
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(status_code=404, detail="知识库文章不存在")

    await db.delete(article)
    await db.commit()

    return {"message": "操作成功"}


# ==================== 运维统计 ====================

@router.get("/statistics", response_model=OperationStatistics, summary="获取运维统计信息")
async def get_statistics(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取运维统计信息
    """
    # 工单统计
    total_orders_result = await db.execute(select(func.count(WorkOrder.id)))
    total_orders = total_orders_result.scalar() or 0

    pending_orders_result = await db.execute(
        select(func.count(WorkOrder.id)).where(WorkOrder.status == WorkOrderStatus.pending)
    )
    pending_orders = pending_orders_result.scalar() or 0

    processing_orders_result = await db.execute(
        select(func.count(WorkOrder.id)).where(WorkOrder.status == WorkOrderStatus.processing)
    )
    processing_orders = processing_orders_result.scalar() or 0

    completed_orders_result = await db.execute(
        select(func.count(WorkOrder.id)).where(WorkOrder.status == WorkOrderStatus.completed)
    )
    completed_orders = completed_orders_result.scalar() or 0

    # 逾期巡检统计
    overdue_result = await db.execute(
        select(func.count(InspectionTask.id)).where(InspectionTask.status == InspectionStatus.overdue)
    )
    overdue_inspections = overdue_result.scalar() or 0

    # 知识库统计
    knowledge_result = await db.execute(select(func.count(KnowledgeBase.id)))
    knowledge_count = knowledge_result.scalar() or 0

    return OperationStatistics(
        total_orders=total_orders,
        pending_orders=pending_orders,
        processing_orders=processing_orders,
        completed_orders=completed_orders,
        overdue_inspections=overdue_inspections,
        knowledge_count=knowledge_count
    )
