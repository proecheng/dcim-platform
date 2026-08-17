"""
配电与制冷拓扑配置 API
"""

import json
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError

from ..deps import (
    SiteAccessContext,
    apply_cabinet_site_scope,
    apply_cooling_zone_site_scope,
    apply_site_scope,
    get_authorized_cabinet,
    get_authorized_device,
    get_authorized_room,
    get_db,
    get_site_access_context,
    require_admin,
    require_operator,
    require_viewer,
)
from ...models.user import User
from ...models.device import Device
from ...models.asset import Cabinet, Asset
from ...models.cooling import CoolingUnit
from ...models.spatial import Site, Floor, Room, Row
from ...models.topology_config import (
    PowerPhaseMapping,
    CoolingZone,
    CoolingZoneCabinet,
    CoolingZoneUnit,
)
from ...models.energy import DistributionPanel, DistributionCircuit, PowerDevice
from ...models.alarm import Alarm
from ...models.point import Point
from ...schemas.topology_config import (
    PowerPhaseMappingCreate,
    PowerPhaseMappingUpdate,
    PowerPhaseMappingResponse,
    CoolingZoneCreate,
    CoolingZoneUpdate,
    CoolingZoneResponse,
    CoolingZoneCabinetItem,
    CoolingZoneUnitItem,
    PhaseBalanceResponse,
    CabinetTopologySummary,
    SpatialInfo,
    PowerInfo,
    CoolingInfo,
    CoolingZoneCapacityResponse,
    SmartSiteRequest,
    SmartSiteResponse,
    CabinetSiteScore,
    DimensionScore,
    SmartSiteWeights,
    FaultImpactRequest,
    FaultImpactResponse,
    AffectedCabinet,
    AffectedAsset,
    CoolingImpactItem,
    RelatedAlarmItem,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_power_phase_scope(statement, context: SiteAccessContext):
    """Require ownership of both ends of a cabinet-to-PDU mapping."""
    if context.site_ids is None:
        return statement
    statement = apply_cabinet_site_scope(statement, PowerPhaseMapping.cabinet_id, context)
    authorized_devices = select(Device.id).where(Device.site_id.in_(context.site_ids))
    return statement.where(PowerPhaseMapping.pdu_device_id.in_(authorized_devices))


async def _get_authorized_power_phase_mapping(
    db: AsyncSession, mapping_id: int, context: SiteAccessContext
) -> PowerPhaseMapping:
    statement = _apply_power_phase_scope(select(PowerPhaseMapping).where(PowerPhaseMapping.id == mapping_id), context)
    mapping = (await db.execute(statement)).scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="映射不存在")
    return mapping


async def _load_authorized_cabinet_sites(
    db: AsyncSession, cabinet_ids: list[int], context: SiteAccessContext
) -> dict[int, int]:
    unique_ids = set(cabinet_ids)
    if not unique_ids:
        return {}
    statement = (
        select(Cabinet.id, Floor.site_id)
        .outerjoin(Row, Cabinet.row_id == Row.id)
        .outerjoin(Room, Row.room_id == Room.id)
        .outerjoin(Floor, Room.floor_id == Floor.id)
        .where(Cabinet.id.in_(unique_ids))
    )
    statement = apply_site_scope(statement, Floor.site_id, context)
    rows = (await db.execute(statement)).all()
    result = {row[0]: row[1] for row in rows}
    if set(result) != unique_ids:
        raise HTTPException(status_code=404, detail="机柜不存在")
    return result


async def _load_authorized_cooling_unit_sites(
    db: AsyncSession, unit_ids: list[int], context: SiteAccessContext
) -> dict[int, int]:
    unique_ids = set(unit_ids)
    if not unique_ids:
        return {}
    statement = (
        select(CoolingUnit.id, Device.site_id)
        .join(Device, CoolingUnit.device_id == Device.id)
        .where(CoolingUnit.id.in_(unique_ids))
    )
    statement = apply_site_scope(statement, Device.site_id, context)
    rows = (await db.execute(statement)).all()
    result = {row[0]: row[1] for row in rows}
    if set(result) != unique_ids:
        raise HTTPException(status_code=404, detail="空调不存在")
    return result


def _require_zone_relation_sites(zone_site_id: Optional[int], relation_sites: list[int]) -> None:
    if zone_site_id is not None and any(site_id != zone_site_id for site_id in relation_sites):
        raise HTTPException(status_code=400, detail="制冷区域关联对象必须属于同一站点")


# ==================== 三相接线映射 ====================


