"""
设备管理 API - v1
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.device import Device
from ...models.point import Point
from ...schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceInfo, DeviceTree, DeviceStatusSummary
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[DeviceInfo], summary="获取设备列表")
async def get_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    area_code: Optional[str] = Query(None, description="区域代码"),
    status: Optional[str] = Query(None, description="状态"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备列表（分页）
    """
    query = select(Device)

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
