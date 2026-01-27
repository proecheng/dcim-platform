"""
设备配置自动生成服务
当创建新设备时自动生成转移配置和调节配置
"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import PowerDevice, DeviceShiftConfig, LoadRegulationConfig


class DeviceConfigAutoGenerator:
    """设备配置自动生成器"""

    # 设备类型 -> 转移配置模板
    SHIFT_TEMPLATES = {
        "AC": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.30,
            "is_critical": False,
            "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 22, 23],
            "forbidden_shift_hours": [8, 9, 18, 19, 20, 21],
            "min_continuous_runtime": 0.5,
            "max_shift_duration": 4.0,
            "max_ramp_rate": 5.0,
            "shift_notice_time": 15,
            "requires_manual_approval": False
        },
        "HVAC": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.35,
            "is_critical": False,
            "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 22, 23],
            "forbidden_shift_hours": [8, 9, 18, 19, 20, 21],
            "min_continuous_runtime": 0.5,
            "max_shift_duration": 4.0,
            "max_ramp_rate": 10.0,
            "shift_notice_time": 15,
            "requires_manual_approval": False
        },
        "LIGHT": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.50,
            "is_critical": False,
            "allowed_shift_hours": list(range(24)),
            "forbidden_shift_hours": [],
            "min_continuous_runtime": 0.0,
            "max_shift_duration": 8.0,
            "max_ramp_rate": 100.0,
            "shift_notice_time": 5,
            "requires_manual_approval": False
        },
        "LIGHTING": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.50,
            "is_critical": False,
            "allowed_shift_hours": list(range(24)),
            "forbidden_shift_hours": [],
            "min_continuous_runtime": 0.0,
            "max_shift_duration": 8.0,
            "max_ramp_rate": 100.0,
            "shift_notice_time": 5,
            "requires_manual_approval": False
        },
        "PUMP": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.40,
            "is_critical": False,
            "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 22, 23],
            "forbidden_shift_hours": [8, 9, 10, 18, 19, 20],
            "min_continuous_runtime": 1.0,
            "max_shift_duration": 3.0,
            "max_ramp_rate": 3.0,
            "shift_notice_time": 30,
            "requires_manual_approval": False
        },
        "CHILLER": {
            "is_shiftable": True,
            "shiftable_power_ratio": 0.25,
            "is_critical": False,
            "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 22, 23],
            "forbidden_shift_hours": [8, 9, 10, 14, 15, 16, 18, 19],
            "min_continuous_runtime": 2.0,
            "max_shift_duration": 2.0,
            "max_ramp_rate": 2.0,
            "shift_notice_time": 60,
            "requires_manual_approval": True
        },
    }

    # 设备类型 -> 调节配置模板
    REGULATION_TEMPLATES = {
        "AC": {
            "regulation_type": "temperature",
            "min_value": 20.0,
            "max_value": 28.0,
            "default_value": 24.0,
            "step_size": 0.5,
            "unit": "°C",
            "power_factor": -3.0,
            "priority": 3,
            "comfort_impact": "medium",
            "performance_impact": "none",
            "power_curve": [
                {"value": 20.0, "power_ratio": 1.2},
                {"value": 22.0, "power_ratio": 1.0},
                {"value": 24.0, "power_ratio": 0.85},
                {"value": 26.0, "power_ratio": 0.7},
                {"value": 28.0, "power_ratio": 0.55}
            ]
        },
        "HVAC": {
            "regulation_type": "temperature",
            "min_value": 18.0,
            "max_value": 28.0,
            "default_value": 23.0,
            "step_size": 0.5,
            "unit": "°C",
            "power_factor": -4.0,
            "priority": 3,
            "comfort_impact": "medium",
            "performance_impact": "none",
            "power_curve": [
                {"value": 18.0, "power_ratio": 1.3},
                {"value": 20.0, "power_ratio": 1.1},
                {"value": 23.0, "power_ratio": 0.85},
                {"value": 25.0, "power_ratio": 0.7},
                {"value": 28.0, "power_ratio": 0.5}
            ]
        },
        "LIGHT": {
            "regulation_type": "brightness",
            "min_value": 20.0,
            "max_value": 100.0,
            "default_value": 80.0,
            "step_size": 5.0,
            "unit": "%",
            "power_factor": 0.01,
            "priority": 5,
            "comfort_impact": "low",
            "performance_impact": "none",
            "power_curve": [
                {"value": 20, "power_ratio": 0.2},
                {"value": 40, "power_ratio": 0.4},
                {"value": 60, "power_ratio": 0.6},
                {"value": 80, "power_ratio": 0.8},
                {"value": 100, "power_ratio": 1.0}
            ]
        },
        "LIGHTING": {
            "regulation_type": "brightness",
            "min_value": 20.0,
            "max_value": 100.0,
            "default_value": 80.0,
            "step_size": 5.0,
            "unit": "%",
            "power_factor": 0.01,
            "priority": 5,
            "comfort_impact": "low",
            "performance_impact": "none",
            "power_curve": [
                {"value": 20, "power_ratio": 0.2},
                {"value": 40, "power_ratio": 0.4},
                {"value": 60, "power_ratio": 0.6},
                {"value": 80, "power_ratio": 0.8},
                {"value": 100, "power_ratio": 1.0}
            ]
        },
        "PUMP": {
            "regulation_type": "load",
            "min_value": 30.0,
            "max_value": 50.0,
            "default_value": 45.0,
            "step_size": 1.0,
            "unit": "Hz",
            "power_factor": 2.5,
            "priority": 4,
            "comfort_impact": "none",
            "performance_impact": "low",
            "power_curve": [
                {"value": 30, "power_ratio": 0.22},
                {"value": 35, "power_ratio": 0.34},
                {"value": 40, "power_ratio": 0.51},
                {"value": 45, "power_ratio": 0.73},
                {"value": 50, "power_ratio": 1.0}
            ]
        },
        "CHILLER": {
            "regulation_type": "temperature",
            "min_value": 5.0,
            "max_value": 12.0,
            "default_value": 7.0,
            "step_size": 0.5,
            "unit": "°C",
            "power_factor": -5.0,
            "priority": 2,
            "comfort_impact": "none",
            "performance_impact": "medium",
            "power_curve": [
                {"value": 5.0, "power_ratio": 1.15},
                {"value": 7.0, "power_ratio": 1.0},
                {"value": 9.0, "power_ratio": 0.85},
                {"value": 12.0, "power_ratio": 0.65}
            ]
        },
        "UPS": {
            "regulation_type": "mode",
            "min_value": 0,
            "max_value": 1,
            "default_value": 0,
            "step_size": 1,
            "unit": "",
            "power_factor": -2.0,
            "priority": 1,
            "comfort_impact": "none",
            "performance_impact": "high",
            "power_curve": [
                {"value": 0, "power_ratio": 1.0, "label": "正常模式"},
                {"value": 1, "power_ratio": 0.97, "label": "ECO模式"}
            ]
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_configs_for_device(
        self,
        device: PowerDevice,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        为单个设备生成转移和调节配置

        Args:
            device: 用电设备对象
            force: 是否强制覆盖已有配置

        Returns:
            生成结果字典
        """
        result = {
            "device_id": device.id,
            "device_name": device.device_name,
            "shift_config_created": False,
            "regulation_config_created": False,
            "message": []
        }

        # 1. 生成转移配置
        shift_created = await self._generate_shift_config(device, force)
        result["shift_config_created"] = shift_created
        if shift_created:
            result["message"].append("已创建负荷转移配置")

        # 2. 生成调节配置
        reg_created = await self._generate_regulation_config(device, force)
        result["regulation_config_created"] = reg_created
        if reg_created:
            result["message"].append("已创建参数调节配置")

        return result

    async def _generate_shift_config(
        self,
        device: PowerDevice,
        force: bool = False
    ) -> bool:
        """生成设备转移配置"""
        from sqlalchemy import select

        # 检查是否已存在配置
        existing = await self.db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device.id)
        )
        if existing.scalar_one_or_none() and not force:
            return False

        device_type = device.device_type.upper() if device.device_type else ""
        template = self.SHIFT_TEMPLATES.get(device_type)

        # 构建配置
        if template:
            # 使用模板
            min_power = device.rated_power * 0.2 if device.rated_power and template["is_shiftable"] else None
            config_data = {
                "device_id": device.id,
                **template,
                "min_power": min_power
            }
        else:
            # 默认配置 - 不可转移
            config_data = {
                "device_id": device.id,
                "is_shiftable": False,
                "shiftable_power_ratio": 0.0,
                "is_critical": device.is_critical or False,
                "allowed_shift_hours": [],
                "forbidden_shift_hours": list(range(24)),
                "min_continuous_runtime": 0,
                "max_shift_duration": 0,
                "min_power": None,
                "max_ramp_rate": 0,
                "shift_notice_time": 0,
                "requires_manual_approval": True
            }

        # 如果已存在则删除
        if force:
            await self.db.execute(
                DeviceShiftConfig.__table__.delete().where(
                    DeviceShiftConfig.device_id == device.id
                )
            )

        # 创建配置
        config = DeviceShiftConfig(**config_data)
        self.db.add(config)
        await self.db.flush()

        return True

    async def _generate_regulation_config(
        self,
        device: PowerDevice,
        force: bool = False
    ) -> bool:
        """生成设备调节配置"""
        from sqlalchemy import select

        # 检查是否已存在配置
        existing = await self.db.execute(
            select(LoadRegulationConfig).where(LoadRegulationConfig.device_id == device.id)
        )
        if existing.scalar_one_or_none() and not force:
            return False

        device_type = device.device_type.upper() if device.device_type else ""
        template = self.REGULATION_TEMPLATES.get(device_type)

        if not template:
            # 该类型设备不支持调节
            return False

        # 计算base_power和power_curve
        base_power = device.rated_power or 0
        power_curve = [
            {**point, "power": round(base_power * point.get("power_ratio", 1.0), 2)}
            for point in template.get("power_curve", [])
        ]

        config_data = {
            "device_id": device.id,
            "regulation_type": template["regulation_type"],
            "min_value": template["min_value"],
            "max_value": template["max_value"],
            "default_value": template["default_value"],
            "current_value": template["default_value"],
            "step_size": template["step_size"],
            "unit": template.get("unit", ""),
            "power_factor": template.get("power_factor"),
            "base_power": base_power,
            "power_curve": power_curve,
            "priority": template.get("priority", 5),
            "comfort_impact": template.get("comfort_impact", "none"),
            "performance_impact": template.get("performance_impact", "none"),
            "is_enabled": True,
            "is_auto": False
        }

        # 如果已存在则删除
        if force:
            await self.db.execute(
                LoadRegulationConfig.__table__.delete().where(
                    LoadRegulationConfig.device_id == device.id
                )
            )

        # 创建配置
        config = LoadRegulationConfig(**config_data)
        self.db.add(config)
        await self.db.flush()

        return True

    async def batch_generate_configs(
        self,
        device_ids: list[int],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        批量生成设备配置

        Args:
            device_ids: 设备ID列表
            force: 是否强制覆盖已有配置

        Returns:
            批量生成结果
        """
        from sqlalchemy import select

        results = []
        shift_count = 0
        reg_count = 0

        for device_id in device_ids:
            # 查询设备
            result = await self.db.execute(
                select(PowerDevice).where(PowerDevice.id == device_id)
            )
            device = result.scalar_one_or_none()

            if not device:
                continue

            # 生成配置
            res = await self.generate_configs_for_device(device, force)
            results.append(res)

            if res["shift_config_created"]:
                shift_count += 1
            if res["regulation_config_created"]:
                reg_count += 1

        await self.db.commit()

        return {
            "total_devices": len(device_ids),
            "shift_configs_created": shift_count,
            "regulation_configs_created": reg_count,
            "details": results
        }
