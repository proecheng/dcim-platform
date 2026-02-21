"""
供配电管理 API - v1
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.device import Device
from ...models.point import Point, PointRealtime
from ...models.power import UPSDevice, BatteryGroup
from ...schemas.power import (
    UPSDeviceCreate,
    UPSDeviceUpdate,
    UPSDeviceInfo,
    BatteryGroupCreate,
    BatteryGroupUpdate,
    BatteryGroupInfo,
    PowerOverviewSummary,
)
from ...schemas.device import DeviceInfo
from ...schemas.common import PageResponse

router = APIRouter()


# ==================== 供配电总览 ====================


@router.get("/overview", response_model=PowerOverviewSummary, summary="供配电总览")
async def get_power_overview(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取供配电系统总览统计"""
    # UPS统计
    ups_total_r = await db.execute(select(func.count(Device.id)).where(Device.device_type == "UPS"))
    ups_total = ups_total_r.scalar() or 0

    ups_online_r = await db.execute(
        select(func.count(Device.id)).where(Device.device_type == "UPS", Device.status == "online")
    )
    ups_online = ups_online_r.scalar() or 0

    ups_offline_r = await db.execute(
        select(func.count(Device.id)).where(Device.device_type == "UPS", Device.status == "offline")
    )
    ups_offline = ups_offline_r.scalar() or 0

    ups_alarm_r = await db.execute(
        select(func.count(Device.id)).where(Device.device_type == "UPS", Device.status == "alarm")
    )
    ups_alarm = ups_alarm_r.scalar() or 0

    # 电池组统计
    battery_total_r = await db.execute(select(func.count(BatteryGroup.id)))
    battery_total = battery_total_r.scalar() or 0

    # 电池SOH/SOC — 从关联点位实时值获取
    battery_avg_soh = 0.0
    battery_lowest_soc = 0.0

    soh_r = await db.execute(
        select(func.avg(PointRealtime.value))
        .select_from(PointRealtime.__table__.join(Point.__table__, PointRealtime.point_id == Point.id))
        .where(Point.point_code.like("%_soh"))
    )
    soh_val = soh_r.scalar()
    if soh_val is not None:
        battery_avg_soh = round(float(soh_val), 1)

    soc_r = await db.execute(
        select(func.min(PointRealtime.value))
        .select_from(PointRealtime.__table__.join(Point.__table__, PointRealtime.point_id == Point.id))
        .where(Point.point_code.like("%_soc"))
    )
    soc_val = soc_r.scalar()
    if soc_val is not None:
        battery_lowest_soc = round(float(soc_val), 1)

    # 配电柜 / PDU 统计
    cabinet_total_r = await db.execute(select(func.count(Device.id)).where(Device.device_type == "CABINET"))
    cabinet_total = cabinet_total_r.scalar() or 0

    pdu_total_r = await db.execute(select(func.count(Device.id)).where(Device.device_type == "PDU"))
    pdu_total = pdu_total_r.scalar() or 0

    # 总负载 / 平均负载率 — 从UPS负载率点位获取
    load_r = await db.execute(
        select(
            func.sum(PointRealtime.value),
            func.avg(PointRealtime.value),
        )
        .select_from(PointRealtime.__table__.join(Point.__table__, PointRealtime.point_id == Point.id))
        .where(Point.point_code.like("%_load_rate"))
    )
    load_row = load_r.first()
    total_load_kw = 0.0
    avg_load_rate = 0.0
    if load_row and load_row[1] is not None:
        avg_load_rate = round(float(load_row[1]), 1)

    # total_load_kw 从 total_power 点位获取
    power_r = await db.execute(
        select(func.sum(PointRealtime.value))
        .select_from(PointRealtime.__table__.join(Point.__table__, PointRealtime.point_id == Point.id))
        .where(Point.point_code.like("%_total_power"))
    )
    power_val = power_r.scalar()
    if power_val is not None:
        total_load_kw = round(float(power_val), 1)

    return PowerOverviewSummary(
        ups_total=ups_total,
        ups_online=ups_online,
        ups_offline=ups_offline,
        ups_alarm=ups_alarm,
        battery_total=battery_total,
        battery_avg_soh=battery_avg_soh,
        battery_lowest_soc=battery_lowest_soc,
        cabinet_total=cabinet_total,
        pdu_total=pdu_total,
        total_load_kw=total_load_kw,
        avg_load_rate=avg_load_rate,
    )


# ==================== UPS设备 CRUD ====================


