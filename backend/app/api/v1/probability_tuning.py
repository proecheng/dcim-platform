"""
概率调参 API - Story 26.3
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from app.core.database import get_db
from app.api.deps import require_role, require_viewer, get_current_user
from app.models.diagnosis import ProbabilityAdjustmentLog
from app.models.fault_tree import FaultTree
from app.services.diagnosis.probability_tuning_service import ProbabilityTuningService
from app.services.diagnosis.version_manager import VersionManager
from app.services.websocket import ws_manager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnosis/probability-tuning", tags=["probability-tuning"])


# ============================================================
# Schemas
# ============================================================


class ProbabilityAdjustmentResponse(BaseModel):
    """调参记录响应"""

    id: int
    tree_id: int
    tree_name: str
    node_id: int
    node_name: str
    node_type: str
    current_probability: float
    proposed_probability: float
    adjustment_percent: float
    sample_count: int
    accurate_count: int
    inaccurate_count: int
    accuracy_rate: float
    status: str
    reason: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProbabilityAdjustmentListResponse(BaseModel):
    """调参记录列表响应"""

    items: List[ProbabilityAdjustmentResponse]
    total: int


class ApproveRequest(BaseModel):
    """审批请求"""

    reason: Optional[str] = Field(None, description="审批理由（可选）")


class RejectRequest(BaseModel):
    """拒绝请求"""

    reason: str = Field(..., description="拒绝理由（必填）")


class TriggerAnalysisResponse(BaseModel):
    """触发分析响应"""

    analyzed_trees: int
    analyzed_nodes: int
    total_adjustments: int
    pending_approvals: int


# ============================================================
# API Endpoints
# ============================================================


@router.post("/analyze", response_model=TriggerAnalysisResponse, dependencies=[Depends(require_role(["admin"]))])
@router.post("/trigger", response_model=TriggerAnalysisResponse, dependencies=[Depends(require_role(["admin"]))])
async def trigger_analysis(tree_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    触发概率调参分析

    - **tree_id**: 可选，指定故障树 ID（不指定则分析所有故障树）
    - **返回**: 分析结果摘要
    """
    service = ProbabilityTuningService()
    result = await service.analyze_all_trees(tree_id_filter=tree_id)
    return result


@router.get("/adjustments", response_model=ProbabilityAdjustmentListResponse)
async def list_adjustments(
    tree_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer),
):
    """
    获取调参记录列表

    - **tree_id**: 可选，按故障树 ID 过滤
    - **status**: 可选，按状态过滤 (pending/approved/rejected)
    - **skip**: 跳过记录数
    - **limit**: 返回记录数
    - **返回**: 调参记录列表
    """
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="无效的状态值")

    query = select(ProbabilityAdjustmentLog)

    if tree_id is not None:
        query = query.where(ProbabilityAdjustmentLog.tree_id == tree_id)
    if status:
        query = query.where(ProbabilityAdjustmentLog.status == status)

    # 获取总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 获取分页数据
    query = query.order_by(ProbabilityAdjustmentLog.created_at.desc())
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    adjustments = result.scalars().all()

    # 查询故障树名称
    tree_ids = list(set(adj.tree_id for adj in adjustments))
    trees_result = await db.execute(select(FaultTree).where(FaultTree.id.in_(tree_ids)))
    trees = {tree.id: tree.name for tree in trees_result.scalars().all()}

    # 构建响应
    items = [
        ProbabilityAdjustmentResponse(
            id=adj.id,
            tree_id=adj.tree_id,
            tree_name=trees.get(adj.tree_id, "Unknown"),
            node_id=adj.node_id,
            node_name=adj.node_name,
            node_type=adj.node_type,
            current_probability=adj.current_probability,
            proposed_probability=adj.proposed_probability,
            adjustment_percent=adj.adjustment_percent,
            sample_count=adj.sample_count,
            accurate_count=adj.accurate_count,
            inaccurate_count=adj.inaccurate_count,
            accuracy_rate=adj.accuracy_rate,
            status=adj.status,
            reason=adj.reason,
            approved_by=adj.approved_by,
            approved_at=adj.approved_at,
            created_at=adj.created_at,
        )
        for adj in adjustments
    ]

    return ProbabilityAdjustmentListResponse(items=items, total=total)


