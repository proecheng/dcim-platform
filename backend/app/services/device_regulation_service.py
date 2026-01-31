"""
设备调节能力服务 - 从 load_regulation_configs 和 device_shift_configs 查询
V2.4 数据驱动版本
V2.5 新增 shiftable_power_ratio 智能推荐功能
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.energy import (
    PowerDevice, DeviceShiftConfig, LoadRegulationConfig,
    EnergyHourly, EnergyDaily
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

    # ========== 设备典型日功率 Profile ==========

    # 默认时段配置（可被电价配置覆盖）
    DEFAULT_HOUR_PERIODS = {
        11: "sharp", 18: "sharp",
        9: "peak", 10: "peak", 17: "peak", 19: "peak", 20: "peak",
        8: "flat", 13: "flat", 14: "flat", 15: "flat", 16: "flat", 21: "flat",
        22: "valley", 23: "valley", 6: "valley", 7: "valley",
        0: "deep_valley", 1: "deep_valley", 2: "deep_valley",
        3: "deep_valley", 4: "deep_valley", 5: "deep_valley",
        12: "flat",
    }

    def _get_hour_period(self, hour: int) -> str:
        """根据小时返回时段类型"""
        return self.DEFAULT_HOUR_PERIODS.get(hour, "flat")

    async def get_device_typical_profile(
        self, device_id: int, days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        获取设备典型日功率 Profile（24小时按小时聚合）

        Args:
            device_id: 设备ID
            days: 分析天数（默认30天）

        Returns:
            Dict: 典型日功率数据，包含24小时的avg/max/min功率和时段标识
        """
        from sqlalchemy import extract

        # 查找设备
        device_result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = device_result.scalar_one_or_none()
        if not device:
            return None

        rated_power = device.rated_power or 0
        cutoff_date = datetime.now() - timedelta(days=days)

        # 按小时分组聚合
        result = await self.db.execute(
            select(
                extract("hour", EnergyHourly.stat_time).label("hour"),
                func.avg(EnergyHourly.avg_power).label("avg_power"),
                func.max(EnergyHourly.max_power).label("max_power"),
                func.min(EnergyHourly.min_power).label("min_power"),
                func.count(EnergyHourly.id).label("record_count"),
            ).where(
                and_(
                    EnergyHourly.device_id == device_id,
                    EnergyHourly.stat_time >= cutoff_date,
                )
            ).group_by(
                extract("hour", EnergyHourly.stat_time)
            ).order_by(
                extract("hour", EnergyHourly.stat_time)
            )
        )

        rows = result.all()
        data_days = 0

        # 构建24小时profile
        hourly_map = {}
        for row in rows:
            h = int(row.hour)
            hourly_map[h] = {
                "hour": h,
                "avg_power": round(float(row.avg_power or 0), 2),
                "max_power": round(float(row.max_power or 0), 2),
                "min_power": round(float(row.min_power or 0), 2),
                "period_type": self._get_hour_period(h),
            }
            data_days = max(data_days, (row.record_count or 0))

        # 估算数据天数（每小时最多有 days 条记录）
        data_days = min(data_days, days)

        # 填充缺失小时（使用模拟值）
        hourly_profile = []
        has_real_data = len(hourly_map) > 0

        for h in range(24):
            if h in hourly_map:
                hourly_profile.append(hourly_map[h])
            else:
                # 无数据时使用基于额定功率的估算
                import random
                base = rated_power * 0.6 if rated_power > 0 else 10
                hourly_profile.append({
                    "hour": h,
                    "avg_power": round(base * (0.8 + 0.4 * (0.5 - abs(h - 14) / 24)), 2),
                    "max_power": round(base * (1.0 + 0.3 * (0.5 - abs(h - 14) / 24)), 2),
                    "min_power": round(base * (0.5 + 0.2 * (0.5 - abs(h - 14) / 24)), 2),
                    "period_type": self._get_hour_period(h),
                })

        # 汇总指标
        avg_powers = [p["avg_power"] for p in hourly_profile]
        max_powers = [p["max_power"] for p in hourly_profile]
        min_powers = [p["min_power"] for p in hourly_profile]

        overall_avg = sum(avg_powers) / 24 if avg_powers else 0
        overall_max = max(max_powers) if max_powers else 0
        overall_min = min(min_powers) if min_powers else 0

        # 峰时用电占比
        peak_hours_power = sum(
            p["avg_power"] for p in hourly_profile
            if p["period_type"] in ("sharp", "peak")
        )
        total_power_sum = sum(avg_powers)
        peak_ratio = peak_hours_power / total_power_sum if total_power_sum > 0 else 0

        load_rate = overall_avg / rated_power if rated_power > 0 else 0

        return {
            "device_id": device.id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": round(rated_power, 2),
            "data_days": data_days,
            "hourly_profile": hourly_profile,
            "summary": {
                "avg_power": round(overall_avg, 2),
                "max_power": round(overall_max, 2),
                "min_power": round(overall_min, 2),
                "load_rate": round(load_rate, 3),
                "peak_energy_ratio": round(peak_ratio, 3),
                "has_real_data": has_real_data,
            }
        }

    # ========== shiftable_power_ratio 智能推荐 ==========

    # 设备类型柔性系数
    FLEXIBILITY_FACTORS = {
        "PUMP": 0.7, "AC": 0.5, "HVAC": 0.6,
        "LIGHTING": 0.8, "CHILLER": 0.4,
        "COOLING_TOWER": 0.5, "AHU": 0.5,
        "COMPRESSOR": 0.4
    }

    # 设备类型最大可转移比例
    TYPE_MAX_RATIOS = {
        "PUMP": 0.50, "AC": 0.40, "HVAC": 0.45,
        "LIGHTING": 0.60, "CHILLER": 0.30,
        "COOLING_TOWER": 0.40, "AHU": 0.35,
        "COMPRESSOR": 0.30,
        "UPS": 0.0, "IT_SERVER": 0.0, "IT_STORAGE": 0.0
    }

    async def get_ratio_recommendations(self, days: int = 30) -> Dict[str, Any]:
        """
        获取所有设备的 shiftable_power_ratio 推荐值

        Args:
            days: 分析历史数据的天数 (默认30天)

        Returns:
            Dict: 包含所有设备推荐值的响应
        """
        # 获取所有有转移配置的设备
        result = await self.db.execute(
            select(PowerDevice, DeviceShiftConfig).outerjoin(
                DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id
            ).where(PowerDevice.is_enabled == True)
            .order_by(PowerDevice.device_type, PowerDevice.device_code)
        )

        recommendations = []
        total_current_power = 0
        total_recommended_power = 0
        devices_with_change = 0

        cutoff_date = datetime.now() - timedelta(days=days)

        for device, shift_config in result.all():
            # 跳过关键负荷
            if device.is_critical or (shift_config and shift_config.is_critical):
                continue

            # 跳过不可转移的设备类型
            device_type = (device.device_type or "").upper()
            if device_type in ["UPS", "IT_SERVER", "IT_STORAGE"]:
                continue

            # 获取历史数据统计
            hourly_stats = await self._get_hourly_stats(device.id, cutoff_date)
            daily_stats = await self._get_daily_stats(device.id, cutoff_date)

            # 计算推荐值
            recommendation = self._calculate_recommendation(
                device, shift_config, hourly_stats, daily_stats
            )

            recommendations.append(recommendation)

            total_current_power += recommendation["current_shiftable_power"]
            total_recommended_power += recommendation["recommended_shiftable_power"]
            if recommendation["has_change"]:
                devices_with_change += 1

        return {
            "total_devices": len(recommendations),
            "devices_with_change": devices_with_change,
            "recommendations": recommendations,
            "summary": {
                "current_total_power": round(total_current_power, 2),
                "recommended_total_power": round(total_recommended_power, 2),
                "power_change": round(total_recommended_power - total_current_power, 2),
                "analysis_days": days
            }
        }

    async def _get_hourly_stats(self, device_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """获取设备小时级功率统计"""
        result = await self.db.execute(
            select(
                func.avg(EnergyHourly.avg_power).label("avg_power"),
                func.max(EnergyHourly.max_power).label("max_power"),
                func.min(EnergyHourly.min_power).label("min_power"),
                func.count(EnergyHourly.id).label("record_count")
            ).where(
                and_(
                    EnergyHourly.device_id == device_id,
                    EnergyHourly.stat_time >= cutoff_date
                )
            )
        )
        row = result.first()

        if row and row.record_count and row.record_count > 0:
            return {
                "avg_power": float(row.avg_power or 0),
                "max_power": float(row.max_power or 0),
                "min_power": float(row.min_power or 0),
                "data_days": row.record_count // 24,  # 估算天数
                "has_data": True
            }
        return {"avg_power": 0, "max_power": 0, "min_power": 0, "data_days": 0, "has_data": False}

    async def _get_daily_stats(self, device_id: int, cutoff_date: datetime) -> Dict[str, Any]:
        """获取设备日级峰谷用电统计"""
        result = await self.db.execute(
            select(
                func.sum(EnergyDaily.peak_energy).label("total_peak"),
                func.sum(EnergyDaily.valley_energy).label("total_valley"),
                func.sum(EnergyDaily.total_energy).label("total_energy"),
                func.count(EnergyDaily.id).label("record_count")
            ).where(
                and_(
                    EnergyDaily.device_id == device_id,
                    EnergyDaily.stat_date >= cutoff_date.date()
                )
            )
        )
        row = result.first()

        if row and row.total_energy and row.total_energy > 0:
            peak_ratio = float(row.total_peak or 0) / float(row.total_energy)
            valley_ratio = float(row.total_valley or 0) / float(row.total_energy)
            return {
                "peak_ratio": peak_ratio,
                "valley_ratio": valley_ratio,
                "peak_valley_diff": peak_ratio - valley_ratio,
                "data_days": row.record_count or 0,
                "has_data": True
            }
        return {"peak_ratio": 0.4, "valley_ratio": 0.3, "peak_valley_diff": 0.1, "data_days": 0, "has_data": False}

    def _calculate_recommendation(
        self,
        device: PowerDevice,
        shift_config: Optional[DeviceShiftConfig],
        hourly_stats: Dict,
        daily_stats: Dict
    ) -> Dict[str, Any]:
        """计算单个设备的推荐 ratio"""

        rated_power = device.rated_power
        current_ratio = shift_config.shiftable_power_ratio if shift_config else 0
        device_type = (device.device_type or "").upper()

        # CRITICAL: 验证额定功率有效性
        if not rated_power or rated_power <= 0:
            return {
                "device_id": device.id,
                "device_code": device.device_code,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "rated_power": 0,
                "current_ratio": round(current_ratio, 2),
                "recommended_ratio": 0,
                "current_shiftable_power": 0,
                "recommended_shiftable_power": 0,
                "confidence": "low",
                "data_days": 0,
                "has_change": False,
                "calculation_details": {"error": "设备额定功率无效"}
            }

        # 获取历史统计（如果没有数据则使用估算值）
        if hourly_stats["has_data"]:
            avg_power = hourly_stats["avg_power"]
            max_power = hourly_stats["max_power"]
            min_power = hourly_stats["min_power"]
        else:
            # 无历史数据时使用默认估算
            avg_power = rated_power * 0.7
            max_power = rated_power * 0.9
            min_power = rated_power * 0.3

        peak_ratio = daily_stats["peak_ratio"]
        data_days = max(hourly_stats.get("data_days", 0), daily_stats.get("data_days", 0))

        # 获取设备类型参数
        flexibility = self.FLEXIBILITY_FACTORS.get(device_type, 0.3)
        type_max = self.TYPE_MAX_RATIOS.get(device_type, 0.3)

        # 计算四个约束条件
        # 约束1: 最低功率约束 - 设备必须保持的最低功率不可转移
        constraint_1 = max(0, 1 - min_power / rated_power) if rated_power > 0 else 0

        # 约束2: 负荷波动空间 - 历史最大与平均之差代表可削减空间
        constraint_2 = max(0, (max_power - avg_power) / rated_power) if rated_power > 0 else 0

        # 约束3: 峰时用电可转移 - 峰时占比越高，可转移潜力越大
        constraint_3 = peak_ratio * flexibility

        # 约束4: 设备类型上限
        constraint_4 = type_max

        # 综合计算：取最小值 × 安全系数
        raw_ratio = min(constraint_1, constraint_2, constraint_3, constraint_4)
        safety_factor = 0.85
        recommended = round(raw_ratio * safety_factor, 2)

        # 确保推荐值在合理范围内
        recommended = max(0, min(recommended, type_max))

        # 置信度评估
        if data_days >= 30:
            confidence = "high"
        elif data_days >= 14:
            confidence = "medium"
        else:
            confidence = "low"

        # 判断是否有变化（差异超过1%）
        has_change = abs(recommended - current_ratio) > 0.01

        return {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": round(rated_power, 2),
            "current_ratio": round(current_ratio, 2),
            "recommended_ratio": recommended,
            "current_shiftable_power": round(rated_power * current_ratio, 2),
            "recommended_shiftable_power": round(rated_power * recommended, 2),
            "confidence": confidence,
            "data_days": data_days,
            "has_change": has_change,
            "calculation_details": {
                "avg_power": round(avg_power, 2),
                "max_power": round(max_power, 2),
                "min_power": round(min_power, 2),
                "peak_ratio": round(peak_ratio, 3),
                "flexibility_factor": flexibility,
                "type_max_ratio": type_max,
                "constraints": [
                    round(constraint_1, 3),
                    round(constraint_2, 3),
                    round(constraint_3, 3),
                    round(constraint_4, 3)
                ],
                "raw_ratio": round(raw_ratio, 3)
            }
        }

    async def update_device_ratio(
        self,
        device_id: int,
        new_ratio: float,
        auto_commit: bool = True
    ) -> Dict[str, Any]:
        """
        更新单个设备的 shiftable_power_ratio

        Args:
            device_id: 设备ID
            new_ratio: 新的比例值 (0-1)
            auto_commit: 是否自动提交事务（批量操作时设为False）

        Returns:
            Dict: 更新结果
        """
        # 输入验证
        if not (0 <= new_ratio <= 1):
            raise ValueError(f"new_ratio 必须在 0-1 之间，当前值: {new_ratio}")

        # 查找现有配置
        result = await self.db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device_id)
        )
        config = result.scalar_one_or_none()

        if config:
            old_ratio = config.shiftable_power_ratio
            config.shiftable_power_ratio = new_ratio
            config.is_shiftable = new_ratio > 0
            config.updated_at = datetime.now()
        else:
            # 创建新配置
            old_ratio = 0
            config = DeviceShiftConfig(
                device_id=device_id,
                is_shiftable=new_ratio > 0,
                shiftable_power_ratio=new_ratio
            )
            self.db.add(config)

        if auto_commit:
            await self.db.commit()

        return {
            "device_id": device_id,
            "old_ratio": old_ratio,
            "new_ratio": new_ratio,
            "success": True
        }

    async def batch_update_ratios(self, updates: Dict[int, float]) -> Dict[str, Any]:
        """
        批量更新设备的 shiftable_power_ratio (事务性操作)

        Args:
            updates: {device_id: new_ratio} 字典

        Returns:
            Dict: 批量更新结果
        """
        if not updates:
            return {
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "results": []
            }

        results = []
        success_count = 0

        try:
            for device_id, new_ratio in updates.items():
                try:
                    result = await self.update_device_ratio(device_id, new_ratio, auto_commit=False)
                    results.append(result)
                    if result["success"]:
                        success_count += 1
                except ValueError as e:
                    results.append({
                        "device_id": device_id,
                        "success": False,
                        "error": str(e)
                    })

            # 统一提交事务
            await self.db.commit()
        except Exception as e:
            # 失败时回滚
            await self.db.rollback()
            raise

        return {
            "total": len(updates),
            "success_count": success_count,
            "failed_count": len(updates) - success_count,
            "results": results
        }

    async def accept_all_recommendations(self, days: int = 30) -> Dict[str, Any]:
        """
        接受所有推荐值

        Args:
            days: 分析天数

        Returns:
            Dict: 更新结果
        """
        # 先获取所有推荐
        recommendations = await self.get_ratio_recommendations(days)

        # 筛选有变化的设备
        updates = {}
        for rec in recommendations["recommendations"]:
            if rec["has_change"]:
                updates[rec["device_id"]] = rec["recommended_ratio"]

        if not updates:
            return {
                "message": "没有需要更新的设备",
                "updated_count": 0
            }

        # 批量更新
        result = await self.batch_update_ratios(updates)
        result["message"] = f"已更新 {result['success_count']} 台设备的转移配置"

        return result
