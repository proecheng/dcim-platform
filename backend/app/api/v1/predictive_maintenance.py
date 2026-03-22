"""预测性维护 API — Story 36.3

4 个端点: 列表查询、详情、确认转工单、拒绝标误报
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db, require_viewer, require_operator
from ...models.report import MaintenanceAdvice
from ...models.user import User
from ...schemas.predictive_maintenance import (
    MaintenanceAdviceInfo,
    AdviceRejectRequest,
    AdviceConfirmResponse,
)
from ...services.predictive_maintenance.advisor import MaintenanceAdvisor

router = APIRouter()


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
