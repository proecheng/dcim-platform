"""
Load Shift API - 负荷转移 API
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..deps import get_db, get_current_user, require_operator
from ...models.user import User
from ...models.load_shift import ShiftPlan
from ...models.energy import PowerDevice, DeviceShiftConfig
from ...schemas.load_shift import (
    # Plan schemas
    ShiftPlanCreate,
    ShiftPlanUpdate,
    ShiftPlanResponse,
    ShiftPlanDetail,
    ShiftPlanApproval,
    ShiftPlanStatus,
    # Analysis schemas
    FeasibilityAnalysisRequest,
    FeasibilityAnalysisResponse,
    ConstraintCheckResult,
    BenefitAnalysisResponse,
    RiskAssessmentResponse,
    # Device schemas
    DeviceShiftPotentialResponse,
    # Dashboard schemas
    ShiftDashboardOverview,
    ShiftRealtimeData,
    ShiftTrendData,
    # Statistics schemas
    ShiftStatisticsSummary,
    # Opportunity schemas
    ShiftOpportunityResponse,
    ShiftOpportunityDetail,
)
from ...services.load_shift.shift_plan_service import ShiftPlanService
from ...services.load_shift.algorithms.constraint_checker import ConstraintChecker
from ...services.load_shift.algorithms.benefit_calculator import BenefitCalculator

router = APIRouter(tags=["Load Shift"])


# ========== Plan Management Endpoints ==========


@router.get("/plans", response_model=List[ShiftPlanResponse])
async def get_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ShiftPlanStatus] = None,
    shift_date_from: Optional[date] = None,
    shift_date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shift plans list with filters
    获取转移计划列表（支持筛选）
    """
    plans = await ShiftPlanService.get_plans(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        shift_date_from=shift_date_from,
        shift_date_to=shift_date_to,
    )
    return plans


