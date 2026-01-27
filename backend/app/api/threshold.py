"""
阈值配置路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core import get_db, get_current_user
from ..models import User, Point, AlarmThreshold
from ..schemas import (
    AlarmThresholdCreate, AlarmThresholdUpdate, AlarmThresholdResponse
)

router = APIRouter(prefix="/thresholds", tags=["阈值配置"])


@router.get("", response_model=List[AlarmThresholdResponse])
async def get_thresholds(
    point_id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取阈值配置列表"""
    query = select(AlarmThreshold)
    if point_id:
        query = query.where(AlarmThreshold.point_id == point_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/point/{point_id}", response_model=List[AlarmThresholdResponse])
async def get_point_thresholds(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取点位的阈值配置"""
    result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == point_id)
    )
    return result.scalars().all()


@router.post("", response_model=AlarmThresholdResponse)
async def create_threshold(
    data: AlarmThresholdCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建阈值配置"""
    # 验证点位存在
    result = await db.execute(select(Point).where(Point.id == data.point_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="点位不存在")

    threshold = AlarmThreshold(**data.model_dump())
    db.add(threshold)
    await db.commit()
    await db.refresh(threshold)
    return threshold


@router.put("/{threshold_id}", response_model=AlarmThresholdResponse)
async def update_threshold(
    threshold_id: int,
    data: AlarmThresholdUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新阈值配置"""
    result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.id == threshold_id)
    )
    threshold = result.scalar_one_or_none()

    if not threshold:
        raise HTTPException(status_code=404, detail="阈值配置不存在")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(threshold, key, value)

    await db.commit()
    await db.refresh(threshold)
    return threshold


@router.delete("/{threshold_id}")
async def delete_threshold(
    threshold_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除阈值配置"""
    result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.id == threshold_id)
    )
    threshold = result.scalar_one_or_none()

    if not threshold:
        raise HTTPException(status_code=404, detail="阈值配置不存在")

    await db.delete(threshold)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/batch")
async def batch_create_thresholds(
    data: List[AlarmThresholdCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量创建阈值配置"""
    created = []
    for item in data:
        threshold = AlarmThreshold(**item.model_dump())
        db.add(threshold)
        created.append(threshold)

    await db.commit()
    return {"message": f"成功创建 {len(created)} 条阈值配置"}
