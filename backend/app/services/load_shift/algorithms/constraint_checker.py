"""
Constraint Checker - Validate shift plan constraints
约束检查器 - 验证转移计划约束
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, time
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load_shift import ShiftConstraint, CoolingLinkageConfig
from app.models.energy import PowerDevice, DeviceShiftConfig
from app.schemas.load_shift import (
    ConstraintType,
    ConstraintCheckResult,
    FeasibilityAnalysisRequest
)

logger = logging.getLogger(__name__)


class ConstraintChecker:
    """Constraint checker - 约束检查器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _cfg(constraint: ShiftConstraint) -> Dict[str, Any]:
        """统一读取约束配置，兼容旧字段。"""
        cfg = getattr(constraint, "constraint_config", None)
        if isinstance(cfg, dict):
            return cfg
        old_cfg = getattr(constraint, "constraint_params", None)
        return old_cfg if isinstance(old_cfg, dict) else {}

    async def _get_dynamic_cooling_ratio(self, zone_id_raw: Any) -> Optional[float]:
        """
        获取动态制冷可转移比例（TCL/THM）

        Args:
            zone_id_raw: 从约束配置中获取的 cooling_zone_id（可能为 None/str/int）

        Returns:
            float: 动态比例（0~1），或 None（调用方应回退到固定值）
        """
        if zone_id_raw is None:
            return None

        try:
            zone_id = int(zone_id_raw)
        except (ValueError, TypeError):
            return None

        try:
            # 检查 precool_enabled 特性开关
            result = await self.db.execute(
                select(CoolingLinkageConfig)
                .where(CoolingLinkageConfig.cooling_zone_id == zone_id)
            )
            linkage_config = result.scalar_one_or_none()

            if linkage_config is None or not getattr(linkage_config, 'precool_enabled', False):
                return None

            # 延迟导入避免循环依赖
            from app.services.datacenter_shift_strategy import calculate_shiftable_power_for_zone

            calc_result = await calculate_shiftable_power_for_zone(zone_id, self.db)

            if "error" in calc_result:
                logger.warning(
                    f"Zone {zone_id} 动态制冷比例计算失败: {calc_result.get('error')}, "
                    f"详情: {calc_result.get('details', '')}, 回退到固定比例"
                )
                return None

            ratio = calc_result.get("shiftable_ratio")
            if ratio is not None:
                logger.info(f"Zone {zone_id} 使用动态制冷比例: {ratio:.4f} (方法: {calc_result.get('method', 'unknown')})")
                return float(ratio)

            return None
        except Exception as e:
            logger.warning(f"Zone {zone_id_raw} 动态制冷比例查询异常: {e}, 回退到固定比例")
            return None

    @staticmethod
    def _estimate_device_power(device: PowerDevice) -> float:
        """估算设备当前功率（无实时点位时回退到额定功率×负载率）。"""
        rated = float(device.rated_power or 0)
        if rated <= 0:
            return 0.0
        if device.avg_load_rate is not None:
            return rated * max(0.0, min(float(device.avg_load_rate) / 100.0, 1.5))
        return rated * 0.6

    @staticmethod
    def _device_bucket(device: PowerDevice) -> str:
        """将设备归类到 IT/COOLING/DISTRIBUTION/OTHER。"""
        dtype = (device.device_type or "").upper()

        if dtype in {"IT", "IT_SERVER", "IT_STORAGE", "NETWORK_SWITCH", "CORE_ROUTER"}:
            return "it"
        if dtype in {"AC", "HVAC", "CHILLER", "COOLING_TOWER", "CT", "PUMP", "PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR"}:
            return "cooling"
        if dtype in {"UPS", "PDU", "PDB", "DISTRIBUTION", "SWITCHGEAR", "TRANSFORMER"}:
            return "distribution"
        return "other"

    async def _load_all_enabled_devices(self) -> List[PowerDevice]:
        """加载全站启用设备，用于站级约束（IT占比、UPS容量）计算。"""
        result = await self.db.execute(select(PowerDevice).where(PowerDevice.is_enabled == True))
        return result.scalars().all()

    async def check_all_constraints(
        self,
        request: FeasibilityAnalysisRequest,
        device_ids: List[int]
    ) -> ConstraintCheckResult:
        """
        Check all constraints for shift plan - 检查所有约束
        
        Args:
            request: Feasibility analysis request
            device_ids: List of device IDs to check
            
        Returns:
            Constraint check result
        """
        violated_constraints = []
        warnings = []
        constraint_details = {}

        # Load all active constraints
        constraints = await self._load_constraints()
        
        # Load device information
        devices = await self._load_devices(device_ids)
        device_configs = await self._load_device_configs(device_ids)
        
        # Check each constraint type
        power_result = await self._check_power_constraints(
            request, devices, device_configs, constraints
        )
        if not power_result["is_valid"]:
            violated_constraints.extend(power_result["violations"])
        warnings.extend(power_result.get("warnings", []))
        constraint_details["power"] = power_result
        
        time_result = await self._check_time_constraints(
            request, devices, device_configs, constraints
        )
        if not time_result["is_valid"]:
            violated_constraints.extend(time_result["violations"])
        warnings.extend(time_result.get("warnings", []))
        constraint_details["time"] = time_result
        
        device_result = await self._check_device_constraints(
            request, devices, device_configs, constraints
        )
        if not device_result["is_valid"]:
            violated_constraints.extend(device_result["violations"])
        warnings.extend(device_result.get("warnings", []))
        constraint_details["device"] = device_result
        
        safety_result = await self._check_safety_constraints(
            request, devices, device_configs, constraints
        )
        if not safety_result["is_valid"]:
            violated_constraints.extend(safety_result["violations"])
        warnings.extend(safety_result.get("warnings", []))
        constraint_details["safety"] = safety_result
        
        # Overall result
        is_valid = len(violated_constraints) == 0
        
        return ConstraintCheckResult(
            is_valid=is_valid,
            violated_constraints=violated_constraints,
            warnings=warnings,
            constraint_details=constraint_details
        )

    async def _load_constraints(self) -> List[ShiftConstraint]:
        """Load all active constraints - 加载所有活跃约束"""
        result = await self.db.execute(
            select(ShiftConstraint).where(ShiftConstraint.is_enabled == True)
        )
        return result.scalars().all()

    async def _load_devices(self, device_ids: List[int]) -> List[PowerDevice]:
        """Load device information - 加载设备信息"""
        result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id.in_(device_ids))
        )
        return result.scalars().all()

    async def _load_device_configs(self, device_ids: List[int]) -> List[DeviceShiftConfig]:
        """Load device shift configurations - 加载设备转移配置"""
        result = await self.db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id.in_(device_ids))
        )
        return result.scalars().all()

    async def _check_power_constraints(
        self,
        request: FeasibilityAnalysisRequest,
        devices: List[PowerDevice],
        device_configs: List[DeviceShiftConfig],
        constraints: List[ShiftConstraint]
    ) -> Dict[str, Any]:
        """
        Check power constraints - 检查功率约束
        
        Constraints:
        - max_shift_power: Maximum shift power limit
        - min_shift_power: Minimum shift power requirement
        - max_ramp_rate: Maximum power ramp rate (kW/min)
        - safety_factor: Safety factor (default 0.85)
        """
        violations = []
        warnings = []
        
        # Get power constraints
        power_constraints = [c for c in constraints if c.constraint_type == ConstraintType.POWER]
        
        # Calculate total available power
        total_available_power = sum(d.rated_power or 0 for d in devices)
        
        # Apply safety factor (default 0.85)
        safety_factor = 0.85
        for constraint in power_constraints:
            if "safety_factor" in constraint.constraint_config:
                safety_factor = constraint.constraint_config["safety_factor"]
                break
        
        safe_shift_power = total_available_power * safety_factor
        
        # Check max_shift_power
        for constraint in power_constraints:
            if "max_shift_power" in constraint.constraint_config:
                max_shift_power = constraint.constraint_config["max_shift_power"]
                if request.target_shift_power > max_shift_power:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "power",
                        "violation_type": "max_shift_power_exceeded",
                        "message": f"目标转移功率 {request.target_shift_power} kW 超过最大限制 {max_shift_power} kW",
                        "current_value": request.target_shift_power,
                        "limit_value": max_shift_power
                    })
        
        # Check min_shift_power
        for constraint in power_constraints:
            if "min_shift_power" in constraint.constraint_config:
                min_shift_power = constraint.constraint_config["min_shift_power"]
                if request.target_shift_power < min_shift_power:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "power",
                        "violation_type": "min_shift_power_not_met",
                        "message": f"目标转移功率 {request.target_shift_power} kW 低于最小要求 {min_shift_power} kW",
                        "current_value": request.target_shift_power,
                        "limit_value": min_shift_power
                    })
        
        # Check safety factor
        if request.target_shift_power > safe_shift_power:
            warnings.append(
                f"目标转移功率 {request.target_shift_power} kW 超过安全功率 {safe_shift_power:.2f} kW "
                f"(安全系数 {safety_factor})"
            )
        
        # Check max_ramp_rate
        for constraint in power_constraints:
            if "max_ramp_rate" in constraint.constraint_config:
                max_ramp_rate = constraint.constraint_config["max_ramp_rate"]
                # Assume 5-minute startup time (from technical doc)
                startup_time_minutes = 5
                required_ramp_rate = request.target_shift_power / startup_time_minutes
                
                if required_ramp_rate > max_ramp_rate:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "power",
                        "violation_type": "max_ramp_rate_exceeded",
                        "message": f"所需爬坡速率 {required_ramp_rate:.2f} kW/min 超过最大限制 {max_ramp_rate} kW/min",
                        "current_value": required_ramp_rate,
                        "limit_value": max_ramp_rate
                    })
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "total_available_power": total_available_power,
            "safe_shift_power": safe_shift_power,
            "safety_factor": safety_factor
        }

    async def _check_time_constraints(
        self,
        request: FeasibilityAnalysisRequest,
        devices: List[PowerDevice],
        device_configs: List[DeviceShiftConfig],
        constraints: List[ShiftConstraint]
    ) -> Dict[str, Any]:
        """
        Check time constraints - 检查时间约束
        
        Constraints:
        - min_continuous_runtime: Minimum continuous runtime (hours)
        - max_shift_duration: Maximum shift duration (hours)
        - allowed_hours: Allowed shift hours [0-23]
        - forbidden_hours: Forbidden shift hours [0-23]
        """
        violations = []
        warnings = []
        
        # Get time constraints
        time_constraints = [c for c in constraints if c.constraint_type == ConstraintType.TIME]
        
        # Check allowed/forbidden hours
        shift_hour = request.shift_date.hour if hasattr(request.shift_date, 'hour') else 0
        
        for constraint in time_constraints:
            if "allowed_hours" in constraint.constraint_config:
                allowed_hours = constraint.constraint_config["allowed_hours"]
                if shift_hour not in allowed_hours:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "time",
                        "violation_type": "not_in_allowed_hours",
                        "message": f"转移时段 {shift_hour}:00 不在允许的时段内",
                        "current_value": shift_hour,
                        "allowed_values": allowed_hours
                    })
            
            if "forbidden_hours" in constraint.constraint_config:
                forbidden_hours = constraint.constraint_config["forbidden_hours"]
                if shift_hour in forbidden_hours:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "time",
                        "violation_type": "in_forbidden_hours",
                        "message": f"转移时段 {shift_hour}:00 在禁止的时段内",
                        "current_value": shift_hour,
                        "forbidden_values": forbidden_hours
                    })
        
        # Check device-specific time constraints
        config_dict = {c.device_id: c for c in device_configs}
        for device in devices:
            config = config_dict.get(device.id)
            if not config:
                continue
            
            # Check allowed_shift_hours
            if config.allowed_shift_hours:
                if shift_hour not in config.allowed_shift_hours:
                    warnings.append(
                        f"设备 {device.device_name} 在 {shift_hour}:00 不在允许转移时段内"
                    )
            
            # Check forbidden_shift_hours
            if config.forbidden_shift_hours:
                if shift_hour in config.forbidden_shift_hours:
                    warnings.append(
                        f"设备 {device.device_name} 在 {shift_hour}:00 处于禁止转移时段"
                    )
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "shift_hour": shift_hour
        }

    async def _check_device_constraints(
        self,
        request: FeasibilityAnalysisRequest,
        devices: List[PowerDevice],
        device_configs: List[DeviceShiftConfig],
        constraints: List[ShiftConstraint]
    ) -> Dict[str, Any]:
        """
        Check device constraints - 检查设备约束
        
        Constraints:
        - max_devices: Maximum number of devices
        - allow_critical_devices: Allow critical devices
        - startup_time: Device startup time (minutes)
        """
        violations = []
        warnings = []
        
        # Get device constraints
        device_constraints = [c for c in constraints if c.constraint_type == ConstraintType.DEVICE]
        
        # Check max_devices
        for constraint in device_constraints:
            if "max_devices" in constraint.constraint_config:
                max_devices = constraint.constraint_config["max_devices"]
                if len(devices) > max_devices:
                    violations.append({
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "device",
                        "violation_type": "max_devices_exceeded",
                        "message": f"设备数量 {len(devices)} 超过最大限制 {max_devices}",
                        "current_value": len(devices),
                        "limit_value": max_devices
                    })
        
        # Check critical devices
        config_dict = {c.device_id: c for c in device_configs}
        critical_devices = []
        
        for device in devices:
            config = config_dict.get(device.id)
            if config and config.is_critical:
                critical_devices.append(device)
        
        if critical_devices:
            for constraint in device_constraints:
                if "allow_critical_devices" in constraint.constraint_config:
                    allow_critical = constraint.constraint_config["allow_critical_devices"]
                    if not allow_critical:
                        violations.append({
                            "constraint_id": constraint.id,
                            "constraint_name": constraint.constraint_name,
                            "constraint_type": "device",
                            "violation_type": "critical_devices_not_allowed",
                            "message": f"不允许转移关键设备，但选中了 {len(critical_devices)} 台关键设备",
                            "critical_devices": [d.device_name for d in critical_devices]
                        })
        
        # Check device shiftability
        non_shiftable_devices = []
        for device in devices:
            config = config_dict.get(device.id)
            if config and not config.is_shiftable:
                non_shiftable_devices.append(device)
        
        if non_shiftable_devices:
            violations.append({
                "constraint_type": "device",
                "violation_type": "non_shiftable_devices",
                "message": f"选中了 {len(non_shiftable_devices)} 台不可转移设备",
                "non_shiftable_devices": [d.device_name for d in non_shiftable_devices]
            })
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "total_devices": len(devices),
            "critical_devices_count": len(critical_devices),
            "non_shiftable_devices_count": len(non_shiftable_devices)
        }

    async def _check_safety_constraints(
        self,
        request: FeasibilityAnalysisRequest,
        devices: List[PowerDevice],
        device_configs: List[DeviceShiftConfig],
        constraints: List[ShiftConstraint]
    ) -> Dict[str, Any]:
        """
        Check safety constraints - 检查安全约束
        
        Constraints:
        - safety_factor: Safety factor (default 0.85)
        - min_ups_capacity_ratio: Minimum UPS capacity ratio
        - max_it_load_ratio: Maximum IT load ratio
        """
        violations = []
        warnings = []
        
        # 兼容三类来源：
        # 1) SAFETY（旧模型）
        # 2) DATACENTER_LOAD（新模型：IT占比）
        # 3) UPS_CAPACITY（新模型：UPS容量）
        safety_constraints = [c for c in constraints if c.constraint_type == ConstraintType.SAFETY]
        dc_constraints = [c for c in constraints if c.constraint_type == ConstraintType.DATACENTER_LOAD]
        ups_constraints = [c for c in constraints if c.constraint_type == ConstraintType.UPS_CAPACITY]

        all_devices = await self._load_all_enabled_devices()
        selected_device_ids = {d.id for d in devices}

        # 站级功率分解
        total_power = 0.0
        it_power = 0.0
        cooling_power = 0.0
        distribution_power = 0.0
        other_power = 0.0
        ups_capacity = 0.0

        for dev in all_devices:
            p = self._estimate_device_power(dev)
            total_power += p

            bucket = self._device_bucket(dev)
            if bucket == "it":
                it_power += p
            elif bucket == "cooling":
                cooling_power += p
            elif bucket == "distribution":
                distribution_power += p
            else:
                other_power += p

            if (dev.device_type or "").upper() == "UPS":
                ups_capacity += float(dev.rated_power or 0.0)

        # 对转移目标按“加法保守估计”做峰值校验
        projected_peak_power = total_power + float(request.target_shift_power)

        # ---------- IT 负载占比 + 最大可转移功率 ----------
        merged_dc_constraints = dc_constraints + [
            c for c in safety_constraints if "max_it_load_ratio" in self._cfg(c)
        ]

        for constraint in merged_dc_constraints:
            cfg = self._cfg(constraint)

            # 比例配置：优先显式配置，否则用实时占比估计
            current_cooling_ratio = (cooling_power / total_power) if total_power > 0 else 0.0
            current_other_ratio = (other_power / total_power) if total_power > 0 else 0.0
            current_it_ratio = (it_power / total_power) if total_power > 0 else 0.0

            it_min = float(cfg.get("it_load_ratio_min", 0.60))
            it_max = float(cfg.get("it_load_ratio_max", cfg.get("max_it_load_ratio", 0.80)))
            cooling_ratio = float(cfg.get("cooling_ratio", current_cooling_ratio))
            other_ratio = float(cfg.get("other_ratio", current_other_ratio))
            cooling_transferable_ratio = float(cfg.get("cooling_transferable_ratio", 0.40))
            # 动态制冷比例: 如果配置了 cooling_zone_id 且 precool_enabled，使用 TCL/THM 动态计算
            dynamic_ratio = await self._get_dynamic_cooling_ratio(cfg.get("cooling_zone_id"))
            if dynamic_ratio is not None:
                cooling_transferable_ratio = dynamic_ratio
            other_transferable_ratio = float(cfg.get("other_transferable_ratio", 0.60))

            max_transfer_power = total_power * (
                cooling_ratio * cooling_transferable_ratio + other_ratio * other_transferable_ratio
            )

            # IT占比边界校验
            if total_power > 0 and (current_it_ratio < it_min or current_it_ratio > it_max):
                violations.append(
                    {
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "datacenter_load",
                        "violation_type": "it_load_ratio_out_of_range",
                        "message": (
                            f"IT负载占比 {current_it_ratio:.2%} 不在允许区间 [{it_min:.2%}, {it_max:.2%}]"
                        ),
                        "current_value": round(current_it_ratio, 4),
                        "limit_value": {"min": it_min, "max": it_max},
                    }
                )

            # 最大可转移功率校验
            if request.target_shift_power > max_transfer_power:
                violations.append(
                    {
                        "constraint_id": constraint.id,
                        "constraint_name": constraint.constraint_name,
                        "constraint_type": "datacenter_load",
                        "violation_type": "max_transfer_power_exceeded",
                        "message": (
                            f"目标转移功率 {request.target_shift_power:.2f} kW 超过算力中心可转移上限 "
                            f"{max_transfer_power:.2f} kW"
                        ),
                        "current_value": float(request.target_shift_power),
                        "limit_value": round(max_transfer_power, 2),
                        "suggested_max_shift_power": round(max_transfer_power, 2),
                    }
                )

        # ---------- UPS 容量约束 ----------
        merged_ups_constraints = ups_constraints + [
            c for c in safety_constraints if "min_ups_capacity_ratio" in self._cfg(c)
        ]

        for constraint in merged_ups_constraints:
            cfg = self._cfg(constraint)

            # 两套参数兼容：
            # - 新：safety_factor（默认0.8）
            # - 旧：min_ups_capacity_ratio（最小剩余比例） -> 转换为 safety_factor=1-ratio
            safety_factor = cfg.get("safety_factor")
            if safety_factor is None:
                min_ups_ratio = float(cfg.get("min_ups_capacity_ratio", 0.2))
                safety_factor = 1.0 - min_ups_ratio
            safety_factor = float(safety_factor)
            safety_factor = max(0.1, min(0.99, safety_factor))

            max_allowed_ups_load = ups_capacity * safety_factor
            overload = projected_peak_power > max_allowed_ups_load if ups_capacity > 0 else True
            suggested_max_shift_power = max(0.0, max_allowed_ups_load - total_power)

            auto_adjust = bool(cfg.get("auto_adjust", True))
            reject_on_exceed = bool(cfg.get("reject_on_exceed", True))

            if overload:
                if reject_on_exceed:
                    violations.append(
                        {
                            "constraint_id": constraint.id,
                            "constraint_name": constraint.constraint_name,
                            "constraint_type": "ups_capacity",
                            "violation_type": "ups_capacity_exceeded",
                            "message": (
                                f"转移后峰值 {projected_peak_power:.2f} kW 超过 UPS 允许上限 "
                                f"{max_allowed_ups_load:.2f} kW（安全系数 {safety_factor:.2f}）"
                            ),
                            "current_value": round(projected_peak_power, 2),
                            "limit_value": round(max_allowed_ups_load, 2),
                            "suggested_max_shift_power": round(suggested_max_shift_power, 2),
                        }
                    )
                elif auto_adjust:
                    warnings.append(
                        (
                            f"UPS容量接近上限，建议将目标转移功率从 {request.target_shift_power:.2f} kW "
                            f"调整为 {suggested_max_shift_power:.2f} kW"
                        )
                    )

        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "load_breakdown": {
                "total_power": round(total_power, 2),
                "it_power": round(it_power, 2),
                "cooling_power": round(cooling_power, 2),
                "distribution_power": round(distribution_power, 2),
                "other_power": round(other_power, 2),
                "it_ratio": round((it_power / total_power), 4) if total_power > 0 else 0.0,
            },
            "ups_check": {
                "ups_capacity": round(ups_capacity, 2),
                "projected_peak_power": round(projected_peak_power, 2),
            },
            "selected_devices_count": len(selected_device_ids),
        }