@router.post("/adjustments/{adjustment_id}/approve", dependencies=[Depends(require_role(["admin"]))])
async def approve_adjustment(
    adjustment_id: int,
    request: ApproveRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    审批调参建议

    - **adjustment_id**: 调参记录 ID
    - **request**: 审批请求（包含可选的审批理由）
    - **返回**: 成功消息
    - **错误**:
        - 404 - 调参记录不存在
        - 400 - 状态不是 pending / 乐观锁冲突
    """
    # 使用乐观锁查询
    result = await db.execute(
        select(ProbabilityAdjustmentLog).where(
            ProbabilityAdjustmentLog.id == adjustment_id, ProbabilityAdjustmentLog.status == "pending"
        )
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调参记录不存在或状态不是 pending")

    # 记录当前版本号
    current_version = adjustment.version

    # 更新节点概率
    from app.models.fault_tree import FaultTreeNode

    node = await db.get(FaultTreeNode, adjustment.node_id)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"节点 {adjustment.node_id} 不存在")

    # 更新调参记录状态（使用乐观锁，必须在修改节点概率之前检查）
    update_result = await db.execute(
        select(ProbabilityAdjustmentLog)
        .where(ProbabilityAdjustmentLog.id == adjustment_id, ProbabilityAdjustmentLog.version == current_version)
        .with_for_update()
    )
    locked_adjustment = update_result.scalar_one_or_none()

    if not locked_adjustment:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="调参记录已被其他用户修改，请刷新后重试")

    # 乐观锁检查通过后，更新节点概率
    node.prior_probability = adjustment.proposed_probability

    # 创建新版本（审批后自动创建版本）
    try:
        version = await VersionManager.create_version(db, adjustment.tree_id, current_user.id)
        logger.info(f"审批调参 {adjustment_id} 后创建版本 {version.id}")
    except Exception as e:
        logger.error(f"创建版本失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="创建版本失败，请稍后重试")

    locked_adjustment.status = "approved"
    locked_adjustment.reason = request.reason
    locked_adjustment.approved_by = current_user.id
    locked_adjustment.approved_at = func.now()
    locked_adjustment.version += 1

    await db.commit()

    # 发送 WebSocket 通知
    await ws_manager.broadcast_diagnosis(
        msg_type="probability_adjustment_updated",
        data={
            "adjustment_id": adjustment_id,
            "tree_id": adjustment.tree_id,
            "node_name": adjustment.node_name,
            "status": "approved",
            "approved_by": current_user.username,
        },
        target_roles=["admin"],
    )

    return {"message": "审批成功", "version_id": version.id}


@router.post("/adjustments/{adjustment_id}/reject", dependencies=[Depends(require_role(["admin"]))])
async def reject_adjustment(
    adjustment_id: int,
    request: RejectRequest = Body(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    拒绝调参建议

    - **adjustment_id**: 调参记录 ID
    - **request**: 拒绝请求（包含必填的拒绝理由）
    - **返回**: 成功消息
    - **错误**:
        - 404 - 调参记录不存在
        - 400 - 状态不是 pending / 乐观锁冲突
    """
    # 使用乐观锁查询
    result = await db.execute(
        select(ProbabilityAdjustmentLog).where(
            ProbabilityAdjustmentLog.id == adjustment_id, ProbabilityAdjustmentLog.status == "pending"
        )
    )
    adjustment = result.scalar_one_or_none()

    if not adjustment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="调参记录不存在或状态不是 pending")

    # 记录当前版本号
    current_version = adjustment.version

    # 更新调参记录状态（使用乐观锁）
    update_result = await db.execute(
        select(ProbabilityAdjustmentLog)
        .where(ProbabilityAdjustmentLog.id == adjustment_id, ProbabilityAdjustmentLog.version == current_version)
        .with_for_update()
    )
    locked_adjustment = update_result.scalar_one_or_none()

    if not locked_adjustment:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="调参记录已被其他用户修改，请刷新后重试")

    locked_adjustment.status = "rejected"
    locked_adjustment.reason = request.reason
    locked_adjustment.approved_by = current_user.id
    locked_adjustment.approved_at = func.now()
    locked_adjustment.version += 1

    await db.commit()

    # 发送 WebSocket 通知
    await ws_manager.broadcast_diagnosis(
        msg_type="probability_adjustment_updated",
        data={
            "adjustment_id": adjustment_id,
            "tree_id": adjustment.tree_id,
            "node_name": adjustment.node_name,
            "status": "rejected",
            "approved_by": current_user.username,
        },
        target_roles=["admin"],
    )

    return {"message": "已拒绝"}


@router.post("/rollback/{tree_id}", dependencies=[Depends(require_role(["admin"]))])
async def rollback_tree(tree_id: int, db: AsyncSession = Depends(get_db)):
    """
    回滚故障树到上一个版本

    - **tree_id**: 故障树 ID
    - **返回**: 回滚后的版本信息
    - **错误**:
        - 404 - 没有可回滚的版本
        - 429 - 回滚过于频繁
        - 400 - DAG 验证失败 / 快照完整性验证失败
    """
    try:
        version = await VersionManager.rollback_version(db, tree_id)
        return {"message": "回滚成功", "version_id": version.id, "version_number": version.version_number}
    except ValueError as e:
        logger.error(f"回滚故障树 {tree_id} 失败: {e}")
        error_msg = str(e)
        if "没有可回滚的版本" in error_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
        elif "回滚过于频繁" in error_msg:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
