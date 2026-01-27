"""
设备选择服务
Device Selector Service

提供参与优化的设备选择、能力查询、时段交集计算等功能
对应设计文档第五节"设备选择器设计"
"""
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models.energy import (
    PowerDevice, DeviceShiftConfig, LoadRegulationConfig
)


class DeviceSelectorService:
    """
    设备选择服务

    核心功能:
    1. 获取可参与优化的设备列表（含能力信息）
    2. 计算多设备可调时段交集
    3. 自动选择最优设备组合
    4. 验证设备选择可行性
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_available_devices(
        self,
        regulation_type: Optional[str] = None,
        execution_mode: Optional[str] = None,
        only_shiftable: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取可参与优化的设备列表

        Args:
            regulation_type: 调节类型过滤（temperature/brightness/load）
            execution_mode: 执行方式过滤（auto/manual）
            only_shiftable: 只显示可转移负荷的设备

        Returns:
            设备能力列表
        """
        devices = []

        # 1. 查询有调节配置的设备
        reg_query = (
            select(PowerDevice, LoadRegulationConfig)
            .join(LoadRegulationConfig, PowerDevice.id == LoadRegulationConfig.device_id)
            .where(
                and_(
                    PowerDevice.is_enabled == True,
                    LoadRegulationConfig.is_enabled == True
                )
            )
        )
        if regulation_type:
            reg_query = reg_query.where(
                LoadRegulationConfig.regulation_type == regulation_type
            )

        result = await self.db.execute(reg_query)
        reg_rows = result.all()

        # 2. 查询有转移配置的设备
        shift_query = (
            select(PowerDevice, DeviceShiftConfig)
            .join(DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id)
            .where(
                and_(
                    PowerDevice.is_enabled == True,
                    DeviceShiftConfig.is_shiftable == True
                )
            )
        )
        result = await self.db.execute(shift_query)
        shift_rows = result.all()

        # 构建设备映射（去重）
        device_map: Dict[int, Dict] = {}

        # 处理调节配置
        for device, reg_config in reg_rows:
            dev_id = device.id
            adjustable_power = self._calc_adjustable_power(device, reg_config)

            # 判断执行方式
            exec_mode = "auto" if reg_config.is_auto else "manual"
            if execution_mode and exec_mode != execution_mode:
                continue

            if dev_id not in device_map:
                device_map[dev_id] = {
                    "device_id": dev_id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "rated_power": device.rated_power,
                    "regulations": [],
                    "shift_config": None,
                    "allowed_hours": [],
                    "is_shiftable": False
                }

            device_map[dev_id]["regulations"].append({
                "config_id": reg_config.id,
                "regulation_type": reg_config.regulation_type,
                "adjustable_power": adjustable_power,
                "execution_mode": exec_mode,
                "current_value": reg_config.current_value,
                "min_value": reg_config.min_value,
                "max_value": reg_config.max_value,
                "default_value": reg_config.default_value,
                "step_size": reg_config.step_size,
                "unit": reg_config.unit,
                "comfort_impact": reg_config.comfort_impact,
                "performance_impact": reg_config.performance_impact,
                "is_auto": reg_config.is_auto
            })

        # 处理转移配置
        for device, shift_config in shift_rows:
            dev_id = device.id
            if only_shiftable and not shift_config.is_shiftable:
                continue

            if dev_id not in device_map:
                device_map[dev_id] = {
                    "device_id": dev_id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "rated_power": device.rated_power,
                    "regulations": [],
                    "shift_config": None,
                    "allowed_hours": [],
                    "is_shiftable": False
                }

            shiftable_power = (device.rated_power or 0) * (shift_config.shiftable_power_ratio or 0)
            device_map[dev_id]["shift_config"] = {
                "is_shiftable": shift_config.is_shiftable,
                "shiftable_power": shiftable_power,
                "shiftable_power_ratio": shift_config.shiftable_power_ratio,
                "is_critical": shift_config.is_critical,
                "requires_manual_approval": shift_config.requires_manual_approval,
                "min_continuous_runtime": shift_config.min_continuous_runtime,
                "max_shift_duration": shift_config.max_shift_duration
            }
            device_map[dev_id]["is_shiftable"] = shift_config.is_shiftable
            device_map[dev_id]["allowed_hours"] = shift_config.allowed_shift_hours or []

        # 转为列表并计算综合能力
        for dev in device_map.values():
            dev["total_adjustable_power"] = self._calc_total_adjustable(dev)
            dev["primary_execution_mode"] = self._determine_execution_mode(dev)
            devices.append(dev)

        # 按可调功率排序
        devices.sort(key=lambda d: d["total_adjustable_power"], reverse=True)

        return devices

    async def get_device_capabilities(
        self,
        device_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取单个设备的完整能力信息"""
        devices = await self.get_available_devices()
        for dev in devices:
            if dev["device_id"] == device_id:
                return dev
        return None

    def calculate_time_intersection(
        self,
        devices: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        计算多设备可调时段交集

        Args:
            devices: 设备列表（每个设备需含allowed_hours字段）

        Returns:
            {
                "intersection_hours": [22, 23, 0, 1, 2, 3, 4, 5],
                "intersection_count": 8,
                "per_device_hours": {...},
                "has_intersection": True
            }
        """
        if not devices:
            return {
                "intersection_hours": [],
                "intersection_count": 0,
                "per_device_hours": {},
                "has_intersection": False
            }

        # 收集每个设备的可调时段
        all_hours: List[Set[int]] = []
        per_device_hours = {}

        for dev in devices:
            hours = set(dev.get("allowed_hours", []))
            # 如果设备没有指定时段限制，默认全天可调
            if not hours:
                hours = set(range(24))
            all_hours.append(hours)
            per_device_hours[dev.get("device_name", f"device_{dev.get('device_id')}")] = sorted(hours)

        # 计算交集
        if all_hours:
            intersection = all_hours[0]
            for hours in all_hours[1:]:
                intersection = intersection & hours
        else:
            intersection = set()

        # 排序（处理跨天情况：22,23,0,1,2...）
        sorted_hours = sorted(intersection)

        return {
            "intersection_hours": sorted_hours,
            "intersection_count": len(sorted_hours),
            "per_device_hours": per_device_hours,
            "has_intersection": len(sorted_hours) > 0,
            "display": self._format_hour_range(sorted_hours)
        }

    async def select_optimal_devices(
        self,
        target_power: float,
        regulation_type: Optional[str] = None,
        prefer_auto: bool = True
    ) -> Dict[str, Any]:
        """
        自动选择最优设备组合

        策略：
        1. 优先选择自动控制的设备
        2. 按可调功率从大到小选择
        3. 确保总功率满足目标

        Args:
            target_power: 目标功率 kW
            regulation_type: 调节类型
            prefer_auto: 是否优先选择自动控制的设备

        Returns:
            选择结果
        """
        devices = await self.get_available_devices(regulation_type=regulation_type)

        # 排序策略
        if prefer_auto:
            devices.sort(key=lambda d: (
                0 if d["primary_execution_mode"] == "auto" else 1,
                -d["total_adjustable_power"]
            ))
        else:
            devices.sort(key=lambda d: -d["total_adjustable_power"])

        selected = []
        accumulated_power = 0

        for dev in devices:
            if accumulated_power >= target_power:
                break
            selected.append(dev)
            accumulated_power += dev["total_adjustable_power"]

        # 计算时段交集
        time_intersection = self.calculate_time_intersection(selected)

        return {
            "selected_devices": selected,
            "selected_count": len(selected),
            "total_adjustable_power": round(accumulated_power, 2),
            "target_power": target_power,
            "is_sufficient": accumulated_power >= target_power,
            "surplus_power": round(max(0, accumulated_power - target_power), 2),
            "time_intersection": time_intersection,
            "auto_count": sum(1 for d in selected if d["primary_execution_mode"] == "auto"),
            "manual_count": sum(1 for d in selected if d["primary_execution_mode"] == "manual")
        }

    async def validate_device_selection(
        self,
        device_ids: List[int],
        target_power: Optional[float] = None,
        target_hours: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        验证设备选择是否可行

        Args:
            device_ids: 选中的设备ID列表
            target_power: 目标功率
            target_hours: 目标时段

        Returns:
            验证结果
        """
        all_devices = await self.get_available_devices()
        selected = [d for d in all_devices if d["device_id"] in device_ids]

        warnings = []
        is_valid = True

        if len(selected) != len(device_ids):
            missing = set(device_ids) - set(d["device_id"] for d in selected)
            warnings.append(f"以下设备不可用或不存在: {missing}")
            is_valid = False

        # 检查总功率
        total_power = sum(d["total_adjustable_power"] for d in selected)
        if target_power and total_power < target_power:
            warnings.append(
                f"可调总功率({total_power:.1f}kW)不足目标({target_power:.1f}kW)"
            )
            is_valid = False

        # 检查时段交集
        time_result = self.calculate_time_intersection(selected)
        if not time_result["has_intersection"]:
            warnings.append("选中设备没有共同可调时段")
            is_valid = False

        if target_hours:
            target_set = set(target_hours)
            available_set = set(time_result["intersection_hours"])
            unavailable = target_set - available_set
            if unavailable:
                warnings.append(f"以下时段不在可调范围内: {sorted(unavailable)}")
                is_valid = False

        # 检查关键负荷
        critical_devices = [d for d in selected if d.get("shift_config", {}).get("is_critical", False)]
        if critical_devices:
            names = [d["device_name"] for d in critical_devices]
            warnings.append(f"以下为关键负荷设备，调节需谨慎: {', '.join(names)}")

        return {
            "is_valid": is_valid,
            "selected_count": len(selected),
            "total_adjustable_power": round(total_power, 2),
            "time_intersection": time_result,
            "warnings": warnings,
            "auto_devices": [d["device_name"] for d in selected if d["primary_execution_mode"] == "auto"],
            "manual_devices": [d["device_name"] for d in selected if d["primary_execution_mode"] == "manual"]
        }

    # ========== 私有方法 ==========

    def _calc_adjustable_power(
        self,
        device: PowerDevice,
        reg_config: LoadRegulationConfig
    ) -> float:
        """计算设备可调功率"""
        if reg_config.power_factor and reg_config.base_power:
            # 基于功率系数计算
            value_range = (reg_config.max_value or 0) - (reg_config.min_value or 0)
            return abs(value_range * reg_config.power_factor * reg_config.base_power / 10)
        elif device.rated_power:
            # 默认按额定功率的30%估算
            return device.rated_power * 0.3
        return 0

    def _calc_total_adjustable(self, dev: Dict) -> float:
        """计算设备总可调功率"""
        total = 0
        # 调节配置的可调功率
        for reg in dev.get("regulations", []):
            total += reg.get("adjustable_power", 0)
        # 转移配置的可调功率
        shift = dev.get("shift_config")
        if shift:
            total = max(total, shift.get("shiftable_power", 0))
        return round(total, 2)

    def _determine_execution_mode(self, dev: Dict) -> str:
        """确定设备主要执行方式"""
        has_auto = any(r.get("is_auto") for r in dev.get("regulations", []))
        if has_auto:
            return "auto"
        shift = dev.get("shift_config")
        if shift and not shift.get("requires_manual_approval", True):
            return "auto"
        return "manual"

    def _format_hour_range(self, hours: List[int]) -> str:
        """格式化时段显示"""
        if not hours:
            return "无可调时段"

        # 简单格式化：找连续时段
        ranges = []
        start = hours[0]
        prev = hours[0]

        for h in hours[1:]:
            if h == prev + 1 or (prev == 23 and h == 0):
                prev = h
            else:
                ranges.append(f"{start:02d}:00-{(prev + 1) % 24:02d}:00")
                start = h
                prev = h

        ranges.append(f"{start:02d}:00-{(prev + 1) % 24:02d}:00")
        return ", ".join(ranges)
