"""
节能机会管理 API - v1
提供机会仪表盘、详情、模拟、设备选择和执行功能
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ..deps import get_db, require_viewer, require_admin
from ...models.user import User
from ...models.energy import (
    EnergyOpportunity, OpportunityMeasure,
    ExecutionPlan, ExecutionTask, ExecutionResult
)
from ...schemas.energy import (
    EnergyOpportunityCreate, EnergyOpportunityUpdate, EnergyOpportunityResponse,
    OpportunityMeasureCreate, OpportunityMeasureResponse,
    ExecutionPlanCreate, ExecutionPlanResponse,
    ExecutionTaskCreate, ExecutionTaskResponse,
    DashboardResponse, DashboardSummaryCards, OpportunitySummary,
    SimulationRequest, SimulationResponse,
    DeviceSelectionRequest, DeviceSelectionResponse
)
from ...services.opportunity_engine import OpportunityEngine, OpportunityCategory
from ...services.simulation_service import SimulationService
from ...services.device_selector_service import DeviceSelectorService

router = APIRouter()


# ========== 仪表盘 ==========

@router.get("/dashboard", summary="获取机会仪表盘数据")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
) -> DashboardResponse:
    """
    获取节能机会仪表盘数据，包括：
    - 概览卡片（年度可节省/待处理/执行中/本月已节省）
    - 机会列表按优先级排序
    - 按类别分组的机会
    """
    # 获取机会统计
    engine = OpportunityEngine(db)
    summary = await engine.get_opportunity_summary()

    # 查询数据库中的机会
    result = await db.execute(
        select(EnergyOpportunity)
        .where(EnergyOpportunity.status.in_(["discovered", "simulating", "ready"]))
        .order_by(
            # 优先级排序：high > medium > low
            func.field(EnergyOpportunity.priority, "high", "medium", "low"),
            EnergyOpportunity.potential_saving.desc()
        )
    )
    db_opportunities = result.scalars().all()

    # 执行中的计划数
    exec_result = await db.execute(
        select(func.count(ExecutionPlan.id))
        .where(ExecutionPlan.status == "executing")
    )
    executing_count = exec_result.scalar() or 0

    # 本月已完成的节省
    monthly_result = await db.execute(
        select(func.sum(ExecutionResult.actual_saving))
        .join(ExecutionPlan)
        .where(
            and_(
                ExecutionResult.status == "completed",
                ExecutionResult.tracking_end >= datetime.now().replace(day=1).date()
            )
        )
    )
    monthly_saving = monthly_result.scalar() or 0

    # 构建响应
    opportunities = [
        OpportunitySummary(
            id=o.id,
            category=o.category,
            title=o.title,
            description=o.description,
            priority=o.priority,
            potential_saving=float(o.potential_saving or 0),
            confidence=float(o.confidence or 0.8),
            status=o.status,
            source_plugin=o.source_plugin,
            analysis_data=o.analysis_data if isinstance(o.analysis_data, dict) else None
        )
        for o in db_opportunities
    ]

    # 按类别分组
    by_category = {}
    for o in opportunities:
        cat_name = _get_category_name(o.category)
        if cat_name not in by_category:
            by_category[cat_name] = []
        by_category[cat_name].append(o)

    # 计算年度潜在节省
    annual_saving = summary.get("total_potential_saving_annual", 0)
    if db_opportunities:
        annual_saving = max(annual_saving, sum(float(o.potential_saving or 0) for o in db_opportunities))

    return DashboardResponse(
        summary_cards=DashboardSummaryCards(
            annual_potential_saving=round(annual_saving, 2),
            pending_opportunities=len([o for o in opportunities if o.status in ["discovered", "ready"]]),
            executing_plans=executing_count,
            monthly_actual_saving=round(monthly_saving, 2)
        ),
        opportunities=opportunities,
        by_category=by_category,
        total_count=len(opportunities)
    )


# ========== 机会详情 ==========

@router.get("/{opportunity_id}/detail", summary="获取机会详情")
async def get_opportunity_detail(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
) -> EnergyOpportunityResponse:
    """获取单个节能机会的详细信息，包括措施列表"""
    result = await db.execute(
        select(EnergyOpportunity)
        .where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()

    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    # 获取关联的措施
    measures_result = await db.execute(
        select(OpportunityMeasure)
        .where(OpportunityMeasure.opportunity_id == opportunity_id)
        .order_by(OpportunityMeasure.sort_order)
    )
    measures = measures_result.scalars().all()

    response = EnergyOpportunityResponse.model_validate(opportunity)
    response.measures = [OpportunityMeasureResponse.model_validate(m) for m in measures]

    return response


# ========== 模拟 ==========

@router.post("/{opportunity_id}/simulate", summary="模拟参数调整效果")
async def simulate_opportunity(
    opportunity_id: int,
    request: SimulationRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
) -> SimulationResponse:
    """
    模拟参数调整后的效果，支持：
    - demand_adjustment: 需量调整模拟
    - peak_shift: 峰谷转移模拟
    - device_regulation: 设备调节模拟
    """
    # 验证机会存在
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    simulation = SimulationService(db)
    sim_type = request.simulation_type
    params = request.parameters

    try:
        if sim_type == "demand_adjustment":
            result = await simulation.simulate_demand_adjustment(
                new_declared_demand=params.get("new_declared_demand", 0),
                historical_days=params.get("historical_days", 30)
            )
        elif sim_type == "peak_shift":
            result = await simulation.simulate_peak_shift(
                shift_power=params.get("shift_power", 0),
                shift_hours=params.get("shift_hours", 4),
                source_period=params.get("source_period", "peak"),
                target_period=params.get("target_period", "valley")
            )
        elif sim_type == "device_regulation":
            result = await simulation.simulate_device_regulation(
                device_id=params.get("device_id"),
                target_value=params.get("target_value"),
                regulation_type=params.get("regulation_type", "temperature")
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的模拟类型: {sim_type}")

        return SimulationResponse(
            is_feasible=result.is_feasible,
            current_state=result.current_state,
            simulated_state=result.simulated_state,
            benefit=result.benefit,
            confidence=result.confidence,
            warnings=result.warnings,
            recommendations=result.recommendations
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模拟失败: {str(e)}")


# ========== 设备选择 ==========

@router.get("/{opportunity_id}/devices", summary="获取可参与设备列表")
async def get_available_devices(
    opportunity_id: int,
    regulation_type: Optional[str] = Query(None, description="调节类型过滤"),
    execution_mode: Optional[str] = Query(None, description="执行方式过滤: auto/manual"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取可参与该优化机会的设备列表"""
    # 验证机会存在
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    selector = DeviceSelectorService(db)
    devices = await selector.get_available_devices(
        regulation_type=regulation_type,
        execution_mode=execution_mode
    )

    return {
        "opportunity_id": opportunity_id,
        "opportunity_title": opportunity.title,
        "available_devices": devices,
        "device_count": len(devices),
        "total_adjustable_power": round(sum(d["total_adjustable_power"] for d in devices), 2)
    }


