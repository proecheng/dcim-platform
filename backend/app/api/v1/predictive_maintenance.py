"""预测性维护 API — Story 36.3 + 36.4

Story 36.3: 列表查询、详情、确认转工单、拒绝标误报（4 个端点）
Story 36.4: 仪表盘统计、设备健康度详情（2 个端点）
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db, require_viewer, require_operator
from ...models.device import Device
from ...models.report import MaintenanceAdvice, DeviceHealthScore
from ...models.user import User
from ...schemas.predictive_maintenance import (
    MaintenanceAdviceInfo,
    AdviceRejectRequest,
    AdviceConfirmResponse,
    DashboardSummary,
    DeviceHealthItem,
    DashboardResponse,
    ScoreFactorDetail,
    DeviceDetailResponse,
)
from ...services.predictive_maintenance.advisor import MaintenanceAdvisor

router = APIRouter()


# ==================== Story 36.4: Dashboard + Device Detail ====================


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    device_type: str | None = Query(None, description="按设备类型筛选"),
    health_level: str | None = Query(None, description="按健康等级筛选: 健康/关注/预警/危险"),
    site_id: int | None = Query(None, description="按站点筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """预测性维护仪表盘 — 统计概览 + 设备健康度列表"""
    # 1. site_id 基础条件（共享给 summary 和 device 两个查询）
    base_cond = []
    if site_id:
        base_cond.append(
            DeviceHealthScore.device_id.in_(
                select(Device.id).where(Device.site_id == site_id)
            )
        )

    # 2. summary 聚合查询（GROUP BY health_level，只受 site_id 过滤）
    summary_stmt = (
        select(DeviceHealthScore.health_level, func.count())
        .where(*base_cond)
        .group_by(DeviceHealthScore.health_level)
    )
    summary_result = await db.execute(summary_stmt)
    level_counts = {row[0]: row[1] for row in summary_result.fetchall()}
    total = sum(level_counts.values())
    summary = DashboardSummary(
        total=total,
        healthy=level_counts.get("健康", 0),
        attention=level_counts.get("关注", 0),
        warning=level_counts.get("预警", 0),
        danger=level_counts.get("危险", 0),
    )

    # 3. 设备列表查询（SQL 层过滤 + 排序）
    device_stmt = select(DeviceHealthScore).where(*base_cond)
    if device_type:
        device_stmt = device_stmt.where(DeviceHealthScore.device_type == device_type)
    if health_level:
        device_stmt = device_stmt.where(DeviceHealthScore.health_level == health_level)
    device_stmt = device_stmt.order_by(DeviceHealthScore.score.asc())

    result = await db.execute(device_stmt)
    devices = [DeviceHealthItem.model_validate(r) for r in result.scalars().all()]

    return DashboardResponse(summary=summary, devices=devices)


@router.get("/devices/{device_id}/detail", response_model=DeviceDetailResponse)
async def get_device_detail(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """设备健康度详情 — 因子明细 + 维护建议列表"""
    # 1. 查询 DeviceHealthScore
    result = await db.execute(
        select(DeviceHealthScore).where(DeviceHealthScore.device_id == device_id)
    )
    health = result.scalar_one_or_none()
    if not health:
        raise HTTPException(status_code=404, detail="设备健康度记录不存在")

    health_item = DeviceHealthItem.model_validate(health)

    # 2. 防御性解析 score_factors（Text 列，可能为 None）
    factors = None
    if health.score_factors:
        try:
            factors_dict = json.loads(health.score_factors)
            factors = ScoreFactorDetail(**factors_dict)
        except (json.JSONDecodeError, TypeError, ValueError):
            factors = None

    # 3. 查询维护建议（最近 10 条，最新优先）
    advice_result = await db.execute(
        select(MaintenanceAdvice)
        .where(MaintenanceAdvice.device_id == device_id)
        .order_by(MaintenanceAdvice.created_at.desc())
        .limit(10)
    )
    advices = [MaintenanceAdviceInfo.model_validate(a) for a in advice_result.scalars().all()]

    return DeviceDetailResponse(health=health_item, factors=factors, advices=advices)


# ==================== Story 36.3: Advice CRUD ====================


@router.get("/advices", response_model=list[MaintenanceAdviceInfo])
async def list_advices(
    status: str | None = Query(None, description="按状态筛选: pending/converted/rejected/auto_closed"),
    device_type: str | None = Query(None, description="按设备类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """列表查询维护建议"""
    stmt = select(MaintenanceAdvice)
    if status:
        stmt = stmt.where(MaintenanceAdvice.status == status)
    if device_type:
        stmt = stmt.where(MaintenanceAdvice.device_type == device_type)
    stmt = stmt.order_by(MaintenanceAdvice.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    advices = result.scalars().all()
    return [MaintenanceAdviceInfo.model_validate(a) for a in advices]


@router.get("/advices/{advice_id}", response_model=MaintenanceAdviceInfo)
async def get_advice(
    advice_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取维护建议详情"""
    advice = await db.get(MaintenanceAdvice, advice_id)
    if not advice:
        raise HTTPException(status_code=404, detail="建议不存在")
    return MaintenanceAdviceInfo.model_validate(advice)


@router.post("/advices/{advice_id}/confirm", response_model=AdviceConfirmResponse)
async def confirm_advice(
    advice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
):
    """确认建议 → 创建维护工单"""
    advisor = MaintenanceAdvisor(db)
    try:
        wo = await advisor.confirm_advice(advice_id, user.id)
        await db.commit()
        return AdviceConfirmResponse(
            advice_id=advice_id,
            work_order_id=wo.id,
            work_order_no=wo.order_no,
        )
    except ValueError as e:
        status_code = 404 if "不存在" in str(e) else 409
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/advices/{advice_id}/reject", response_model=MaintenanceAdviceInfo)
async def reject_advice(
    advice_id: int,
    body: AdviceRejectRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """拒绝建议（标记误报）"""
    advisor = MaintenanceAdvisor(db)
    try:
        advice = await advisor.reject_advice(advice_id, body.feedback)
        await db.commit()
        return MaintenanceAdviceInfo.model_validate(advice)
    except ValueError as e:
        status_code = 404 if "不存在" in str(e) else 409
        raise HTTPException(status_code=status_code, detail=str(e))
