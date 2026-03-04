"""
Constraint Checker - Validate shift plan constraints
约束检查器 - 验证转移计划约束
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load_shift import ShiftConstraint
from app.models.energy import PowerDevice, DeviceShiftConfig
from app.schemas.load_shift import (
    ConstraintType,
    ConstraintCheckResult,
    FeasibilityAnalysisRequest
)


class ConstraintChecker:
    """Constraint checker - 约束检查器"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
        
        # Get safety constraints
        safety_constraints = [c for c in constraints if c.constraint_type == ConstraintType.SAFETY]
        
        # Check safety_factor (already checked in power constraints)
        # This is a placeholder for additional safety checks
        
        # Check UPS capacity
        for constraint in safety_constraints:
            if "min_ups_capacity_ratio" in constraint.constraint_config:
                min_ups_ratio = constraint.constraint_config["min_ups_capacity_ratio"]
                # TODO: Query actual UPS capacity and calculate ratio
                # For now, just add a warning
                warnings.append(
                    f"需要验证 UPS 容量比例是否满足最小要求 {min_ups_ratio}"
                )
        
        # Check IT load ratio
        for constraint in safety_constraints:
            if "max_it_load_ratio" in constraint.constraint_config:
                max_it_ratio = constraint.constraint_config["max_it_load_ratio"]
                # TODO: Query actual IT load and calculate ratio
                # For now, just add a warning
                warnings.append(
                    f"需要验证 IT 负载比例是否低于最大限制 {max_it_ratio}"
                )
        
        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings
        }
