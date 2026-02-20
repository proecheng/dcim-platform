"""
控制命令分级确认 API
Story 9-6: 控制命令分级确认
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from ..deps import get_db, require_operator, require_admin, require_viewer
from ...models.user import User
from ...models.command import CommandApproval, CommandAuditLog
from ...schemas.command import (
    CommandSubmitRequest,
    CommandSubmitResponse,
    CommandApprovalResponse,
    ApprovalRejectRequest,
    CommandAuditLogResponse,
    RiskConfigUpdateRequest,
)
from ...services import command_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== 命令提交 ====================


@router.post("/submit", response_model=CommandSubmitResponse, summary="提交控制命令")
async def submit_command(
    data: CommandSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    提交控制命令，系统根据风险等级自动判断确认流程：
    - 普通命令：直接执行
    - 关键命令：创建审批工单，等待审批
    """
    result = await command_service.submit_command(
        db=db,
        command_type=data.command_type,
        target_device_id=data.target_device_id,
        target_device_name=data.target_device_name,
        command_content=data.command_content,
        operator_id=current_user.id,
        operator_name=current_user.username,
    )
    return CommandSubmitResponse(**result)


# ==================== 审批管理 ====================


@router.get("/approvals", summary="审批工单列表")
async def list_approvals(
    status: Optional[str] = Query(None, description="状态筛选: pending/approved/rejected/timeout"),
    requester_name: Optional[str] = Query(None, description="发起人筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取审批工单列表（分页），查询前自动检查超时"""
    # 惰性超时检查
    await command_service.check_expired_approvals(db)

    query = select(CommandApproval)
    count_query = select(func.count(CommandApproval.id))

    if status:
        query = query.where(CommandApproval.status == status)
        count_query = count_query.where(CommandApproval.status == status)
    if requester_name:
        query = query.where(CommandApproval.requester_name.contains(requester_name))
        count_query = count_query.where(CommandApproval.requester_name.contains(requester_name))

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = query.order_by(desc(CommandApproval.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "items": [CommandApprovalResponse.model_validate(item) for item in items],
        "page": page,
        "page_size": page_size,
    }


@router.get("/approvals/{approval_id}", response_model=CommandApprovalResponse, summary="审批工单详情")
async def get_approval(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取审批工单详情"""
    result = await db.execute(select(CommandApproval).where(CommandApproval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="审批工单不存在")
    return CommandApprovalResponse.model_validate(approval)


@router.post("/approvals/{approval_id}/approve", response_model=CommandApprovalResponse, summary="批准审批")
async def approve(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批准审批工单，命令将被执行"""
    try:
        approval = await command_service.approve_command(
            db=db,
            approval_id=approval_id,
            approver_id=current_user.id,
            approver_name=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not approval:
        raise HTTPException(status_code=404, detail="审批工单不存在")
    return CommandApprovalResponse.model_validate(approval)


@router.post("/approvals/{approval_id}/reject", response_model=CommandApprovalResponse, summary="驳回审批")
async def reject(
    approval_id: int,
    data: ApprovalRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """驳回审批工单"""
    try:
        approval = await command_service.reject_command(
            db=db,
            approval_id=approval_id,
            approver_id=current_user.id,
            approver_name=current_user.username,
            reason=data.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not approval:
        raise HTTPException(status_code=404, detail="审批工单不存在")
    return CommandApprovalResponse.model_validate(approval)


# ==================== 审计日志 ====================


@router.get("/audit-logs", summary="审计日志列表")
async def list_audit_logs(
    command_type: Optional[str] = Query(None, description="命令类型筛选"),
    operator_name: Optional[str] = Query(None, description="操作人筛选"),
    result_filter: Optional[str] = Query(None, alias="result", description="结果筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取命令审计日志列表（分页）"""
    query = select(CommandAuditLog)
    count_query = select(func.count(CommandAuditLog.id))

    if command_type:
        query = query.where(CommandAuditLog.command_type == command_type)
        count_query = count_query.where(CommandAuditLog.command_type == command_type)
    if operator_name:
        query = query.where(CommandAuditLog.operator_name.contains(operator_name))
        count_query = count_query.where(CommandAuditLog.operator_name.contains(operator_name))
    if result_filter:
        query = query.where(CommandAuditLog.result == result_filter)
        count_query = count_query.where(CommandAuditLog.result == result_filter)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = query.order_by(desc(CommandAuditLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "items": [CommandAuditLogResponse.model_validate(item) for item in items],
        "page": page,
        "page_size": page_size,
    }


# ==================== 风险配置 ====================


@router.get("/risk-configs", summary="获取风险等级配置")
async def get_risk_configs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取所有命令类型的风险等级配置"""
    configs = await command_service.get_risk_configs(db)
    return configs


@router.put("/risk-configs", summary="更新风险等级配置")
async def update_risk_configs(
    data: RiskConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批量更新命令风险等级配置（管理员）"""
    try:
        updated = await command_service.update_risk_configs(
            db=db,
            configs=[item.model_dump() for item in data.configs],
            updated_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"已更新 {updated} 条风险配置", "updated": updated}
