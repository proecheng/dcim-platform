"""Cooling dispatch strategy helpers for load-shift recommendations."""

from __future__ import annotations

from typing import Any


VALLEY_HOURS = [0, 1, 2, 3, 4, 5, 6, 7, 22, 23]
PEAK_HOURS = [9, 10, 11, 17, 18, 19, 20]
FLAT_HOURS = [8, 12, 13, 14, 15, 16, 21]

COOLING_SUBTYPES = {
    "row_ac",
    "cabinet_ac",
    "room_ac",
    "chilled_water_terminal",
    "water_cooled_chiller",
    "pump_vfd",
    "cooling_tower",
    "thermal_storage",
}


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _has_control(control_params: list[str], *keys: str) -> bool:
    controls = set(control_params or [])
    return bool(controls & set(keys))


def _storage_metrics(
    storage: dict[str, float],
    *,
    rated_power: float,
    recommended_kw: float,
    peak_duration_hours: float = 4.0,
    charge_duration_hours: float = 6.0,
) -> dict[str, float]:
    if not storage:
        return {}

    capacity_kwh = max(0.0, storage.get("capacity_kwh", 0.0) or 0.0)
    soc_min = storage.get("usable_soc_min", 0.1) or 0.1
    soc_max = storage.get("usable_soc_max", 0.9) or 0.9
    usable_soc = max(0.0, min(1.0, soc_max) - max(0.0, soc_min))
    usable_cooling_kwh = capacity_kwh * usable_soc

    max_discharge_kw = max(0.0, storage.get("max_discharge_kw", 0.0) or 0.0)
    capacity_discharge_kw = usable_cooling_kwh / max(peak_duration_hours, 0.25) if usable_cooling_kwh else 0.0
    discharge_kwth = max_discharge_kw if max_discharge_kw else capacity_discharge_kw
    if capacity_discharge_kw:
        discharge_kwth = min(discharge_kwth, capacity_discharge_kw) if discharge_kwth else capacity_discharge_kw

    discharge_efficiency = max(0.1, min(1.0, storage.get("discharge_efficiency", 0.9) or 0.9))
    equivalent_cop = max(0.5, storage.get("equivalent_cop", 4.0) or 4.0)
    auxiliary_power_kw = max(0.0, storage.get("auxiliary_power_kw", 0.0) or 0.0)
    equivalent_reduction_kw = max(0.0, discharge_kwth * discharge_efficiency / equivalent_cop - auxiliary_power_kw)

    max_charge_kw = max(0.0, storage.get("max_charge_kw", 0.0) or 0.0)
    charge_kwth = (
        max_charge_kw
        if max_charge_kw
        else (usable_cooling_kwh / max(charge_duration_hours, 0.25) if usable_cooling_kwh else 0.0)
    )

    return {
        "usable_cooling_kwh": _round(usable_cooling_kwh),
        "discharge_kwth": _round(discharge_kwth),
        "charge_kwth": _round(charge_kwth),
        "equivalent_reduction_kw": _round(equivalent_reduction_kw),
        "equivalent_ratio": _round(equivalent_reduction_kw / rated_power, 3) if rated_power > 0 else 0.0,
        "recommended_kw": _round(recommended_kw),
        "peak_duration_hours": peak_duration_hours,
        "charge_duration_hours": charge_duration_hours,
    }


def _pump_frequency_target(recommended_ratio: float) -> dict[str, float]:
    ratio = max(0.0, min(0.75, recommended_ratio))
    target_fraction = max(0.65, (1.0 - ratio) ** (1.0 / 3.0))
    return {
        "target_frequency_percent": _round(target_fraction * 100, 1),
        "power_ratio": _round(target_fraction**3, 3),
    }


