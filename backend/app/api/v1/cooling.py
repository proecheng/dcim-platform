"""
制冷系统 API - 精密空调、群控组、冷通道
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...schemas.cooling import (
    CoolingUnitCreate,
    CoolingUnitUpdate,
    CoolingUnitInfo,
    CoolingUnitDetail,
    CoolingGroupCreate,
    CoolingGroupUpdate,
    CoolingGroupInfo,
    ColdAisleCreate,
    ColdAisleUpdate,
    ColdAisleInfo,
    ColdAisleDetail,
    CoolingOverviewSummary,
)
from ...schemas.common import PageResponse

router = APIRouter()


# ==================== Overview ====================


@router.get("/overview", response_model=CoolingOverviewSummary, summary="制冷系统总览")
async def get_cooling_overview(db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取制冷系统总览统计
    """
    from ...models.device import Device
    from ...models.cooling import CoolingGroup, ColdAisle
    from ...models.point import PointRealtime, Point

    # 空调统计
    ac_result = await db.execute(
        select(Device.status, func.count(Device.id))
        .where(Device.device_type.in_(["AC", "PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR"]))
        .group_by(Device.status)
    )
    ac_stats = {row[0]: row[1] for row in ac_result.all()}
    ac_total = sum(ac_stats.values())
    ac_running = ac_stats.get("running", 0)
    ac_stopped = ac_stats.get("stopped", 0)
    ac_alarm = ac_stats.get("alarm", 0)

    # 平均送风/回风温度
    supply_temp_result = await db.execute(
        select(PointRealtime.value)
        .join(Point, PointRealtime.point_id == Point.id)
        .where(Point.point_code.like("%supply_temp%"))
    )
    supply_temps = [row[0] for row in supply_temp_result.all() if row[0] is not None]
    avg_supply_temp = sum(supply_temps) / len(supply_temps) if supply_temps else 0.0

    return_temp_result = await db.execute(
        select(PointRealtime.value)
        .join(Point, PointRealtime.point_id == Point.id)
        .where(Point.point_code.like("%return_temp%"))
    )
    return_temps = [row[0] for row in return_temp_result.all() if row[0] is not None]
    avg_return_temp = sum(return_temps) / len(return_temps) if return_temps else 0.0

    # 冷通道统计
    cold_aisle_count = await db.execute(select(func.count()).select_from(ColdAisle))
    cold_aisle_total = cold_aisle_count.scalar()

    # 群控组统计
    group_result = await db.execute(
        select(CoolingGroup.group_mode, func.count(CoolingGroup.id)).group_by(CoolingGroup.group_mode)
    )
    group_stats = {row[0]: row[1] for row in group_result.all()}
    group_total = sum(group_stats.values())
    group_linked = group_stats.get("linked", 0)

    return CoolingOverviewSummary(
        ac_total=ac_total,
        ac_running=ac_running,
        ac_stopped=ac_stopped,
        ac_alarm=ac_alarm,
        avg_supply_temp=round(avg_supply_temp, 2),
        avg_return_temp=round(avg_return_temp, 2),
        cold_aisle_total=cold_aisle_total,
        group_total=group_total,
        group_linked=group_linked,
    )


# ==================== CoolingUnit CRUD ====================


