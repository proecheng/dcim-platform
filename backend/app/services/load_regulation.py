"""
负荷调节服务 V2.3
实现温度、亮度、运行模式等负荷调节功能
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import LoadRegulationConfig, RegulationHistory, PowerDevice
from ..models.point import PointRealtime
from .device_config_generator import DeviceConfigAutoGenerator
from .device_control_service import ControlResult, DeviceControlService
from .command_registry import authorize_command
from ..schemas.energy import (
    LoadRegulationConfigCreate,
    LoadRegulationConfigUpdate,
    LoadRegulationConfigResponse,
    RegulationSimulateResponse,
    RegulationHistoryResponse,
    RegulationRecommendation,
)


class LoadRegulationService:
    """负荷调节服务"""

    REALTIME_MAX_AGE = timedelta(minutes=5)
    NON_MEASURED_SOURCES = {"demo", "demo_backfill", "simulated", "unknown"}

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
            "performance_impact": "low",
        },
        "brightness": {
            "name": "亮度调节",
            "unit": "%",
            "default_min": 30,
            "default_max": 100,
            "default_step": 10,
            "power_factor": 0.01,  # 每降低1%，功率降低1%
            "comfort_impact": "low",
            "performance_impact": "none",
        },
        "mode": {
            "name": "运行模式",
            "unit": "mode",
            "default_min": 0,  # 0=节能, 1=标准, 2=高性能
            "default_max": 2,
            "default_step": 1,
            "power_factor": 0.15,  # 每降低一档，功率降低15%
            "comfort_impact": "none",
            "performance_impact": "medium",
        },
        "load": {
            "name": "负载优先级",
            "unit": "level",
            "default_min": 1,  # 1=高优先级, 2=中, 3=低
            "default_max": 3,
            "default_step": 1,
            "power_factor": 0.3,  # 每降低一级，可调功率30%
            "comfort_impact": "none",
            "performance_impact": "high",
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_configs(
        self, device_id: Optional[int] = None, regulation_type: Optional[str] = None, is_enabled: bool = True
    ) -> List[LoadRegulationConfigResponse]:
        """获取负荷调节配置列表"""
        await DeviceConfigAutoGenerator(self.db).ensure_missing_regulation_configs()

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
                "rated_power": device.rated_power,
                "power_point_id": device.power_point_id,
            }
            configs.append(LoadRegulationConfigResponse(**config_dict))

        return configs

    async def get_config_by_id(self, config_id: int) -> Optional[LoadRegulationConfigResponse]:
        """根据ID获取配置"""
        query = (
            select(LoadRegulationConfig, PowerDevice)
            .join(PowerDevice, LoadRegulationConfig.device_id == PowerDevice.id)
            .where(LoadRegulationConfig.id == config_id)
        )

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
            rated_power=device.rated_power,
            power_point_id=device.power_point_id,
        )

    @staticmethod
    def _current_value(config: LoadRegulationConfigResponse) -> float:
        for value in (config.current_value, config.default_value, config.min_value):
            if value is not None:
                return float(value)
        return 0.0

    @staticmethod
    def _interpolate_curve(curve: Optional[List[dict]], value: float) -> Optional[float]:
        points: List[tuple[float, float]] = []
        for item in curve or []:
            if not isinstance(item, dict) or item.get("value") is None:
                continue
            metric = item.get("power_ratio")
            if metric is None:
                metric = item.get("power")
            if metric is not None:
                points.append((float(item["value"]), float(metric)))
        points.sort(key=lambda item: item[0])
        if not points or value < points[0][0] or value > points[-1][0]:
            return None
        for point_value, metric in points:
            if abs(value - point_value) < 1e-9:
                return metric
        for (left_value, left_metric), (right_value, right_metric) in zip(points, points[1:]):
            if left_value <= value <= right_value:
                ratio = (value - left_value) / (right_value - left_value)
                return left_metric + (right_metric - left_metric) * ratio
        return None

    @staticmethod
    def _validate_target(config: LoadRegulationConfigResponse, target_value: float) -> None:
        if target_value < config.min_value or target_value > config.max_value:
            raise ValueError(f"目标值必须在 {config.min_value} 至 {config.max_value}{config.unit or ''} 范围内")
        if config.step_size > 0:
            steps = (target_value - config.min_value) / config.step_size
            if abs(steps - round(steps)) > 1e-6:
                raise ValueError(f"目标值必须按 {config.step_size}{config.unit or ''} 步长设置")

    async def _get_current_power(self, power_point_id: Optional[int]) -> tuple[Optional[float], Optional[str], str]:
        if not power_point_id:
            return None, None, "设备未关联实时功率点位"
        realtime = await self.db.get(PointRealtime, power_point_id)
        if realtime is None or realtime.value is None:
            return None, None, "实时功率点位暂无读数"
        source = (realtime.source or "unknown").lower()
        if source in self.NON_MEASURED_SOURCES:
            return None, source, f"功率点位来源为 {source}，不能作为真实节能量依据"
        if realtime.quality != 0 or realtime.status not in {None, "normal"}:
            return None, source, "实时功率读数质量异常或设备离线"
        if realtime.updated_at is None:
            return None, source, "实时功率读数缺少更新时间"
        now = datetime.now(realtime.updated_at.tzinfo) if realtime.updated_at.tzinfo else datetime.now()
        if now - realtime.updated_at > self.REALTIME_MAX_AGE:
            return None, source, "实时功率读数已超过5分钟，不能用于当前调节模拟"
        current_power = float(realtime.value)
        if current_power < 0:
            return None, source, "实时功率读数不能为负数"
        return current_power, source, ""

    def _estimate_power(
        self,
        config: LoadRegulationConfigResponse,
        current_value: float,
        target_value: float,
        current_power: float,
    ) -> tuple[Optional[float], Optional[str]]:
        current_curve_value = self._interpolate_curve(config.power_curve, current_value)
        target_curve_value = self._interpolate_curve(config.power_curve, target_value)
        if current_curve_value is not None and target_curve_value is not None and current_curve_value > 0:
            return max(0.0, current_power * target_curve_value / current_curve_value), "实时功率×功率曲线插值"

        if config.power_factor is None:
            return None, None
        value_change = target_value - current_value
        power_factor = float(config.power_factor)
        if abs(power_factor) <= 1:
            power_change = current_power * power_factor * value_change
            method = "实时功率×比例系数"
        else:
            power_change = power_factor * value_change
            method = "实时功率+kW单位变化系数"
        return max(0.0, current_power + power_change), method

    async def _build_simulation(
        self, config: LoadRegulationConfigResponse, target_value: float
    ) -> RegulationSimulateResponse:
        self._validate_target(config, target_value)
        current_value = self._current_value(config)
        current_power, source, warning = await self._get_current_power(config.power_point_id)
        estimated_power: Optional[float] = None
        calculation_method: Optional[str] = None
        if current_power is not None:
            estimated_power, calculation_method = self._estimate_power(
                config, current_value, target_value, current_power
            )
            if estimated_power is None:
                warning = "缺少覆盖当前值与目标值的功率曲线或有效功率系数"

        data_sufficient = current_power is not None and estimated_power is not None
        power_change = estimated_power - current_power if data_sufficient else None
        return RegulationSimulateResponse(
            config_id=config.id,
            device_id=config.device_id,
            device_name=config.device_name or "Unknown",
            regulation_type=config.regulation_type,
            current_value=current_value,
            target_value=target_value,
            current_power=round(current_power, 3) if current_power is not None else None,
            estimated_power=round(estimated_power, 3) if estimated_power is not None else None,
            power_change=round(power_change, 3) if power_change is not None else None,
            data_sufficient=data_sufficient,
            data_source=source,
            calculation_method=calculation_method,
            warning=warning or None,
            comfort_impact=config.comfort_impact,
            performance_impact=config.performance_impact,
        )

    async def create_config(self, data: LoadRegulationConfigCreate) -> LoadRegulationConfig:
        """创建负荷调节配置"""
        existing = await self.db.execute(
            select(LoadRegulationConfig.id)
            .where(
                LoadRegulationConfig.device_id == data.device_id,
                LoadRegulationConfig.regulation_type == data.regulation_type,
            )
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("该设备已存在同类型负荷调节配置")

        # 获取调节类型默认配置
        type_config = self.REGULATION_TYPES.get(data.regulation_type, {})

        config = LoadRegulationConfig(
            device_id=data.device_id,
            regulation_type=data.regulation_type,
            min_value=data.min_value,
            max_value=data.max_value,
            current_value=data.current_value if data.current_value is not None else data.default_value,
            default_value=data.default_value,
            step_size=data.step_size,
            unit=data.unit or type_config.get("unit"),
            power_factor=data.power_factor if data.power_factor is not None else type_config.get("power_factor"),
            base_power=data.base_power,
            priority=data.priority,
            comfort_impact=data.comfort_impact or type_config.get("comfort_impact", "low"),
            performance_impact=data.performance_impact or type_config.get("performance_impact", "none"),
            power_curve=data.power_curve,
            is_auto=data.is_auto,
        )

        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def update_config(self, config_id: int, data: LoadRegulationConfigUpdate) -> Optional[LoadRegulationConfig]:
        """更新负荷调节配置"""
        result = await self.db.execute(select(LoadRegulationConfig).where(LoadRegulationConfig.id == config_id))
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
        result = await self.db.execute(select(LoadRegulationConfig).where(LoadRegulationConfig.id == config_id))
        config = result.scalar_one_or_none()

        if not config:
            return False

        await self.db.delete(config)
        await self.db.commit()
        return True

    async def simulate_regulation(self, config_id: int, target_value: float) -> Optional[RegulationSimulateResponse]:
        """模拟调节效果"""
        config_resp = await self.get_config_by_id(config_id)
        if not config_resp:
            return None
        return await self._build_simulation(config_resp, target_value)

    async def apply_regulation(
        self,
        config_id: int,
        target_value: float,
        reason: str = "manual",
        operator_id: Optional[int] = None,
        remark: Optional[str] = None,
    ) -> Optional[RegulationHistoryResponse]:
        """应用调节方案"""
        # 获取配置
        result = await self.db.execute(
            select(LoadRegulationConfig, PowerDevice)
            .join(PowerDevice, LoadRegulationConfig.device_id == PowerDevice.id)
            .where(LoadRegulationConfig.id == config_id)
        )
        row = result.first()
        if not row:
            return None

        config, device = row

        config_resp = await self.get_config_by_id(config_id)
        if config_resp is None:
            return None
        self._validate_target(config_resp, target_value)

        # 估算功率变化并通过统一设备控制入口提交，不能直接把数据库写入当执行成功。
        sim_result = await self.simulate_regulation(config_id, target_value)
        if not sim_result:
            return None

        authorization = authorize_command(
            "device_regulation",
            {
                "device_id": config.device_id,
                "regulation_type": config.regulation_type,
                "target_value": target_value,
                "force": False,
            },
            entrypoint="load_regulation",
        )
        action = await DeviceControlService(self.db).control_device_regulation(
            device_id=config.device_id,
            regulation_type=config.regulation_type,
            target_value=target_value,
            command_authorization=authorization,
        )
        status_map = {
            ControlResult.SUCCESS: "completed",
            ControlResult.PENDING: "pending",
            ControlResult.SIMULATED: "simulated",
            ControlResult.PARTIAL: "failed",
            ControlResult.FAILED: "failed",
        }
        status = status_map[action.result]
        details = "; ".join(part for part in (remark, action.message) if part)

        # 创建历史记录
        history = RegulationHistory(
            config_id=config_id,
            device_id=config.device_id,
            regulation_type=config.regulation_type,
            old_value=config.current_value,
            new_value=target_value,
            power_before=sim_result.current_power,
            power_after=sim_result.estimated_power,
            power_saved=(
                abs(sim_result.power_change)
                if status == "completed" and sim_result.power_change is not None and sim_result.power_change < 0
                else None
            ),
            trigger_reason=reason,
            trigger_detail=details or None,
            status=status,
            executed_at=datetime.now() if status in {"completed", "simulated"} else None,
            operator_id=operator_id,
        )
        self.db.add(history)

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
            created_at=history.created_at,
        )

    async def get_history(
        self, device_id: Optional[int] = None, config_id: Optional[int] = None, limit: int = 50
    ) -> List[RegulationHistoryResponse]:
        """获取调节历史"""
        query = select(RegulationHistory, PowerDevice).join(PowerDevice, RegulationHistory.device_id == PowerDevice.id)

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
                created_at=h.created_at,
            )
            for h, d in rows
        ]

    async def get_recommendations(
        self, current_demand: Optional[float] = None, declared_demand: Optional[float] = None
    ) -> List[RegulationRecommendation]:
        """获取调节建议"""
        configs = await self.get_configs(is_enabled=True)
        recommendations = []

        for config in configs:
            # 根据当前需量情况生成建议
            if config.regulation_type == "temperature":
                # 温度调节建议
                current = self._current_value(config)
                if current < 26:
                    recommended = min(config.max_value, current + 2)
                    simulation = await self._build_simulation(config, recommended)
                    power_saving = max(0.0, -simulation.power_change) if simulation.power_change is not None else None
                    saving_text = (
                        f"可节省约{power_saving:.1f}kW" if power_saving is not None else "节能量待实时功率接入后评估"
                    )
                    recommendations.append(
                        RegulationRecommendation(
                            config_id=config.id,
                            device_id=config.device_id,
                            device_name=config.device_name or "Unknown",
                            regulation_type=config.regulation_type,
                            current_value=current,
                            recommended_value=recommended,
                            power_saving=power_saving,
                            data_sufficient=simulation.data_sufficient,
                            data_source=simulation.data_source,
                            reason=f"将温度从{current}℃调高至{recommended}℃，{saving_text}",
                            priority="medium",
                        )
                    )

            elif config.regulation_type == "brightness":
                # 亮度调节建议
                current = self._current_value(config)
                if current > 70:
                    recommended = 70
                    simulation = await self._build_simulation(config, recommended)
                    power_saving = max(0.0, -simulation.power_change) if simulation.power_change is not None else None
                    saving_text = (
                        f"可节省约{power_saving:.1f}kW" if power_saving is not None else "节能量待实时功率接入后评估"
                    )
                    recommendations.append(
                        RegulationRecommendation(
                            config_id=config.id,
                            device_id=config.device_id,
                            device_name=config.device_name or "Unknown",
                            regulation_type=config.regulation_type,
                            current_value=current,
                            recommended_value=recommended,
                            power_saving=power_saving,
                            data_sufficient=simulation.data_sufficient,
                            data_source=simulation.data_source,
                            reason=f"将亮度从{current}%降至{recommended}%，{saving_text}",
                            priority="low",
                        )
                    )

        # 按节省功率排序
        recommendations.sort(key=lambda item: item.power_saving if item.power_saving is not None else -1, reverse=True)
        return recommendations