@router.get("/ups", response_model=PageResponse[UPSDeviceInfo], summary="UPS设备列表")
async def list_ups_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ups_type: Optional[str] = Query(None, description="UPS类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取UPS设备列表（分页）"""
    query = select(UPSDevice)
    if ups_type:
        query = query.where(UPSDevice.ups_type == ups_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(UPSDevice.id)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[UPSDeviceInfo.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/ups/{ups_id}", summary="UPS设备详情")
async def get_ups_device(
    ups_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取UPS设备详情，含关联点位实时值"""
    result = await db.execute(select(UPSDevice).where(UPSDevice.id == ups_id))
    ups = result.scalar_one_or_none()
    if not ups:
        raise HTTPException(status_code=404, detail="UPS设备不存在")

    # 获取关联Device
    dev_r = await db.execute(select(Device).where(Device.id == ups.device_id))
    device = dev_r.scalar_one_or_none()

    # 获取关联点位及实时值
    points_r = await db.execute(
        select(Point, PointRealtime)
        .outerjoin(PointRealtime, PointRealtime.point_id == Point.id)
        .where(Point.device_id == ups.device_id)
        .order_by(Point.sort_order)
    )
    points_data = []
    for p, pr in points_r.all():
        points_data.append(
            {
                "id": p.id,
                "code": p.point_code,
                "name": p.point_name,
                "type": p.point_type,
                "unit": p.unit,
                "value": pr.value if pr else None,
                "status": pr.status if pr else "offline",
                "updated_at": pr.updated_at.isoformat() if pr and pr.updated_at else None,
            }
        )

    return {
        "ups": UPSDeviceInfo.model_validate(ups),
        "device": DeviceInfo.model_validate(device) if device else None,
        "points": points_data,
    }


@router.post("/ups", response_model=UPSDeviceInfo, summary="创建UPS设备")
async def create_ups_device(
    data: UPSDeviceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """创建UPS设备扩展记录"""
    # 校验device_id存在且类型为UPS
    dev_r = await db.execute(select(Device).where(Device.id == data.device_id))
    device = dev_r.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=400, detail="关联设备不存在")

    # 检查是否已有UPS扩展记录
    exist_r = await db.execute(select(UPSDevice).where(UPSDevice.device_id == data.device_id))
    if exist_r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该设备已有UPS扩展记录")

    ups = UPSDevice(**data.model_dump())
    db.add(ups)
    await db.commit()
    await db.refresh(ups)
    return UPSDeviceInfo.model_validate(ups)


@router.put("/ups/{ups_id}", response_model=UPSDeviceInfo, summary="更新UPS设备")
async def update_ups_device(
    ups_id: int,
    data: UPSDeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """更新UPS设备扩展记录"""
    result = await db.execute(select(UPSDevice).where(UPSDevice.id == ups_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="UPS设备不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(UPSDevice).where(UPSDevice.id == ups_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(UPSDevice).where(UPSDevice.id == ups_id))
    return UPSDeviceInfo.model_validate(result.scalar_one())


@router.delete("/ups/{ups_id}", summary="删除UPS设备")
async def delete_ups_device(
    ups_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除UPS设备扩展记录"""
    result = await db.execute(select(UPSDevice).where(UPSDevice.id == ups_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="UPS设备不存在")

    # 先删除关联电池组
    await db.execute(delete(BatteryGroup).where(BatteryGroup.ups_device_id == ups_id))
    await db.execute(delete(UPSDevice).where(UPSDevice.id == ups_id))
    await db.commit()
    return {"message": "UPS设备已删除"}


# ==================== 电池组 CRUD ====================


@router.get("/batteries", response_model=PageResponse[BatteryGroupInfo], summary="电池组列表")
async def list_battery_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ups_device_id: Optional[int] = Query(None, description="关联UPS设备ID"),
    battery_type: Optional[str] = Query(None, description="电池类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取电池组列表（分页）"""
    query = select(BatteryGroup)
    if ups_device_id is not None:
        query = query.where(BatteryGroup.ups_device_id == ups_device_id)
    if battery_type:
        query = query.where(BatteryGroup.battery_type == battery_type)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(BatteryGroup.id)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[BatteryGroupInfo.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/batteries/{bg_id}", summary="电池组详情")
async def get_battery_group(
    bg_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取电池组详情，含关联点位实时值"""
    result = await db.execute(select(BatteryGroup).where(BatteryGroup.id == bg_id))
    bg = result.scalar_one_or_none()
    if not bg:
        raise HTTPException(status_code=404, detail="电池组不存在")

    # 获取关联UPS的device_id，再查点位
    ups_r = await db.execute(select(UPSDevice).where(UPSDevice.id == bg.ups_device_id))
    ups = ups_r.scalar_one_or_none()

    points_data = []
    if ups:
        # 查找该UPS设备下以电池组名称前缀匹配的点位
        group_prefix = (bg.group_name or "").replace(" ", "")
        points_r = await db.execute(
            select(Point, PointRealtime)
            .outerjoin(PointRealtime, PointRealtime.point_id == Point.id)
            .where(
                Point.device_id == ups.device_id,
                Point.point_code.like(f"%{group_prefix}%"),
            )
            .order_by(Point.sort_order)
        )
        for p, pr in points_r.all():
            points_data.append(
                {
                    "id": p.id,
                    "code": p.point_code,
                    "name": p.point_name,
                    "type": p.point_type,
                    "unit": p.unit,
                    "value": pr.value if pr else None,
                    "status": pr.status if pr else "offline",
                }
            )

    return {
        "battery_group": BatteryGroupInfo.model_validate(bg),
        "points": points_data,
    }


@router.post("/batteries", response_model=BatteryGroupInfo, summary="创建电池组")
async def create_battery_group(
    data: BatteryGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """创建电池组"""
    # 校验UPS设备存在
    ups_r = await db.execute(select(UPSDevice).where(UPSDevice.id == data.ups_device_id))
    if not ups_r.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="关联UPS设备不存在")

    bg = BatteryGroup(**data.model_dump())
    db.add(bg)
    await db.commit()
    await db.refresh(bg)
    return BatteryGroupInfo.model_validate(bg)


@router.put("/batteries/{bg_id}", response_model=BatteryGroupInfo, summary="更新电池组")
async def update_battery_group(
    bg_id: int,
    data: BatteryGroupUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """更新电池组"""
    result = await db.execute(select(BatteryGroup).where(BatteryGroup.id == bg_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="电池组不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(BatteryGroup).where(BatteryGroup.id == bg_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(BatteryGroup).where(BatteryGroup.id == bg_id))
    return BatteryGroupInfo.model_validate(result.scalar_one())


@router.delete("/batteries/{bg_id}", summary="删除电池组")
async def delete_battery_group(
    bg_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除电池组"""
    result = await db.execute(select(BatteryGroup).where(BatteryGroup.id == bg_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="电池组不存在")

    await db.execute(delete(BatteryGroup).where(BatteryGroup.id == bg_id))
    await db.commit()
    return {"message": "电池组已删除"}


# ==================== 配电柜 / PDU ====================


@router.get("/cabinets", summary="配电柜列表")
async def list_cabinets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取配电柜列表（device_type=CABINET），含聚合点位数据"""
    query = select(Device).where(Device.device_type == "CABINET")

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Device.device_code)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    devices = result.scalars().all()

    items = []
    for dev in devices:
        # 获取该设备的点位实时值
        pr = await db.execute(
            select(Point.point_code, Point.point_name, Point.unit, PointRealtime.value)
            .outerjoin(PointRealtime, PointRealtime.point_id == Point.id)
            .where(Point.device_id == dev.id)
        )
        point_values = {row[0]: {"name": row[1], "unit": row[2], "value": row[3]} for row in pr.all()}
        items.append(
            {
                "device": DeviceInfo.model_validate(dev),
                "points": point_values,
            }
        )

    return PageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cabinets/{device_id}/branches", summary="配电柜支路详情")
async def get_cabinet_branches(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取配电柜的支路/回路信息（从 distribution_circuits 表查询）"""
    from ...models.energy import DistributionPanel, DistributionCircuit

    # 通过 device_id 找到对应的 DistributionPanel
    panel_r = await db.execute(select(DistributionPanel).where(DistributionPanel.device_id == device_id))
    panel = panel_r.scalar_one_or_none()

    if not panel:
        # 也尝试通过 device_code 匹配
        dev_r = await db.execute(select(Device).where(Device.id == device_id))
        dev = dev_r.scalar_one_or_none()
        if dev:
            panel_r2 = await db.execute(
                select(DistributionPanel).where(DistributionPanel.panel_code == dev.device_code)
            )
            panel = panel_r2.scalar_one_or_none()

    if not panel:
        return {"branches": [], "panel_id": None}

    # 查询该 panel 下的所有回路
    circuits_r = await db.execute(
        select(DistributionCircuit)
        .where(
            DistributionCircuit.panel_id == panel.id,
            DistributionCircuit.is_enabled == True,
        )
        .order_by(DistributionCircuit.circuit_code)
    )
    circuits = circuits_r.scalars().all()

    branches = []
    for c in circuits:
        branches.append(
            {
                "branch_name": c.circuit_name,
                "circuit_code": c.circuit_code,
                "rated_current": c.rated_current,
                "breaker_type": c.breaker_type,
                "load_type": c.load_type,
                "current": None,
                "voltage": None,
                "power": None,
                "breaker_status": "on" if c.is_enabled else "off",
            }
        )

    return {"branches": branches, "panel_id": panel.id}


@router.get("/pdus", summary="PDU列表")
async def list_pdus(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取PDU列表（device_type=PDU），含聚合点位数据"""
    query = select(Device).where(Device.device_type == "PDU")

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Device.device_code)
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    devices = result.scalars().all()

    items = []
    for dev in devices:
        pr = await db.execute(
            select(Point.point_code, Point.point_name, Point.unit, PointRealtime.value)
            .outerjoin(PointRealtime, PointRealtime.point_id == Point.id)
            .where(Point.device_id == dev.id)
        )
        point_values = {row[0]: {"name": row[1], "unit": row[2], "value": row[3]} for row in pr.all()}
        items.append(
            {
                "device": DeviceInfo.model_validate(dev),
                "points": point_values,
            }
        )

    return PageResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
