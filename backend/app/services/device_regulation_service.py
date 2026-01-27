"""
设备调节能力服务 - 从 load_regulation_configs 和 device_shift_configs 查询
V2.4 数据驱动版本
"""
from typing import Dict, List, Optional, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.energy import (
    PowerDevice, DeviceShiftConfig, LoadRegulationConfig
)


class DeviceRegulationService:
    """设备调节能力服务 - 查询设备的调节和转移能力"""

    # 设备类型到调节方式的映射
    REGULATION_METHODS = {
        "HVAC": "调节供电频率/设定温度改变功率",
        "AC": "调节供电频率/设定温度改变功率",
        "PUMP": "变频调速控制流量",
        "COMPRESSOR": "变频调速/台数控制",
        "LIGHTING": "分区控制/调光",
        "CHILLER": "调节冷冻水温度/变频控制",
        "COOLING_TOWER": "变频调速/风机台数控制",
        "AHU": "变频调速/新风比例调节",
        "UPS": "ECO模式切换",
        "IT_SERVER": "负载迁移/休眠策略",
        "IT_STORAGE": "分层存储策略",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_shiftable_devices(self) -> List[Dict]:
        """
        获取所有可转移负荷的设备

        Returns:
            List[Dict]: 可转移设备列表，包含设备信息和转移配置
        """
        result = await self.db.execute(
            select(PowerDevice, DeviceShiftConfig).join(
                DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id
            ).where(
                and_(
                    DeviceShiftConfig.is_shiftable == True,
                    PowerDevice.is_enabled == True
                )
            ).order_by(PowerDevice.device_type, PowerDevice.device_code)
        )

        devices = []
        for device, shift_config in result.all():
            rated_power = device.rated_power or 0
            shiftable_ratio = shift_config.shiftable_power_ratio or 0
            shiftable_power = rated_power * shiftable_ratio

            devices.append({
                "device_id": device.id,
                "device_code": device.device_code,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "rated_power": rated_power,
                "shiftable_power": round(shiftable_power, 2),
                "shiftable_ratio": shiftable_ratio,
                "allowed_shift_hours": shift_config.allowed_shift_hours or [],
                "forbidden_shift_hours": shift_config.forbidden_shift_hours or [],
                "min_continuous_runtime": shift_config.min_continuous_runtime,
                "max_shift_duration": shift_config.max_shift_duration,
                "min_power": shift_config.min_power,
                "max_ramp_rate": shift_config.max_ramp_rate,
                "shift_notice_time": shift_config.shift_notice_time or 30,
                "requires_manual_approval": shift_config.requires_manual_approval,
                "is_critical": shift_config.is_critical or device.is_critical,
                "regulation_method": self._get_regulation_method(device.device_type),
                "area_code": device.area_code
            })

        return devices

    async def get_adjustable_devices(self) -> List[Dict]:
        """
        获取所有可调节参数的设备（温度/频率/亮度等）

        Returns:
            List[Dict]: 可调节设备列表，包含设备信息和调节配置
        """
        result = await self.db.execute(
            select(PowerDevice, LoadRegulationConfig).join(
                LoadRegulationConfig, PowerDevice.id == LoadRegulationConfig.device_id
            ).where(
                and_(
                    LoadRegulationConfig.is_enabled == True,
                    PowerDevice.is_enabled == True
                )
            ).order_by(PowerDevice.device_type, PowerDevice.device_code)
        )

        devices = []
        for device, reg_config in result.all():
            # 计算功率变化范围
            power_range = self._calc_power_range(reg_config)

            devices.append({
                "device_id": device.id,
                "device_code": device.device_code,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "rated_power": device.rated_power or 0,
                "config_id": reg_config.id,
                "regulation_type": reg_config.regulation_type,
                "current_value": reg_config.current_value,
                "default_value": reg_config.default_value,
                "min_value": reg_config.min_value,
                "max_value": reg_config.max_value,
                "step_size": reg_config.step_size or 1,
                "unit": reg_config.unit or "",
                "power_factor": reg_config.power_factor,
                "base_power": reg_config.base_power,
                "power_curve": reg_config.power_curve,
                "power_range": power_range,
                "priority": reg_config.priority or 5,
                "comfort_impact": reg_config.comfort_impact or "low",
                "performance_impact": reg_config.performance_impact or "none",
                "is_auto": reg_config.is_auto,
                "regulation_method": self._get_regulation_method(device.device_type),
                "area_code": device.area_code
            })

        return devices

    async def get_device_shift_config(self, device_id: int) -> Optional[Dict]:
        """
        获取单个设备的转移配置

        Args:
            device_id: 设备ID

        Returns:
            Dict or None: 设备转移配置
        """
        result = await self.db.execute(
            select(PowerDevice, DeviceShiftConfig).outerjoin(
                DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id
            ).where(PowerDevice.id == device_id)
        )

        row = result.first()
        if not row:
            return None

        device, shift_config = row

        if not shift_config:
            return {
                "device_id": device.id,
                "device_code": device.device_code,
                "device_name": device.device_name,
                "is_shiftable": False,
                "has_config": False
            }

        return {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": device.rated_power or 0,
            "is_shiftable": shift_config.is_shiftable,
            "shiftable_power": (device.rated_power or 0) * (shift_config.shiftable_power_ratio or 0),
            "shiftable_ratio": shift_config.shiftable_power_ratio,
            "allowed_shift_hours": shift_config.allowed_shift_hours or [],
            "forbidden_shift_hours": shift_config.forbidden_shift_hours or [],
            "min_continuous_runtime": shift_config.min_continuous_runtime,
            "max_shift_duration": shift_config.max_shift_duration,
            "is_critical": shift_config.is_critical,
            "has_config": True
        }

    async def get_devices_by_type(
        self,
        device_type: str,
        shiftable_only: bool = False
    ) -> List[Dict]:
        """
        按设备类型获取设备列表

        Args:
            device_type: 设备类型
            shiftable_only: 是否只返回可转移设备

        Returns:
            List[Dict]: 设备列表
        """
        if shiftable_only:
            result = await self.db.execute(
                select(PowerDevice, DeviceShiftConfig).join(
                    DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id
                ).where(
                    and_(
                        PowerDevice.device_type == device_type,
                        PowerDevice.is_enabled == True,
                        DeviceShiftConfig.is_shiftable == True
                    )
                )
            )
            return [self._build_device_dict(device, shift_config)
                    for device, shift_config in result.all()]
        else:
            result = await self.db.execute(
                select(PowerDevice).where(
                    and_(
                        PowerDevice.device_type == device_type,
                        PowerDevice.is_enabled == True
                    )
                )
            )
            return [self._build_device_dict(device, None)
                    for device in result.scalars().all()]

    async def get_total_shiftable_power(self) -> Dict[str, Any]:
        """
        获取总可转移功率统计

        Returns:
            Dict: 可转移功率统计
        """
        devices = await self.get_shiftable_devices()

        total_power = sum(d["shiftable_power"] for d in devices)
        by_type = {}
        for d in devices:
            device_type = d["device_type"]
            if device_type not in by_type:
                by_type[device_type] = {"count": 0, "power": 0}
            by_type[device_type]["count"] += 1
            by_type[device_type]["power"] += d["shiftable_power"]

        return {
            "total_shiftable_power": round(total_power, 2),
            "shiftable_device_count": len(devices),
            "by_device_type": by_type,
            "devices": devices
        }

    async def get_devices_for_suggestion(
        self,
        suggestion_type: str = "peak_valley"
    ) -> List[Dict]:
        """
        根据建议类型获取相关设备列表

        Args:
            suggestion_type: 建议类型 (peak_valley/pue/demand等)

        Returns:
            List[Dict]: 相关设备列表
        """
        if suggestion_type in ["peak_valley", "peak_ratio_high", "load_shift"]:
            # 峰谷套利相关：返回可转移设备
            return await self.get_shiftable_devices()
        elif suggestion_type in ["pue", "pue_high", "cooling"]:
            # PUE优化相关：返回制冷设备
            return await self.get_devices_by_type("HVAC", shiftable_only=False)
        elif suggestion_type in ["temperature", "ac_temp_low"]:
            # 温度调节：返回可调节温度的设备
            devices = await self.get_adjustable_devices()
            return [d for d in devices if d["regulation_type"] == "temperature"]
        else:
            # 默认返回所有可调节设备
            return await self.get_adjustable_devices()

    async def validate_shift_constraints(
        self,
        device_ids: List[int],
        target_hours: List[int]
    ) -> Dict[str, Any]:
        """
        验证设备转移时段约束

        Args:
            device_ids: 设备ID列表
            target_hours: 目标转移时段 (0-23)

        Returns:
            Dict: 验证结果
        """
        valid_devices = []
        invalid_devices = []
        warnings = []

        for device_id in device_ids:
            config = await self.get_device_shift_config(device_id)
            if not config or not config.get("is_shiftable"):
                invalid_devices.append({
                    "device_id": device_id,
                    "reason": "设备不可转移或未配置"
                })
                continue

            allowed = set(config.get("allowed_shift_hours", []))
            forbidden = set(config.get("forbidden_shift_hours", []))
            target_set = set(target_hours)

            # 检查是否有禁止时段冲突
            conflicts = target_set & forbidden
            if conflicts:
                invalid_devices.append({
                    "device_id": device_id,
                    "device_name": config.get("device_name"),
                    "reason": f"目标时段 {list(conflicts)} 在禁止转移列表中"
                })
                continue

            # 检查是否在允许时段内（如果配置了允许时段）
            if allowed and not (target_set <= allowed):
                outside = target_set - allowed
                warnings.append({
                    "device_id": device_id,
                    "device_name": config.get("device_name"),
                    "warning": f"时段 {list(outside)} 不在推荐转移时段内"
                })

            valid_devices.append(config)

        return {
            "is_valid": len(invalid_devices) == 0,
            "valid_devices": valid_devices,
            "invalid_devices": invalid_devices,
            "warnings": warnings,
            "total_shiftable_power": sum(d.get("shiftable_power", 0) for d in valid_devices)
        }

    async def get_regulation_data_source(self) -> Dict[str, Any]:
        """
        获取设备调节数据来源信息（用于前端显示数据溯源）

        Returns:
            Dict: 数据来源信息
        """
        # 统计配置数量
        shift_result = await self.db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.is_shiftable == True)
        )
        shift_count = len(shift_result.scalars().all())

        reg_result = await self.db.execute(
            select(LoadRegulationConfig).where(LoadRegulationConfig.is_enabled == True)
        )
        reg_count = len(reg_result.scalars().all())

        return {
            "shift_config_source": "device_shift_configs表",
            "regulation_config_source": "load_regulation_configs表",
            "device_source": "power_devices表",
            "shiftable_config_count": shift_count,
            "regulation_config_count": reg_count,
            "message": "数据来源：系统设置 → 设备配置"
        }

    def _calc_power_range(self, config: LoadRegulationConfig) -> Dict:
        """
        根据调节配置计算功率变化范围

        Args:
            config: 调节配置

        Returns:
            Dict: {"min_power": x, "max_power": y, "max_change": z}
        """
        if config.power_curve:
            # 使用功率曲线
            try:
                powers = [p.get("power", 0) for p in config.power_curve]
                return {
                    "min_power": min(powers),
                    "max_power": max(powers),
                    "max_change": max(powers) - min(powers)
                }
            except (TypeError, AttributeError):
                pass

        if config.power_factor and config.base_power:
            # 使用线性系数计算
            default_value = config.default_value or config.current_value or 0
            min_change = config.power_factor * (config.min_value - default_value)
            max_change = config.power_factor * (config.max_value - default_value)

            return {
                "min_power": config.base_power + min(min_change, max_change),
                "max_power": config.base_power + max(min_change, max_change),
                "max_change": abs(max_change - min_change)
            }

        return {"min_power": 0, "max_power": 0, "max_change": 0}

    def _get_regulation_method(self, device_type: str) -> str:
        """获取设备的调节方式描述"""
        return self.REGULATION_METHODS.get(device_type, "负荷转移/功率调节")

    def _build_device_dict(
        self,
        device: PowerDevice,
        shift_config: Optional[DeviceShiftConfig]
    ) -> Dict:
        """构建设备字典"""
        base_dict = {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": device.rated_power or 0,
            "is_critical": device.is_critical,
            "regulation_method": self._get_regulation_method(device.device_type)
        }

        if shift_config:
            base_dict.update({
                "is_shiftable": shift_config.is_shiftable,
                "shiftable_power": (device.rated_power or 0) * (shift_config.shiftable_power_ratio or 0),
                "shiftable_ratio": shift_config.shiftable_power_ratio,
                "allowed_shift_hours": shift_config.allowed_shift_hours or [],
                "forbidden_shift_hours": shift_config.forbidden_shift_hours or []
            })
        else:
            base_dict.update({
                "is_shiftable": False,
                "shiftable_power": 0,
                "shiftable_ratio": 0
            })

        return base_dict
