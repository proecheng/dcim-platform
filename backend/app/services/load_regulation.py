"""
负荷调节服务 V2.3
实现温度、亮度、运行模式等负荷调节功能
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import LoadRegulationConfig, RegulationHistory, PowerDevice
from ..schemas.energy import (
    LoadRegulationConfigCreate,
    LoadRegulationConfigUpdate,
    LoadRegulationConfigResponse,
    RegulationSimulateRequest,
    RegulationSimulateResponse,
    RegulationApplyRequest,
    RegulationHistoryResponse,
    RegulationRecommendation
)


class LoadRegulationService:
    """负荷调节服务"""

    # 调节类型配置
    REGULATION_TYPES = {
        "temperature": {
            "name": "温度调节",
            "unit": "℃",
            "default_min": 22,
            "default_max": 28,
            "default_step": 1,
            "power_factor": -0.06,  # 每升高1℃，功率降低6%
            "comfort_impact": "medium",
            "performance_impact": "low"
        },
        "brightness": {
            "name": "亮度调节",
            "unit": "%",
            "default_min": 30,
            "default_max": 100,
            "default_step": 10,
            "power_factor": 0.01,  # 每降低1%，功率降低1%
            "comfort_impact": "low",
            "performance_impact": "none"
        },
        "mode": {
            "name": "运行模式",
            "unit": "mode",
            "default_min": 0,  # 0=节能, 1=标准, 2=高性能
            "default_max": 2,
            "default_step": 1,
            "power_factor": 0.15,  # 每降低一档，功率降低15%
            "comfort_impact": "none",
            "performance_impact": "medium"
        },
        "load": {
            "name": "负载优先级",
            "unit": "level",
            "default_min": 1,  # 1=高优先级, 2=中, 3=低
            "default_max": 3,
            "default_step": 1,
            "power_factor": 0.3,  # 每降低一级，可调功率30%
            "comfort_impact": "none",
            "performance_impact": "high"
        }
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_configs(
        self,
        device_id: Optional[int] = None,
        regulation_type: Optional[str] = None,
        is_enabled: bool = True
    ) -> List[LoadRegulationConfigResponse]:
        """获取负荷调节配置列表"""
        query = select(LoadRegulationConfig, PowerDevice).join(
            PowerDevice, LoadRegulationConfig.device_id == PowerDevice.id
        )

        conditions = []
        if device_id:
            conditions.append(LoadRegulationConfig.device_id == device_id)
        if regulation_type:
            conditions.append(LoadRegulationConfig.regulation_type == regulation_type)
        if is_enabled is not None:
            conditions.append(LoadRegulationConfig.is_enabled == is_enabled)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        rows = result.all()

        configs = []
        for config, device in rows:
            config_dict = {
                "id": config.id,
                "device_id": config.device_id,
                "regulation_type": config.regulation_type,
                "min_value": config.min_value,
                "max_value": config.max_value,
                "current_value": config.current_value,
                "default_value": config.default_value,
                "step_size": config.step_size,
                "unit": config.unit,
                "power_factor": config.power_factor,
                "base_power": config.base_power,
                "priority": config.priority,
                "comfort_impact": config.comfort_impact,
                "performance_impact": config.performance_impact,
                "power_curve": config.power_curve,
                "is_enabled": config.is_enabled,
                "is_auto": config.is_auto,
                "created_at": config.created_at,
                "updated_at": config.updated_at,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "rated_power": device.rated_power
            }
            configs.append(LoadRegulationConfigResponse(**config_dict))

        return configs

    async def get_config_by_id(self, config_id: int) -> Optional[LoadRegulationConfigResponse]:
        """根据ID获取配置"""
        query = select(LoadRegulationConfig, PowerDevice).join(
            PowerDevice, LoadRegulationConfig.device_id == PowerDevice.id
        ).where(LoadRegulationConfig.id == config_id)

        result = await self.db.execute(query)
        row = result.first()

        if not row:
            return None

        config, device = row
        return LoadRegulationConfigResponse(
            id=config.id,
            device_id=config.device_id,
            regulation_type=config.regulation_type,
            min_value=config.min_value,
            max_value=config.max_value,
            current_value=config.current_value,
            default_value=config.default_value,
            step_size=config.step_size,
            unit=config.unit,
            power_factor=config.power_factor,
            base_power=config.base_power,
            priority=config.priority,
            comfort_impact=config.comfort_impact,
            performance_impact=config.performance_impact,
            power_curve=config.power_curve,
            is_enabled=config.is_enabled,
            is_auto=config.is_auto,
            created_at=config.created_at,
            updated_at=config.updated_at,
            device_name=device.device_name,
            device_type=device.device_type,
            rated_power=device.rated_power
        )

    async def create_config(self, data: LoadRegulationConfigCreate) -> LoadRegulationConfig:
        """创建负荷调节配置"""
        # 获取调节类型默认配置
        type_config = self.REGULATION_TYPES.get(data.regulation_type, {})

        config = LoadRegulationConfig(
            device_id=data.device_id,
            regulation_type=data.regulation_type,
            min_value=data.min_value,
            max_value=data.max_value,
            current_value=data.current_value or data.default_value,
            default_value=data.default_value,
            step_size=data.step_size,
            unit=data.unit or type_config.get("unit"),
            power_factor=data.power_factor or type_config.get("power_factor"),
            base_power=data.base_power,
            priority=data.priority,
            comfort_impact=data.comfort_impact or type_config.get("comfort_impact", "low"),
            performance_impact=data.performance_impact or type_config.get("performance_impact", "none"),
            power_curve=data.power_curve,
            is_auto=data.is_auto
        )

        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def update_config(self, config_id: int, data: LoadRegulationConfigUpdate) -> Optional[LoadRegulationConfig]:
        """更新负荷调节配置"""
        result = await self.db.execute(
            select(LoadRegulationConfig).where(LoadRegulationConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)

        config.updated_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def delete_config(self, config_id: int) -> bool:
        """删除负荷调节配置"""
        result = await self.db.execute(
            select(LoadRegulationConfig).where(LoadRegulationConfig.id == config_id)
        )
        config = result.scalar_one_or_none()

        if not config:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def simulate_regulation(
        self,
        config_id: int,
        target_value: float
    ) -> Optional[RegulationSimulateResponse]:
        """模拟调节效果"""
        config_resp = await self.get_config_by_id(config_id)
        if not config_resp:
            return None

        # 计算功率变化
        current_value = config_resp.current_value or config_resp.default_value or config_resp.min_value
        base_power = config_resp.base_power or config_resp.rated_power or 10.0
        power_factor = config_resp.power_factor or 0.05

        # 根据调节类型计算功率
        value_change = target_value - current_value
        if config_resp.regulation_type == "temperature":
            # 温度升高，功率降低
            power_change = base_power * power_factor * value_change
        elif config_resp.regulation_type == "brightness":
            # 亮度降低，功率降低
            power_change = base_power * (value_change / 100)
        else:
            # 其他类型
            power_change = base_power * power_factor * value_change

        current_power = base_power
        estimated_power = max(0, current_power + power_change)

        return RegulationSimulateResponse(
            config_id=config_id,
            device_id=config_resp.device_id,
            device_name=config_resp.device_name or "Unknown",
            regulation_type=config_resp.regulation_type,
            current_value=current_value,
            target_value=target_value,
            current_power=current_power,
            estimated_power=estimated_power,
            power_change=power_change,
            comfort_impact=config_resp.comfort_impact,
            performance_impact=config_resp.performance_impact
        )

    async def apply_regulation(
        self,
        config_id: int,
        target_value: float,
        reason: str = "manual",
        operator_id: Optional[int] = None,
        remark: Optional[str] = None
    ) -> Optional[RegulationHistoryResponse]:
        """应用调节方案"""
        # 获取配置
        result = await self.db.execute(
            select(LoadRegulationConfig, PowerDevice).join(
                PowerDevice, LoadRegulationConfig.device_id == PowerDevice.id
            ).where(LoadRegulationConfig.id == config_id)
        )
        row = result.first()
        if not row:
            return None

        config, device = row

        # 模拟计算功率变化
        sim_result = await self.simulate_regulation(config_id, target_value)
        if not sim_result:
            return None

        # 创建历史记录
        history = RegulationHistory(
            config_id=config_id,
            device_id=config.device_id,
            regulation_type=config.regulation_type,
            old_value=config.current_value,
            new_value=target_value,
            power_before=sim_result.current_power,
            power_after=sim_result.estimated_power,
            power_saved=abs(sim_result.power_change) if sim_result.power_change < 0 else 0,
            trigger_reason=reason,
            trigger_detail=remark,
            status="completed",
            executed_at=datetime.now(),
            operator_id=operator_id
        )
        self.db.add(history)

        # 更新配置当前值
        config.current_value = target_value
        config.updated_at = datetime.now()

        await self.db.commit()
        await self.db.refresh(history)

        return RegulationHistoryResponse(
            id=history.id,
            config_id=history.config_id,
            device_id=history.device_id,
            device_name=device.device_name,
            regulation_type=history.regulation_type,
            old_value=history.old_value,
            new_value=history.new_value,
            power_before=history.power_before,
            power_after=history.power_after,
            power_saved=history.power_saved,
            trigger_reason=history.trigger_reason,
            status=history.status,
            executed_at=history.executed_at,
            created_at=history.created_at
        )

    async def get_history(
        self,
        device_id: Optional[int] = None,
        config_id: Optional[int] = None,
        limit: int = 50
    ) -> List[RegulationHistoryResponse]:
        """获取调节历史"""
        query = select(RegulationHistory, PowerDevice).join(
            PowerDevice, RegulationHistory.device_id == PowerDevice.id
        )

        if device_id:
            query = query.where(RegulationHistory.device_id == device_id)
        if config_id:
            query = query.where(RegulationHistory.config_id == config_id)

        query = query.order_by(RegulationHistory.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        return [
            RegulationHistoryResponse(
                id=h.id,
                config_id=h.config_id,
                device_id=h.device_id,
                device_name=d.device_name,
                regulation_type=h.regulation_type,
                old_value=h.old_value,
                new_value=h.new_value,
                power_before=h.power_before,
                power_after=h.power_after,
                power_saved=h.power_saved,
                trigger_reason=h.trigger_reason,
                status=h.status,
                executed_at=h.executed_at,
                created_at=h.created_at
            )
            for h, d in rows
        ]

    async def get_recommendations(
        self,
        current_demand: Optional[float] = None,
        declared_demand: Optional[float] = None
    ) -> List[RegulationRecommendation]:
        """获取调节建议"""
        configs = await self.get_configs(is_enabled=True)
        recommendations = []

        for config in configs:
            # 根据当前需量情况生成建议
            if config.regulation_type == "temperature":
                # 温度调节建议
                current = config.current_value or 24
                if current < 26:
                    recommended = min(config.max_value, current + 2)
                    power_saving = (config.base_power or 10) * 0.12
                    recommendations.append(RegulationRecommendation(
                        config_id=config.id,
                        device_id=config.device_id,
                        device_name=config.device_name or "Unknown",
                        regulation_type=config.regulation_type,
                        current_value=current,
                        recommended_value=recommended,
                        power_saving=power_saving,
                        reason=f"将温度从{current}℃调高至{recommended}℃可节省约{power_saving:.1f}kW",
                        priority="medium"
                    ))

            elif config.regulation_type == "brightness":
                # 亮度调节建议
                current = config.current_value or 100
                if current > 70:
                    recommended = 70
                    power_saving = (config.base_power or 5) * 0.3
                    recommendations.append(RegulationRecommendation(
                        config_id=config.id,
                        device_id=config.device_id,
                        device_name=config.device_name or "Unknown",
                        regulation_type=config.regulation_type,
                        current_value=current,
                        recommended_value=recommended,
                        power_saving=power_saving,
                        reason=f"将亮度从{current}%降至{recommended}%可节省约{power_saving:.1f}kW",
                        priority="low"
                    ))

        # 按节省功率排序
        recommendations.sort(key=lambda x: x.power_saving, reverse=True)
        return recommendations
