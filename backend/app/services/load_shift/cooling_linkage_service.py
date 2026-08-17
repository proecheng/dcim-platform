"""
Cooling Linkage Service
制冷联动服务 - 负荷转移时自动调整制冷系统
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.models.load_shift import CoolingLinkageConfig, CoolingLinkageRecord
from app.models.topology_config import CoolingZone


CONFIG_FIELDS = {
    "enabled",
    "lag_time_minutes",
    "target_cop",
    "cop_lower_threshold",
    "cop_upper_threshold",
    "target_supply_temp",
    "supply_temp_lower",
    "supply_temp_upper",
    "target_return_temp",
    "return_temp_lower",
    "return_temp_upper",
    "power_adjust_step",
    "max_adjust_ratio",
    "adjust_interval_minutes",
    "safety_protection_enabled",
    "min_cooling_power",
    "max_cooling_power",
    "precool_target_temp",
    "precool_enabled",
}


class CoolingLinkageService:
    """制冷联动服务"""

    @staticmethod
    async def _resolve_cooling_zone_id(db: AsyncSession, requested_zone_id: Optional[int] = None) -> int:
        """Return a valid cooling zone id for global linkage config."""
        if requested_zone_id:
            return int(requested_zone_id)

        result = await db.execute(select(CoolingZone).order_by(CoolingZone.id).limit(1))
        zone = result.scalar_one_or_none()
        if zone:
            return int(zone.id)

        zone = CoolingZone(
            zone_code="DEFAULT-COOLING-ZONE",
            zone_name="默认制冷区域",
            design_capacity_kw=2000,
            description="系统自动创建，用于全局制冷联动配置",
        )
        db.add(zone)
        await db.flush()
        return int(zone.id)

    @staticmethod
    async def get_config(db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        获取制冷联动配置

        Returns:
            配置字典，如果不存在则返回默认配置
        """
        result = await db.execute(select(CoolingLinkageConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            # 返回默认配置
            return {
                "enabled": True,
                "lag_time_minutes": 20,
                "target_cop": 3.0,
                "cop_lower_threshold": 2.0,
                "cop_upper_threshold": 4.5,
                "target_supply_temp": 10.0,
                "supply_temp_lower": 5.0,
                "supply_temp_upper": 15.0,
                "target_return_temp": 15.0,
                "return_temp_lower": 10.0,
                "return_temp_upper": 20.0,
                "power_adjust_step": 20,
                "max_adjust_ratio": 0.25,
                "adjust_interval_minutes": 10,
                "safety_protection_enabled": True,
                "min_cooling_power": 100,
                "max_cooling_power": 2000,
            }

        return {
            "id": config.id,
            "enabled": config.enabled,
            "lag_time_minutes": config.lag_time_minutes,
            "target_cop": float(config.target_cop) if config.target_cop else 3.0,
            "cop_lower_threshold": float(config.cop_lower_threshold) if config.cop_lower_threshold else 2.0,
            "cop_upper_threshold": float(config.cop_upper_threshold) if config.cop_upper_threshold else 4.5,
            "target_supply_temp": float(config.target_supply_temp) if config.target_supply_temp else 10.0,
            "supply_temp_lower": float(config.supply_temp_lower) if config.supply_temp_lower else 5.0,
            "supply_temp_upper": float(config.supply_temp_upper) if config.supply_temp_upper else 15.0,
            "target_return_temp": float(config.target_return_temp) if config.target_return_temp else 15.0,
            "return_temp_lower": float(config.return_temp_lower) if config.return_temp_lower else 10.0,
            "return_temp_upper": float(config.return_temp_upper) if config.return_temp_upper else 20.0,
            "power_adjust_step": config.power_adjust_step,
            "max_adjust_ratio": float(config.max_adjust_ratio) if config.max_adjust_ratio else 0.25,
            "adjust_interval_minutes": config.adjust_interval_minutes,
            "safety_protection_enabled": config.safety_protection_enabled,
            "min_cooling_power": float(config.min_cooling_power) if config.min_cooling_power else 100,
            "max_cooling_power": float(config.max_cooling_power) if config.max_cooling_power else 2000,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

    @staticmethod
    async def update_config(db: AsyncSession, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新制冷联动配置

        Args:
            db: 数据库会话
            config_data: 配置数据

        Returns:
            更新后的配置
        """
        result = await db.execute(select(CoolingLinkageConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            # 创建新配置
            cooling_zone_id = await CoolingLinkageService._resolve_cooling_zone_id(
                db, config_data.get("cooling_zone_id")
            )
            config = CoolingLinkageConfig(
                cooling_zone_id=cooling_zone_id,
                enabled=config_data.get("enabled", True),
                lag_time_minutes=config_data.get("lag_time_minutes", 20),
                target_cop=config_data.get("target_cop", 3.0),
                cop_lower_threshold=config_data.get("cop_lower_threshold", 2.0),
                cop_upper_threshold=config_data.get("cop_upper_threshold", 4.5),
                target_supply_temp=config_data.get("target_supply_temp", 10.0),
                supply_temp_lower=config_data.get("supply_temp_lower", 5.0),
                supply_temp_upper=config_data.get("supply_temp_upper", 15.0),
                target_return_temp=config_data.get("target_return_temp", 15.0),
                return_temp_lower=config_data.get("return_temp_lower", 10.0),
                return_temp_upper=config_data.get("return_temp_upper", 20.0),
                power_adjust_step=config_data.get("power_adjust_step", 20),
                max_adjust_ratio=config_data.get("max_adjust_ratio", 0.25),
                adjust_interval_minutes=config_data.get("adjust_interval_minutes", 10),
                safety_protection_enabled=config_data.get("safety_protection_enabled", True),
                min_cooling_power=config_data.get("min_cooling_power", 100),
                max_cooling_power=config_data.get("max_cooling_power", 2000),
            )
            db.add(config)
        else:
            # 更新现有配置
            if not config.cooling_zone_id:
                config.cooling_zone_id = await CoolingLinkageService._resolve_cooling_zone_id(
                    db, config_data.get("cooling_zone_id")
                )
            for key, value in config_data.items():
                if key in CONFIG_FIELDS:
                    setattr(config, key, value)
            config.updated_at = datetime.now()

        await db.commit()
        await db.refresh(config)

        return await CoolingLinkageService.get_config(db)

    @staticmethod
    async def get_status(db: AsyncSession) -> Dict[str, Any]:
        """
        获取制冷联动当前状态

        Returns:
            状态字典
        """
        records_result = await db.execute(
            select(CoolingLinkageRecord).order_by(desc(CoolingLinkageRecord.timestamp)).limit(200)
        )
        records = records_result.scalars().all()
        latest = records[0] if records else None
        if latest is None:
            return {
                "total_cooling_power": None,
                "current_cop": None,
                "supply_temp": None,
                "return_temp": None,
                "linkage_active": False,
                "last_adjust_time": None,
                "adjust_count": 0,
                "total_energy_saving": None,
                "total_cost_saving": None,
                "data_sufficient": False,
                "data_source": None,
                "warning": "暂无制冷联动执行记录，无法确认当前状态或累计节能收益",
            }

        return {
            "total_cooling_power": float(latest.after_power) if latest.after_power is not None else None,
            "current_cop": float(latest.cop_after) if latest.cop_after is not None else None,
            "supply_temp": float(latest.supply_temp_after) if latest.supply_temp_after is not None else None,
            "return_temp": float(latest.return_temp_after) if latest.return_temp_after is not None else None,
            "linkage_active": False,
            "last_adjust_time": latest.timestamp.isoformat() if latest.timestamp else None,
            "adjust_count": len(records),
            "total_energy_saving": None,
            "total_cost_saving": None,
            "data_sufficient": True,
            "data_source": "cooling_linkage_records",
            "warning": "联动记录未包含持续时长与电价，暂不能计算累计节能量和成本收益",
        }

    @staticmethod
    async def get_history(
        db: AsyncSession, limit: int = 50, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取制冷联动历史记录

        Args:
            db: 数据库会话
            limit: 返回记录数量限制
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            历史记录列表
        """
        query = select(CoolingLinkageRecord)

        conditions = []
        if start_time:
            conditions.append(CoolingLinkageRecord.timestamp >= start_time)
        if end_time:
            conditions.append(CoolingLinkageRecord.timestamp <= end_time)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(CoolingLinkageRecord.timestamp)).limit(limit)

        result = await db.execute(query)
        records = result.scalars().all()

        return [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "event_type": record.event_type,
                "before_power": float(record.before_power) if record.before_power else 0,
                "after_power": float(record.after_power) if record.after_power else 0,
                "power_change": float(record.power_change) if record.power_change else 0,
                "cop_before": float(record.cop_before) if record.cop_before else 0,
                "cop_after": float(record.cop_after) if record.cop_after else 0,
                "supply_temp_before": float(record.supply_temp_before) if record.supply_temp_before else 0,
                "supply_temp_after": float(record.supply_temp_after) if record.supply_temp_after else 0,
                "return_temp_before": float(record.return_temp_before) if record.return_temp_before else 0,
                "return_temp_after": float(record.return_temp_after) if record.return_temp_after else 0,
                "reason": record.reason,
                "execution_id": record.execution_id,
            }
            for record in records
        ]

    @staticmethod
    async def create_history_record(
        db: AsyncSession,
        event_type: str,
        before_power: float,
        after_power: float,
        cop_before: float,
        cop_after: float,
        supply_temp_before: float,
        supply_temp_after: float,
        return_temp_before: float,
        return_temp_after: float,
        reason: str,
        execution_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        创建制冷联动历史记录

        Args:
            db: 数据库会话
            event_type: 事件类型 (adjust/alarm/recovery/manual)
            before_power: 调整前功率
            after_power: 调整后功率
            cop_before: 调整前COP
            cop_after: 调整后COP
            supply_temp_before: 调整前供水温度
            supply_temp_after: 调整后供水温度
            return_temp_before: 调整前回水温度
            return_temp_after: 调整后回水温度
            reason: 调整原因
            execution_id: 关联的执行记录ID

        Returns:
            创建的历史记录
        """
        record = CoolingLinkageRecord(
            timestamp=datetime.now(),
            event_type=event_type,
            before_power=before_power,
            after_power=after_power,
            power_change=after_power - before_power,
            cop_before=cop_before,
            cop_after=cop_after,
            supply_temp_before=supply_temp_before,
            supply_temp_after=supply_temp_after,
            return_temp_before=return_temp_before,
            return_temp_after=return_temp_after,
            reason=reason,
            execution_id=execution_id,
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        return {
            "id": record.id,
            "timestamp": record.timestamp.isoformat(),
            "event_type": record.event_type,
            "before_power": float(record.before_power),
            "after_power": float(record.after_power),
            "power_change": float(record.power_change),
            "cop_before": float(record.cop_before),
            "cop_after": float(record.cop_after),
            "reason": record.reason,
        }