@router.post("/plans", response_model=ShiftPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    plan_data: ShiftPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Create new shift plan
    创建新的转移计划
    """
    plan = await ShiftPlanService.create_plan(
        db=db,
        plan_data=plan_data,
        user_id=current_user.id,
    )
    return plan


@router.get("/plans/{plan_id}", response_model=ShiftPlanDetail)
async def get_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shift plan detail
    获取转移计划详情
    """
    plan = await ShiftPlanService.get_plan(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在",
        )
    return plan


@router.put("/plans/{plan_id}", response_model=ShiftPlanResponse)
async def update_plan(
    plan_id: int,
    plan_data: ShiftPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Update shift plan (only draft status)
    更新转移计划（仅草稿状态）
    """
    plan = await ShiftPlanService.update_plan(
        db=db,
        plan_id=plan_id,
        plan_data=plan_data,
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在",
        )
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Delete shift plan (only draft status)
    删除转移计划（仅草稿状态）
    """
    success = await ShiftPlanService.delete_plan(db=db, plan_id=plan_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在或无法删除",
        )


@router.post("/plans/{plan_id}/submit", response_model=ShiftPlanResponse)
async def submit_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Submit plan for approval
    提交计划审批
    """
    plan = await ShiftPlanService.submit_for_approval(db=db, plan_id=plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在或状态不允许提交",
        )
    return plan


@router.post("/plans/{plan_id}/approve", response_model=ShiftPlanResponse)
async def approve_plan(
    plan_id: int,
    approval_data: ShiftPlanApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Approve or reject plan
    审批计划（批准/拒绝）
    """
    try:
        plan = await ShiftPlanService.approve_plan(
            db=db,
            plan_id=plan_id,
            approval_data=approval_data,
            approver_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在或状态不允许审批",
        )
    return plan


@router.post("/plans/{plan_id}/execute", response_model=ShiftPlanResponse)
async def execute_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Start plan execution
    开始执行计划
    """
    try:
        plan = await ShiftPlanService.start_execution(db=db, plan_id=plan_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"计划 ID {plan_id} 不存在或状态不允许执行",
        )
    return plan


# ========== Opportunity Endpoints ==========


@router.post("/opportunities/analyze")
async def analyze_opportunities(
    analysis_date: date = Query(default_factory=date.today),
    lookback_days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Trigger opportunity analysis
    触发机会分析
    """
    from ...services.load_shift.algorithms.opportunity_finder import OpportunityFinder

    try:
        finder = OpportunityFinder(db)
        opportunities = await finder.find_daily_opportunities(analysis_date=analysis_date, lookback_days=lookback_days)

        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"机会分析失败: {str(e)}")

    return {
        "analysis_date": analysis_date,
        "opportunities_found": len(opportunities),
        "opportunities": [
            {
                "id": opp.id,
                "opportunity_code": opp.opportunity_code,
                "opportunity_name": opp.opportunity_name,
                "recommended_shift_from": opp.recommended_shift_from,
                "recommended_shift_to": opp.recommended_shift_to,
                "recommended_shift_power": opp.recommended_shift_power,
                "predicted_cost_saving": float(opp.predicted_cost_saving),
                "confidence_score": opp.confidence_score,
                "priority": opp.priority,
            }
            for opp in opportunities
        ],
    }


@router.get("/opportunities", response_model=List[ShiftOpportunityResponse])
async def get_opportunities(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get opportunities list
    获取机会列表
    """
    from ...models.load_shift import ShiftOpportunity

    stmt = select(ShiftOpportunity)

    if status:
        stmt = stmt.where(ShiftOpportunity.status == status)
    if priority:
        stmt = stmt.where(ShiftOpportunity.priority == priority)

    stmt = stmt.order_by(ShiftOpportunity.recommended_date.desc())
    stmt = stmt.offset(skip).limit(limit)

    result = await db.execute(stmt)
    opportunities = result.scalars().all()

    return opportunities


@router.get("/opportunities/{opp_id}", response_model=ShiftOpportunityDetail)
async def get_opportunity_detail(
    opp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get opportunity detail
    获取机会详情
    """
    from ...models.load_shift import ShiftOpportunity

    stmt = select(ShiftOpportunity).where(ShiftOpportunity.id == opp_id)
    result = await db.execute(stmt)
    opportunity = result.scalar_one_or_none()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"机会 ID {opp_id} 不存在",
        )

    return opportunity


@router.post("/opportunities/{opp_id}/convert", response_model=ShiftPlanResponse)
async def convert_opportunity_to_plan(
    opp_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """
    Convert opportunity to shift plan
    将机会转换为转移计划
    """
    from ...models.load_shift import ShiftOpportunity
    from datetime import time

    # Get opportunity
    stmt = select(ShiftOpportunity).where(ShiftOpportunity.id == opp_id)
    result = await db.execute(stmt)
    opportunity = result.scalar_one_or_none()

    if not opportunity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"机会 ID {opp_id} 不存在",
        )

    if opportunity.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该机会已经转换为计划",
        )

    # Create plan from opportunity
    plan_data = ShiftPlanCreate(
        plan_name=f"基于机会 {opportunity.opportunity_code} 的转移计划",
        shift_from_period=opportunity.recommended_shift_from,
        shift_to_period=opportunity.recommended_shift_to,
        shift_date=opportunity.recommended_date,
        start_time=time(1, 0),  # Default 01:00
        end_time=time(5, 0),  # Default 05:00
        target_shift_power=opportunity.recommended_shift_power,
        selected_devices=[d["device_id"] for d in opportunity.recommended_devices],
        constraints={"safety_factor": 0.85, "cooling_lag_minutes": 20, "three_phase_balance_threshold": 0.1},
        expected_cost_saving=opportunity.predicted_cost_saving,
        expected_energy_saving=opportunity.recommended_shift_power * 4,  # 4 hours
        description=f"由机会 {opportunity.opportunity_code} 自动生成，置信度 {opportunity.confidence_score}",
    )

    plan = await ShiftPlanService.create_plan(db=db, plan_data=plan_data, created_by=current_user.id)

    # Update opportunity status
    opportunity.status = "converted"
    await db.commit()

    return plan


