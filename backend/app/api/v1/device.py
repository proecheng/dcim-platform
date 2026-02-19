"""
设备管理 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator, require_admin, get_user_site_ids
from ...models.user import User
from ...models.device import Device
from ...models.point import Point, PointRealtime
from ...models.alarm import Alarm
from ...schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceInfo, DeviceTree, DeviceStatusSummary
)
from ...schemas.common import PageResponse
from ...core.redis import redis_service

router = APIRouter()


@router.get("", response_model=PageResponse[DeviceInfo], summary="获取设备列表")
async def get_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    area_code: Optional[str] = Query(None, description="区域代码"),
    status: Optional[str] = Query(None, description="状态"),
    site_id: Optional[int] = Query(None, description="站点ID"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    user_site_ids: Optional[List[int]] = Depends(get_user_site_ids)
):
    """
    获取设备列表（分页），按用户站点权限过滤
    """
    query = select(Device)

    # 站点权限过滤（非 admin 用户仅可见授权站点设备）
    if user_site_ids is not None:
        query = query.where(Device.site_id.in_(user_site_ids))

    # 手动站点筛选
    if site_id is not None:
        query = query.where(Device.site_id == site_id)

    if keyword:
        query = query.where(
            (Device.device_code.contains(keyword)) |
            (Device.device_name.contains(keyword))
        )
    if device_type:
        query = query.where(Device.device_type == device_type)
    if area_code:
        query = query.where(Device.area_code == area_code)
    if status:
        query = query.where(Device.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Device.area_code, Device.device_code)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    devices = result.scalars().all()

    return PageResponse(
        items=[DeviceInfo.model_validate(d) for d in devices],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/tree", summary="获取设备树结构")
async def get_device_tree(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备树结构（按区域-设备类型-设备）
    """
    result = await db.execute(
        select(Device).where(Device.is_enabled == True).order_by(Device.area_code, Device.device_type)
    )
    devices = result.scalars().all()

    # 构建树结构
    tree = {}
    for device in devices:
        area = device.area_code
        dtype = device.device_type

        if area not in tree:
            tree[area] = {"label": f"{area}区", "children": {}}
        if dtype not in tree[area]["children"]:
            tree[area]["children"][dtype] = {"label": dtype, "children": []}

        tree[area]["children"][dtype]["children"].append({
            "id": device.id,
            "label": device.device_name,
            "code": device.device_code,
            "status": device.status
        })

    # 转换为列表格式
    result_tree = []
    for area_code, area_data in tree.items():
        area_node = {
            "label": area_data["label"],
            "children": []
        }
        for dtype, type_data in area_data["children"].items():
            type_node = {
                "label": type_data["label"],
                "children": type_data["children"]
            }
            area_node["children"].append(type_node)
        result_tree.append(area_node)

    return result_tree


@router.get("/status-summary", response_model=DeviceStatusSummary, summary="获取设备状态汇总")
async def get_status_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备状态汇总统计
    """
    # 总数和启用数
    total_result = await db.execute(select(func.count(Device.id)))
    total = total_result.scalar()

    enabled_result = await db.execute(
        select(func.count(Device.id)).where(Device.is_enabled == True)
    )
    enabled = enabled_result.scalar()

    # 按状态统计
    status_result = await db.execute(
        select(Device.status, func.count(Device.id)).group_by(Device.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    # 按类型统计
    type_result = await db.execute(
        select(Device.device_type, func.count(Device.id)).group_by(Device.device_type)
    )
    type_counts = {row[0]: row[1] for row in type_result.all()}

    return DeviceStatusSummary(
        total=total,
        enabled=enabled,
        online=status_counts.get("online", 0),
        offline=status_counts.get("offline", 0),
        alarm=status_counts.get("alarm", 0),
        maintenance=status_counts.get("maintenance", 0),
        by_type=type_counts
    )


@router.get("/status-board", summary="获取设备状态看板")
async def get_status_board(
    area_code: Optional[str] = Query(None, description="区域代码"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备状态看板 — 按区域和设备类型分组，Redis 判断在线状态
    """
    query = select(Device).where(Device.is_enabled == True)
    if area_code:
        query = query.where(Device.area_code == area_code)
    if device_type:
        query = query.where(Device.device_type == device_type)

    result = await db.execute(query.order_by(Device.area_code, Device.device_type))
    devices = result.scalars().all()

    # 批量检查 Redis 在线状态
    online_map: dict = {}
    if redis_service.is_available and devices:
        try:
            keys = [f"device:{d.id}:online" for d in devices]
            values = await redis_service.mget(keys)
            for i, d in enumerate(devices):
                online_map[d.id] = values[i] is not None if i < len(values) else False
        except Exception:
            pass

    # 分组统计
    groups: dict = {}
    summary = {"total": 0, "online": 0, "offline": 0, "alarm": 0, "maintenance": 0}
    for d in devices:
        if d.id in online_map:
            effective_status = "online" if online_map[d.id] else d.status
        else:
            effective_status = d.status

        summary["total"] += 1
        summary[effective_status] = summary.get(effective_status, 0) + 1

        key = f"{d.area_code}_{d.device_type}"
        if key not in groups:
            groups[key] = {
                "area_code": d.area_code,
                "device_type": d.device_type,
                "devices": [],
                "stats": {"online": 0, "offline": 0, "alarm": 0, "maintenance": 0}
            }
        groups[key]["devices"].append({
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "status": effective_status,
        })
        groups[key]["stats"][effective_status] = groups[key]["stats"].get(effective_status, 0) + 1

    return {
        "summary": summary,
        "groups": list(groups.values())
    }


