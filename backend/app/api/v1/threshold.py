"""
阈值配置 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator
from ...models.user import User
from ...models.alarm import AlarmThreshold
from ...models.point import Point
from ...schemas.threshold import (
    ThresholdCreate, ThresholdUpdate, ThresholdInfo, ThresholdBatchCreate
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[ThresholdInfo], summary="获取阈值配置列表")
async def get_thresholds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    point_id: Optional[int] = Query(None),
    threshold_type: Optional[str] = Query(None),
    is_enabled: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取阈值配置列表
    """
    query = select(AlarmThreshold)

    if point_id:
        query = query.where(AlarmThreshold.point_id == point_id)
    if threshold_type:
        query = query.where(AlarmThreshold.threshold_type == threshold_type)
    if is_enabled is not None:
        query = query.where(AlarmThreshold.is_enabled == is_enabled)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(AlarmThreshold.point_id, AlarmThreshold.priority.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    thresholds = result.scalars().all()

    # 附加点位信息
    threshold_list = []
    for threshold in thresholds:
        point_result = await db.execute(select(Point).where(Point.id == threshold.point_id))
        point = point_result.scalar_one_or_none()
        info = ThresholdInfo.model_validate(threshold)
        if point:
            info.point_code = point.point_code
            info.point_name = point.point_name
        threshold_list.append(info)

    return PageResponse(
        items=threshold_list,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/point/{point_id}", summary="获取点位阈值配置")
async def get_point_thresholds(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取指定点位的所有阈值配置
    """
    result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == point_id).order_by(
            AlarmThreshold.priority.desc()
        )
    )
    thresholds = result.scalars().all()

    return [ThresholdInfo.model_validate(t) for t in thresholds]


@router.post("", response_model=ThresholdInfo, summary="创建阈值配置")
async def create_threshold(
    data: ThresholdCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建阈值配置
    """
    # 检查点位是否存在
    point_result = await db.execute(select(Point).where(Point.id == data.point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    threshold = AlarmThreshold(**data.model_dump())
    db.add(threshold)
    await db.commit()
    await db.refresh(threshold)

    info = ThresholdInfo.model_validate(threshold)
    info.point_code = point.point_code
    info.point_name = point.point_name

    return info


@router.post("/batch", summary="批量配置阈值")
async def batch_create_thresholds(
    data: ThresholdBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    为多个点位批量创建相同的阈值配置
    """
    success_count = 0
    error_list = []

    for point_id in data.point_ids:
        # 检查点位是否存在
        point_result = await db.execute(select(Point).where(Point.id == point_id))
        point = point_result.scalar_one_or_none()

        if not point:
            error_list.append(f"点位 {point_id} 不存在")
            continue

        try:
            threshold = AlarmThreshold(
                point_id=point_id,
                threshold_type=data.threshold_type,
                threshold_value=data.threshold_value,
                alarm_level=data.alarm_level,
                alarm_message=data.alarm_message or f"{point.point_name} 超过阈值",
                delay_seconds=data.delay_seconds,
                dead_band=data.dead_band,
                is_enabled=True
            )
            db.add(threshold)
            success_count += 1
        except Exception as e:
            error_list.append(f"点位 {point_id}: {str(e)}")

    await db.commit()

    return {
        "success_count": success_count,
        "error_count": len(error_list),
        "errors": error_list
    }


@router.post("/copy", summary="复制阈值配置到其他点位")
async def copy_thresholds(
    source_point_id: int,
    target_point_ids: List[int],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    将一个点位的阈值配置复制到其他点位
    """
    # 获取源点位的阈值配置
    source_result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == source_point_id)
    )
    source_thresholds = source_result.scalars().all()

    if not source_thresholds:
        raise HTTPException(status_code=404, detail="源点位没有阈值配置")

    success_count = 0
    for target_id in target_point_ids:
        if target_id == source_point_id:
            continue

        # 检查目标点位是否存在
        point_result = await db.execute(select(Point).where(Point.id == target_id))
        if not point_result.scalar_one_or_none():
            continue

        # 删除目标点位现有阈值
        await db.execute(
            delete(AlarmThreshold).where(AlarmThreshold.point_id == target_id)
        )

        # 复制阈值
        for src in source_thresholds:
            new_threshold = AlarmThreshold(
                point_id=target_id,
                threshold_type=src.threshold_type,
                threshold_value=src.threshold_value,
                alarm_level=src.alarm_level,
                alarm_message=src.alarm_message,
                delay_seconds=src.delay_seconds,
                dead_band=src.dead_band,
                is_enabled=src.is_enabled,
                priority=src.priority
            )
            db.add(new_threshold)

        success_count += 1

    await db.commit()

    return {"message": f"已复制到 {success_count} 个点位"}


@router.put("/{threshold_id}", response_model=ThresholdInfo, summary="更新阈值配置")
async def update_threshold(
    threshold_id: int,
    data: ThresholdUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新阈值配置
    """
    result = await db.execute(select(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    threshold = result.scalar_one_or_none()
    if not threshold:
        raise HTTPException(status_code=404, detail="阈值配置不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(
        update(AlarmThreshold).where(AlarmThreshold.id == threshold_id).values(**update_data)
    )
    await db.commit()

    result = await db.execute(select(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    threshold = result.scalar_one()

    return ThresholdInfo.model_validate(threshold)


@router.delete("/{threshold_id}", summary="删除阈值配置")
async def delete_threshold(
    threshold_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    删除阈值配置
    """
    result = await db.execute(select(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="阈值配置不存在")

    await db.execute(delete(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    await db.commit()

    return {"message": "阈值配置已删除"}