@router.post("/{opportunity_id}/select-devices", summary="选择参与设备")
async def select_devices(
    opportunity_id: int,
    request: DeviceSelectionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
) -> DeviceSelectionResponse:
    """
    选择参与优化的设备，返回验证结果和时段交集
    """
    # 验证机会存在
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    selector = DeviceSelectorService(db)
    validation = await selector.validate_device_selection(
        device_ids=request.selected_device_ids,
        target_power=request.target_power,
        target_hours=request.target_hours
    )

    return DeviceSelectionResponse(
        selected_count=validation["selected_count"],
        total_adjustable_power=validation["total_adjustable_power"],
        time_intersection=validation["time_intersection"]["intersection_hours"],
        is_feasible=validation["is_valid"],
        warnings=validation["warnings"]
    )


# ========== 执行 ==========

@router.post("/{opportunity_id}/execute", summary="确认执行")
async def execute_opportunity(
    opportunity_id: int,
    selected_device_ids: List[int] = [],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    确认执行节能机会，生成执行计划和任务清单
    """
    # 验证机会存在且状态正确
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    if opportunity.status not in ["discovered", "simulating", "ready"]:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态({opportunity.status})不允许执行"
        )

    # 获取措施
    measures_result = await db.execute(
        select(OpportunityMeasure)
        .where(OpportunityMeasure.opportunity_id == opportunity_id)
        .order_by(OpportunityMeasure.sort_order)
    )
    measures = measures_result.scalars().all()

    # 创建执行计划
    plan = ExecutionPlan(
        opportunity_id=opportunity_id,
        plan_name=f"{opportunity.title} - 执行计划",
        expected_saving=opportunity.potential_saving,
        status="pending",
        created_by=current_user.id
    )
    db.add(plan)
    await db.flush()

    # 为每个措施创建执行任务
    tasks = []
    for idx, measure in enumerate(measures):
        task = ExecutionTask(
            plan_id=plan.id,
            task_type=measure.measure_type,
            task_name=measure.measure_name or f"任务{idx + 1}",
            target_object=measure.regulation_object,
            execution_mode=measure.execution_mode,
            parameters={
                "current_state": measure.current_state,
                "target_state": measure.target_state,
                "selected_devices": measure.selected_devices or selected_device_ids
            },
            status="pending",
            sort_order=idx
        )
        db.add(task)
        tasks.append(task)

    # 更新机会状态
    opportunity.status = "executing"
    opportunity.updated_at = datetime.now()

    await db.commit()
    await db.refresh(plan)

    return {
        "message": "执行计划创建成功",
        "plan_id": plan.id,
        "task_count": len(tasks),
        "expected_saving": float(plan.expected_saving or 0),
        "status": plan.status
    }


# ========== CRUD 辅助 ==========

@router.get("", summary="获取机会列表")
async def list_opportunities(
    category: Optional[int] = Query(None, description="分类过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    priority: Optional[str] = Query(None, description="优先级过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """获取节能机会列表"""
    query = select(EnergyOpportunity)
    count_query = select(func.count(EnergyOpportunity.id))

    if category:
        query = query.where(EnergyOpportunity.category == category)
        count_query = count_query.where(EnergyOpportunity.category == category)
    if status:
        query = query.where(EnergyOpportunity.status == status)
        count_query = count_query.where(EnergyOpportunity.status == status)
    if priority:
        query = query.where(EnergyOpportunity.priority == priority)
        count_query = count_query.where(EnergyOpportunity.priority == priority)

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 获取数据
    query = query.order_by(EnergyOpportunity.discovered_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [EnergyOpportunityResponse.model_validate(i) for i in items],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("", summary="创建节能机会")
async def create_opportunity(
    data: EnergyOpportunityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """手动创建节能机会"""
    opportunity = EnergyOpportunity(**data.model_dump())
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)
    return EnergyOpportunityResponse.model_validate(opportunity)


@router.put("/{opportunity_id}", summary="更新节能机会")
async def update_opportunity(
    opportunity_id: int,
    data: EnergyOpportunityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """更新节能机会"""
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(opportunity, key, value)

    opportunity.updated_at = datetime.now()
    await db.commit()
    await db.refresh(opportunity)

    return EnergyOpportunityResponse.model_validate(opportunity)


@router.delete("/{opportunity_id}", summary="删除节能机会")
async def delete_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """删除节能机会（仅限discovered状态）"""
    result = await db.execute(
        select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail=f"机会ID {opportunity_id} 不存在")

    if opportunity.status != "discovered":
        raise HTTPException(status_code=400, detail="只能删除discovered状态的机会")

    await db.delete(opportunity)
    await db.commit()

    return {"message": "删除成功"}


# ========== 工具函数 ==========

def _get_category_name(category: int) -> str:
    """获取类别名称"""
    names = {
        1: "bill_optimization",
        2: "device_operation",
        3: "equipment_upgrade",
        4: "comprehensive"
    }
    return names.get(category, "unknown")