# ========== Analysis Endpoints ==========


@router.post("/analysis/feasibility", response_model=FeasibilityAnalysisResponse)
async def analyze_feasibility(
    request: FeasibilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze shift feasibility (constraint check + benefit analysis)
    分析转移可行性（约束检查 + 收益分析）
    """
    # Constraint check
    checker = ConstraintChecker(db)
    constraint_result = await checker.check_all_constraints(
        request=request,
        device_ids=request.selected_devices or [],
    )

    # Benefit calculation
    calculator = BenefitCalculator(db)
    benefit_result = await calculator.calculate_benefits(
        request=request,
        device_ids=request.selected_devices or [],
    )

    return FeasibilityAnalysisResponse(
        is_feasible=constraint_result.is_valid,
        feasibility_score=1.0 if constraint_result.is_valid else 0.0,
        available_devices=[],
        max_shift_power=benefit_result.benefit_details.get("total_shift_power", 0.0),
        recommended_devices=request.selected_devices or [],
        warnings=constraint_result.warnings,
        suggestions=[] if constraint_result.is_valid else ["请根据约束检查结果调整目标功率或设备范围"],
    )


@router.post("/analysis/constraints", response_model=ConstraintCheckResult)
async def check_constraints(
    request: FeasibilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check constraints only
    仅检查约束条件
    """
    checker = ConstraintChecker(db)
    result = await checker.check_all_constraints(
        request=request,
        device_ids=request.selected_devices or [],
    )
    return result


@router.post("/analysis/benefit", response_model=BenefitAnalysisResponse)
async def analyze_benefit(
    request: FeasibilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate benefit only
    仅计算收益
    """
    calculator = BenefitCalculator(db)
    result = await calculator.calculate_benefits(
        request=request,
        device_ids=request.selected_devices or [],
    )
    return result


@router.post("/analysis/risk", response_model=RiskAssessmentResponse)
async def assess_risk(
    request: FeasibilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assess shift risk
    评估转移风险
    """
    # Risk assessment logic (placeholder - to be implemented in Phase 2)
    return RiskAssessmentResponse(
        overall_risk_level="low",
        risk_score=0.2,
        risk_factors=[
            {"factor": "cooling_lag", "severity": "low", "description": "制冷滞后效应风险较低"},
            {"factor": "device_lifespan", "severity": "low", "description": "设备寿命影响较小"},
        ],
        mitigation_measures=[
            "建议在转移前 15 分钟提前调整制冷系统",
            "建议避免频繁启停关键设备",
        ],
    )


# ========== Device Endpoints ==========


@router.get("/devices/shiftable", response_model=List[DeviceShiftPotentialResponse])
async def get_shiftable_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shiftable devices with potential
    获取可转移设备及潜力
    """
    devices_result = await db.execute(
        select(PowerDevice)
        .where(PowerDevice.is_enabled == True)
        .order_by(PowerDevice.device_type, PowerDevice.device_name)
    )
    devices = devices_result.scalars().all()

    if not devices:
        return []

    config_result = await db.execute(select(DeviceShiftConfig))
    configs = {c.device_id: c for c in config_result.scalars().all()}

    items: List[DeviceShiftPotentialResponse] = []
    for d in devices:
        cfg = configs.get(d.id)
        is_shiftable = bool(cfg.is_shiftable) if cfg is not None else True

        rated_power = float(d.rated_power or 0.0)
        avg_load_ratio = float(d.avg_load_rate or 60.0) / 100.0
        current_power = rated_power * avg_load_ratio

        shiftable_ratio = (
            float(cfg.shiftable_power_ratio) if cfg is not None and cfg.shiftable_power_ratio is not None else 0.2
        )
        shiftable_power = max(0.0, current_power * shiftable_ratio) if is_shiftable else 0.0

        constraints: List[str] = []
        if cfg is not None and bool(cfg.is_critical):
            constraints.append("critical_device")
        if cfg is not None and cfg.max_ramp_rate is not None:
            constraints.append(f"max_ramp_rate:{cfg.max_ramp_rate}")

        items.append(
            DeviceShiftPotentialResponse(
                device_id=d.id,
                device_name=d.device_name,
                device_type=d.device_type,
                rated_power=rated_power,
                current_power=round(current_power, 2),
                shift_potential=round(shiftable_power, 2),
                is_shiftable=is_shiftable,
                shift_score=round(min(1.0, shiftable_ratio if is_shiftable else 0.0), 2),
                constraints=constraints,
                last_shift_time=None,
                shift_count_today=0,
            )
        )

    return items


@router.get("/devices/{device_id}/potential", response_model=DeviceShiftPotentialResponse)
async def get_device_potential(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get device shift potential
    获取设备转移潜力
    """
    # Placeholder - to be implemented with shift_device_service
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="设备潜力分析功能待实现",
    )


# ========== Dashboard Endpoints ==========


@router.get("/dashboard/overview", response_model=ShiftDashboardOverview)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard overview
    获取仪表盘概览
    """
    # Get statistics
    stats = await ShiftPlanService.get_plan_statistics(db=db)

    # Get today's plans
    today = date.today()
    today_plans_result = await db.execute(
        select(ShiftPlan).where(ShiftPlan.shift_date == today).order_by(ShiftPlan.start_time)
    )
    today_plans = today_plans_result.scalars().all()

    # Get recent executions (placeholder - not used yet)
    # recent_executions_result = await db.execute(
    #     select(ShiftExecution)
    #     .order_by(ShiftExecution.start_time.desc())
    #     .limit(10)
    # )
    # recent_executions = recent_executions_result.scalars().all()

    return ShiftDashboardOverview(
        total_plans=stats.get("total_plans", 0),
        pending_approval=stats.get("pending_approval", 0),
        executing=stats.get("executing", 0),
        completed_today=len([p for p in today_plans if p.status == ShiftPlanStatus.COMPLETED]),
        total_cost_saving_today=0.0,
        total_energy_saving_today=0.0,
        total_shift_power_today=0.0,
        success_rate=stats.get("success_rate", 0.0),
        opportunities_count=0,
    )


@router.get("/dashboard/realtime", response_model=ShiftRealtimeData)
async def get_realtime_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get realtime shift data
    获取实时转移数据
    """
    # Placeholder - to be implemented with shift_dashboard_service
    return ShiftRealtimeData(
        current_shift_power=0.0,
        target_shift_power=0.0,
        completion_rate=0.0,
        active_devices=0,
        cooling_status={},
        execution_status="idle",
    )


@router.get("/dashboard/trends", response_model=List[ShiftTrendData])
async def get_trends(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shift trends
    获取转移趋势
    """
    # Placeholder - to be implemented with shift_dashboard_service
    return []


# ========== Statistics Endpoints ==========


@router.get("/statistics/summary", response_model=ShiftStatisticsSummary)
async def get_statistics_summary(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shift statistics summary
    获取转移统计汇总
    """
    # Placeholder - to be implemented with shift_dashboard_service
    start_date = date_from or date.today()
    end_date = date_to or date.today()
    return ShiftStatisticsSummary(
        period="daily",
        start_date=start_date,
        end_date=end_date,
        total_plans=0,
        completed_plans=0,
        failed_plans=0,
        total_shift_power=0.0,
        total_cost_saving=0.0,
        total_energy_saving=0.0,
        average_success_rate=0.0,
        peak_reduction_total=0.0,
        valley_filling_total=0.0,
    )


# ========== 制冷联动端点 ==========


@router.get("/cooling/config", response_model=Dict[str, Any])
async def get_cooling_config(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get cooling linkage configuration
    获取制冷联动配置
    """
    from app.services.load_shift.cooling_linkage_service import CoolingLinkageService

    config = await CoolingLinkageService.get_config(db)
    return {"data": config}


@router.put("/cooling/config", response_model=Dict[str, Any])
async def update_cooling_config(
    config_data: Dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Update cooling linkage configuration
    更新制冷联动配置
    """
    from app.services.load_shift.cooling_linkage_service import CoolingLinkageService

    config = await CoolingLinkageService.update_config(db, config_data)
    return {"data": config}


@router.get("/cooling/status", response_model=Dict[str, Any])
async def get_cooling_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get cooling linkage current status
    获取制冷联动当前状态
    """
    from app.services.load_shift.cooling_linkage_service import CoolingLinkageService

    status = await CoolingLinkageService.get_status(db)
    return {"data": status}


@router.get("/cooling/history", response_model=Dict[str, Any])
async def get_cooling_history(
    limit: int = Query(50, ge=1, le=200),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get cooling linkage history records
    获取制冷联动历史记录
    """
    from app.services.load_shift.cooling_linkage_service import CoolingLinkageService

    history = await CoolingLinkageService.get_history(db, limit, start_time, end_time)
    return {"data": history}


# ========== 报表端点 ==========
@router.get("/reports/{report_type}", response_model=Dict[str, Any])
async def get_shift_report(
    report_type: str,
    year: int = Query(..., ge=2020, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get shift report (monthly or yearly)
    获取负荷转移报表（月度或年度）
    """
    from app.services.load_shift.shift_report_service import ShiftReportService

    if report_type == "monthly":
        if not month:
            raise HTTPException(status_code=400, detail="Month is required for monthly report")
        report_data = await ShiftReportService.generate_monthly_report(db, year, month)
    elif report_type == "yearly":
        report_data = await ShiftReportService.generate_yearly_report(db, year)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")

    return {"data": report_data}


@router.post("/reports/export", response_model=Dict[str, Any])
async def export_shift_report(
    report_data: Dict[str, Any],
    format: str = Query(..., pattern="^(excel|pdf)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Export shift report to Excel or PDF
    导出负荷转移报表为 Excel 或 PDF
    """
    from app.services.load_shift.shift_report_service import ShiftReportService

    if format == "excel":
        file_path = await ShiftReportService.export_report_excel(report_data)
    else:
        file_path = await ShiftReportService.export_report_pdf(report_data)

    return {"data": {"download_url": file_path}}


# ========== 约束管理端点 ==========
@router.get("/constraints", response_model=Dict[str, Any])
async def get_constraints(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get all constraints
    获取所有约束配置
    """
    from app.services.load_shift.shift_constraint_service import ShiftConstraintService

    constraints = await ShiftConstraintService.get_constraints(db)
    return {"data": constraints}


@router.post("/constraints", response_model=Dict[str, Any])
async def create_constraint(
    data: Dict[str, Any], db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create constraint
    创建约束配置
    """
    from app.services.load_shift.shift_constraint_service import ShiftConstraintService

    constraint = await ShiftConstraintService.create_constraint(db, data)
    return {"data": constraint}


@router.put("/constraints/{constraint_id}", response_model=Dict[str, Any])
async def update_constraint(
    constraint_id: int,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update constraint
    更新约束配置
    """
    from app.services.load_shift.shift_constraint_service import ShiftConstraintService

    constraint = await ShiftConstraintService.update_constraint(db, constraint_id, data)
    return {"data": constraint}


@router.delete("/constraints/{constraint_id}", response_model=Dict[str, Any])
async def delete_constraint(
    constraint_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete constraint
    删除约束配置
    """
    from app.services.load_shift.shift_constraint_service import ShiftConstraintService

    success = await ShiftConstraintService.delete_constraint(db, constraint_id)
    return {"data": {"success": success}}
