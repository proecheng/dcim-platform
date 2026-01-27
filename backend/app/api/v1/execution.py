"""
执行管理 API - v1
提供执行计划、任务执行、效果追踪等功能
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db, get_current_user, require_viewer, require_admin
from ...models.user import User
from ...models.energy import EnergyOpportunity, ExecutionPlan, ExecutionTask
from ...services.execution_service import ExecutionService
from ...schemas.common import ResponseModel
from ...schemas.energy import (
    ExecutionPlanResponse, ExecutionTaskResponse, ExecutionResultResponse,
    CreateLoadShiftPlanRequest, CreateLoadShiftPlanResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== 请求模型 ==========

class UpdatePlanStatusRequest(BaseModel):
    """更新计划状态请求"""
    status: str = Field(..., description="状态: pending/executing/completed/failed/cancelled")
    notes: Optional[str] = Field(None, description="备注")


class ExecuteTaskRequest(BaseModel):
    """执行任务请求"""
    force: bool = Field(False, description="是否强制执行（忽略部分约束）")


class CompleteTaskRequest(BaseModel):
    """完成任务请求"""
    completed_by: Optional[str] = Field(None, description="完成人")
    notes: Optional[str] = Field(None, description="备注")


class TrackingRequest(BaseModel):
    """追踪请求"""
    tracking_days: int = Field(7, ge=1, le=30, description="追踪天数")


# ========== 从负荷转移创建执行计划 ==========

@router.post("/plans/from-shift", response_model=ResponseModel[CreateLoadShiftPlanResponse], summary="从负荷转移配置创建执行计划")
async def create_plan_from_load_shift(
    request: CreateLoadShiftPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从负荷转移配置创建执行计划

    流程：
    1. 创建EnergyOpportunity记录（节能机会）
    2. 创建ExecutionPlan记录（执行计划）
    3. 为每个设备的每条规则创建ExecutionTask（执行任务）
    """
    try:
        # 1. 创建节能机会
        device_names = [d.device_name for d in request.device_rules]
        description_suffix = '等' if len(device_names) > 3 else ''
        description_devices = ', '.join(device_names[:3])

        opportunity = EnergyOpportunity(
            category=1,  # 电费结构优化
            title=request.plan_name,
            description=f"负荷转移优化方案 - {description_devices}{description_suffix}",
            source_plugin='peak_valley_optimizer',
            priority='high' if request.annual_saving > 50000 else 'medium',
            status='accepted',  # 直接进入执行状态
            potential_saving=request.annual_saving,
            confidence=0.85,
            analysis_data={
                'strategy': request.strategy,
                'device_rules': [rule.model_dump() for rule in request.device_rules],
                'daily_saving': request.daily_saving,
                'annual_saving': request.annual_saving,
                'meter_point_id': request.meter_point_id,
                'remark': request.remark
            }
        )
        db.add(opportunity)
        await db.flush()  # 获取 opportunity.id

        # 2. 创建执行计划
        plan = ExecutionPlan(
            opportunity_id=opportunity.id,
            plan_name=request.plan_name,
            expected_saving=request.annual_saving,
            status='pending',
            created_by=current_user.id if current_user else None
        )
        db.add(plan)
        await db.flush()  # 获取 plan.id

        # 3. 为每个设备的每条规则创建执行任务
        task_count = 0
        period_names = {
            'sharp': '尖峰', 'peak': '峰时', 'flat': '平时',
            'valley': '谷时', 'deep_valley': '深谷'
        }

        for device_rule in request.device_rules:
            for rule_idx, rule in enumerate(device_rule.rules):
                source_name = period_names.get(rule.source_period, rule.source_period)
                target_name = period_names.get(rule.target_period, rule.target_period)

                task = ExecutionTask(
                    plan_id=plan.id,
                    task_type='load_shift',
                    task_name=f"{device_rule.device_name} - {source_name}转{target_name}",
                    target_object=f"device:{device_rule.device_id}",
                    execution_mode='manual',  # 负荷转移通常需要人工调整
                    parameters={
                        'device_id': device_rule.device_id,
                        'device_name': device_rule.device_name,
                        'source_period': rule.source_period,
                        'target_period': rule.target_period,
                        'power': rule.power,
                        'hours': rule.hours,
                        'rule_index': rule_idx
                    },
                    status='pending',
                    sort_order=task_count
                )
                db.add(task)
                task_count += 1

        await db.commit()

        return ResponseModel(
            code=0,
            message="执行计划创建成功",
            data=CreateLoadShiftPlanResponse(
                plan_id=plan.id,
                opportunity_id=opportunity.id,
                plan_name=plan.plan_name,
                expected_saving=float(plan.expected_saving) if plan.expected_saving else 0,
                task_count=task_count
            )
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"创建负荷转移执行计划失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建执行计划失败: {str(e)}")


