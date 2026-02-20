"""
运维管理 API - v1
"""

from typing import Optional, List, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.operation import (
    WorkOrder,
    WorkOrderLog,
    WorkOrderStatus,
    WorkOrderPriority,
    WorkOrderType,
    InspectionPlan,
    InspectionTask,
    InspectionStatus,
    KnowledgeBase,
    AlarmWorkOrderRule,
    WorkOrderApproval,
    ApprovalStatus,
)
from ...schemas.operation import (
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
    WorkOrderLogResponse,
    InspectionPlanCreate,
    InspectionPlanUpdate,
    InspectionPlanResponse,
    InspectionTaskCreate,
    InspectionTaskUpdate,
    InspectionTaskResponse,
    KnowledgeCreate,
    KnowledgeUpdate,
    KnowledgeResponse,
    OperationStatistics,
    AlarmWorkOrderRuleCreate,
    AlarmWorkOrderRuleUpdate,
    AlarmWorkOrderRuleResponse,
    AlarmCheckRequest,
    WorkOrderApprovalCreate,
    WorkOrderApprovalResponse,
    ApproveRequest,
    RejectRequest,
)

router = APIRouter(prefix="/operation", tags=["运维管理"])


# ==================== 状态转换规则 ====================

VALID_TRANSITIONS = {
    WorkOrderStatus.pending: [WorkOrderStatus.assigned, WorkOrderStatus.cancelled],
    WorkOrderStatus.assigned: [WorkOrderStatus.accepted, WorkOrderStatus.cancelled],
    WorkOrderStatus.accepted: [WorkOrderStatus.processing, WorkOrderStatus.cancelled],
    WorkOrderStatus.processing: [WorkOrderStatus.completed],
    WorkOrderStatus.completed: [WorkOrderStatus.closed],
    WorkOrderStatus.closed: [],
    WorkOrderStatus.cancelled: [],
}


def _check_transition(current: WorkOrderStatus, target: WorkOrderStatus) -> None:
    """校验状态转换是否合法"""
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(status_code=400, detail=f"不允许从 {current.value} 转换到 {target.value}")


# ==================== 巡检任务状态转换规则 ====================

VALID_TASK_TRANSITIONS = {
    InspectionStatus.pending: [InspectionStatus.in_progress],
    InspectionStatus.in_progress: [InspectionStatus.completed],
    InspectionStatus.completed: [],
    InspectionStatus.overdue: [InspectionStatus.in_progress],
}


