"""
实时数据路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core import get_db, get_current_user
from ..models import User, Point, PointRealtime
from ..schemas import PointRealtimeResponse, RealtimeSummary

router = APIRouter(prefix="/realtime", tags=["实时数据"])


@router.get("", response_model=List[PointRealtimeResponse])
async def get_realtime_data(
    point_type: Optional[str] = Query(None, description="点位类型"),
    area_code: Optional[str] = Query(None, description="区域代码"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有点位实时数据"""
    query = select(Point, PointRealtime).outerjoin(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.is_enabled == True)

    if point_type:
        query = query.where(Point.point_type == point_type)
    if area_code:
        query = query.where(Point.area_code == area_code)

    result = await db.execute(query)
    rows = result.all()

    return [
        PointRealtimeResponse(
            point_id=point.id,
            point_code=point.point_code,
            point_name=point.point_name,
            point_type=point.point_type,
            value=realtime.value if realtime else None,
            value_text=realtime.value_text if realtime else None,
            unit=point.unit,
            quality=realtime.quality if realtime else 0,
            status=realtime.status if realtime else "offline",
            updated_at=realtime.updated_at if realtime else None
        )
        for point, realtime in rows
    ]


@router.get("/summary", response_model=RealtimeSummary)
async def get_realtime_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取实时数据汇总"""
    # 总点位数
    total_result = await db.execute(
        select(func.count(Point.id)).where(Point.is_enabled == True)
    )
    total = total_result.scalar() or 0

    # 各状态统计
    query = select(
        PointRealtime.status,
        func.count(PointRealtime.point_id)
    ).join(Point).where(Point.is_enabled == True).group_by(PointRealtime.status)

    result = await db.execute(query)
    status_counts = {row[0]: row[1] for row in result.all()}

    return RealtimeSummary(
        total=total,
        normal=status_counts.get("normal", 0),
        alarm=status_counts.get("alarm", 0),
        offline=status_counts.get("offline", 0)
    )


@router.get("/{point_id}", response_model=PointRealtimeResponse)
async def get_point_realtime(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个点位实时数据"""
    query = select(Point, PointRealtime).outerjoin(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.id == point_id)

    result = await db.execute(query)
    row = result.first()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="点位不存在")

    point, realtime = row
    return PointRealtimeResponse(
        point_id=point.id,
        point_code=point.point_code,
        point_name=point.point_name,
        point_type=point.point_type,
        value=realtime.value if realtime else None,
        value_text=realtime.value_text if realtime else None,
        unit=point.unit,
        quality=realtime.quality if realtime else 0,
        status=realtime.status if realtime else "offline",
        updated_at=realtime.updated_at if realtime else None
    )