@router.get("/power-phase", response_model=List[PowerPhaseMappingResponse])
async def list_power_phase_mappings(
    pdu_device_id: Optional[int] = Query(None, description="PDU设备ID过滤"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取三相接线映射列表"""
    stmt = select(PowerPhaseMapping)
    if pdu_device_id is not None:
        await get_authorized_device(db, pdu_device_id, context)
        stmt = stmt.where(PowerPhaseMapping.pdu_device_id == pdu_device_id)
    stmt = _apply_power_phase_scope(stmt, context)
    stmt = stmt.order_by(PowerPhaseMapping.id)
    result = await db.execute(stmt)
    mappings = result.scalars().all()

    # 丰富响应数据
    items = []
    for m in mappings:
        resp = PowerPhaseMappingResponse(
            id=m.id,
            cabinet_id=m.cabinet_id,
            pdu_device_id=m.pdu_device_id,
            phase=m.phase,
            feed_type=m.feed_type,
            rated_current=m.rated_current,
            description=m.description,
        )
        # 查询 PDU 设备信息
        dev_result = await db.execute(select(Device).where(Device.id == m.pdu_device_id))
        dev = dev_result.scalar_one_or_none()
        if dev:
            resp.pdu_device_name = dev.device_name
            resp.pdu_device_code = dev.device_code
        # 查询机柜信息
        cab_result = await db.execute(select(Cabinet).where(Cabinet.id == m.cabinet_id))
        cab = cab_result.scalar_one_or_none()
        if cab:
            resp.cabinet_code = cab.cabinet_code
            resp.cabinet_name = cab.cabinet_name
        items.append(resp)
    return items


@router.get("/power-phase/cabinet/{cabinet_id}", response_model=List[PowerPhaseMappingResponse])
async def get_cabinet_power_phase(
    cabinet_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取机柜的三相接线"""
    await get_authorized_cabinet(db, cabinet_id, context)
    stmt = _apply_power_phase_scope(
        select(PowerPhaseMapping).where(PowerPhaseMapping.cabinet_id == cabinet_id), context
    )
    result = await db.execute(stmt)
    mappings = result.scalars().all()

    items = []
    for m in mappings:
        resp = PowerPhaseMappingResponse(
            id=m.id,
            cabinet_id=m.cabinet_id,
            pdu_device_id=m.pdu_device_id,
            phase=m.phase,
            feed_type=m.feed_type,
            rated_current=m.rated_current,
            description=m.description,
        )
        dev_result = await db.execute(select(Device).where(Device.id == m.pdu_device_id))
        dev = dev_result.scalar_one_or_none()
        if dev:
            resp.pdu_device_name = dev.device_name
            resp.pdu_device_code = dev.device_code
        cab_result = await db.execute(select(Cabinet).where(Cabinet.id == m.cabinet_id))
        cab = cab_result.scalar_one_or_none()
        if cab:
            resp.cabinet_code = cab.cabinet_code
            resp.cabinet_name = cab.cabinet_name
        items.append(resp)
    return items


@router.get("/power-phase/pdu/{pdu_device_id}/balance", response_model=PhaseBalanceResponse)
async def get_phase_balance(
    pdu_device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取PDU三相不平衡度"""
    # 查询 PDU 设备名称
    dev = await get_authorized_device(db, pdu_device_id, context)
    pdu_name = dev.device_name

    # 查询该 PDU 的所有映射
    stmt = _apply_power_phase_scope(
        select(PowerPhaseMapping).where(PowerPhaseMapping.pdu_device_id == pdu_device_id), context
    )
    result = await db.execute(stmt)
    mappings = result.scalars().all()

    phase_power = {"A": 0.0, "B": 0.0, "C": 0.0}
    phase_cabinets: dict[str, List[str]] = {"A": [], "B": [], "C": []}

    for m in mappings:
        cab_result = await db.execute(select(Cabinet).where(Cabinet.id == m.cabinet_id))
        cab = cab_result.scalar_one_or_none()
        if cab:
            phase_power[m.phase] += cab.max_power if cab.max_power is not None else 0
            phase_cabinets[m.phase].append(cab.cabinet_code or f"Cabinet-{cab.id}")

    a, b, c = phase_power["A"], phase_power["B"], phase_power["C"]

    if a == 0 and b == 0 and c == 0:
        return PhaseBalanceResponse(
            pdu_device_id=pdu_device_id,
            pdu_device_name=pdu_name,
            phase_a_power=a,
            phase_b_power=b,
            phase_c_power=c,
            imbalance_rate=None,
            data_source="no_data",
            phase_a_cabinets=phase_cabinets["A"],
            phase_b_cabinets=phase_cabinets["B"],
            phase_c_cabinets=phase_cabinets["C"],
        )

    avg = (a + b + c) / 3
    if avg == 0:
        imbalance_rate = None
    else:
        imbalance_rate = round((max(a, b, c) - min(a, b, c)) / avg * 100, 2)

    return PhaseBalanceResponse(
        pdu_device_id=pdu_device_id,
        pdu_device_name=pdu_name,
        phase_a_power=a,
        phase_b_power=b,
        phase_c_power=c,
        imbalance_rate=imbalance_rate,
        data_source="estimated",
        phase_a_cabinets=phase_cabinets["A"],
        phase_b_cabinets=phase_cabinets["B"],
        phase_c_cabinets=phase_cabinets["C"],
    )


@router.post("/power-phase", response_model=PowerPhaseMappingResponse)
async def create_power_phase_mapping(
    data: PowerPhaseMappingCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """创建三相接线映射"""
    # 校验 phase
    if data.phase not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="相位必须为 A/B/C")
    # 校验 feed_type
    if data.feed_type not in ("primary", "backup"):
        raise HTTPException(status_code=400, detail="馈电类型必须为 primary/backup")
    # 校验 PDU 设备类型
    dev = await get_authorized_device(db, data.pdu_device_id, context)
    if dev.device_type != "PDU":
        raise HTTPException(status_code=400, detail="指定设备不是PDU类型")
    # 校验机柜
    cab = await get_authorized_cabinet(db, data.cabinet_id, context)

    mapping = PowerPhaseMapping(**data.model_dump())
    db.add(mapping)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该机柜的此馈电类型已存在映射")
    await db.refresh(mapping)

    # 发布 Redis 更新通知
    await _publish_topology_update("create", mapping.id, "power_phase")

    return PowerPhaseMappingResponse(
        id=mapping.id,
        cabinet_id=mapping.cabinet_id,
        pdu_device_id=mapping.pdu_device_id,
        phase=mapping.phase,
        feed_type=mapping.feed_type,
        rated_current=mapping.rated_current,
        description=mapping.description,
        pdu_device_name=dev.device_name,
        pdu_device_code=dev.device_code,
        cabinet_code=cab.cabinet_code,
        cabinet_name=cab.cabinet_name,
    )


@router.put("/power-phase/{mapping_id}", response_model=PowerPhaseMappingResponse)
async def update_power_phase_mapping(
    mapping_id: int,
    data: PowerPhaseMappingUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """更新三相接线映射"""
    mapping = await _get_authorized_power_phase_mapping(db, mapping_id, context)

    update_data = data.model_dump(exclude_unset=True)
    if "phase" in update_data and update_data["phase"] not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="相位必须为 A/B/C")
    if "feed_type" in update_data and update_data["feed_type"] not in ("primary", "backup"):
        raise HTTPException(status_code=400, detail="馈电类型必须为 primary/backup")

    allowed_fields = {"phase", "feed_type", "rated_current", "description"}
    for k, v in update_data.items():
        if k in allowed_fields:
            setattr(mapping, k, v)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="该机柜的此馈电类型已存在映射")
    await db.refresh(mapping)

    # 发布 Redis 更新通知
    await _publish_topology_update("update", mapping.id, "power_phase")

    # 丰富响应
    dev_result = await db.execute(select(Device).where(Device.id == mapping.pdu_device_id))
    dev = dev_result.scalar_one_or_none()
    cab_result = await db.execute(select(Cabinet).where(Cabinet.id == mapping.cabinet_id))
    cab = cab_result.scalar_one_or_none()

    return PowerPhaseMappingResponse(
        id=mapping.id,
        cabinet_id=mapping.cabinet_id,
        pdu_device_id=mapping.pdu_device_id,
        phase=mapping.phase,
        feed_type=mapping.feed_type,
        rated_current=mapping.rated_current,
        description=mapping.description,
        pdu_device_name=dev.device_name if dev else None,
        pdu_device_code=dev.device_code if dev else None,
        cabinet_code=cab.cabinet_code if cab else None,
        cabinet_name=cab.cabinet_name if cab else None,
    )


@router.delete("/power-phase/{mapping_id}")
async def delete_power_phase_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """删除三相接线映射"""
    mapping = await _get_authorized_power_phase_mapping(db, mapping_id, context)
    await db.delete(mapping)
    await db.commit()

    # 发布 Redis 更新通知
    await _publish_topology_update("delete", mapping_id, "power_phase")

    return {"detail": "删除成功"}


# ==================== 制冷区域 ====================


async def _build_zone_response(db: AsyncSession, zone: CoolingZone) -> CoolingZoneResponse:
    """构建制冷区域响应（含关联机柜和空调）"""
    # 查询关联机柜
    cab_stmt = (
        select(CoolingZoneCabinet.cabinet_id, Cabinet.cabinet_code, Cabinet.cabinet_name)
        .join(Cabinet, Cabinet.id == CoolingZoneCabinet.cabinet_id)
        .where(CoolingZoneCabinet.zone_id == zone.id)
    )
    cab_result = await db.execute(cab_stmt)
    cabinets = [CoolingZoneCabinetItem(id=row[0], cabinet_code=row[1], cabinet_name=row[2]) for row in cab_result.all()]

    # 查询关联空调 → join devices 获取设备名称
    unit_stmt = (
        select(
            CoolingZoneUnit.cooling_unit_id,
            Device.device_code,
            Device.device_name,
            CoolingUnit.cooling_capacity_kw,
        )
        .join(CoolingUnit, CoolingUnit.id == CoolingZoneUnit.cooling_unit_id)
        .join(Device, Device.id == CoolingUnit.device_id)
        .where(CoolingZoneUnit.zone_id == zone.id)
    )
    unit_result = await db.execute(unit_stmt)
    cooling_units = [
        CoolingZoneUnitItem(id=row[0], device_code=row[1], device_name=row[2], cooling_capacity_kw=row[3])
        for row in unit_result.all()
    ]

    return CoolingZoneResponse(
        id=zone.id,
        zone_code=zone.zone_code,
        zone_name=zone.zone_name,
        room_id=zone.room_id,
        design_capacity_kw=zone.design_capacity_kw,
        description=zone.description,
        cabinets=cabinets,
        cooling_units=cooling_units,
    )


@router.get("/cooling-zones", response_model=List[CoolingZoneResponse])
async def list_cooling_zones(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取制冷区域列表"""
    statement = apply_cooling_zone_site_scope(
        select(CoolingZone).order_by(CoolingZone.id), CoolingZone.site_id, context
    )
    result = await db.execute(statement)
    zones = result.scalars().all()
    return [await _build_zone_response(db, z) for z in zones]


@router.get("/cooling-zones/{zone_id}", response_model=CoolingZoneResponse)
async def get_cooling_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取制冷区域详情"""
    statement = apply_cooling_zone_site_scope(
        select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
    )
    result = await db.execute(statement)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="制冷区域不存在")
    return await _build_zone_response(db, zone)


@router.post("/cooling-zones", response_model=CoolingZoneResponse)
async def create_cooling_zone(
    data: CoolingZoneCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """创建制冷区域"""
    if data.room_id is None:
        if context.site_ids is not None:
            raise HTTPException(status_code=403, detail="非管理员创建制冷区域时必须指定授权房间")
        site_id = None
    else:
        _, site_id = await get_authorized_room(db, data.room_id, context)

    cabinet_sites = await _load_authorized_cabinet_sites(db, data.cabinet_ids, context)
    unit_sites = await _load_authorized_cooling_unit_sites(db, data.cooling_unit_ids, context)
    _require_zone_relation_sites(site_id, [*cabinet_sites.values(), *unit_sites.values()])

    # 自动生成 zone_code: 查询最大序号 +1
    max_result = await db.execute(select(func.max(CoolingZone.zone_code)))
    max_code = max_result.scalar()
    if max_code and max_code.startswith("CZ-"):
        try:
            seq = int(max_code[3:]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    zone_code = f"CZ-{seq:03d}"

    zone = CoolingZone(
        zone_code=zone_code,
        zone_name=data.zone_name,
        room_id=data.room_id,
        site_id=site_id,
        design_capacity_kw=data.design_capacity_kw,
        description=data.description,
    )
    db.add(zone)
    try:
        await db.flush()
        for cabinet_id in dict.fromkeys(data.cabinet_ids):
            db.add(CoolingZoneCabinet(zone_id=zone.id, cabinet_id=cabinet_id))
        for unit_id in dict.fromkeys(data.cooling_unit_ids):
            db.add(CoolingZoneUnit(zone_id=zone.id, cooling_unit_id=unit_id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="制冷区域编码冲突，请重试")
    await db.refresh(zone)

    # 发布 Redis 更新通知
    await _publish_topology_update("create", zone.id, "cooling_zone")

    return await _build_zone_response(db, zone)


@router.put("/cooling-zones/{zone_id}", response_model=CoolingZoneResponse)
async def update_cooling_zone(
    zone_id: int,
    data: CoolingZoneUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """更新制冷区域"""
    statement = apply_cooling_zone_site_scope(
        select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
    )
    result = await db.execute(statement)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="制冷区域不存在")

    update_data = data.model_dump(exclude_unset=True)

    target_site_id = zone.site_id
    if "room_id" in update_data:
        if update_data["room_id"] is None:
            if context.site_ids is not None:
                raise HTTPException(status_code=403, detail="非管理员不能移除制冷区域站点归属")
            target_site_id = None
        else:
            _, target_site_id = await get_authorized_room(db, update_data["room_id"], context)

    if "cabinet_ids" in update_data and update_data["cabinet_ids"] is not None:
        cabinet_ids = list(dict.fromkeys(update_data["cabinet_ids"]))
    else:
        cabinet_ids = list(
            (await db.execute(select(CoolingZoneCabinet.cabinet_id).where(CoolingZoneCabinet.zone_id == zone_id)))
            .scalars()
            .all()
        )
    if "cooling_unit_ids" in update_data and update_data["cooling_unit_ids"] is not None:
        cooling_unit_ids = list(dict.fromkeys(update_data["cooling_unit_ids"]))
    else:
        cooling_unit_ids = list(
            (await db.execute(select(CoolingZoneUnit.cooling_unit_id).where(CoolingZoneUnit.zone_id == zone_id)))
            .scalars()
            .all()
        )

    cabinet_sites = await _load_authorized_cabinet_sites(db, cabinet_ids, context)
    unit_sites = await _load_authorized_cooling_unit_sites(db, cooling_unit_ids, context)
    _require_zone_relation_sites(target_site_id, [*cabinet_sites.values(), *unit_sites.values()])

    # 更新基本字段
    for k in ("zone_name", "room_id", "design_capacity_kw", "description"):
        if k in update_data:
            setattr(zone, k, update_data[k])
    zone.site_id = target_site_id

    # 更新机柜关联：先删旧再插新
    if "cabinet_ids" in update_data and update_data["cabinet_ids"] is not None:
        await db.execute(delete(CoolingZoneCabinet).where(CoolingZoneCabinet.zone_id == zone_id))
        for cab_id in cabinet_ids:
            db.add(CoolingZoneCabinet(zone_id=zone_id, cabinet_id=cab_id))

    # 更新空调关联
    if "cooling_unit_ids" in update_data and update_data["cooling_unit_ids"] is not None:
        await db.execute(delete(CoolingZoneUnit).where(CoolingZoneUnit.zone_id == zone_id))
        for unit_id in cooling_unit_ids:
            db.add(CoolingZoneUnit(zone_id=zone_id, cooling_unit_id=unit_id))

    await db.commit()
    await db.refresh(zone)

    # 发布 Redis 更新通知
    await _publish_topology_update("update", zone.id, "cooling_zone")

    return await _build_zone_response(db, zone)


@router.delete("/cooling-zones/{zone_id}")
async def delete_cooling_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """删除制冷区域"""
    statement = apply_cooling_zone_site_scope(
        select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
    )
    result = await db.execute(statement)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="制冷区域不存在")
    # 级联删除关联表
    await db.execute(delete(CoolingZoneCabinet).where(CoolingZoneCabinet.zone_id == zone_id))
    await db.execute(delete(CoolingZoneUnit).where(CoolingZoneUnit.zone_id == zone_id))
    await db.delete(zone)
    await db.commit()

    # 发布 Redis 更新通知
    await _publish_topology_update("delete", zone_id, "cooling_zone")

    return {"detail": "删除成功"}


@router.get("/cooling-zones/{zone_id}/capacity", response_model=CoolingZoneCapacityResponse)
async def get_cooling_zone_capacity(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取制冷区域容量使用"""
    statement = apply_cooling_zone_site_scope(
        select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
    )
    result = await db.execute(statement)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="制冷区域不存在")

    # 计算关联机柜总功率
    power_stmt = (
        select(func.coalesce(func.sum(Cabinet.max_power), 0.0))
        .join(CoolingZoneCabinet, CoolingZoneCabinet.cabinet_id == Cabinet.id)
        .where(CoolingZoneCabinet.zone_id == zone_id)
    )
    power_result = await db.execute(power_stmt)
    total_power = float(power_result.scalar() or 0)

    utilization = None
    if zone.design_capacity_kw and zone.design_capacity_kw > 0:
        utilization = round(total_power / zone.design_capacity_kw * 100, 2)

    return CoolingZoneCapacityResponse(
        zone_id=zone.id,
        zone_name=zone.zone_name,
        design_capacity_kw=zone.design_capacity_kw,
        total_cabinet_power=total_power,
        utilization_rate=utilization,
    )


# ==================== 机柜拓扑汇总 ====================


@router.get("/cabinet/{cabinet_id}/topology-summary", response_model=CabinetTopologySummary)
async def get_cabinet_topology_summary(
    cabinet_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """获取机柜拓扑汇总（空间+配电+制冷）"""
    cab = await get_authorized_cabinet(db, cabinet_id, context)

    # 空间信息
    spatial = None
    if cab.row_id:
        row_result = await db.execute(select(Row).where(Row.id == cab.row_id))
        row = row_result.scalar_one_or_none()
        if row:
            room_result = await db.execute(select(Room).where(Room.id == row.room_id))
            room = room_result.scalar_one_or_none()
            if room:
                floor_result = await db.execute(select(Floor).where(Floor.id == room.floor_id))
                floor = floor_result.scalar_one_or_none()
                if floor:
                    site_result = await db.execute(select(Site).where(Site.id == floor.site_id))
                    site = site_result.scalar_one_or_none()
                    spatial = SpatialInfo(
                        site_name=site.site_name if site else None,
                        floor_name=floor.floor_name,
                        room_name=room.room_name,
                        row_name=row.row_name,
                    )

    # 配电信息
    power_stmt = select(PowerPhaseMapping).where(PowerPhaseMapping.cabinet_id == cabinet_id)
    power_result = await db.execute(power_stmt)
    power_mappings = power_result.scalars().all()
    power_list = []
    for pm in power_mappings:
        dev_result = await db.execute(select(Device).where(Device.id == pm.pdu_device_id))
        dev = dev_result.scalar_one_or_none()
        power_list.append(
            PowerInfo(
                pdu_device_name=dev.device_name if dev else None,
                phase=pm.phase,
                feed_type=pm.feed_type,
            )
        )

    # 制冷信息
    cooling_stmt = (
        select(CoolingZone.zone_name, CoolingZone.design_capacity_kw)
        .join(CoolingZoneCabinet, CoolingZoneCabinet.zone_id == CoolingZone.id)
        .where(CoolingZoneCabinet.cabinet_id == cabinet_id)
    )
    cooling_result = await db.execute(cooling_stmt)
    cooling_list = [CoolingInfo(zone_name=row[0], design_capacity_kw=row[1]) for row in cooling_result.all()]

    return CabinetTopologySummary(
        cabinet_id=cab.id,
        cabinet_code=cab.cabinet_code,
        cabinet_name=cab.cabinet_name,
        spatial=spatial,
        power=power_list,
        cooling=cooling_list,
    )


# ==================== 智能选址推荐 ====================


@router.post("/smart-site-selection", response_model=SmartSiteResponse)
async def smart_site_selection(
    data: SmartSiteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """基于三合一拓扑的五维智能选址推荐 (FR65)"""
    weights = data.weights or SmartSiteWeights()

    # 1. 批量预加载所有数据
    cabinet_statement = apply_cabinet_site_scope(select(Cabinet), Cabinet.id, context)
    cab_result = await db.execute(cabinet_statement)
    cabinets = cab_result.scalars().all()
    cabinet_ids = [cabinet.id for cabinet in cabinets]
    total_evaluated = len(cabinets)

    # used_u 聚合
    used_u_stmt = (
        select(Asset.cabinet_id, func.coalesce(func.sum(Asset.u_height), 0).label("used_u"))
        .where(Asset.u_height.isnot(None), Asset.cabinet_id.in_(cabinet_ids))
        .group_by(Asset.cabinet_id)
    )
    used_u_result = await db.execute(used_u_stmt)
    used_u_map = {row.cabinet_id: int(row.used_u) for row in used_u_result}

    # PowerPhaseMapping
    ppm_statement = _apply_power_phase_scope(
        select(PowerPhaseMapping).where(PowerPhaseMapping.cabinet_id.in_(cabinet_ids)), context
    )
    ppm_result = await db.execute(ppm_statement)
    all_ppms = ppm_result.scalars().all()
    cab_ppm_map: dict[int, list] = {}
    pdu_ppm_map: dict[int, list] = {}
    for ppm in all_ppms:
        cab_ppm_map.setdefault(ppm.cabinet_id, []).append(ppm)
        pdu_ppm_map.setdefault(ppm.pdu_device_id, []).append(ppm)

    # CoolingZoneCabinet + CoolingZone
    czc_statement = (
        select(CoolingZoneCabinet)
        .join(CoolingZone, CoolingZoneCabinet.zone_id == CoolingZone.id)
        .where(CoolingZoneCabinet.cabinet_id.in_(cabinet_ids))
    )
    czc_statement = apply_cooling_zone_site_scope(czc_statement, CoolingZone.site_id, context)
    czc_result = await db.execute(czc_statement)
    all_czcs = czc_result.scalars().all()
    cab_zone_map: dict[int, list[int]] = {}
    zone_cab_map: dict[int, list[int]] = {}
    for czc in all_czcs:
        cab_zone_map.setdefault(czc.cabinet_id, []).append(czc.zone_id)
        zone_cab_map.setdefault(czc.zone_id, []).append(czc.cabinet_id)

    zone_statement = apply_cooling_zone_site_scope(select(CoolingZone), CoolingZone.site_id, context)
    cz_result = await db.execute(zone_statement)
    zone_map = {z.id: z for z in cz_result.scalars().all()}

    cab_power_map = {c.id: (c.max_power if c.max_power is not None else 0) for c in cabinets}

    # Row + Room 预加载
    row_result = await db.execute(select(Row))
    row_map = {r.id: r for r in row_result.scalars().all()}
    room_result = await db.execute(select(Room))
    room_map = {r.id: r for r in room_result.scalars().all()}

    # 2. 评分函数
    def score_cabinet(cab):
        used_u = used_u_map.get(cab.id, 0)
        available_u = (cab.total_u or 42) - used_u
        if available_u < data.required_u:
            return None
        # 承重硬性筛选
        if data.required_weight_kg is not None:
            if cab.max_weight is None or cab.max_weight < data.required_weight_kg:
                return None
        if data.required_power_kw is not None and data.required_power_kw > 0:
            if cab.max_power is None or cab.max_power < data.required_power_kw:
                return None

        dimensions = []
        req_power = data.required_power_kw

        # 空间评分
        space_score = min(100, (available_u / data.required_u) * 50)
        dimensions.append(
            DimensionScore(
                dimension="空间容量",
                score=round(space_score, 1),
                weight=weights.space,
                weighted_score=round(space_score * weights.space / 100, 2),
                data_available=True,
                detail=f"可用{available_u}U，需要{data.required_u}U",
            )
        )

        # 电力评分
        if req_power is None:
            p_score, p_avail, p_detail = 100.0, True, "无功率需求"
        elif req_power == 0:
            p_score, p_avail, p_detail = 100.0, True, "功率需求为0"
        elif cab.max_power is None:
            p_score, p_avail, p_detail = 50.0, False, "机柜未配置最大功率"
        else:
            p_score = min(100, (cab.max_power / req_power) * 50)
            p_avail, p_detail = True, f"最大{cab.max_power}kW，需要{req_power}kW"
        dimensions.append(
            DimensionScore(
                dimension="电力容量",
                score=round(p_score, 1),
                weight=weights.power,
                weighted_score=round(p_score * weights.power / 100, 2),
                data_available=p_avail,
                detail=p_detail,
            )
        )

        # 三相平衡度评分
        cab_ppms = cab_ppm_map.get(cab.id, [])
        primary_ppm = next((p for p in cab_ppms if p.feed_type == "primary"), None)
        if not primary_ppm:
            ph_score, ph_avail, ph_detail = 50.0, False, "未配置PDU接线"
        else:
            pdu_ppms = pdu_ppm_map.get(primary_ppm.pdu_device_id, [])
            phase_power = {"A": 0.0, "B": 0.0, "C": 0.0}
            for p in pdu_ppms:
                phase_power[p.phase] = phase_power.get(p.phase, 0) + cab_power_map.get(p.cabinet_id, 0)
            phase_power[primary_ppm.phase] += req_power or 0
            a, b, c = phase_power["A"], phase_power["B"], phase_power["C"]
            avg = (a + b + c) / 3
            if avg == 0:
                ph_score, ph_avail, ph_detail = 80.0, True, "PDU空载"
            else:
                imbalance = (max(a, b, c) - min(a, b, c)) / avg * 100
                ph_score = max(0, 100 - imbalance * 3)
                ph_avail, ph_detail = True, f"模拟不平衡度{imbalance:.1f}%"
        dimensions.append(
            DimensionScore(
                dimension="三相平衡度",
                score=round(ph_score, 1),
                weight=weights.phase_balance,
                weighted_score=round(ph_score * weights.phase_balance / 100, 2),
                data_available=ph_avail,
                detail=ph_detail,
            )
        )

        # 温度环境评分
        zone_ids = cab_zone_map.get(cab.id, [])
        if not zone_ids:
            t_score, t_avail, t_detail = 50.0, False, "未关联制冷区域"
        else:
            zone = zone_map.get(zone_ids[0])
            if not zone or not zone.design_capacity_kw or zone.design_capacity_kw <= 0:
                t_score, t_avail, t_detail = 50.0, False, "制冷区域未配置设计容量"
            else:
                zone_cabs = zone_cab_map.get(zone.id, [])
                total_power = sum(cab_power_map.get(cid, 0) for cid in zone_cabs)
                utilization = total_power / zone.design_capacity_kw * 100
                t_score = max(0, 100 - utilization)
                t_avail, t_detail = True, f"制冷利用率{utilization:.1f}%"
        dimensions.append(
            DimensionScore(
                dimension="温度环境",
                score=round(t_score, 1),
                weight=weights.temperature,
                weighted_score=round(t_score * weights.temperature / 100, 2),
                data_available=t_avail,
                detail=t_detail,
            )
        )

        # 制冷余量评分
        if req_power is None or req_power == 0:
            cl_score, cl_avail = 100.0, True
            cl_detail = "无功率需求" if req_power is None else "功率需求为0"
        elif not zone_ids:
            cl_score, cl_avail, cl_detail = 50.0, False, "未关联制冷区域"
        else:
            zone = zone_map.get(zone_ids[0])
            if not zone or not zone.design_capacity_kw or zone.design_capacity_kw <= 0:
                cl_score, cl_avail, cl_detail = 50.0, False, "制冷区域未配置设计容量"
            else:
                zone_cabs = zone_cab_map.get(zone.id, [])
                total_power = sum(cab_power_map.get(cid, 0) for cid in zone_cabs)
                remaining = zone.design_capacity_kw - total_power - req_power
                if remaining <= 0:
                    cl_score, cl_detail = 0.0, f"制冷不足(剩余{remaining:.1f}kW)"
                else:
                    cl_score = min(100, (remaining / req_power) * 50)
                    cl_detail = f"剩余制冷{remaining:.1f}kW"
                cl_avail = True
        dimensions.append(
            DimensionScore(
                dimension="制冷余量",
                score=round(cl_score, 1),
                weight=weights.cooling,
                weighted_score=round(cl_score * weights.cooling / 100, 2),
                data_available=cl_avail,
                detail=cl_detail,
            )
        )

        # 综合评分 + 置信度
        total_score = sum(d.weighted_score for d in dimensions)
        avail_count = sum(1 for d in dimensions if d.data_available)
        confidence = "high" if avail_count >= 5 else ("medium" if avail_count >= 3 else "low")

        room_name = row_name = None
        if cab.row_id:
            row = row_map.get(cab.row_id)
            if row:
                row_name = row.row_name
                room = room_map.get(row.room_id)
                if room:
                    room_name = room.room_name

        return CabinetSiteScore(
            cabinet_id=cab.id,
            cabinet_code=cab.cabinet_code,
            cabinet_name=cab.cabinet_name,
            location=cab.location,
            room_name=room_name,
            row_name=row_name,
            available_u=available_u,
            total_score=round(total_score, 1),
            confidence=confidence,
            dimensions=dimensions,
            grid_x=cab.grid_x,
            grid_y=cab.grid_y,
            aisle_type=cab.aisle_type,
        )

    # 3. 评分所有机柜
    candidates = []
    for cab in cabinets:
        result = score_cabinet(cab)
        if result is not None:
            candidates.append(result)

    candidates.sort(key=lambda x: x.total_score, reverse=True)

    return SmartSiteResponse(
        candidates=candidates[: data.limit],
        total_evaluated=total_evaluated,
        qualified_count=len(candidates),
    )


# ==================== 故障影响分析 ====================


@router.post("/fault-impact-analysis", response_model=FaultImpactResponse)
async def fault_impact_analysis(
    data: FaultImpactRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
    context: SiteAccessContext = Depends(get_site_access_context),
):
    """故障影响分析 — 分析 PDU 或配电柜故障对下游机柜/资产/制冷/告警的影响"""
    if data.fault_source_type not in ("pdu", "panel"):
        raise HTTPException(status_code=400, detail="fault_source_type 必须为 pdu 或 panel")

    fault_source_name: str | None = None
    affected_pdu_device_ids: set[int] = set()
    all_panel_ids: set[int] = set()

    # ---- PDU 故障 ----
    if data.fault_source_type == "pdu":
        dev = await get_authorized_device(db, data.fault_source_id, context)
        if dev.device_type != "PDU":
            raise HTTPException(status_code=400, detail="指定设备不是PDU类型")
        fault_source_name = dev.device_name
        affected_pdu_device_ids.add(dev.id)

    # ---- 配电柜故障 ----
    elif data.fault_source_type == "panel":
        panel_statement = select(DistributionPanel).where(DistributionPanel.id == data.fault_source_id)
        if context.site_ids is not None:
            authorized_panel_ids = (
                select(DistributionPanel.id)
                .join(Device, DistributionPanel.device_id == Device.id)
                .where(Device.site_id.in_(context.site_ids))
            )
            panel_statement = panel_statement.where(DistributionPanel.id.in_(authorized_panel_ids))
        panel_result = await db.execute(panel_statement)
        panel = panel_result.scalar_one_or_none()
        if not panel:
            raise HTTPException(status_code=404, detail="配电柜不存在")
        fault_source_name = panel.panel_name

        # BFS 递归查子配电柜
        visited: set[int] = set()
        queue = [data.fault_source_id]
        max_depth = 10
        depth = 0
        while queue and depth < max_depth:
            next_queue: list[int] = []
            for pid in queue:
                if pid in visited:
                    continue
                visited.add(pid)
                child_statement = select(DistributionPanel.id).where(DistributionPanel.parent_panel_id == pid)
                if context.site_ids is not None:
                    child_statement = child_statement.join(Device, DistributionPanel.device_id == Device.id).where(
                        Device.site_id.in_(context.site_ids)
                    )
                child_result = await db.execute(child_statement)
                for row in child_result.all():
                    if row[0] not in visited:
                        next_queue.append(row[0])
            queue = next_queue
            depth += 1
        all_panel_ids = visited

        # 查询回路 → PowerDevice → 过滤 PDU
        if all_panel_ids:
            circuit_result = await db.execute(
                select(DistributionCircuit.id).where(DistributionCircuit.panel_id.in_(all_panel_ids))
            )
            circuit_ids = [r[0] for r in circuit_result.all()]

            if circuit_ids:
                pd_result = await db.execute(
                    select(PowerDevice.monitor_device_id).where(
                        PowerDevice.circuit_id.in_(circuit_ids),
                        PowerDevice.monitor_device_id.isnot(None),
                    )
                )
                monitor_device_ids = {r[0] for r in pd_result.all()}

                if monitor_device_ids:
                    pdu_statement = select(Device.id).where(
                        Device.id.in_(monitor_device_ids),
                        Device.device_type == "PDU",
                    )
                    pdu_statement = apply_site_scope(pdu_statement, Device.site_id, context)
                    pdu_dev_result = await db.execute(pdu_statement)
                    affected_pdu_device_ids = {r[0] for r in pdu_dev_result.all()}

    # ---- 受影响机柜 (通过 PowerPhaseMapping) ----
    affected_cabinets_list: list[AffectedCabinet] = []
    affected_cabinet_ids: set[int] = set()

    if affected_pdu_device_ids:
        ppm_statement = _apply_power_phase_scope(
            select(PowerPhaseMapping).where(PowerPhaseMapping.pdu_device_id.in_(affected_pdu_device_ids)), context
        )
        ppm_result = await db.execute(ppm_statement)
        ppms = ppm_result.scalars().all()

        # 按 cabinet_id 分组
        cab_ppm_map: dict[int, list] = {}
        for ppm in ppms:
            cab_ppm_map.setdefault(ppm.cabinet_id, []).append(ppm)

        cab_ids = list(cab_ppm_map.keys())
        if cab_ids:
            cab_result = await db.execute(select(Cabinet).where(Cabinet.id.in_(cab_ids)))
            cab_map = {c.id: c for c in cab_result.scalars().all()}

            # 资产计数
            asset_count_result = await db.execute(
                select(Asset.cabinet_id, func.count(Asset.id))
                .where(Asset.cabinet_id.in_(cab_ids))
                .group_by(Asset.cabinet_id)
            )
            asset_count_map = {r[0]: r[1] for r in asset_count_result.all()}

            for cab_id, ppms_for_cab in cab_ppm_map.items():
                cab = cab_map.get(cab_id)
                if not cab:
                    continue
                affected_cabinet_ids.add(cab_id)

                # 取第一条映射的 feed_type/phase 作为代表
                first_ppm = ppms_for_cab[0]

                # 双路供电判断: 检查是否有另一路 (不同 feed_type) 且不在故障 PDU 列表中
                other_feed_statement = _apply_power_phase_scope(
                    select(PowerPhaseMapping).where(
                        PowerPhaseMapping.cabinet_id == cab_id,
                        PowerPhaseMapping.pdu_device_id.notin_(affected_pdu_device_ids),
                    ),
                    context,
                )
                other_feed_result = await db.execute(other_feed_statement)
                has_other_feed = len(other_feed_result.scalars().all()) > 0

                impact_level = "degraded" if has_other_feed else "power_loss"
                has_redundancy = has_other_feed

                affected_cabinets_list.append(
                    AffectedCabinet(
                        cabinet_id=cab_id,
                        cabinet_code=cab.cabinet_code,
                        cabinet_name=cab.cabinet_name,
                        location=cab.location,
                        feed_type=first_ppm.feed_type,
                        phase=first_ppm.phase,
                        asset_count=asset_count_map.get(cab_id, 0),
                        impact_level=impact_level,
                        has_redundancy=has_redundancy,
                    )
                )

    # ---- 受影响资产 ----
    affected_assets_list: list[AffectedAsset] = []
    if affected_cabinet_ids:
        asset_result = await db.execute(
            select(Asset, Cabinet.cabinet_code)
            .join(Cabinet, Cabinet.id == Asset.cabinet_id)
            .where(Asset.cabinet_id.in_(affected_cabinet_ids))
        )
        for row in asset_result.all():
            asset = row[0]
            cab_code = row[1]
            asset_type_val = asset.asset_type
            if hasattr(asset_type_val, "value"):
                asset_type_val = asset_type_val.value
            affected_assets_list.append(
                AffectedAsset(
                    asset_id=asset.id,
                    asset_code=asset.asset_code,
                    asset_name=asset.asset_name,
                    asset_type=str(asset_type_val) if asset_type_val else None,
                    cabinet_code=cab_code,
                )
            )

    # ---- 制冷交叉影响 ----
    cooling_impacts_list: list[CoolingImpactItem] = []
    if affected_cabinet_ids:
        czc_result = await db.execute(
            select(CoolingZoneCabinet.zone_id).where(CoolingZoneCabinet.cabinet_id.in_(affected_cabinet_ids)).distinct()
        )
        zone_ids = [r[0] for r in czc_result.all()]

        for zone_id in zone_ids:
            zone_statement = apply_cooling_zone_site_scope(
                select(CoolingZone).where(CoolingZone.id == zone_id), CoolingZone.site_id, context
            )
            zone_result = await db.execute(zone_statement)
            zone = zone_result.scalar_one_or_none()
            if not zone:
                continue

            # 该区域所有机柜
            all_czc_result = await db.execute(
                select(CoolingZoneCabinet.cabinet_id).where(CoolingZoneCabinet.zone_id == zone_id)
            )
            zone_cab_ids = {r[0] for r in all_czc_result.all()}
            affected_in_zone = zone_cab_ids & affected_cabinet_ids

            # 查询制冷单元
            czu_result = await db.execute(
                select(CoolingZoneUnit.cooling_unit_id).where(CoolingZoneUnit.zone_id == zone_id)
            )
            cu_ids = [r[0] for r in czu_result.all()]

            cooling_unit_names: list[str] = []
            same_power_circuit = False
            data_source = "unknown"

            for cu_id in cu_ids:
                cu_statement = (
                    select(CoolingUnit).join(Device, CoolingUnit.device_id == Device.id).where(CoolingUnit.id == cu_id)
                )
                cu_statement = apply_site_scope(cu_statement, Device.site_id, context)
                cu_result = await db.execute(cu_statement)
                cu = cu_result.scalar_one_or_none()
                if not cu:
                    continue

                # 获取空调设备名称
                ac_device_statement = apply_site_scope(
                    select(Device).where(Device.id == cu.device_id), Device.site_id, context
                )
                ac_dev_result = await db.execute(ac_device_statement)
                ac_dev = ac_dev_result.scalar_one_or_none()
                if ac_dev:
                    cooling_unit_names.append(ac_dev.device_name)

                # 同回路判断: PowerDevice(HVAC) 的 monitor_device_id == cu.device_id
                if all_panel_ids and data.fault_source_type == "panel":
                    hvac_pd_result = await db.execute(
                        select(PowerDevice).where(
                            PowerDevice.monitor_device_id == cu.device_id,
                            PowerDevice.device_type == "HVAC",
                        )
                    )
                    hvac_pd = hvac_pd_result.scalar_one_or_none()
                    if hvac_pd and hvac_pd.circuit_id:
                        circ_result = await db.execute(
                            select(DistributionCircuit.panel_id).where(DistributionCircuit.id == hvac_pd.circuit_id)
                        )
                        circ_row = circ_result.first()
                        if circ_row and circ_row[0] in all_panel_ids:
                            same_power_circuit = True
                            data_source = "confirmed"

            if data_source == "unknown" and all_panel_ids:
                data_source = "unknown"

            cooling_impacts_list.append(
                CoolingImpactItem(
                    zone_id=zone_id,
                    zone_name=zone.zone_name,
                    affected_cabinet_count=len(affected_in_zone),
                    total_cabinet_count=len(zone_cab_ids),
                    cooling_units=cooling_unit_names,
                    same_power_circuit=same_power_circuit,
                    power_circuit_data_source=data_source,
                )
            )

    # ---- 关联告警 ----
    related_alarms_list: list[RelatedAlarmItem] = []
    all_affected_device_ids: set[int] = set(affected_pdu_device_ids)

    # 也收集 PowerDevice.monitor_device_id
    if all_panel_ids:
        circuit_result2 = await db.execute(
            select(DistributionCircuit.id).where(DistributionCircuit.panel_id.in_(all_panel_ids))
        )
        cids2 = [r[0] for r in circuit_result2.all()]
        if cids2:
            pd_result2 = await db.execute(
                select(PowerDevice.monitor_device_id).where(
                    PowerDevice.circuit_id.in_(cids2),
                    PowerDevice.monitor_device_id.isnot(None),
                )
            )
            for r in pd_result2.all():
                all_affected_device_ids.add(r[0])

    if all_affected_device_ids:
        if context.site_ids is not None:
            authorized_devices_result = await db.execute(
                select(Device.id).where(
                    Device.id.in_(all_affected_device_ids),
                    Device.site_id.in_(context.site_ids),
                )
            )
            all_affected_device_ids = set(authorized_devices_result.scalars().all())
        point_result = await db.execute(select(Point.id).where(Point.device_id.in_(all_affected_device_ids)))
        point_ids = [r[0] for r in point_result.all()]

        if point_ids:
            alarm_result = await db.execute(
                select(Alarm).where(
                    Alarm.point_id.in_(point_ids),
                    Alarm.status.in_(["active", "acknowledged"]),
                )
            )
            for alarm in alarm_result.scalars().all():
                related_alarms_list.append(
                    RelatedAlarmItem(
                        alarm_id=alarm.id,
                        alarm_no=alarm.alarm_no,
                        alarm_level=alarm.alarm_level,
                        alarm_message=alarm.alarm_message,
                        status=alarm.status,
                        created_at=alarm.created_at.isoformat() if alarm.created_at else None,
                    )
                )

    # ---- 建议操作 ----
    suggestions: list[str] = []
    if affected_cabinets_list:
        cab_count = len(affected_cabinets_list)
        degraded_count = sum(1 for c in affected_cabinets_list if c.impact_level == "degraded")
        loss_count = cab_count - degraded_count
        if loss_count > 0:
            suggestions.append(f"有 {loss_count} 个机柜完全失去供电，请立即检查配电设备并启动应急预案")
        if degraded_count > 0:
            suggestions.append(f"有 {degraded_count} 个机柜降级运行（冗余供电），建议尽快恢复故障线路")
    if affected_assets_list:
        suggestions.append(f"受影响设备共 {len(affected_assets_list)} 台，建议确认关键业务设备运行状态")
    if cooling_impacts_list:
        same_circuit = [c for c in cooling_impacts_list if c.same_power_circuit]
        if same_circuit:
            suggestions.append("警告: 部分制冷设备与故障设备同配电回路，可能导致制冷中断")
        else:
            suggestions.append("制冷设备供电独立于故障回路，制冷系统不受直接影响")
    if not affected_cabinets_list:
        suggestions.append("未发现受影响的下游设备，请确认拓扑配置是否完整")

    return FaultImpactResponse(
        fault_source_type=data.fault_source_type,
        fault_source_id=data.fault_source_id,
        fault_source_name=fault_source_name,
        affected_cabinets=affected_cabinets_list,
        affected_assets=affected_assets_list,
        cooling_impacts=cooling_impacts_list,
        related_alarms=related_alarms_list,
        suggestions=suggestions,
        analysis_time=datetime.now().isoformat(),
    )


# ==================== Redis 事件发布辅助函数 ====================


async def _publish_topology_update(event_type: str, entity_id: int, entity_type: str):
    """
    发布拓扑配置更新通知到 Redis

    Args:
        event_type: 事件类型 (create/update/delete)
        entity_id: 实体 ID
        entity_type: 实体类型 (power_phase/cooling_zone)
    """
    try:
        import redis.asyncio as redis
        from app.core.config import get_settings

        settings = get_settings()

        redis_client = redis.from_url(settings.effective_redis_url, decode_responses=True)
        payload = json.dumps(
            {
                "event_type": event_type,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await redis_client.publish("topology:config_update", payload)
        await redis_client.close()
        logger.debug(f"发布拓扑更新通知: {event_type} {entity_type} {entity_id}")
    except ImportError:
        logger.warning("Redis 不可用，跳过拓扑更新通知")
    except Exception as e:
        logger.error(f"发布拓扑更新通知失败: {e}")
