"""
点位路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core import get_db, get_current_user
from ..models import User, Point, PointRealtime
from ..schemas import (
    PointCreate, PointUpdate, PointResponse,
    PointRealtimeResponse, PointTypeStats, RealtimeSummary
)

router = APIRouter(prefix="/points", tags=["点位管理"])


@router.get("", response_model=List[PointResponse])
async def get_points(
    point_type: Optional[str] = Query(None, description="点位类型 AI/DI/AO/DO"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    area_code: Optional[str] = Query(None, description="区域代码"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位列表"""
    query = select(Point)

    if point_type:
        query = query.where(Point.point_type == point_type)
    if device_type:
        query = query.where(Point.device_type == device_type)
    if area_code:
        query = query.where(Point.area_code == area_code)
    if is_enabled is not None:
        query = query.where(Point.is_enabled == is_enabled)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/types", response_model=List[PointTypeStats])
async def get_point_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位类型统计"""
    query = select(
        Point.point_type,
        func.count(Point.id).label("count"),
        func.sum(func.cast(Point.is_enabled, Integer)).label("enabled_count")
    ).group_by(Point.point_type)

    from sqlalchemy import Integer
    result = await db.execute(query)
    rows = result.all()

    return [
        PointTypeStats(
            point_type=row[0],
            count=row[1],
            enabled_count=row[2] or 0
        )
        for row in rows
    ]


@router.get("/{point_id}", response_model=PointResponse)
async def get_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位详情"""
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")
    return point


@router.post("", response_model=PointResponse)
async def create_point(
    point_data: PointCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建点位"""
    # 检查编码是否重复
    result = await db.execute(select(Point).where(Point.point_code == point_data.point_code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="点位编码已存在")

    point = Point(**point_data.model_dump())
    db.add(point)
    await db.flush()

    # 创建实时值记录
    realtime = PointRealtime(point_id=point.id)
    db.add(realtime)

    await db.commit()
    await db.refresh(point)
    return point


@router.put("/{point_id}", response_model=PointResponse)
async def update_point(
    point_id: int,
    point_data: PointUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新点位"""
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    for key, value in point_data.model_dump(exclude_unset=True).items():
        setattr(point, key, value)

    await db.commit()
    await db.refresh(point)
    return point


@router.delete("/{point_id}")
async def delete_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除点位"""
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    await db.delete(point)
    await db.commit()
    return {"message": "删除成功"}


@router.put("/{point_id}/enable")
async def enable_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """启用点位"""
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    point.is_enabled = True
    await db.commit()
    return {"message": "启用成功"}


@router.put("/{point_id}/disable")
async def disable_point(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """禁用点位"""
    result = await db.execute(select(Point).where(Point.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    point.is_enabled = False
    await db.commit()
    return {"message": "禁用成功"}