# ========== 执行计划管理 ==========

@router.get("/plans", summary="获取执行计划列表")
async def list_plans(
    status: Optional[str] = Query(None, description="状态过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取执行计划列表"""
    try:
        from sqlalchemy import select, func
        from ...models.energy import ExecutionPlan

        query = select(ExecutionPlan)
        count_query = select(func.count(ExecutionPlan.id))

        if status:
            query = query.where(ExecutionPlan.status == status)
            count_query = count_query.where(ExecutionPlan.status == status)

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取数据
        query = query.order_by(ExecutionPlan.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        # 简化响应，不使用 ExecutionPlanResponse
        response_items = []
        for item in items:
            response_items.append({
                "id": item.id,
                "opportunity_id": item.opportunity_id,
                "plan_name": item.plan_name,
                "expected_saving": float(item.expected_saving) if item.expected_saving else 0,
                "status": item.status,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None
            })

        return ResponseModel(
            code=0,
            message="success",
            data={
                "items": response_items,
                "total": total,
                "skip": skip,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error(f"list_plans failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plans/{plan_id}", summary="获取执行计划详情")
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取执行计划详细信息，包括任务列表和追踪结果"""
    service = ExecutionService(db)
    plan_data = await service.get_plan_with_tasks(plan_id)

    if not plan_data:
        raise HTTPException(status_code=404, detail=f"计划ID {plan_id} 不存在")

    return ResponseModel(
        code=0,
        message="success",
        data=plan_data
    )


@router.put("/plans/{plan_id}/status", summary="更新计划状态")
async def update_plan_status(
    plan_id: int,
    request: UpdatePlanStatusRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """手动更新执行计划状态"""
    from sqlalchemy import select
    from ...models.energy import ExecutionPlan
    from datetime import datetime

    result = await db.execute(
        select(ExecutionPlan).where(ExecutionPlan.id == plan_id)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail=f"计划ID {plan_id} 不存在")

    old_status = plan.status
    plan.status = request.status
    plan.updated_at = datetime.now()

    if request.status == "executing" and not plan.started_at:
        plan.started_at = datetime.now()
    elif request.status == "completed" and not plan.completed_at:
        plan.completed_at = datetime.now()

    if request.notes:
        plan.notes = request.notes

    await db.commit()

    return {
        "message": "状态更新成功",
        "plan_id": plan_id,
        "old_status": old_status,
        "new_status": plan.status
    }


@router.get("/plans/{plan_id}/checklist", summary="生成执行清单")
async def get_checklist(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """生成执行清单（用于导出PDF或创建工单）"""
    service = ExecutionService(db)
    checklist = await service.generate_task_checklist(plan_id)

    if "error" in checklist:
        raise HTTPException(status_code=404, detail=checklist["error"])

    return checklist


# ========== 任务执行 ==========

@router.post("/tasks/{task_id}/execute", summary="执行自动任务")
async def execute_task(
    task_id: int,
    request: ExecuteTaskRequest = ExecuteTaskRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    执行自动控制任务

    仅适用于 execution_mode="auto" 的任务
    系统将通过BMS或其他控制接口执行设备调节
    """
    service = ExecutionService(db)
    result = await service.execute_auto_task(task_id, force=request.force)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "执行失败"))

    return result


@router.post("/tasks/{task_id}/complete", summary="完成手动任务")
async def complete_task(
    task_id: int,
    request: CompleteTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    标记手动任务为已完成

    适用于 execution_mode="manual" 的任务
    用户人工执行任务后，通过此接口标记完成
    """
    service = ExecutionService(db)
    result = await service.complete_manual_task(
        task_id,
        completed_by=request.completed_by or current_user.username,
        notes=request.notes
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "操作失败"))

    return result


@router.get("/tasks/{task_id}", summary="获取任务详情")
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取单个任务的详细信息"""
    from sqlalchemy import select
    from ...models.energy import ExecutionTask

    result = await db.execute(
        select(ExecutionTask).where(ExecutionTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail=f"任务ID {task_id} 不存在")

    return ExecutionTaskResponse.model_validate(task)


# ========== 效果追踪 ==========

@router.get("/plans/{plan_id}/tracking", summary="获取效果追踪数据")
async def get_tracking(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取执行计划的效果追踪数据

    对比执行前后的能耗数据，计算实际节省和达成率
    """
    service = ExecutionService(db)
    tracking = await service.track_execution_effect(plan_id, tracking_days=7)

    if "error" in tracking:
        raise HTTPException(status_code=400, detail=tracking["error"])

    return tracking


@router.post("/plans/{plan_id}/tracking", summary="创建追踪任务")
async def create_tracking(
    plan_id: int,
    request: TrackingRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    创建效果追踪任务

    指定追踪周期，系统将在追踪期结束后自动计算效果
    """
    service = ExecutionService(db)
    tracking = await service.track_execution_effect(plan_id, tracking_days=request.tracking_days)

    if "error" in tracking:
        raise HTTPException(status_code=400, detail=tracking["error"])

    return {
        "message": "追踪任务创建成功",
        "tracking": tracking
    }


@router.get("/results", summary="获取追踪结果列表")
async def list_results(
    plan_id: Optional[int] = Query(None, description="计划ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤: tracking/completed"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取追踪结果列表"""
    from sqlalchemy import select, func, and_
    from ...models.energy import ExecutionResult

    query = select(ExecutionResult)
    count_query = select(func.count(ExecutionResult.id))

    conditions = []
    if plan_id:
        conditions.append(ExecutionResult.plan_id == plan_id)
    if status:
        conditions.append(ExecutionResult.status == status)

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 获取数据
    query = query.order_by(ExecutionResult.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [ExecutionResultResponse.model_validate(i) for i in items],
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ========== 统计汇总 ==========

@router.get("/stats/summary", summary="获取执行统计汇总")
async def get_execution_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取执行统计汇总

    包括：
    - 各状态计划数量
    - 总预期节省
    - 总实际节省
    - 总体达成率
    """
    from sqlalchemy import select, func
    from ...models.energy import ExecutionPlan, ExecutionResult

    # 计划统计（按状态分组）
    plan_stats_result = await db.execute(
        select(
            ExecutionPlan.status,
            func.count(ExecutionPlan.id),
            func.sum(ExecutionPlan.expected_saving)
        ).group_by(ExecutionPlan.status)
    )
    plan_stats = plan_stats_result.all()

    stats_by_status = {}
    total_expected = 0
    completed_expected = 0  # 只统计已完成计划的预期节省
    for status, count, saving in plan_stats:
        saving_value = float(saving or 0)
        stats_by_status[status] = {
            "count": count,
            "expected_saving": saving_value
        }
        total_expected += saving_value
        if status == "completed":
            completed_expected = saving_value

    # 实际节省统计（从追踪结果中获取）
    result_stats = await db.execute(
        select(
            func.sum(ExecutionResult.actual_saving),
            func.count(ExecutionResult.id)
        ).where(ExecutionResult.status == "completed")
    )
    actual_saving, completed_tracking_count = result_stats.one()

    actual_total = float(actual_saving or 0)

    # 达成率计算说明：
    # 1. 如果有已完成的追踪记录，基于已追踪计划的预期节省计算达成率
    # 2. 获取已追踪计划的预期节省总和作为分母
    tracked_expected = 0
    if completed_tracking_count and completed_tracking_count > 0:
        # 获取有追踪记录的计划的预期节省
        tracked_plans_result = await db.execute(
            select(func.sum(ExecutionPlan.expected_saving))
            .where(
                ExecutionPlan.id.in_(
                    select(ExecutionResult.plan_id)
                    .where(ExecutionResult.status == "completed")
                    .distinct()
                )
            )
        )
        tracked_expected = float(tracked_plans_result.scalar() or 0)

    # 达成率 = 实际节省 / 已追踪计划的预期节省 × 100%
    achievement_rate = (actual_total / tracked_expected * 100) if tracked_expected > 0 else 0

    return ResponseModel(
        code=0,
        message="success",
        data={
            "plans": {
                "total": sum(s["count"] for s in stats_by_status.values()),
                "by_status": stats_by_status,
                "total_expected_saving": round(total_expected, 2),
                "completed_expected_saving": round(completed_expected, 2)
            },
            "results": {
                "completed_count": completed_tracking_count or 0,
                "total_actual_saving": round(actual_total, 2),
                "tracked_expected_saving": round(tracked_expected, 2),
                "overall_achievement_rate": round(achievement_rate, 1)
            }
        }
    )
