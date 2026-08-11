"""
传感器数据漂移检测 API
Story 9-7: 传感器数据漂移检测
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from ..deps import (
    SiteAccessContext,
    apply_point_site_scope,
    authorized_point_ids_query,
    get_db,
    get_site_access_context,
    require_operator,
    require_viewer,
)
from ...models.user import User
from ...models.drift import DriftDetectionResult
from ...schemas.drift import (
    DriftDetectionResultResponse,
    DriftDetectionSummary,
    DriftDetectResponse,
)
from ...services import drift_detection

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/detect", response_model=DriftDetectResponse, summary="触发漂移检测")
async def trigger_detection(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """触发一次漂移检测，扫描所有 AI 类型点位"""
    result = await drift_detection.run_drift_detection(db, allowed_point_ids=authorized_point_ids_query(context))
    return DriftDetectResponse(
        message=f"检测完成: 检查 {result['total_checked']} 个点位",
        total_checked=result["total_checked"],
        new_suspected=result["new_suspected"],
        new_confirmed=result["new_confirmed"],
        auto_resolved=result["auto_resolved"],
    )


@router.get("/results", summary="漂移检测结果列表")
async def list_results(
    status: Optional[str] = Query(None, description="状态筛选: suspected/confirmed/resolved"),
    area_code: Optional[str] = Query(None, description="区域筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取漂移检测结果列表（分页）"""
    query = select(DriftDetectionResult)
    count_query = select(func.count(DriftDetectionResult.id))
    query = apply_point_site_scope(query, DriftDetectionResult.point_id, context)
    count_query = apply_point_site_scope(count_query, DriftDetectionResult.point_id, context)

    if status:
        query = query.where(DriftDetectionResult.status == status)
        count_query = count_query.where(DriftDetectionResult.status == status)
    if area_code:
        query = query.where(DriftDetectionResult.area_code == area_code)
        count_query = count_query.where(DriftDetectionResult.area_code == area_code)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(DriftDetectionResult.detected_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "items": [DriftDetectionResultResponse.model_validate(item) for item in items],
        "page": page,
        "page_size": page_size,
    }


@router.get("/summary", response_model=DriftDetectionSummary, summary="漂移检测概览")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取漂移检测统计概览"""
    stats_query = select(
            DriftDetectionResult.status,
            func.count(DriftDetectionResult.id),
        ).group_by(DriftDetectionResult.status)
    stats_result = await db.execute(
        apply_point_site_scope(stats_query, DriftDetectionResult.point_id, context)
    )
    counts = {row[0]: row[1] for row in stats_result.all()}

    return DriftDetectionSummary(
        total_checked=sum(counts.values()),
        suspected_count=counts.get("suspected", 0),
        confirmed_count=counts.get("confirmed", 0),
        resolved_count=counts.get("resolved", 0),
        skipped_count=0,
    )


@router.get("/results/{result_id}", response_model=DriftDetectionResultResponse, summary="漂移检测结果详情")
async def get_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取单条漂移检测结果详情"""
    query = apply_point_site_scope(
        select(DriftDetectionResult).where(DriftDetectionResult.id == result_id),
        DriftDetectionResult.point_id,
        context,
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="漂移检测记录不存在")
    return DriftDetectionResultResponse.model_validate(record)


@router.post("/results/{result_id}/resolve", response_model=DriftDetectionResultResponse, summary="手动解除漂移标记")
async def resolve_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """手动解除漂移标记，恢复点位数据质量"""
    authorized = apply_point_site_scope(
        select(DriftDetectionResult.id).where(DriftDetectionResult.id == result_id),
        DriftDetectionResult.point_id,
        context,
    )
    if (await db.execute(authorized)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="漂移检测记录不存在")
    try:
        record = await drift_detection.resolve_drift(db, result_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not record:
        raise HTTPException(status_code=404, detail="漂移检测记录不存在")
    return DriftDetectionResultResponse.model_validate(record)