@router.get("/units", response_model=PageResponse[CoolingUnitInfo], summary="获取空调列表")
async def get_cooling_units(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unit_type: Optional[str] = Query(None, description="类型: indoor/outdoor"),
    group_id: Optional[int] = Query(None, description="群控组ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取精密空调列表（分页、筛选）
    """
    from ...models.cooling import CoolingUnit, CoolingGroup
    from ...models.device import Device

    query = (
        select(CoolingUnit, Device, CoolingGroup)
        .join(Device, CoolingUnit.device_id == Device.id)
        .outerjoin(CoolingGroup, CoolingUnit.group_id == CoolingGroup.id)
        .where(Device.device_type.in_(["AC", "PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR"]))
    )

    if unit_type:
        query = query.where(CoolingUnit.unit_type == unit_type)
    if group_id:
        query = query.where(CoolingUnit.group_id == group_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(CoolingUnit.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    unit_list = []
    for unit, device, group in rows:
        unit_info = CoolingUnitInfo.model_validate(unit)
        unit_info.device_code = device.device_code
        unit_info.device_name = device.device_name
        unit_info.device_status = device.status
        unit_info.group_name = group.group_name if group else None
        unit_list.append(unit_info)

    return PageResponse(items=unit_list, total=total, page=page, page_size=page_size)


@router.get("/units/{unit_id}", response_model=CoolingUnitDetail, summary="获取空调详情")
async def get_cooling_unit(unit_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取精密空调详情（含关联设备信息和点位实时值）
    """
    from ...models.cooling import CoolingUnit, CoolingGroup
    from ...models.device import Device
    from ...models.point import Point, PointRealtime

    result = await db.execute(
        select(CoolingUnit, Device, CoolingGroup)
        .join(Device, CoolingUnit.device_id == Device.id)
        .outerjoin(CoolingGroup, CoolingUnit.group_id == CoolingGroup.id)
        .where(CoolingUnit.id == unit_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="空调不存在")

    unit, device, group = row
    unit_info = CoolingUnitInfo.model_validate(unit)
    unit_info.device_code = device.device_code
    unit_info.device_name = device.device_name
    unit_info.device_status = device.status
    unit_info.group_name = group.group_name if group else None

    # 查询关联点位实时值
    points_result = await db.execute(
        select(Point, PointRealtime)
        .outerjoin(PointRealtime, Point.id == PointRealtime.point_id)
        .where(Point.device_id == unit.device_id)
    )
    points = []
    for point, realtime in points_result.all():
        point_data = {
            "id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "value": realtime.value if realtime else None,
            "status": realtime.status if realtime else None,
            "updated_at": realtime.updated_at.isoformat() if realtime and realtime.updated_at else None,
        }
        points.append(point_data)

    return CoolingUnitDetail(
        unit=unit_info,
        device={
            "id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "status": device.status,
        },
        points=points,
    )


@router.post("/units", response_model=CoolingUnitInfo, summary="创建空调")
async def create_cooling_unit(
    data: CoolingUnitCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建精密空调扩展记录
    """
    from ...models.cooling import CoolingUnit
    from ...models.device import Device

    # 验证设备是否存在
    device_result = await db.execute(select(Device).where(Device.id == data.device_id))
    device = device_result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    unit = CoolingUnit(**data.model_dump())
    db.add(unit)
    await db.commit()
    await db.refresh(unit)

    unit_info = CoolingUnitInfo.model_validate(unit)
    unit_info.device_code = device.device_code
    unit_info.device_name = device.device_name
    unit_info.device_status = device.status

    return unit_info


@router.put("/units/{unit_id}", response_model=CoolingUnitInfo, summary="更新空调")
async def update_cooling_unit(
    unit_id: int, data: CoolingUnitUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    更新精密空调扩展记录
    """
    from ...models.cooling import CoolingUnit, CoolingGroup
    from ...models.device import Device

    result = await db.execute(select(CoolingUnit).where(CoolingUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="空调不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(unit, key, value)
    unit.updated_at = datetime.now()

    await db.commit()
    await db.refresh(unit)

    # 获取关联信息
    device_result = await db.execute(select(Device).where(Device.id == unit.device_id))
    device = device_result.scalar_one()
    group_result = await db.execute(select(CoolingGroup).where(CoolingGroup.id == unit.group_id))
    group = group_result.scalar_one_or_none()

    unit_info = CoolingUnitInfo.model_validate(unit)
    unit_info.device_code = device.device_code
    unit_info.device_name = device.device_name
    unit_info.device_status = device.status
    unit_info.group_name = group.group_name if group else None

    return unit_info


@router.delete("/units/{unit_id}", summary="删除空调")
async def delete_cooling_unit(unit_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    删除精密空调扩展记录
    """
    from ...models.cooling import CoolingUnit

    result = await db.execute(select(CoolingUnit).where(CoolingUnit.id == unit_id))
    unit = result.scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="空调不存在")

    await db.delete(unit)
    await db.commit()

    return {"message": "空调已删除"}


# ==================== CoolingGroup CRUD ====================


@router.get("/groups", response_model=PageResponse[CoolingGroupInfo], summary="获取群控组列表")
async def get_cooling_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取空调群控组列表
    """
    from ...models.cooling import CoolingGroup

    count_query = select(func.count()).select_from(CoolingGroup)
    total = (await db.execute(count_query)).scalar()

    query = select(CoolingGroup).order_by(CoolingGroup.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    groups = result.scalars().all()

    return PageResponse(
        items=[CoolingGroupInfo.model_validate(g) for g in groups], total=total, page=page, page_size=page_size
    )


@router.get("/groups/{group_id}", response_model=CoolingGroupInfo, summary="获取群控组详情")
async def get_cooling_group(group_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取群控组详情
    """
    from ...models.cooling import CoolingGroup

    result = await db.execute(select(CoolingGroup).where(CoolingGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群控组不存在")

    return CoolingGroupInfo.model_validate(group)


@router.post("/groups", response_model=CoolingGroupInfo, summary="创建群控组")
async def create_cooling_group(
    data: CoolingGroupCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建空调群控组
    """
    from ...models.cooling import CoolingGroup

    group = CoolingGroup(**data.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)

    return CoolingGroupInfo.model_validate(group)


@router.put("/groups/{group_id}", response_model=CoolingGroupInfo, summary="更新群控组")
async def update_cooling_group(
    group_id: int, data: CoolingGroupUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    更新空调群控组
    """
    from ...models.cooling import CoolingGroup

    result = await db.execute(select(CoolingGroup).where(CoolingGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群控组不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    group.updated_at = datetime.now()

    await db.commit()
    await db.refresh(group)

    return CoolingGroupInfo.model_validate(group)


@router.delete("/groups/{group_id}", summary="删除群控组")
async def delete_cooling_group(group_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    删除空调群控组（检查是否有关联空调）
    """
    from ...models.cooling import CoolingGroup, CoolingUnit

    # 检查是否有关联空调
    unit_count = await db.execute(select(func.count()).where(CoolingUnit.group_id == group_id))
    if unit_count.scalar() > 0:
        raise HTTPException(status_code=400, detail="群控组下有关联空调，无法删除")

    result = await db.execute(select(CoolingGroup).where(CoolingGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="群控组不存在")

    await db.delete(group)
    await db.commit()

    return {"message": "群控组已删除"}


# ==================== ColdAisle CRUD ====================


@router.get("/cold-aisles", response_model=PageResponse[ColdAisleInfo], summary="获取冷通道列表")
async def get_cold_aisles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """
    获取冷通道列表
    """
    from ...models.cooling import ColdAisle
    from ...models.device import Device

    query = select(ColdAisle, Device).join(Device, ColdAisle.device_id == Device.id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(ColdAisle.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    aisle_list = []
    for aisle, device in rows:
        aisle_info = ColdAisleInfo.model_validate(aisle)
        aisle_info.device_code = device.device_code
        aisle_info.device_name = device.device_name
        aisle_info.device_status = device.status
        aisle_list.append(aisle_info)

    return PageResponse(items=aisle_list, total=total, page=page, page_size=page_size)


@router.get("/cold-aisles/{aisle_id}", response_model=ColdAisleDetail, summary="获取冷通道详情")
async def get_cold_aisle(aisle_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_viewer)):
    """
    获取冷通道详情（含关联设备信息和点位实时值）
    """
    from ...models.cooling import ColdAisle
    from ...models.device import Device
    from ...models.point import Point, PointRealtime

    result = await db.execute(
        select(ColdAisle, Device).join(Device, ColdAisle.device_id == Device.id).where(ColdAisle.id == aisle_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="冷通道不存在")

    aisle, device = row
    aisle_info = ColdAisleInfo.model_validate(aisle)
    aisle_info.device_code = device.device_code
    aisle_info.device_name = device.device_name
    aisle_info.device_status = device.status

    # 查询关联点位实时值
    points_result = await db.execute(
        select(Point, PointRealtime)
        .outerjoin(PointRealtime, Point.id == PointRealtime.point_id)
        .where(Point.device_id == aisle.device_id)
    )
    points = []
    for point, realtime in points_result.all():
        point_data = {
            "id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "value": realtime.value if realtime else None,
            "status": realtime.status if realtime else None,
            "updated_at": realtime.updated_at.isoformat() if realtime and realtime.updated_at else None,
        }
        points.append(point_data)

    return ColdAisleDetail(
        aisle=aisle_info,
        device={
            "id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "status": device.status,
        },
        points=points,
    )


@router.post("/cold-aisles", response_model=ColdAisleInfo, summary="创建冷通道")
async def create_cold_aisle(
    data: ColdAisleCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    创建冷通道
    """
    from ...models.cooling import ColdAisle
    from ...models.device import Device

    # 验证设备是否存在
    device_result = await db.execute(select(Device).where(Device.id == data.device_id))
    device = device_result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    aisle = ColdAisle(**data.model_dump())
    db.add(aisle)
    await db.commit()
    await db.refresh(aisle)

    aisle_info = ColdAisleInfo.model_validate(aisle)
    aisle_info.device_code = device.device_code
    aisle_info.device_name = device.device_name
    aisle_info.device_status = device.status

    return aisle_info


@router.put("/cold-aisles/{aisle_id}", response_model=ColdAisleInfo, summary="更新冷通道")
async def update_cold_aisle(
    aisle_id: int, data: ColdAisleUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(require_operator)
):
    """
    更新冷通道
    """
    from ...models.cooling import ColdAisle
    from ...models.device import Device

    result = await db.execute(select(ColdAisle).where(ColdAisle.id == aisle_id))
    aisle = result.scalar_one_or_none()
    if not aisle:
        raise HTTPException(status_code=404, detail="冷通道不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(aisle, key, value)
    aisle.updated_at = datetime.now()

    await db.commit()
    await db.refresh(aisle)

    # 获取关联信息
    device_result = await db.execute(select(Device).where(Device.id == aisle.device_id))
    device = device_result.scalar_one()

    aisle_info = ColdAisleInfo.model_validate(aisle)
    aisle_info.device_code = device.device_code
    aisle_info.device_name = device.device_name
    aisle_info.device_status = device.status

    return aisle_info


@router.delete("/cold-aisles/{aisle_id}", summary="删除冷通道")
async def delete_cold_aisle(aisle_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(require_admin)):
    """
    删除冷通道
    """
    from ...models.cooling import ColdAisle

    result = await db.execute(select(ColdAisle).where(ColdAisle.id == aisle_id))
    aisle = result.scalar_one_or_none()
    if not aisle:
        raise HTTPException(status_code=404, detail="冷通道不存在")

    await db.delete(aisle)
    await db.commit()

    return {"message": "冷通道已删除"}
