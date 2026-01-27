"""
用电设备服务
Power Device Service

提供用电设备管理、点位关联、负荷转移配置功能
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from ..models.energy import (
    PowerDevice, DeviceShiftConfig, DeviceLoadProfile,
    DistributionCircuit
)
from ..models.point import Point, PointRealtime
from ..models.device import Device


class PowerDeviceService:
    """用电设备服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        device_type: Optional[str] = None,
        circuit_id: Optional[int] = None,
        is_metered: Optional[bool] = None,
        is_it_load: Optional[bool] = None,
        is_critical: Optional[bool] = None,
        is_enabled: Optional[bool] = None
    ) -> tuple[List[PowerDevice], int]:
        """获取用电设备列表"""
        query = select(PowerDevice).options(
            selectinload(PowerDevice.circuit),
            selectinload(PowerDevice.load_profile),
            selectinload(PowerDevice.shift_config)
        )
        count_query = select(func.count(PowerDevice.id))

        conditions = []
        if device_type:
            conditions.append(PowerDevice.device_type == device_type)
        if circuit_id:
            conditions.append(PowerDevice.circuit_id == circuit_id)
        if is_metered is not None:
            conditions.append(PowerDevice.is_metered == is_metered)
        if is_it_load is not None:
            conditions.append(PowerDevice.is_it_load == is_it_load)
        if is_critical is not None:
            conditions.append(PowerDevice.is_critical == is_critical)
        if is_enabled is not None:
            conditions.append(PowerDevice.is_enabled == is_enabled)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = query.order_by(PowerDevice.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        return list(items), total

    @staticmethod
    async def get_by_id(db: AsyncSession, device_id: int) -> Optional[PowerDevice]:
        """根据ID获取用电设备"""
        result = await db.execute(
            select(PowerDevice)
            .options(
                selectinload(PowerDevice.circuit),
                selectinload(PowerDevice.load_profile),
                selectinload(PowerDevice.shift_config)
            )
            .where(PowerDevice.id == device_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[PowerDevice]:
        """根据编码获取用电设备"""
        result = await db.execute(
            select(PowerDevice).where(PowerDevice.device_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: Dict[str, Any]) -> PowerDevice:
        """创建用电设备"""
        device = PowerDevice(**data)
        db.add(device)
        await db.commit()
        await db.refresh(device)
        return device

    @staticmethod
    async def update(
        db: AsyncSession,
        device_id: int,
        data: Dict[str, Any]
    ) -> Optional[PowerDevice]:
        """更新用电设备"""
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        for key, value in data.items():
            if hasattr(device, key) and value is not None:
                setattr(device, key, value)

        device.updated_at = datetime.now()
        await db.commit()
        await db.refresh(device)
        return device

    @staticmethod
    async def delete(db: AsyncSession, device_id: int) -> bool:
        """删除用电设备"""
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return False

        # 删除关联的配置
        if device.load_profile:
            await db.delete(device.load_profile)
        if device.shift_config:
            await db.delete(device.shift_config)

        await db.delete(device)
        await db.commit()
        return True

    @staticmethod
    async def configure_points(
        db: AsyncSession,
        device_id: int,
        point_config: Dict[str, Optional[int]]
    ) -> Optional[PowerDevice]:
        """
        配置设备点位关联

        Args:
            point_config: {
                "monitor_device_id": 监控设备ID,
                "power_point_id": 功率点位ID,
                "energy_point_id": 电量点位ID,
                "voltage_point_id": 电压点位ID,
                "current_point_id": 电流点位ID,
                "pf_point_id": 功率因数点位ID
            }
        """
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        # 验证点位是否存在
        for field, point_id in point_config.items():
            if point_id is not None and field.endswith("_point_id"):
                point_result = await db.execute(
                    select(Point).where(Point.id == point_id)
                )
                if not point_result.scalar_one_or_none():
                    raise ValueError(f"点位ID {point_id} 不存在")

        # 验证监控设备是否存在
        if point_config.get("monitor_device_id"):
            monitor_device_result = await db.execute(
                select(Device).where(Device.id == point_config["monitor_device_id"])
            )
            if not monitor_device_result.scalar_one_or_none():
                raise ValueError(f"监控设备ID {point_config['monitor_device_id']} 不存在")

        # 更新点位关联
        for field, value in point_config.items():
            if hasattr(device, field):
                setattr(device, field, value)

        device.updated_at = datetime.now()
        await db.commit()
        await db.refresh(device)
        return device

    @staticmethod
    async def get_points_config(
        db: AsyncSession,
        device_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取设备点位关联配置"""
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        config = {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "monitor_device": None,
            "points": {
                "power": None,
                "energy": None,
                "voltage": None,
                "current": None,
                "power_factor": None
            }
        }

        # 获取监控设备信息
        if device.monitor_device_id:
            monitor_result = await db.execute(
                select(Device).where(Device.id == device.monitor_device_id)
            )
            monitor_device = monitor_result.scalar_one_or_none()
            if monitor_device:
                config["monitor_device"] = {
                    "id": monitor_device.id,
                    "name": monitor_device.device_name,
                    "type": monitor_device.device_type,
                    "protocol": monitor_device.protocol,
                    "status": monitor_device.status
                }

        # 获取各点位信息
        point_fields = [
            ("power_point_id", "power"),
            ("energy_point_id", "energy"),
            ("voltage_point_id", "voltage"),
            ("current_point_id", "current"),
            ("pf_point_id", "power_factor")
        ]

        for db_field, config_key in point_fields:
            point_id = getattr(device, db_field, None)
            if point_id:
                point_result = await db.execute(
                    select(Point).where(Point.id == point_id)
                )
                point = point_result.scalar_one_or_none()
                if point:
                    # 获取实时值
                    realtime_result = await db.execute(
                        select(PointRealtime).where(PointRealtime.point_id == point_id)
                    )
                    realtime = realtime_result.scalar_one_or_none()

                    config["points"][config_key] = {
                        "id": point.id,
                        "code": point.point_code,
                        "name": point.point_name,
                        "type": point.point_type,
                        "unit": point.unit,
                        "coefficient": point.coefficient,
                        "current_value": realtime.value if realtime else None,
                        "update_time": realtime.update_time.isoformat() if realtime and realtime.update_time else None
                    }

        return config

    @staticmethod
    async def get_realtime_data(
        db: AsyncSession,
        device_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取设备实时电力数据"""
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        data = {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": device.rated_power,
            "power": None,
            "energy": None,
            "voltage": None,
            "current": None,
            "power_factor": None,
            "load_rate": None,
            "update_time": None
        }

        # 获取各点位实时值
        point_mapping = [
            ("power_point_id", "power"),
            ("energy_point_id", "energy"),
            ("voltage_point_id", "voltage"),
            ("current_point_id", "current"),
            ("pf_point_id", "power_factor")
        ]

        latest_time = None
        for db_field, data_key in point_mapping:
            point_id = getattr(device, db_field, None)
            if point_id:
                realtime_result = await db.execute(
                    select(PointRealtime).where(PointRealtime.point_id == point_id)
                )
                realtime = realtime_result.scalar_one_or_none()
                if realtime:
                    data[data_key] = realtime.value
                    if realtime.update_time:
                        if latest_time is None or realtime.update_time > latest_time:
                            latest_time = realtime.update_time

        # 计算负载率
        if data["power"] is not None and device.rated_power and device.rated_power > 0:
            data["load_rate"] = round((data["power"] / device.rated_power) * 100, 1)

        data["update_time"] = latest_time.isoformat() if latest_time else None

        return data

    @staticmethod
    async def configure_shift(
        db: AsyncSession,
        device_id: int,
        shift_config: Dict[str, Any]
    ) -> Optional[DeviceShiftConfig]:
        """
        配置设备负荷转移参数

        Args:
            shift_config: {
                "is_shiftable": 是否可转移,
                "shiftable_power_ratio": 可转移功率比例,
                "is_critical": 是否关键负荷,
                "allowed_shift_hours": 允许转移时段,
                "forbidden_shift_hours": 禁止转移时段,
                "min_continuous_runtime": 最小连续运行时间,
                "max_shift_duration": 最大转移持续时间,
                "min_power": 最低运行功率,
                "max_ramp_rate": 最大爬坡速率,
                "shift_notice_time": 转移提前通知时间,
                "requires_manual_approval": 是否需要人工确认
            }
        """
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        # 查找或创建转移配置
        config_result = await db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device_id)
        )
        config = config_result.scalar_one_or_none()

        if config:
            # 更新现有配置
            for key, value in shift_config.items():
                if hasattr(config, key) and value is not None:
                    setattr(config, key, value)
            config.updated_at = datetime.now()
        else:
            # 创建新配置
            config = DeviceShiftConfig(device_id=device_id, **shift_config)
            db.add(config)

        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def get_shift_config(
        db: AsyncSession,
        device_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取设备负荷转移配置"""
        device = await PowerDeviceService.get_by_id(db, device_id)
        if not device:
            return None

        config_result = await db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device_id)
        )
        config = config_result.scalar_one_or_none()

        if not config:
            # 返回默认配置
            return {
                "device_id": device_id,
                "is_shiftable": False,
                "shiftable_power_ratio": 0,
                "is_critical": device.is_critical,
                "allowed_shift_hours": [],
                "forbidden_shift_hours": [],
                "min_continuous_runtime": None,
                "max_shift_duration": None,
                "min_power": None,
                "max_ramp_rate": None,
                "shift_notice_time": 30,
                "requires_manual_approval": True
            }

        return {
            "device_id": device_id,
            "is_shiftable": config.is_shiftable,
            "shiftable_power_ratio": config.shiftable_power_ratio,
            "is_critical": config.is_critical,
            "allowed_shift_hours": config.allowed_shift_hours or [],
            "forbidden_shift_hours": config.forbidden_shift_hours or [],
            "min_continuous_runtime": config.min_continuous_runtime,
            "max_shift_duration": config.max_shift_duration,
            "min_power": config.min_power,
            "max_ramp_rate": config.max_ramp_rate,
            "shift_notice_time": config.shift_notice_time,
            "requires_manual_approval": config.requires_manual_approval
        }

    @staticmethod
    async def get_shiftable_devices(db: AsyncSession) -> List[Dict[str, Any]]:
        """获取所有可转移负荷的设备"""
        result = await db.execute(
            select(DeviceShiftConfig)
            .options(selectinload(DeviceShiftConfig.device))
            .where(
                DeviceShiftConfig.is_shiftable == True,
                DeviceShiftConfig.is_critical == False
            )
        )
        configs = result.scalars().all()

        devices = []
        for config in configs:
            if config.device and config.device.is_enabled:
                device_data = await PowerDeviceService.get_realtime_data(
                    db, config.device_id
                )
                if device_data:
                    device_data["shift_config"] = {
                        "shiftable_power_ratio": config.shiftable_power_ratio,
                        "allowed_shift_hours": config.allowed_shift_hours or [],
                        "forbidden_shift_hours": config.forbidden_shift_hours or []
                    }
                    devices.append(device_data)

        return devices


# 单例服务实例
power_device_service = PowerDeviceService()
