"""Bind protocol-template data sources to power-device records."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.asset import Asset, AssetStatus, AssetType, Cabinet
from ..models.energy import PowerDevice
from ..models.gateway import DataSource, DeviceTemplate
from ..models.point import Point
from .cooling_flexibility import default_controllable_params_for_subtype, infer_load_subtype
from .device_config_generator import DeviceConfigAutoGenerator


PointBinding = tuple[dict[str, Any], Point]

_DEVICE_CODE_MAX_LENGTH = 50


def infer_template_power_device_type(template: DeviceTemplate) -> str:
    """Infer the business power-device type represented by a protocol template."""
    extra_config = template.extra_config or {}
    configured = extra_config.get("device_type") if isinstance(extra_config, dict) else None
    if configured:
        return str(configured).upper()

    model = (template.model or "").upper()
    name = (template.name or "").upper()
    if "UPS" in model or "UPS" in name:
        return "UPS"
    if "FUSIONCOL" in model or "FUSIONCOL" in name or "COOL" in model or "COOL" in name:
        return "AC"
    return "OTHER"


def _config_value(config: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = config.get(key)
        if value not in (None, ""):
            return value
    return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_device_code(raw: Any, fallback: str) -> str:
    text = str(raw or fallback).strip()
    text = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-_").upper()
    if not text:
        text = fallback
    if len(text) <= _DEVICE_CODE_MAX_LENGTH:
        return text

    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    keep = _DEVICE_CODE_MAX_LENGTH - len(digest) - 1
    return f"{text[:keep]}-{digest}"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        items = []
        for item in value:
            key = item.get("key") if isinstance(item, dict) else item
            if key:
                items.append(str(key).strip())
        return [item for item in items if item]
    return []


def _asset_type_for_device(device_type: str) -> AssetType:
    return {
        "UPS": AssetType.ups,
        "AC": AssetType.ac,
        "HVAC": AssetType.ac,
        "CHILLER": AssetType.ac,
        "PDU": AssetType.pdu,
        "IT_SERVER": AssetType.server,
        "IT_STORAGE": AssetType.storage,
    }.get(device_type.upper(), AssetType.other)


async def _has_u_position_conflict(
    db: AsyncSession,
    cabinet_id: int,
    u_position: int,
    u_height: int,
    exclude_asset_id: int | None = None,
) -> bool:
    query = select(Asset).where(
        Asset.cabinet_id == cabinet_id,
        Asset.u_position.isnot(None),
        Asset.u_height.isnot(None),
    )
    if exclude_asset_id:
        query = query.where(Asset.id != exclude_asset_id)

    result = await db.execute(query)
    new_start = u_position
    new_end = u_position + u_height - 1
    for asset in result.scalars().all():
        existing_start = asset.u_position
        existing_end = asset.u_position + asset.u_height - 1
        if new_start <= existing_end and new_end >= existing_start:
            return True
    return False


async def _upsert_asset_for_power_device(
    db: AsyncSession,
    *,
    template: DeviceTemplate,
    datasource: DataSource,
    device: PowerDevice,
    connection_config: dict[str, Any],
) -> Asset | None:
    asset_code = _config_value(connection_config, "asset_code")
    if not asset_code:
        return None

    result = await db.execute(select(Asset).where(Asset.asset_code == str(asset_code)))
    asset = result.scalar_one_or_none()

    cabinet_id = None
    cabinet_code = _config_value(connection_config, "cabinet_code")
    if cabinet_code:
        cabinet_result = await db.execute(select(Cabinet).where(Cabinet.cabinet_code == str(cabinet_code)))
        cabinet = cabinet_result.scalar_one_or_none()
        if cabinet:
            cabinet_id = cabinet.id

    u_position = _int_or_none(_config_value(connection_config, "u_position"))
    u_height = _int_or_none(_config_value(connection_config, "u_height")) or (1 if u_position else None)
    if cabinet_id and u_position and u_height:
        has_conflict = await _has_u_position_conflict(db, cabinet_id, u_position, u_height, asset.id if asset else None)
        if has_conflict:
            cabinet_id = None
            u_position = None
            u_height = None

    specs = {
        "power_device_id": device.id,
        "datasource_id": datasource.id,
        "device_code": device.device_code,
        "load_subtype": device.load_subtype,
        "controllable_params": device.controllable_params or [],
    }

    if asset is None:
        asset = Asset(
            asset_code=str(asset_code),
            asset_name=str(_config_value(connection_config, "asset_name") or device.device_name),
            asset_type=_asset_type_for_device(device.device_type),
            brand=template.manufacturer,
            model=template.model,
            cabinet_id=cabinet_id,
            u_position=u_position,
            u_height=u_height,
            status=AssetStatus.in_use,
            specifications=json.dumps(specs, ensure_ascii=False),
            remark="Auto-created from protocol-template datasource",
        )
        db.add(asset)
    else:
        asset.asset_name = str(_config_value(connection_config, "asset_name") or asset.asset_name or device.device_name)
        asset.asset_type = _asset_type_for_device(device.device_type)
        asset.brand = asset.brand or template.manufacturer
        asset.model = asset.model or template.model
        asset.status = AssetStatus.in_use
        if cabinet_id:
            asset.cabinet_id = cabinet_id
            asset.u_position = u_position
            asset.u_height = u_height
        asset.specifications = json.dumps(specs, ensure_ascii=False)

    await db.flush()
    return asset


def _point_id(point_cfg: dict[str, Any]) -> str:
    return str(point_cfg.get("point_id") or "").strip().lower()


def _point_category(point_cfg: dict[str, Any]) -> str:
    return str(point_cfg.get("category") or "").strip().lower()


def _point_unit(point_cfg: dict[str, Any]) -> str:
    return str(point_cfg.get("unit") or "").strip().lower()


def _find_by_ids(bindings: Sequence[PointBinding], candidates: Sequence[str]) -> Point | None:
    by_id = {_point_id(point_cfg): point for point_cfg, point in bindings if _point_id(point_cfg)}
    for candidate in candidates:
        point = by_id.get(candidate)
        if point:
            return point
    return None


def _looks_like_electrical_power(point_cfg: dict[str, Any]) -> bool:
    point_id = _point_id(point_cfg)
    category = _point_category(point_cfg)
    unit = _point_unit(point_cfg)
    name = str(point_cfg.get("name") or "").lower()

    if "frequency" in point_id or "frequency" in name:
        return False
    if "cooling_capacity" in point_id or category == "cooling":
        return False
    return unit in {"kw", "w"} and ("power" in point_id or "power" in name or category == "power")


def _looks_like_energy(point_cfg: dict[str, Any]) -> bool:
    point_id = _point_id(point_cfg)
    unit = _point_unit(point_cfg)
    name = str(point_cfg.get("name") or "").lower()
    return unit == "kwh" or "energy" in point_id or "energy" in name


def _fallback_find(bindings: Sequence[PointBinding], predicate) -> Point | None:
    for point_cfg, point in bindings:
        if predicate(point_cfg):
            return point
    return None


def _select_power_device_points(device_type: str, bindings: Sequence[PointBinding]) -> dict[str, int | None]:
    if device_type == "UPS":
        power_point = _find_by_ids(
            bindings,
            [
                "output_active_power_total",
                "total_output_active_power",
                "output_active_power",
                "output_active_power_a",
                "output_active_power_b",
                "output_active_power_c",
            ],
        ) or _fallback_find(bindings, _looks_like_electrical_power)
        voltage_point = _find_by_ids(bindings, ["output_voltage_a", "input_voltage_a"])
        current_point = _find_by_ids(bindings, ["output_current_a", "input_current_a"])
        energy_point = _find_by_ids(bindings, ["cumulative_energy", "total_energy", "output_energy"]) or _fallback_find(
            bindings, _looks_like_energy
        )
        pf_point = _find_by_ids(bindings, ["output_power_factor", "power_factor", "input_power_factor"])
    elif device_type == "AC":
        power_point = _find_by_ids(
            bindings,
            ["active_power", "total_active_power", "input_active_power", "running_power", "compressor_power"],
        ) or _fallback_find(bindings, _looks_like_electrical_power)
        voltage_point = _find_by_ids(bindings, ["ab_line_voltage", "input_voltage", "line_voltage"])
        current_point = _find_by_ids(bindings, ["input_current", "compressor_current", "running_current"])
        energy_point = _find_by_ids(bindings, ["cumulative_energy", "total_energy"]) or _fallback_find(
            bindings, _looks_like_energy
        )
        pf_point = _find_by_ids(bindings, ["power_factor", "input_power_factor"])
    else:
        power_point = _fallback_find(bindings, _looks_like_electrical_power)
        voltage_point = _find_by_ids(bindings, ["voltage", "input_voltage", "line_voltage"])
        current_point = _find_by_ids(bindings, ["current", "input_current"])
        energy_point = _fallback_find(bindings, _looks_like_energy)
        pf_point = _find_by_ids(bindings, ["power_factor", "pf"])

    return {
        "power_point_id": power_point.id if power_point else None,
        "energy_point_id": energy_point.id if energy_point else None,
        "voltage_point_id": voltage_point.id if voltage_point else None,
        "current_point_id": current_point.id if current_point else None,
        "pf_point_id": pf_point.id if pf_point else None,
    }


async def bind_template_datasource_to_power_device(
    db: AsyncSession,
    *,
    template: DeviceTemplate,
    datasource: DataSource,
    point_bindings: Sequence[PointBinding],
) -> PowerDevice | None:
    """Create/update the PowerDevice represented by a structured protocol template."""
    bindings = [(point_cfg, point) for point_cfg, point in point_bindings if point is not None]
    if not bindings:
        return None

    device_type = infer_template_power_device_type(template)
    if device_type == "OTHER":
        return None

    extra_config = template.extra_config or {}
    default_connection_config = (
        extra_config.get("default_connection_config", {}) if isinstance(extra_config, dict) else {}
    )
    connection_config = {
        **(default_connection_config if isinstance(default_connection_config, dict) else {}),
        **(datasource.connection_config or {}),
    }
    device_code = _normalize_device_code(
        _config_value(connection_config, "device_code", "power_device_code"),
        fallback=f"DS-{datasource.id}",
    )

    result = await db.execute(select(PowerDevice).where(PowerDevice.device_code == device_code))
    device = result.scalar_one_or_none()

    device_name = str(_config_value(connection_config, "device_name", "power_device_name") or datasource.name)
    rated_power = _float_or_none(_config_value(connection_config, "rated_power", "nominal_power"))
    rated_voltage = _float_or_none(_config_value(connection_config, "rated_voltage", "nominal_voltage"))
    rated_current = _float_or_none(_config_value(connection_config, "rated_current", "nominal_current"))
    area_code = str(_config_value(connection_config, "area_code") or "A1")[:10]
    configured_subtype = _config_value(connection_config, "load_subtype")
    controllable_params = _as_list(_config_value(connection_config, "controllable_params", "control_params"))
    thermal_storage_config = connection_config.get("thermal_storage_config")
    flexibility_factor = _float_or_none(_config_value(connection_config, "flexibility_factor"))

    if device is None:
        device = PowerDevice(
            device_code=device_code,
            device_name=device_name,
            device_type=device_type,
            rated_power=rated_power,
            rated_voltage=rated_voltage,
            rated_current=rated_current,
            area_code=area_code,
            is_metered=True,
            is_it_load=False,
            is_critical=device_type == "UPS",
            description=f"Auto-created from template {template.name} and datasource {datasource.name}",
        )
        db.add(device)
        await db.flush()
    else:
        device.device_name = device_name
        device.device_type = device_type
        if rated_power is not None:
            device.rated_power = rated_power
        if rated_voltage is not None:
            device.rated_voltage = rated_voltage
        if rated_current is not None:
            device.rated_current = rated_current
        device.area_code = area_code
        device.is_enabled = True

    if configured_subtype:
        device.load_subtype = str(configured_subtype)
    else:
        device.load_subtype = infer_load_subtype(device)
    device.controllable_params = controllable_params or default_controllable_params_for_subtype(device.load_subtype)
    if isinstance(thermal_storage_config, dict):
        device.thermal_storage_config = thermal_storage_config
    if flexibility_factor is not None:
        device.flexibility_factor = flexibility_factor

    selected_points = _select_power_device_points(device_type, bindings)
    for field, point_id in selected_points.items():
        if point_id is not None:
            setattr(device, field, point_id)

    for _, point in bindings:
        point.energy_device_id = device.id

    await _upsert_asset_for_power_device(
        db,
        template=template,
        datasource=datasource,
        device=device,
        connection_config=connection_config,
    )

    await DeviceConfigAutoGenerator(db).generate_configs_for_device(device, force=False)
    await db.flush()
    return device
