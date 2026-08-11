"""数据质量 API"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import SiteAccessContext, apply_point_site_scope, get_db, get_site_access_context, require_viewer
from ...models.user import User
from ...models.point import Point, PointRealtime
from ...schemas.data_quality import DataQualityPointInfo, DataQualityStatus

router = APIRouter()

QUALITY_TEXT_MAP = {0: "正常", 1: "不确定", 2: "不可靠"}


@router.get("/status", response_model=DataQualityStatus, summary="数据质量概览")
async def get_data_quality_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取数据质量统计概览，包含不可靠点位详情"""
    # 按 quality 分组统计
    stats_query = select(
        PointRealtime.quality,
        func.count(PointRealtime.point_id),
    ).group_by(PointRealtime.quality)
    stats_result = await db.execute(
        apply_point_site_scope(stats_query, PointRealtime.point_id, context)
    )
    counts = {row[0] or 0: row[1] for row in stats_result.all()}

    total = sum(counts.values())
    normal_count = counts.get(0, 0)
    uncertain_count = counts.get(1, 0)
    unreliable_count = counts.get(2, 0)

    # 查询不可靠点位详情
    unreliable_points: List[DataQualityPointInfo] = []
    if unreliable_count > 0:
        detail_query = (
            select(
                PointRealtime.point_id,
                Point.point_code,
                Point.point_name,
                Point.device_type,
                PointRealtime.quality,
                PointRealtime.status,
                PointRealtime.updated_at,
            )
            .join(Point, Point.id == PointRealtime.point_id)
            .where(PointRealtime.quality == 2)
        )
        detail_result = await db.execute(
            apply_point_site_scope(detail_query, PointRealtime.point_id, context)
        )
        for row in detail_result.all():
            q = row[4] or 0
            unreliable_points.append(
                DataQualityPointInfo(
                    point_id=row[0],
                    point_code=row[1],
                    point_name=row[2],
                    device_type=row[3],
                    quality=q,
                    quality_text=QUALITY_TEXT_MAP.get(q, "未知"),
                    status=row[5],
                    updated_at=row[6],
                )
            )

    return DataQualityStatus(
        total=total,
        normal_count=normal_count,
        uncertain_count=uncertain_count,
        unreliable_count=unreliable_count,
        unreliable_points=unreliable_points,
    )


@router.get("/points", response_model=List[DataQualityPointInfo], summary="数据质量点位列表")
async def get_data_quality_points(
    quality: Optional[int] = Query(None, ge=0, le=2, description="数据质量过滤: 0=正常 1=不确定 2=不可靠"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """查询点位数据质量列表，可按 quality 过滤"""
    query = select(
        PointRealtime.point_id,
        Point.point_code,
        Point.point_name,
        Point.device_type,
        PointRealtime.quality,
        PointRealtime.status,
        PointRealtime.updated_at,
    ).join(Point, Point.id == PointRealtime.point_id)
    query = apply_point_site_scope(query, PointRealtime.point_id, context)

    if quality is not None:
        query = query.where(PointRealtime.quality == quality)

    result = await db.execute(query)
    items = []
    for row in result.all():
        q = row[4] or 0
        items.append(
            DataQualityPointInfo(
                point_id=row[0],
                point_code=row[1],
                point_name=row[2],
                device_type=row[3],
                quality=q,
                quality_text=QUALITY_TEXT_MAP.get(q, "未知"),
                status=row[5],
                updated_at=row[6],
            )
        )

    return items
