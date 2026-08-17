"""
阈值配置 API - v1
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import (
    SiteAccessContext,
    apply_point_site_scope,
    get_authorized_point,
    get_db,
    get_site_access_context,
    require_operator,
    require_viewer,
)
from ...models.user import User
from ...models.alarm import AlarmThreshold
from ...models.point import Point
from ...schemas.threshold import (
    ThresholdCreate,
    ThresholdUpdate,
    ThresholdInfo,
    ThresholdBatchCreate,
    FourLevelThresholdCreate,
    BatchByDeviceTypeCreate,
)
from ...schemas.common import PageResponse

_threshold_version = 0
_threshold_version_time = datetime.now()


def _increment_version():
    global _threshold_version, _threshold_version_time
    _threshold_version += 1
    _threshold_version_time = datetime.now()


router = APIRouter()


def _threshold_scope(query, context: SiteAccessContext):
    return apply_point_site_scope(query, AlarmThreshold.point_id, context)


async def _authorized_threshold(db: AsyncSession, threshold_id: int, context: SiteAccessContext) -> AlarmThreshold:
    result = await db.execute(
        _threshold_scope(select(AlarmThreshold).where(AlarmThreshold.id == threshold_id), context)
    )
    threshold = result.scalar_one_or_none()
    if threshold is None:
        raise HTTPException(status_code=404, detail="阈值配置不存在")
    return threshold


async def _authorized_points(db: AsyncSession, point_ids: List[int], context: SiteAccessContext) -> dict[int, Point]:
    requested_ids = set(point_ids)
    if not requested_ids:
        return {}
    query = apply_point_site_scope(select(Point).where(Point.id.in_(requested_ids)), Point.id, context)
    points = (await db.execute(query)).scalars().all()
    point_map = {point.id: point for point in points}
    if set(point_map) != requested_ids:
        raise HTTPException(status_code=404, detail="点位不存在")
    return point_map


@router.get("", response_model=PageResponse[ThresholdInfo], summary="获取阈值配置列表")
async def get_thresholds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    point_id: Optional[int] = Query(None),
    threshold_type: Optional[str] = Query(None),
    is_enabled: Optional[bool] = Query(None),
    device_type: Optional[str] = Query(None, description="设备类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取阈值配置列表
    """
    query = _threshold_scope(select(AlarmThreshold), site_context)

    if point_id:
        await get_authorized_point(db, point_id, site_context)
        query = query.where(AlarmThreshold.point_id == point_id)
    if threshold_type:
        query = query.where(AlarmThreshold.threshold_type == threshold_type)
    if is_enabled is not None:
        query = query.where(AlarmThreshold.is_enabled == is_enabled)
    if device_type:
        query = query.join(Point, AlarmThreshold.point_id == Point.id).where(Point.device_type == device_type)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(AlarmThreshold.point_id, AlarmThreshold.priority.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    thresholds = result.scalars().all()

    # 批量附加点位信息，避免每条阈值单独查询产生 N+1 请求。
    point_ids = {threshold.point_id for threshold in thresholds}
    points = []
    if point_ids:
        point_result = await db.execute(select(Point).where(Point.id.in_(point_ids)))
        points = point_result.scalars().all()
    point_map = {point.id: point for point in points}

    threshold_list = []
    for threshold in thresholds:
        point = point_map.get(threshold.point_id)
        info = ThresholdInfo.model_validate(threshold)
        if point:
            info.point_code = point.point_code
            info.point_name = point.point_name
            info.device_type = point.device_type
        threshold_list.append(info)

    return PageResponse(items=threshold_list, total=total, page=page, page_size=page_size)


@router.get("/point/{point_id}", summary="获取点位阈值配置")
async def get_point_thresholds(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    获取指定点位的所有阈值配置
    """
    await get_authorized_point(db, point_id, site_context)
    result = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == point_id).order_by(AlarmThreshold.priority.desc())
    )
    thresholds = result.scalars().all()

    return [ThresholdInfo.model_validate(t) for t in thresholds]


@router.post("", response_model=ThresholdInfo, summary="创建阈值配置")
async def create_threshold(
    data: ThresholdCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    创建阈值配置
    """
    # 检查点位是否存在
    point = await get_authorized_point(db, data.point_id, site_context)

    threshold = AlarmThreshold(**data.model_dump())
    db.add(threshold)
    await db.commit()
    _increment_version()
    await db.refresh(threshold)

    info = ThresholdInfo.model_validate(threshold)
    info.point_code = point.point_code
    info.point_name = point.point_name

    return info


@router.post("/batch", summary="批量配置阈值")
async def batch_create_thresholds(
    data: ThresholdBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    为多个点位批量创建相同的阈值配置
    """
    point_map = await _authorized_points(db, data.point_ids, site_context)
    for point_id in data.point_ids:
        point = point_map[point_id]
        db.add(
            AlarmThreshold(
                point_id=point_id,
                threshold_type=data.threshold_type,
                threshold_value=data.threshold_value,
                alarm_level=data.alarm_level,
                alarm_message=data.alarm_message or f"{point.point_name} 超过阈值",
                delay_seconds=data.delay_seconds,
                dead_band=data.dead_band,
                is_enabled=True,
            )
        )

    await db.commit()
    _increment_version()

    return {"success_count": len(data.point_ids), "error_count": 0, "errors": []}


@router.post("/copy", summary="复制阈值配置到其他点位")
async def copy_thresholds(
    source_point_id: int,
    target_point_ids: List[int],
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    将一个点位的阈值配置复制到其他点位
    """
    # 获取源点位的阈值配置
    await _authorized_points(db, [source_point_id, *target_point_ids], site_context)
    source_result = await db.execute(
        _threshold_scope(select(AlarmThreshold).where(AlarmThreshold.point_id == source_point_id), site_context)
    )
    source_thresholds = source_result.scalars().all()

    if not source_thresholds:
        raise HTTPException(status_code=404, detail="源点位没有阈值配置")

    success_count = 0
    for target_id in target_point_ids:
        if target_id == source_point_id:
            continue

        # 删除目标点位现有阈值
        await db.execute(delete(AlarmThreshold).where(AlarmThreshold.point_id == target_id))

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
                priority=src.priority,
            )
            db.add(new_threshold)

        success_count += 1

    await db.commit()
    _increment_version()

    return {"message": f"已复制到 {success_count} 个点位"}


async def _upsert_four_level(db: AsyncSession, point, data):
    """为单个点位执行4级阈值upsert"""
    level_mapping = {
        "high_high": {"alarm_level": "critical", "priority": 4},
        "high": {"alarm_level": "major", "priority": 3},
        "low": {"alarm_level": "minor", "priority": 2},
        "low_low": {"alarm_level": "info", "priority": 1},
    }

    for threshold_type, item in [
        ("high_high", data.high_high),
        ("high", data.high),
        ("low", data.low),
        ("low_low", data.low_low),
    ]:
        if item is None:
            continue

        mapping = level_mapping[threshold_type]
        existing = await db.execute(
            select(AlarmThreshold).where(
                AlarmThreshold.point_id == point.id, AlarmThreshold.threshold_type == threshold_type
            )
        )
        threshold = existing.scalar_one_or_none()

        if threshold:
            threshold.threshold_value = item.value
            threshold.alarm_message = item.message or f"{point.point_name} {threshold_type} 告警"
            threshold.is_enabled = item.enabled if item.enabled is not None else True
            threshold.alarm_level = mapping["alarm_level"]
            threshold.priority = mapping["priority"]
            threshold.delay_seconds = data.delay_seconds
            threshold.dead_band = data.dead_band
            threshold.updated_at = datetime.now()
        else:
            new_threshold = AlarmThreshold(
                point_id=point.id,
                threshold_type=threshold_type,
                threshold_value=item.value,
                alarm_level=mapping["alarm_level"],
                alarm_message=item.message or f"{point.point_name} {threshold_type} 告警",
                delay_seconds=data.delay_seconds,
                dead_band=data.dead_band,
                is_enabled=item.enabled if item.enabled is not None else True,
                priority=mapping["priority"],
            )
            db.add(new_threshold)


@router.get("/version", summary="获取阈值配置版本号")
async def get_threshold_version():
    """返回阈值配置版本号，用于告警引擎缓存失效判断"""
    return {"version": _threshold_version, "updated_at": _threshold_version_time.isoformat()}


@router.put("/point/{point_id}/four-level", summary="4级阈值一体化配置")
async def set_four_level_thresholds(
    point_id: int,
    data: FourLevelThresholdCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """为指定点位一次性配置4级告警阈值（高高限/高限/低限/低低限）"""
    point = await get_authorized_point(db, point_id, site_context)

    await _upsert_four_level(db, point, data)
    await db.commit()
    _increment_version()

    all_thresholds = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == point_id).order_by(AlarmThreshold.priority.desc())
    )
    return [ThresholdInfo.model_validate(t) for t in all_thresholds.scalars().all()]


@router.post("/batch-by-device-type", summary="按设备类型批量配置阈值")
async def batch_set_by_device_type(
    data: BatchByDeviceTypeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """为指定设备类型下所有AI点位批量配置4级阈值"""
    points_result = await db.execute(
        apply_point_site_scope(
            select(Point).where(Point.device_type == data.device_type, Point.point_type == "AI"), Point.id, site_context
        )
    )
    points = points_result.scalars().all()

    if not points:
        return {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "total_points": 0,
            "message": f"设备类型 {data.device_type} 下没有 AI 类型点位",
        }

    success_count = 0
    error_list = []

    for point in points:
        try:
            async with db.begin_nested():
                await _upsert_four_level(db, point, data.thresholds)
            success_count += 1
        except Exception as e:
            error_list.append(f"点位 {point.point_code}: {str(e)}")

    await db.commit()
    _increment_version()

    return {
        "success_count": success_count,
        "error_count": len(error_list),
        "errors": error_list,
        "total_points": len(points),
    }


@router.put("/{threshold_id}", response_model=ThresholdInfo, summary="更新阈值配置")
async def update_threshold(
    threshold_id: int,
    data: ThresholdUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    更新阈值配置
    """
    await _authorized_threshold(db, threshold_id, site_context)

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(update(AlarmThreshold).where(AlarmThreshold.id == threshold_id).values(**update_data))
    await db.commit()
    _increment_version()

    result = await db.execute(select(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    threshold = result.scalar_one()

    return ThresholdInfo.model_validate(threshold)


@router.delete("/{threshold_id}", summary="删除阈值配置")
async def delete_threshold(
    threshold_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    site_context: SiteAccessContext = Depends(get_site_access_context),
):
    """
    删除阈值配置
    """
    await _authorized_threshold(db, threshold_id, site_context)

    await db.execute(delete(AlarmThreshold).where(AlarmThreshold.id == threshold_id))
    await db.commit()
    _increment_version()

    return {"message": "阈值配置已删除"}