def build_cooling_dispatch_strategy(
    *,
    device: Any,
    load_subtype: str,
    control_params: list[str],
    thermal_storage: dict[str, float],
    recommended_ratio: float,
    rated_power: float,
) -> dict[str, Any] | None:
    """Build an explainable cooling/thermal-storage dispatch strategy.

    The strategy is advisory; hard safety checks still come from temperature,
    redundancy, PUE, and device constraints.
    """
    device_type = str(getattr(device, "device_type", "") or "").upper()
    if load_subtype not in COOLING_SUBTYPES and device_type not in {
        "AC",
        "HVAC",
        "CHILLER",
        "PUMP",
        "COOLING_TOWER",
        "AHU",
    }:
        return None

    recommended_kw = max(0.0, rated_power * max(0.0, recommended_ratio))
    storage_metrics = _storage_metrics(
        thermal_storage,
        rated_power=rated_power,
        recommended_kw=recommended_kw,
    )

    steps: list[dict[str, Any]] = []
    formulas: list[dict[str, str]] = []
    interlocks = [
        "机柜进风温度不超过27℃，且保留2℃安全裕度",
        "N+1或2N冗余容量校验通过后才允许执行",
        "执行前确认冷机最小流量、水泵最小频率和阀门开度未触发保护",
    ]

    if load_subtype in {"row_ac", "cabinet_ac", "room_ac"}:
        if _has_control(control_params, "temperature_setpoint", "supply_air_temperature"):
            steps.append(
                {
                    "phase": "pre_cool",
                    "period": "低谷/平段",
                    "hours": VALLEY_HOURS[:8],
                    "action": "预冷并建立热惯性",
                    "target": "机柜进风温度接近22-24℃，峰前30-60分钟完成",
                    "controls": [
                        c
                        for c in control_params
                        if c in {"temperature_setpoint", "supply_air_temperature", "fan_speed"}
                    ],
                }
            )
            steps.append(
                {
                    "phase": "peak_relief",
                    "period": "尖峰/高峰",
                    "hours": PEAK_HOURS,
                    "action": "提高温度设定并降低压缩机/风机输出",
                    "target": f"削减约{_round(recommended_kw)} kW，温度设定每步0.5℃递增",
                    "controls": [
                        c
                        for c in control_params
                        if c in {"temperature_setpoint", "fan_speed", "cooling_output", "compressor_frequency"}
                    ],
                }
            )
        formulas.append(
            {
                "name": "温度设定削峰",
                "expression": "P_shift = P_rated * r_recommended",
                "meaning": "按推荐比例折算可调节电功率，并由温度约束限制上限",
            }
        )

    if load_subtype == "chilled_water_terminal":
        steps.extend(
            [
                {
                    "phase": "hydraulic_balance",
                    "period": "全日",
                    "hours": list(range(24)),
                    "action": "按末端阀门开度重置水流量和风机输出",
                    "target": "优先保持末端阀门在60%-85%区间，避免过流",
                    "controls": [c for c in control_params if c in {"chilled_water_valve", "fan_speed", "flow_rate"}],
                },
                {
                    "phase": "peak_relief",
                    "period": "尖峰/高峰",
                    "hours": PEAK_HOURS,
                    "action": "提高送风温度或限制阀门开度",
                    "target": f"削减约{_round(recommended_kw)} kW，保持回风温度和湿度边界",
                    "controls": [
                        c for c in control_params if c in {"supply_air_temperature", "chilled_water_valve", "fan_speed"}
                    ],
                },
            ]
        )

    if load_subtype == "water_cooled_chiller":
        steps.extend(
            [
                {
                    "phase": "valley_charge_or_precool",
                    "period": "深谷/低谷",
                    "hours": VALLEY_HOURS,
                    "action": "低价时段降低冷冻水供水温度用于预冷或蓄冷充冷",
                    "target": "供水温度按0.5℃步进，优先利用高COP运行窗口",
                    "controls": [
                        c
                        for c in control_params
                        if c in {"chilled_water_supply_temperature", "compressor_frequency", "storage_charge"}
                    ],
                },
                {
                    "phase": "peak_chw_reset",
                    "period": "尖峰/高峰",
                    "hours": PEAK_HOURS,
                    "action": "峰时提高冷冻水供水温度并限制冷机加载",
                    "target": f"供水温度上调1-2℃，目标削减约{_round(recommended_kw)} kW",
                    "controls": [
                        c
                        for c in control_params
                        if c in {"chilled_water_supply_temperature", "compressor_frequency", "pump_frequency"}
                    ],
                },
            ]
        )
        formulas.append(
            {
                "name": "冷冻水温度重置",
                "expression": "DeltaP ~= P_base * s_chw * DeltaT_chw",
                "meaning": "供水温度上调带来冷机功率下降，s_chw由现场标定或历史拟合",
            }
        )

    if load_subtype == "pump_vfd" or _has_control(control_params, "pump_frequency", "flow_rate"):
        pump_target = _pump_frequency_target(recommended_ratio)
        steps.append(
            {
                "phase": "pump_vfd_reset",
                "period": "高峰优先，全日可用",
                "hours": PEAK_HOURS + FLAT_HOURS,
                "action": "按压差/流量需求重置水泵变频",
                "target": f"频率约{pump_target['target_frequency_percent']}%，估算功率比{pump_target['power_ratio']}",
                "controls": [c for c in control_params if c in {"pump_frequency", "flow_rate"}],
            }
        )
        formulas.append(
            {
                "name": "泵/风机相似定律",
                "expression": "P2 / P1 ~= (f2 / f1)^3",
                "meaning": "变频泵和风机降频时，功率近似按频率三次方下降",
            }
        )

    if load_subtype == "cooling_tower" or _has_control(control_params, "cooling_tower_fan"):
        steps.append(
            {
                "phase": "condenser_water_reset",
                "period": "全日，按湿球温度修正",
                "hours": list(range(24)),
                "action": "重置冷却塔风机频率和冷凝水温度",
                "target": "湿球有利时降低冷凝温度，湿球不利时限制风机无效高转速",
                "controls": [c for c in control_params if c in {"cooling_tower_fan", "flow_rate"}],
            }
        )

    if load_subtype == "thermal_storage" or thermal_storage:
        steps.extend(
            [
                {
                    "phase": "storage_charge",
                    "period": "深谷/低谷",
                    "hours": VALLEY_HOURS,
                    "action": "蓄冷罐充冷并抬高峰时可用SOC",
                    "target": f"充冷功率约{storage_metrics.get('charge_kwth', 0)} kWth，SOC不超过上限",
                    "controls": [
                        c
                        for c in control_params
                        if c in {"storage_charge", "storage_soc", "pump_frequency", "flow_rate"}
                    ],
                },
                {
                    "phase": "storage_discharge",
                    "period": "尖峰/高峰",
                    "hours": PEAK_HOURS,
                    "action": "蓄冷罐放冷接入冷冻水循环，降低冷机电功率",
                    "target": (
                        f"放冷约{storage_metrics.get('discharge_kwth', 0)} kWth，"
                        f"等效削减{storage_metrics.get('equivalent_reduction_kw', 0)} kW"
                    ),
                    "controls": [
                        c
                        for c in control_params
                        if c in {"storage_discharge", "storage_soc", "pump_frequency", "flow_rate"}
                    ],
                },
            ]
        )
        formulas.append(
            {
                "name": "蓄冷等效削峰",
                "expression": "P_e = max(0, min(P_dis, E_usable/t) * eta_dis / COP - P_aux)",
                "meaning": "将蓄冷放冷能力折算为可替代的冷机电功率",
            }
        )
        formulas.append(
            {
                "name": "可用蓄冷量",
                "expression": "E_usable = E_capacity * (SOC_max - SOC_min)",
                "meaning": "由蓄冷罐容量和可用SOC窗口决定峰时可放冷能量",
            }
        )

    if not steps:
        return None

    return {
        "version": "cooling-dispatch-v1",
        "strategy_type": load_subtype,
        "recommended_shift_kw": _round(recommended_kw),
        "periods": {
            "valley_hours": VALLEY_HOURS,
            "peak_hours": PEAK_HOURS,
            "flat_hours": FLAT_HOURS,
        },
        "storage_metrics": storage_metrics,
        "steps": steps,
        "formulas": formulas,
        "interlocks": interlocks,
    }
