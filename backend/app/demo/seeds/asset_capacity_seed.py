"""Demo asset and capacity seed data derived from existing topology/config data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select

from ...core.database import async_session
from ...models.asset import Asset, AssetStatus, AssetType, Cabinet
from ...models.capacity import (
    CapacityStatus,
    CoolingCapacity,
    PowerCapacity,
    SpaceCapacity,
    WeightCapacity,
)
from ...models.cooling import CoolingUnit
from ...models.device import Device
from ...models.energy import DistributionPanel, PowerDevice, Transformer
from ...models.spatial import Floor, Room, Row, Site

logger = logging.getLogger(__name__)

DEMO_PREFIX = "DEMO"
IT_ROOM_SUFFIXES = ("A1", "A2", "B1", "B2", "C1", "C2", "NC")


@dataclass(frozen=True)
class RoomLayout:
    room: Room
    floor_code: str
    site_name: str
    area_code: str
    location: str
    cabinet_count: int


def _capacity_status(used: float, total: float, warning: float, critical: float) -> CapacityStatus:
    if total <= 0:
        return CapacityStatus.normal
    rate = used / total * 100
    if rate >= 100:
        return CapacityStatus.full
    if rate >= critical:
        return CapacityStatus.critical
    if rate >= warning:
        return CapacityStatus.warning
    return CapacityStatus.normal


def _room_area_code(room_code: str) -> str:
    parts = room_code.split("-", 1)
    if len(parts) == 2:
        return parts[1]
    return room_code


def _is_it_room(room_code: str) -> bool:
    return any(room_code.endswith(suffix) for suffix in IT_ROOM_SUFFIXES)


def _cabinet_count_for_room(room_code: str, area_sqm: float | None) -> int:
    if room_code.endswith("NC"):
        return 6
    if _is_it_room(room_code):
        return 10
    area = area_sqm or 0
    if area >= 350:
        return 4
    if area >= 180:
        return 2
    return 0


def _asset_type_for_power_device(device_type: str | None) -> AssetType:
    dtype = (device_type or "").upper()
    if dtype in {"UPS"}:
        return AssetType.ups
    if dtype in {"PDU"}:
        return AssetType.pdu
    if dtype in {"AC", "HVAC", "CHILLER", "CT", "PUMP"}:
        return AssetType.ac
    if dtype in {"IT", "IT_SERVER", "SERVER"}:
        return AssetType.server
    return AssetType.other


async def _get_room_layouts(session) -> list[RoomLayout]:
    stmt = (
        select(Site, Floor, Room)
        .join(Floor, Floor.site_id == Site.id)
        .join(Room, Room.floor_id == Floor.id)
        .where(Site.site_code == "SZ-DC-01")
        .order_by(Floor.sort_order, Room.room_code)
    )
    rows = (await session.execute(stmt)).all()
    layouts: list[RoomLayout] = []
    for site, floor, room in rows:
        count = _cabinet_count_for_room(room.room_code, room.area_sqm)
        if count <= 0:
            continue
        area_code = _room_area_code(room.room_code)
        layouts.append(
            RoomLayout(
                room=room,
                floor_code=floor.floor_code,
                site_name=site.site_name,
                area_code=area_code,
                location=f"{site.site_name}/{floor.floor_code}/{room.room_name}",
                cabinet_count=count,
            )
        )
    return layouts


async def _ensure_row(session, layout: RoomLayout, row_index: int, aisle_type: str) -> Row:
    row_code = f"{DEMO_PREFIX}-{layout.room.room_code}-R{row_index}"
    result = await session.execute(select(Row).where(Row.room_id == layout.room.id, Row.row_code == row_code))
    row = result.scalar_one_or_none()
    if row:
        return row
    row = Row(
        room_id=layout.room.id,
        row_code=row_code,
        row_name=f"{layout.room.room_name} 第{row_index}列",
        aisle_type=aisle_type,
        sort_order=row_index,
        is_demo=True,
    )
    session.add(row)
    await session.flush()
    return row


async def _ensure_cabinets(session, layouts: list[RoomLayout]) -> tuple[list[Cabinet], int]:
    created = 0
    cabinets: list[Cabinet] = []
    for layout in layouts:
        for idx in range(1, layout.cabinet_count + 1):
            row_index = 1 if idx <= (layout.cabinet_count + 1) // 2 else 2
            aisle_type = "cold" if row_index == 1 else "hot"
            row = await _ensure_row(session, layout, row_index, aisle_type)
            cabinet_code = f"{DEMO_PREFIX}-{layout.room.room_code}-CAB-{idx:02d}"
            result = await session.execute(select(Cabinet).where(Cabinet.cabinet_code == cabinet_code))
            cabinet = result.scalar_one_or_none()
            if cabinet is None:
                col = idx if row_index == 1 else idx - ((layout.cabinet_count + 1) // 2)
                cabinet = Cabinet(
                    cabinet_code=cabinet_code,
                    cabinet_name=f"{layout.room.room_name} 机柜{idx:02d}",
                    location=layout.location,
                    row_number=str(row_index),
                    column_number=str(col),
                    total_u=42,
                    max_power=8.0 if _is_it_room(layout.room.room_code) else 5.0,
                    max_weight=800.0 if _is_it_room(layout.room.room_code) else 600.0,
                    row_id=row.id,
                    aisle_type=aisle_type,
                    grid_x=col - 1,
                    grid_y=row_index - 1,
                )
                session.add(cabinet)
                await session.flush()
                created += 1
            cabinets.append(cabinet)
    return cabinets, created


async def _ensure_assets(session, cabinets: list[Cabinet]) -> int:
    created = 0
    today = date.today()
    cabinet_by_area: dict[str, list[Cabinet]] = {}
    cabinet_by_floor: dict[str, list[Cabinet]] = {}
    next_u_by_cabinet: dict[int, int] = {}
    cabinet_ids: list[int] = []
    for cab in cabinets:
        code_parts = cab.cabinet_code.split("-")
        if len(code_parts) >= 4:
            floor_code = code_parts[1]
            area_code = code_parts[2]
            cabinet_by_area.setdefault(area_code, []).append(cab)
            cabinet_by_floor.setdefault(floor_code, []).append(cab)
        if cab.id is not None:
            next_u_by_cabinet[cab.id] = 1
            cabinet_ids.append(cab.id)

    if cabinet_ids:
        existing_positions = (
            await session.execute(
                select(Asset.cabinet_id, Asset.u_position, Asset.u_height)
                .where(
                    Asset.cabinet_id.in_(cabinet_ids),
                    Asset.u_position.isnot(None),
                    Asset.u_height.isnot(None),
                )
                .order_by(Asset.cabinet_id)
            )
        ).all()
        for cabinet_id, u_position, u_height in existing_positions:
            next_u_by_cabinet[cabinet_id] = max(
                next_u_by_cabinet.get(cabinet_id, 1),
                int(u_position or 1) + int(u_height or 1),
            )

    for cab_list in cabinet_by_area.values():
        cab_list.sort(key=lambda c: c.cabinet_code)
    for cab_list in cabinet_by_floor.values():
        cab_list.sort(key=lambda c: c.cabinet_code)

    power_devices = (
        await session.execute(select(PowerDevice).where(PowerDevice.is_enabled == True).order_by(PowerDevice.device_code))
    ).scalars().all()
    for index, device in enumerate(power_devices):
        area_code = device.area_code or ""
        area_cabinets = cabinet_by_area.get(area_code) or cabinet_by_floor.get(area_code)
        if not area_cabinets:
            continue
        cabinet = area_cabinets[index % len(area_cabinets)]
        asset_code = f"{DEMO_PREFIX}-AST-{device.device_code}"
        result = await session.execute(select(Asset).where(Asset.asset_code == asset_code))
        if result.scalar_one_or_none():
            continue
        asset_type = _asset_type_for_power_device(device.device_type)
        u_height = 1
        if asset_type == AssetType.ups:
            u_height = 6
        elif asset_type == AssetType.pdu:
            u_height = 2
        elif asset_type == AssetType.ac:
            u_height = 4
        elif asset_type == AssetType.server:
            u_height = 2
        next_u = next_u_by_cabinet.get(cabinet.id or 0, 1)
        if next_u + u_height - 1 > (cabinet.total_u or 42):
            next_u = 1
        next_u_by_cabinet[cabinet.id or 0] = next_u + u_height
        asset = Asset(
            asset_code=asset_code,
            asset_name=device.device_name,
            asset_type=asset_type,
            brand="Demo",
            model=device.device_type or "PowerDevice",
            serial_number=asset_code,
            cabinet_id=cabinet.id,
            u_position=next_u,
            u_height=u_height,
            status=AssetStatus.in_use,
            purchase_date=today - timedelta(days=420 + index),
            purchase_price=round((device.rated_power or 10.0) * 1200, 2),
            supplier="Demo集成商",
            warranty_start=today - timedelta(days=420 + index),
            warranty_end=today + timedelta(days=180 + index),
            maintenance_vendor="Demo维保",
            owner="平台运维",
            department="数据中心",
            remark="由 demo 采集/配电配置派生的资产台账",
        )
        session.add(asset)
        created += 1

    return created


async def _room_used_u(session, cabinet_ids: list[int]) -> int:
    if not cabinet_ids:
        return 0
    result = await session.execute(
        select(func.coalesce(func.sum(Asset.u_height), 0)).where(Asset.cabinet_id.in_(cabinet_ids))
    )
    return int(result.scalar() or 0)


async def _upsert_capacity(session, model: Any, name: str, values: dict[str, Any]) -> bool:
    result = await session.execute(select(model).where(model.name == name))
    row = result.scalars().first()
    if row is None:
        row = model(name=name, **values)
        session.add(row)
        return True
    for key, value in values.items():
        setattr(row, key, value)
    return False


async def _ensure_capacity_records(session, layouts: list[RoomLayout], cabinets: list[Cabinet]) -> dict[str, int]:
    created = {"space": 0, "power": 0, "cooling": 0, "weight": 0}
    cabinets_by_location: dict[str, list[Cabinet]] = {}
    used_u_by_cabinet: dict[int, int] = {}
    for cab in cabinets:
        cabinets_by_location.setdefault(cab.location or "", []).append(cab)

    cabinet_ids = [cab.id for cab in cabinets if cab.id is not None]
    if cabinet_ids:
        used_rows = (
            await session.execute(
                select(Asset.cabinet_id, func.coalesce(func.sum(Asset.u_height), 0))
                .where(Asset.cabinet_id.in_(cabinet_ids), Asset.u_height.isnot(None))
                .group_by(Asset.cabinet_id)
            )
        ).all()
        used_u_by_cabinet = {cabinet_id: int(used_u or 0) for cabinet_id, used_u in used_rows}

    power_by_area: dict[str, float] = {}
    for area, used_power in (
        await session.execute(
            select(PowerDevice.area_code, func.coalesce(func.sum(PowerDevice.rated_power), 0))
            .where(PowerDevice.is_enabled == True)
            .group_by(PowerDevice.area_code)
        )
    ).all():
        if area:
            power_by_area[str(area)] = float(used_power or 0)

    cooling_by_area: dict[str, float] = {}
    for area, cooling_kw in (
        await session.execute(
            select(Device.area_code, func.coalesce(func.sum(CoolingUnit.cooling_capacity_kw), 0))
            .join(Device, CoolingUnit.device_id == Device.id)
            .group_by(Device.area_code)
        )
    ).all():
        if area:
            cooling_by_area[str(area)] = float(cooling_kw or 0)

    transformer_total = float(
        await session.scalar(select(func.coalesce(func.sum(Transformer.rated_capacity), 0)).where(Transformer.is_enabled == True))
        or 0
    )
    floor_layout_counts: dict[str, int] = {}
    for layout in layouts:
        floor_layout_counts[layout.floor_code] = floor_layout_counts.get(layout.floor_code, 0) + 1

    for layout in layouts:
        room_cabinets = cabinets_by_location.get(layout.location, [])
        cabinet_ids = [cab.id for cab in room_cabinets if cab.id is not None]
        total_u = sum((cab.total_u or 42) for cab in room_cabinets)
        used_u = sum(used_u_by_cabinet.get(cabinet_id, 0) for cabinet_id in cabinet_ids)
        used_cabinets = sum(1 for cabinet_id in cabinet_ids if used_u_by_cabinet.get(cabinet_id, 0) > 0)

        if await _upsert_capacity(
            session,
            SpaceCapacity,
            f"{DEMO_PREFIX}-{layout.room.room_code}-空间容量",
            {
                "location": layout.location,
                "total_area": layout.room.area_sqm or 0,
                "used_area": round((layout.room.area_sqm or 0) * 0.62, 2),
                "total_cabinets": len(room_cabinets),
                "used_cabinets": used_cabinets,
                "total_u_positions": total_u,
                "used_u_positions": used_u,
                "warning_threshold": 80,
                "critical_threshold": 95,
                "status": _capacity_status(used_u, total_u, 80, 95),
            },
        ):
            created["space"] += 1

        floor_share = power_by_area.get(layout.floor_code, 0.0) / max(floor_layout_counts.get(layout.floor_code, 1), 1)
        used_power = round(power_by_area.get(layout.area_code, 0.0) + floor_share, 2)
        total_power = max(used_power * 1.35, len(room_cabinets) * 8.0, transformer_total / 8 if transformer_total else 0)
        total_power = round(total_power, 2)
        if await _upsert_capacity(
            session,
            PowerCapacity,
            f"{DEMO_PREFIX}-{layout.room.room_code}-电力容量",
            {
                "location": layout.location,
                "capacity_type": "room",
                "total_capacity_kva": round(total_power / 0.9, 2) if total_power else 0,
                "used_capacity_kva": round(used_power / 0.9, 2) if used_power else 0,
                "total_capacity_kw": total_power,
                "used_capacity_kw": used_power,
                "redundancy_mode": "N+1",
                "warning_threshold": 70,
                "critical_threshold": 85,
                "status": _capacity_status(used_power, total_power, 70, 85),
            },
        ):
            created["power"] += 1

        floor_cooling_share = cooling_by_area.get(layout.floor_code, 0.0) / max(
            floor_layout_counts.get(layout.floor_code, 1), 1
        )
        available_cooling_source = cooling_by_area.get(layout.area_code, 0.0) + floor_cooling_share
        used_cooling = round(min(used_power * 0.75, available_cooling_source or used_power), 2)
        total_cooling = round(max(available_cooling_source, used_cooling * 1.4, len(room_cabinets) * 6.0), 2)
        if await _upsert_capacity(
            session,
            CoolingCapacity,
            f"{DEMO_PREFIX}-{layout.room.room_code}-制冷容量",
            {
                "location": layout.location,
                "total_cooling_kw": total_cooling,
                "used_cooling_kw": used_cooling,
                "target_temperature": 24,
                "current_temperature": 24.5,
                "humidity_target": 50,
                "current_humidity": 48,
                "warning_threshold": 75,
                "critical_threshold": 90,
                "status": _capacity_status(used_cooling, total_cooling, 75, 90),
            },
        ):
            created["cooling"] += 1

        total_weight = round(sum((cab.max_weight or 600.0) for cab in room_cabinets), 2)
        used_weight = round(used_u * 18.0, 2)
        if await _upsert_capacity(
            session,
            WeightCapacity,
            f"{DEMO_PREFIX}-{layout.room.room_code}-承重容量",
            {
                "location": layout.location,
                "capacity_type": "room",
                "total_weight_kg": total_weight,
                "used_weight_kg": used_weight,
                "warning_threshold": 80,
                "critical_threshold": 95,
                "status": _capacity_status(used_weight, total_weight, 80, 95),
            },
        ):
            created["weight"] += 1

    return created


async def seed_asset_capacity() -> dict[str, Any]:
    """Create demo asset/capacity master data from demo spatial and collection config."""
    async with async_session() as session:
        layouts = await _get_room_layouts(session)
        if not layouts:
            logger.info("资产容量 demo 种子跳过: 未找到 SZ-DC-01 空间房间")
            return {"layouts": 0, "cabinets_created": 0, "assets_created": 0, "capacities_created": {}}

        cabinets, cabinets_created = await _ensure_cabinets(session, layouts)
        assets_created = await _ensure_assets(session, cabinets)
        await session.flush()
        capacities_created = await _ensure_capacity_records(session, layouts, cabinets)
        await session.commit()

        result = {
            "layouts": len(layouts),
            "cabinets_created": cabinets_created,
            "assets_created": assets_created,
            "capacities_created": capacities_created,
        }
        logger.info(
            "资产容量 demo 种子完成: 房间 %d, 新增机柜 %d, 新增资产 %d, 新增容量 %s",
            result["layouts"],
            result["cabinets_created"],
            result["assets_created"],
            result["capacities_created"],
        )
        return result