def _check_task_transition(current: InspectionStatus, target: InspectionStatus) -> None:
    """校验巡检任务状态转换是否合法"""
    allowed = VALID_TASK_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(status_code=400, detail=f"不允许从 {current.value} 转换到 {target.value}")


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
        result = await db.execute(select(func.count(WorkOrder.id)).where(WorkOrder.order_no.like(f"WO-{today}-%")))
        count = result.scalar() or 0
    elif prefix == "IT":
        result = await db.execute(
            select(func.count(InspectionTask.id)).where(InspectionTask.task_no.like(f"IT-{today}-%"))
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
    _: User = Depends(require_viewer),
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
    data: WorkOrderCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建工单
    """
    order_no = await _generate_order_no(db, "WO")
    order = WorkOrder(order_no=order_no, **data.model_dump())

    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 添加创建日志
    log = WorkOrderLog(order_id=order.id, action="创建", content=f"工单 {order_no} 创建成功", operator="系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.get("/workorders/{id}", response_model=WorkOrderResponse, summary="获取工单详情")
async def get_work_order(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
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
    id: int, data: WorkOrderUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def delete_work_order(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
    id: int, data: AssignRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    派单给指定处理人
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    _check_transition(order.status, WorkOrderStatus.assigned)

    order.assignee = data.assignee
    order.assigned_at = datetime.now()
    order.status = WorkOrderStatus.assigned

    await db.commit()
    await db.refresh(order)

    # 添加派单日志
    log = WorkOrderLog(order_id=id, action="派单", content=f"工单已派发给 {data.assignee}", operator="系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/accept", response_model=WorkOrderResponse, summary="接单")
async def accept_work_order(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    接单（处理人确认接受工单）
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    _check_transition(order.status, WorkOrderStatus.accepted)

    order.status = WorkOrderStatus.accepted
    order.accepted_at = datetime.now()

    await db.commit()
    await db.refresh(order)

    # 添加接单日志
    log = WorkOrderLog(order_id=id, action="接单", content="工单已接单", operator=order.assignee or "系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/start", response_model=WorkOrderResponse, summary="开始处理工单")
async def start_work_order(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    开始处理工单
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    _check_transition(order.status, WorkOrderStatus.processing)

    order.status = WorkOrderStatus.processing
    order.started_at = datetime.now()

    await db.commit()
    await db.refresh(order)

    # 添加开始处理日志
    log = WorkOrderLog(order_id=id, action="开始处理", content="工单开始处理", operator=order.assignee or "系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/complete", response_model=WorkOrderResponse, summary="完成工单")
async def complete_work_order(
    id: int, data: CompleteWorkOrderRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    完成工单
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    _check_transition(order.status, WorkOrderStatus.completed)

    order.status = WorkOrderStatus.completed
    order.completed_at = datetime.now()
    if data.solution:
        order.solution = data.solution
    if data.root_cause:
        order.root_cause = data.root_cause

    await db.commit()
    await db.refresh(order)

    # 添加完成日志
    log = WorkOrderLog(order_id=id, action="完成", content="工单处理完成", operator=order.assignee or "系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.post("/workorders/{id}/close", response_model=WorkOrderResponse, summary="关闭工单")
async def close_work_order(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    关闭工单（完成后确认关闭）
    """
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    _check_transition(order.status, WorkOrderStatus.closed)

    order.status = WorkOrderStatus.closed
    order.closed_at = datetime.now()

    await db.commit()
    await db.refresh(order)

    # 添加关闭日志
    log = WorkOrderLog(order_id=id, action="关闭", content="工单已关闭", operator="系统")
    db.add(log)
    await db.commit()

    return WorkOrderResponse.model_validate(order)


@router.get("/workorders/{id}/logs", response_model=List[WorkOrderLogResponse], summary="获取工单日志")
async def get_work_order_logs(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取工单日志
    """
    # 检查工单是否存在
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    result = await db.execute(
        select(WorkOrderLog).where(WorkOrderLog.order_id == id).order_by(WorkOrderLog.created_at.desc())
    )
    logs = result.scalars().all()

    return [WorkOrderLogResponse.model_validate(log) for log in logs]


@router.post("/workorders/{id}/logs", response_model=WorkOrderLogResponse, summary="添加工单日志")
async def add_work_order_log(
    id: int, data: AddLogRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    添加工单日志
    """
    # 检查工单是否存在
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    log = WorkOrderLog(order_id=id, action=data.action, content=data.content, operator=data.operator)

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return WorkOrderLogResponse.model_validate(log)


# ==================== 工单审批管理 ====================


async def _check_approval_timeout(approval: WorkOrderApproval, db: AsyncSession) -> bool:
    """检查审批是否超时，如果超时则处理。返回 True 表示已超时。"""
    from datetime import timedelta

    if approval.status != ApprovalStatus.pending:
        return False

    deadline = approval.created_at + timedelta(hours=approval.timeout_hours or 24)
    if datetime.now() <= deadline:
        return False

    # 超时处理
    if approval.escalate_to:
        # 升级到上级审批人
        approval.status = ApprovalStatus.escalated
        approval.resolved_at = datetime.now()

        # 创建新审批记录给升级审批人
        new_approval = WorkOrderApproval(
            order_id=approval.order_id,
            approver=approval.escalate_to,
            timeout_hours=approval.timeout_hours,
        )
        db.add(new_approval)

        # 添加工单日志
        log = WorkOrderLog(
            order_id=approval.order_id,
            action="审批升级",
            content=f"审批超时，已升级至 {approval.escalate_to}",
            operator="系统",
        )
        db.add(log)
    else:
        approval.status = ApprovalStatus.timeout
        approval.resolved_at = datetime.now()

        log = WorkOrderLog(
            order_id=approval.order_id,
            action="审批超时",
            content=f"审批人 {approval.approver} 审批超时",
            operator="系统",
        )
        db.add(log)

    await db.commit()
    return True


@router.post("/workorders/{id}/submit-approval", response_model=WorkOrderApprovalResponse, summary="提交工单审批")
async def submit_work_order_approval(
    id: int, data: WorkOrderApprovalCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """提交工单审批（仅变更请求类型、已接单状态的工单可提交）"""
    result = await db.execute(select(WorkOrder).where(WorkOrder.id == id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")

    if order.order_type != WorkOrderType.change:
        raise HTTPException(status_code=400, detail="仅变更请求类型的工单需要审批")

    if order.status != WorkOrderStatus.accepted:
        raise HTTPException(status_code=400, detail="仅已接单状态的工单可提交审批")

    # 检查是否有进行中的审批
    existing = await db.execute(
        select(WorkOrderApproval).where(
            WorkOrderApproval.order_id == id, WorkOrderApproval.status == ApprovalStatus.pending
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该工单已有进行中的审批")

    approval = WorkOrderApproval(
        order_id=id,
        approver=data.approver,
        timeout_hours=data.timeout_hours or 24,
        escalate_to=data.escalate_to,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)

    # 添加工单日志
    log = WorkOrderLog(
        order_id=id, action="提交审批", content=f"提交审批，审批人: {data.approver}", operator=order.assignee or "系统"
    )
    db.add(log)
    await db.commit()

    return WorkOrderApprovalResponse.model_validate(approval)


@router.get("/approvals", response_model=List[WorkOrderApprovalResponse], summary="获取审批列表")
async def get_work_order_approvals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[ApprovalStatus] = Query(None, description="审批状态过滤"),
    order_id: Optional[int] = Query(None, description="工单ID过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取工单审批列表（惰性检查超时）"""
    # 惰性检查超时
    pending_result = await db.execute(
        select(WorkOrderApproval).where(WorkOrderApproval.status == ApprovalStatus.pending)
    )
    for appr in pending_result.scalars().all():
        await _check_approval_timeout(appr, db)

    query = select(WorkOrderApproval)
    if status:
        query = query.where(WorkOrderApproval.status == status)
    if order_id is not None:
        query = query.where(WorkOrderApproval.order_id == order_id)

    query = query.order_by(WorkOrderApproval.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    approvals = result.scalars().all()

    return [WorkOrderApprovalResponse.model_validate(a) for a in approvals]


@router.get("/approvals/{id}", response_model=WorkOrderApprovalResponse, summary="获取审批详情")
async def get_work_order_approval(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """获取工单审批详情"""
    result = await db.execute(select(WorkOrderApproval).where(WorkOrderApproval.id == id))
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    # 惰性检查超时
    await _check_approval_timeout(approval, db)
    await db.refresh(approval)

    return WorkOrderApprovalResponse.model_validate(approval)


@router.post("/approvals/{id}/approve", response_model=WorkOrderApprovalResponse, summary="批准审批")
async def approve_work_order_approval(
    id: int, data: ApproveRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """批准工单审批，工单自动转为处理中"""
    result = await db.execute(select(WorkOrderApproval).where(WorkOrderApproval.id == id))
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    if approval.status != ApprovalStatus.pending:
        raise HTTPException(status_code=400, detail=f"审批状态为 {approval.status.value}，无法批准")

    # 检查超时
    timed_out = await _check_approval_timeout(approval, db)
    if timed_out:
        await db.refresh(approval)
        raise HTTPException(status_code=400, detail="审批已超时")

    # 批准
    approval.status = ApprovalStatus.approved
    approval.reason = data.reason
    approval.resolved_at = datetime.now()

    # 自动将工单转为处理中
    order_result = await db.execute(select(WorkOrder).where(WorkOrder.id == approval.order_id))
    order = order_result.scalar_one_or_none()
    if order and order.status == WorkOrderStatus.accepted:
        order.status = WorkOrderStatus.processing
        order.started_at = datetime.now()

    await db.commit()
    await db.refresh(approval)

    # 添加工单日志
    reason_text = f"，意见: {data.reason}" if data.reason else ""
    log = WorkOrderLog(
        order_id=approval.order_id,
        action="审批通过",
        content=f"审批人 {approval.approver} 批准{reason_text}",
        operator=approval.approver,
    )
    db.add(log)
    await db.commit()

    return WorkOrderApprovalResponse.model_validate(approval)


@router.post("/approvals/{id}/reject", response_model=WorkOrderApprovalResponse, summary="驳回审批")
async def reject_work_order_approval(
    id: int, data: RejectRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """驳回工单审批，工单保持已接单状态"""
    result = await db.execute(select(WorkOrderApproval).where(WorkOrderApproval.id == id))
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="审批记录不存在")

    if approval.status != ApprovalStatus.pending:
        raise HTTPException(status_code=400, detail=f"审批状态为 {approval.status.value}，无法驳回")

    approval.status = ApprovalStatus.rejected
    approval.reason = data.reason
    approval.resolved_at = datetime.now()

    await db.commit()
    await db.refresh(approval)

    # 添加工单日志
    log = WorkOrderLog(
        order_id=approval.order_id,
        action="审批驳回",
        content=f"审批人 {approval.approver} 驳回，原因: {data.reason}",
        operator=approval.approver,
    )
    db.add(log)
    await db.commit()

    return WorkOrderApprovalResponse.model_validate(approval)


# ==================== 巡检计划管理 ====================


@router.get("/plans", response_model=List[InspectionPlanResponse], summary="获取巡检计划列表")
async def get_inspection_plans(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    is_active: Optional[bool] = Query(None, description="是否启用过滤"),
    name: Optional[str] = Query(None, description="计划名称搜索"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取巡检计划列表（分页）
    """
    query = select(InspectionPlan)

    if is_active is not None:
        query = query.where(InspectionPlan.is_active == is_active)
    if name:
        query = query.where(InspectionPlan.name.contains(name))

    query = query.order_by(InspectionPlan.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    plans = result.scalars().all()

    return [InspectionPlanResponse.model_validate(plan) for plan in plans]


@router.post("/plans", response_model=InspectionPlanResponse, summary="创建巡检计划")
async def create_inspection_plan(
    data: InspectionPlanCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def get_inspection_plan(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
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
    id: int, data: InspectionPlanUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def delete_inspection_plan(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
    plan_id: Optional[int] = Query(None, description="巡检计划ID过滤"),
    assignee: Optional[str] = Query(None, description="执行人过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取巡检任务列表（分页）
    """
    query = select(InspectionTask)

    if status:
        query = query.where(InspectionTask.status == status)
    if plan_id is not None:
        query = query.where(InspectionTask.plan_id == plan_id)
    if assignee:
        query = query.where(InspectionTask.assignee == assignee)

    query = query.order_by(InspectionTask.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    # 批量获取关联计划名称
    plan_ids = {t.plan_id for t in tasks if t.plan_id}
    plan_names: Dict[int, str] = {}
    if plan_ids:
        plans_result = await db.execute(
            select(InspectionPlan.id, InspectionPlan.name).where(InspectionPlan.id.in_(plan_ids))
        )
        plan_names = {row[0]: row[1] for row in plans_result.all()}

    responses = []
    for task in tasks:
        resp = InspectionTaskResponse.model_validate(task)
        if task.plan_id and task.plan_id in plan_names:
            resp.plan_name = plan_names[task.plan_id]
        responses.append(resp)

    return responses


@router.post("/tasks", response_model=InspectionTaskResponse, summary="创建巡检任务")
async def create_inspection_task(
    data: InspectionTaskCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建巡检任务
    """
    task_no = await _generate_order_no(db, "IT")
    task = InspectionTask(task_no=task_no, **data.model_dump())

    db.add(task)
    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.get("/tasks/{id}", response_model=InspectionTaskResponse, summary="获取巡检任务详情")
async def get_inspection_task(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    根据ID获取巡检任务详情
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    resp = InspectionTaskResponse.model_validate(task)
    if task.plan_id:
        plan_result = await db.execute(select(InspectionPlan.name).where(InspectionPlan.id == task.plan_id))
        plan_name = plan_result.scalar_one_or_none()
        if plan_name:
            resp.plan_name = plan_name

    return resp


@router.put("/tasks/{id}", response_model=InspectionTaskResponse, summary="更新巡检任务")
async def update_inspection_task(
    id: int, data: InspectionTaskUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def start_inspection_task(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    开始巡检任务
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    _check_task_transition(task.status, InspectionStatus.in_progress)

    task.status = InspectionStatus.in_progress
    task.started_at = datetime.now()

    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.post("/tasks/{id}/complete", response_model=InspectionTaskResponse, summary="完成巡检任务")
async def complete_inspection_task(
    id: int, data: CompleteTaskRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    完成巡检任务
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    _check_task_transition(task.status, InspectionStatus.completed)

    task.status = InspectionStatus.completed
    task.completed_at = datetime.now()
    if data.result:
        task.result = data.result
    if data.abnormal_count is not None:
        task.abnormal_count = data.abnormal_count

    await db.commit()
    await db.refresh(task)

    return InspectionTaskResponse.model_validate(task)


@router.delete("/tasks/{id}", summary="删除巡检任务")
async def delete_inspection_task(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    删除巡检任务
    """
    result = await db.execute(select(InspectionTask).where(InspectionTask.id == id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="巡检任务不存在")

    await db.delete(task)
    await db.commit()

    return {"message": "操作成功"}


@router.post("/plans/{id}/generate-tasks", response_model=InspectionTaskResponse, summary="从计划生成巡检任务")
async def generate_inspection_task(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """
    根据巡检计划生成一个巡检任务
    """
    result = await db.execute(select(InspectionPlan).where(InspectionPlan.id == id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="巡检计划不存在")

    if not plan.is_active:
        raise HTTPException(status_code=400, detail="巡检计划未启用")

    task_no = await _generate_order_no(db, "IT")
    task = InspectionTask(
        plan_id=plan.id,
        task_no=task_no,
        assignee=plan.assignee,
        scheduled_date=datetime.now(),
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    resp = InspectionTaskResponse.model_validate(task)
    resp.plan_name = plan.name

    return resp


# ==================== 告警工单规则管理 ====================


@router.get("/alarm-rules", response_model=List[AlarmWorkOrderRuleResponse], summary="获取告警工单规则列表")
async def get_alarm_workorder_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_enabled: Optional[bool] = Query(None, description="是否启用过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取告警工单规则列表"""
    query = select(AlarmWorkOrderRule)
    if is_enabled is not None:
        query = query.where(AlarmWorkOrderRule.is_enabled == is_enabled)
    query = query.order_by(AlarmWorkOrderRule.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    rules = result.scalars().all()
    return [AlarmWorkOrderRuleResponse.model_validate(r) for r in rules]


@router.post("/alarm-rules/check", summary="检查告警并自动创建工单")
async def check_alarm_create_workorder(
    data: AlarmCheckRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """根据告警信息匹配规则，自动创建工单"""
    query = select(AlarmWorkOrderRule).where(
        AlarmWorkOrderRule.is_enabled == True, AlarmWorkOrderRule.alarm_level == data.alarm_level
    )
    if data.alarm_type:
        query = query.where(
            (AlarmWorkOrderRule.alarm_type == None) | (AlarmWorkOrderRule.alarm_type == data.alarm_type)
        )
    else:
        query = query.where(AlarmWorkOrderRule.alarm_type == None)

    result = await db.execute(query)
    rule = result.scalars().first()

    if not rule:
        return {"matched": False, "work_order": None}

    # 创建工单
    order_no = await _generate_order_no(db, "WO")
    order = WorkOrder(
        order_no=order_no,
        title=f"[自动] {data.alarm_message}",
        description=f"由告警自动创建，告警ID: {data.alarm_id}",
        order_type=rule.order_type,
        priority=rule.priority,
        alarm_id=data.alarm_id,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 如果规则有 assignee，自动派单
    if rule.assignee:
        order.assignee = rule.assignee
        order.assigned_at = datetime.now()
        order.status = WorkOrderStatus.assigned
        await db.commit()
        await db.refresh(order)

    # 添加日志
    log = WorkOrderLog(
        order_id=order.id, action="自动创建", content=f"由告警规则「{rule.name}」自动创建", operator="系统"
    )
    db.add(log)
    await db.commit()

    return {"matched": True, "rule_name": rule.name, "work_order": WorkOrderResponse.model_validate(order)}


@router.post("/alarm-rules", response_model=AlarmWorkOrderRuleResponse, summary="创建告警工单规则")
async def create_alarm_workorder_rule(
    data: AlarmWorkOrderRuleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """创建告警工单规则"""
    rule = AlarmWorkOrderRule(**data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return AlarmWorkOrderRuleResponse.model_validate(rule)


@router.put("/alarm-rules/{id}", response_model=AlarmWorkOrderRuleResponse, summary="更新告警工单规则")
async def update_alarm_workorder_rule(
    id: int, data: AlarmWorkOrderRuleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """更新告警工单规则"""
    result = await db.execute(select(AlarmWorkOrderRule).where(AlarmWorkOrderRule.id == id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(rule, key, value)

    rule.updated_at = datetime.now()
    await db.commit()
    await db.refresh(rule)
    return AlarmWorkOrderRuleResponse.model_validate(rule)


@router.delete("/alarm-rules/{id}", summary="删除告警工单规则")
async def delete_alarm_workorder_rule(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    """删除告警工单规则"""
    result = await db.execute(select(AlarmWorkOrderRule).where(AlarmWorkOrderRule.id == id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    await db.delete(rule)
    await db.commit()
    return {"message": "操作成功"}


# ==================== 知识库管理 ====================


@router.get("/knowledge", summary="获取知识库列表")
async def get_knowledge_list(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    page: int = Query(None, ge=1, description="页码（替代skip）"),
    page_size: int = Query(None, ge=1, le=100, description="每页数量（替代limit）"),
    category: Optional[str] = Query(None, description="分类过滤"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取知识库列表（分页）
    """
    # 支持 page/page_size 参数
    if page is not None and page_size is not None:
        skip = (page - 1) * page_size
        limit = page_size

    query = select(KnowledgeBase)

    if category:
        query = query.where(KnowledgeBase.category == category)

    if keyword:
        query = query.where(
            KnowledgeBase.title.contains(keyword)
            | KnowledgeBase.content.contains(keyword)
            | KnowledgeBase.tags.contains(keyword)
        )

    # 获取总数
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(KnowledgeBase.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    articles = result.scalars().all()

    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": [KnowledgeResponse.model_validate(article) for article in articles],
            "total": total,
            "skip": skip,
            "limit": limit,
        },
    }


@router.post("/knowledge", response_model=KnowledgeResponse, summary="创建知识库文章")
async def create_knowledge(
    data: KnowledgeCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def get_knowledge(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
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
    id: int, data: KnowledgeUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
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
async def delete_knowledge(id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
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
async def get_statistics(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
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
        knowledge_count=knowledge_count,
    )