@router.get("/{device_id}", response_model=DeviceInfo, summary="获取设备详情")
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备详情
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    return DeviceInfo.model_validate(device)


@router.get("/{device_id}/points", summary="获取设备下的点位")
async def get_device_points(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备关联的所有点位
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    points_result = await db.execute(
        select(Point).where(Point.device_id == device_id).order_by(Point.point_code)
    )
    points = points_result.scalars().all()

    return {
        "device": DeviceInfo.model_validate(device),
        "points": [{"id": p.id, "code": p.point_code, "name": p.point_name, "type": p.point_type} for p in points]
    }


@router.get("/{device_id}/detail", summary="获取设备详情（聚合）")
async def get_device_detail(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备详情：基本信息 + 关联点位实时数据 + 当前活动告警
    """
    # 1. 设备基本信息
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 2. 关联点位 + 实时数据
    points_result = await db.execute(
        select(Point, PointRealtime).outerjoin(
            PointRealtime, Point.id == PointRealtime.point_id
        ).where(Point.device_id == device_id).order_by(Point.point_code)
    )
    points_data = []
    point_ids = []
    for point, realtime in points_result.all():
        point_ids.append(point.id)
        points_data.append({
            "id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "point_type": point.point_type,
            "device_type": point.device_type,
            "unit": point.unit,
            "value": realtime.value if realtime else None,
            "value_text": realtime.value_text if realtime else None,
            "status": realtime.status if realtime else "offline",
            "alarm_level": realtime.alarm_level if realtime else None,
            "quality": realtime.quality if realtime else None,
            "updated_at": realtime.updated_at.isoformat() if realtime and realtime.updated_at else None,
        })

    # 3. 当前活动告警（通过点位 ID 关联）
    alarms_data = []
    if point_ids:
        alarms_result = await db.execute(
            select(Alarm).where(
                Alarm.point_id.in_(point_ids),
                Alarm.status.in_(["active", "acknowledged"])
            ).order_by(Alarm.created_at.desc())
        )
        for alarm in alarms_result.scalars().all():
            alarms_data.append({
                "id": alarm.id,
                "alarm_no": alarm.alarm_no,
                "point_id": alarm.point_id,
                "alarm_level": alarm.alarm_level,
                "alarm_message": alarm.alarm_message,
                "trigger_value": alarm.trigger_value,
                "threshold_value": alarm.threshold_value,
                "status": alarm.status,
                "created_at": alarm.created_at.isoformat() if alarm.created_at else None,
            })

    return {
        "device": DeviceInfo.model_validate(device),
        "points": points_data,
        "alarms": alarms_data,
    }


@router.post("", response_model=DeviceInfo, summary="创建设备")
async def create_device(
    data: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    创建新设备
    """
    # 检查设备编码唯一性
    result = await db.execute(select(Device).where(Device.device_code == data.device_code))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="设备编码已存在")

    device = Device(**data.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)

    return DeviceInfo.model_validate(device)


@router.put("/{device_id}", response_model=DeviceInfo, summary="更新设备")
async def update_device(
    device_id: int,
    data: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    更新设备信息
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()

    await db.execute(update(Device).where(Device.id == device_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one()

    return DeviceInfo.model_validate(device)


@router.delete("/{device_id}", summary="删除设备")
async def delete_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    删除设备（同时删除关联点位）
    """
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 检查是否有关联点位
    point_count_result = await db.execute(
        select(func.count(Point.id)).where(Point.device_id == device_id)
    )
    point_count = point_count_result.scalar()

    if point_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"设备下有 {point_count} 个点位，请先删除点位"
        )

    await db.execute(delete(Device).where(Device.id == device_id))
    await db.commit()

    return {"message": "设备已删除"}
