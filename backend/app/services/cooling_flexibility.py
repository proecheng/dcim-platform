"""Cooling and thermal-storage flexibility profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FlexibilityProfile:
    subtype: str
    label: str
    base_ratio: float
    max_ratio: float
    default_min_power_ratio: float
    default_variability_ratio: float
    default_peak_ratio: float
    default_controls: tuple[str, ...]


CONTROL_LABELS = {
    "temperature_setpoint": "温度设定",
    "humidity_setpoint": "湿度设定",
    "power_switch": "开关机控制",
    "supply_air_temperature": "送风温度",
    "return_air_temperature": "回风温度",
    "chilled_water_supply_temperature": "冷冻水供水温度",
    "chilled_water_return_temperature": "冷冻水回水温度",
    "chilled_water_valve": "冷冻水阀门开度",
    "fan_speed": "风机转速",
    "indoor_fan_output": "室内风机输出",
    "compressor_frequency": "压缩机频率",
    "cooling_output": "制冷输出",
    "pump_frequency": "水泵变频",
    "flow_rate": "水流量",
    "cooling_tower_fan": "冷却塔风机",
    "storage_charge": "蓄冷充冷",
    "storage_discharge": "蓄冷放冷",
    "storage_soc": "蓄冷余量",
    "brightness": "照明亮度",
}


PROFILES: dict[str, FlexibilityProfile] = {
    "row_ac": FlexibilityProfile(
        "row_ac",
        "行级/微模块空调",
        0.24,
        0.35,
        0.42,
        0.30,
        0.46,
        ("temperature_setpoint", "fan_speed", "cooling_output"),
    ),
    "cabinet_ac": FlexibilityProfile(
        "cabinet_ac",
        "柜类空调",
        0.20,
        0.30,
        0.50,
        0.24,
        0.42,
        ("temperature_setpoint", "fan_speed", "compressor_frequency"),
    ),
    "room_ac": FlexibilityProfile(
        "room_ac",
        "房间级空调",
        0.22,
        0.32,
        0.48,
        0.26,
        0.43,
        ("temperature_setpoint", "fan_speed"),
    ),
    "chilled_water_terminal": FlexibilityProfile(
        "chilled_water_terminal",
        "冷冻水末端",
        0.34,
        0.50,
        0.35,
        0.42,
        0.55,
        ("supply_air_temperature", "chilled_water_valve", "fan_speed"),
    ),
    "water_cooled_chiller": FlexibilityProfile(
        "water_cooled_chiller",
        "大型水冷冷机",
        0.22,
        0.34,
        0.62,
        0.28,
        0.50,
        (
            "chilled_water_supply_temperature",
            "chilled_water_return_temperature",
            "compressor_frequency",
            "pump_frequency",
            "flow_rate",
        ),
    ),
    "pump_vfd": FlexibilityProfile(
        "pump_vfd",
        "变频水泵",
        0.40,
        0.60,
        0.30,
        0.48,
        0.55,
        ("pump_frequency", "flow_rate"),
    ),
    "cooling_tower": FlexibilityProfile(
        "cooling_tower",
        "冷却塔",
        0.30,
        0.45,
        0.42,
        0.36,
        0.50,
        ("cooling_tower_fan",),
    ),
    "thermal_storage": FlexibilityProfile(
        "thermal_storage",
        "蓄冷系统",
        0.60,
        0.85,
        0.15,
        0.70,
        0.75,
        ("storage_charge", "storage_discharge", "storage_soc", "pump_frequency", "flow_rate"),
    ),
    "lighting": FlexibilityProfile(
        "lighting",
        "照明",
        0.45,
        0.60,
        0.20,
        0.55,
        0.50,
        ("brightness",),
    ),
    "ups": FlexibilityProfile("ups", "UPS", 0.0, 0.0, 1.0, 0.0, 0.0, ()),
    "other": FlexibilityProfile("other", "其他设备", 0.12, 0.25, 0.70, 0.18, 0.35, ()),
}


DEVICE_TYPE_DEFAULT_SUBTYPE = {
    "AC": "row_ac",
    "HVAC": "chilled_water_terminal",
    "AHU": "chilled_water_terminal",
    "CHILLER": "water_cooled_chiller",
    "PUMP": "pump_vfd",
    "COOLING_TOWER": "cooling_tower",
    "LIGHT": "lighting",
    "LIGHTING": "lighting",
    "UPS": "ups",
}


def infer_load_subtype(device: Any) -> str:
    configured = getattr(device, "load_subtype", None)
    if configured:
        configured_key = str(configured).strip().lower()
        if configured_key in PROFILES:
            return configured_key

    device_type = str(getattr(device, "device_type", "") or "").upper()
    text = f"{getattr(device, 'device_code', '')} {getattr(device, 'device_name', '')} {getattr(device, 'description', '')}".lower()

    if any(k in text for k in ["蓄冷", "storage", "tes", "ice tank", "cold tank"]):
        return "thermal_storage"
    if any(k in text for k in ["冷却塔", "cooling tower"]):
        return "cooling_tower"
    if any(k in text for k in ["水泵", "pump", "chwp", "cwp"]):
        return "pump_vfd"
    if any(k in text for k in ["冷机", "冷水机", "chiller", "水冷"]):
        return "water_cooled_chiller"
    if any(k in text for k in ["冷冻水", "crah", "ahu", "回水", "chilled water"]):
        return "chilled_water_terminal"
    if any(k in text for k in ["fusioncol", "行级", "列间", "微模块", "in-row", "inrow"]):
        return "row_ac"
    if any(k in text for k in ["柜机", "柜类", "cabinet"]):
        return "cabinet_ac"
    if any(k in text for k in ["房间级", "room ac", "crac"]):
        return "room_ac"

    return DEVICE_TYPE_DEFAULT_SUBTYPE.get(device_type, "other")


def get_profile(subtype: str) -> FlexibilityProfile:
    return PROFILES.get(subtype, PROFILES["other"])


def normalize_control_params(params: Any, profile: FlexibilityProfile) -> list[str]:
    if isinstance(params, dict):
        raw_items = params.get("modes") or params.get("items") or params.get("controls") or []
    elif isinstance(params, list):
        raw_items = params
    else:
        raw_items = []

    normalized: list[str] = []
    for item in raw_items:
        key = str(item.get("key") if isinstance(item, dict) else item).strip()
        if key and key not in normalized:
            normalized.append(key)

    return normalized or list(profile.default_controls)


def normalize_thermal_storage_config(config: Any) -> dict[str, float]:
    if not isinstance(config, dict):
        return {}

    def value(name: str, default: float = 0.0) -> float:
        raw = config.get(name, default)
        try:
            return float(raw or 0)
        except (TypeError, ValueError):
            return default

    capacity = value("capacity_kwh", value("capacity_ton_hour") * 3.516)
    return {
        "capacity_kwh": capacity,
        "max_discharge_kw": value("max_discharge_kw"),
        "max_charge_kw": value("max_charge_kw"),
        "roundtrip_efficiency": value("roundtrip_efficiency", 0.85) or 0.85,
        "discharge_efficiency": value("discharge_efficiency", 0.9) or 0.9,
        "equivalent_cop": value("equivalent_cop", 4.0) or 4.0,
        "auxiliary_power_kw": value("auxiliary_power_kw"),
        "equivalent_power_kw": value("equivalent_power_kw"),
        "usable_soc_min": value("usable_soc_min", 0.1),
        "usable_soc_max": value("usable_soc_max", 0.9),
    }


def control_score(control_params: list[str], profile: FlexibilityProfile) -> float:
    expected = set(profile.default_controls)
    known = {p for p in control_params if p in CONTROL_LABELS}
    overlap = len(known & expected)
    if not expected:
        return 1.0
    return min(1.25, 0.72 + overlap / max(len(expected), 1) * 0.38 + max(len(known) - overlap, 0) * 0.04)


def storage_ratio_limit(storage: dict[str, float], rated_power: float, duration_hours: float = 2.0) -> float | None:
    if rated_power <= 0 or not storage:
        return None

    discharge_kw = storage.get("max_discharge_kw") or 0
    capacity_kwh = storage.get("capacity_kwh") or 0
    usable_soc = max(0.0, (storage.get("usable_soc_max", 0.9) or 0.9) - (storage.get("usable_soc_min", 0.1) or 0.1))
    capacity_limited_kw = capacity_kwh * usable_soc / max(duration_hours, 0.25) if capacity_kwh > 0 else 0

    available_kw = discharge_kw if discharge_kw > 0 else capacity_limited_kw
    if capacity_limited_kw > 0:
        available_kw = min(available_kw, capacity_limited_kw) if available_kw > 0 else capacity_limited_kw
    if available_kw <= 0:
        return None

    equivalent_power_kw = storage.get("equivalent_power_kw") or 0
    if equivalent_power_kw <= 0:
        discharge_efficiency = max(0.1, min(1.0, storage.get("discharge_efficiency", 0.9) or 0.9))
        equivalent_cop = max(0.5, storage.get("equivalent_cop", 4.0) or 4.0)
        auxiliary_power_kw = max(0.0, storage.get("auxiliary_power_kw", 0.0) or 0.0)
        equivalent_power_kw = max(0.0, available_kw * discharge_efficiency / equivalent_cop - auxiliary_power_kw)

    if equivalent_power_kw <= 0:
        return None
    return min(0.95, equivalent_power_kw / rated_power)


def default_controllable_params_for_subtype(subtype: str) -> list[str]:
    return list(get_profile(subtype).default_controls)
