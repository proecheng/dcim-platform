"""
模拟计算服务
Simulation Service

提供What-if模拟计算功能，支持参数调整实时计算收益
用于节能建议详情页的交互式模拟器
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from .pricing_service import PricingService
from ..models.energy import (
    PowerDevice, DeviceShiftConfig, LoadRegulationConfig,
    PUEHistory, EnergyDaily
)

logger = logging.getLogger(__name__)


class SimulationType(str, Enum):
    """模拟类型"""
    DEMAND_ADJUSTMENT = "demand_adjustment"   # 需量调整
    PEAK_SHIFT = "peak_shift"                 # 峰谷转移
    DEVICE_REGULATION = "device_regulation"   # 设备调节
    POWER_FACTOR = "power_factor"             # 功率因数改善


@dataclass
class SimulationResult:
    """模拟结果"""
    simulation_type: SimulationType
    is_feasible: bool
    current_state: Dict[str, Any]
    simulated_state: Dict[str, Any]
    benefit: Dict[str, Any]
    confidence: float
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class SimulationService:
    """
    模拟计算服务

    核心功能:
    1. 需量调整模拟 - 调整申报需量后的电费变化
    2. 峰谷转移模拟 - 负荷从高价时段转移到低价时段
    3. 设备调节模拟 - 调整设备参数（温度、亮度等）
    4. 综合收益计算 - 带置信度的收益估算
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.pricing_service = PricingService(db)

    async def simulate_demand_adjustment(
        self,
        new_declared_demand: float,
        historical_days: int = 30
    ) -> SimulationResult:
        """
        模拟需量调整

        Args:
            new_declared_demand: 新的申报需量 kW
            historical_days: 使用多少天历史数据进行模拟

        Returns:
            SimulationResult: 模拟结果
        """
        # 获取当前电价配置
        full_pricing = await self.pricing_service.get_full_pricing_config()
        global_config = full_pricing.get("global_config") or {}

        current_declared = global_config.get("declared_demand", 0)
        demand_price = global_config.get("demand_price", 38)
        over_multiplier = global_config.get("over_demand_multiplier", 2)

        # 获取历史需量数据
        demand_history = await self._get_demand_history(historical_days)

        if not demand_history:
            return SimulationResult(
                simulation_type=SimulationType.DEMAND_ADJUSTMENT,
                is_feasible=False,
                current_state={"declared_demand": current_declared},
                simulated_state={"declared_demand": new_declared_demand},
                benefit={"error": "缺少历史数据"},
                confidence=0,
                warnings=["无法获取历史需量数据"]
            )

        max_demand = max(demand_history)
        avg_demand = sum(demand_history) / len(demand_history)
        percentile_95 = sorted(demand_history)[int(len(demand_history) * 0.95)]

        # 计算当前成本（按月）
        current_monthly_cost = self._calculate_demand_cost(
            current_declared, max_demand, demand_price, over_multiplier
        )

        # 计算模拟成本
        simulated_monthly_cost = self._calculate_demand_cost(
            new_declared_demand, max_demand, demand_price, over_multiplier
        )

        # 计算超需量风险
        over_risk = self._calculate_over_demand_risk(
            new_declared_demand, demand_history
        )

        # 计算收益
        monthly_saving = current_monthly_cost - simulated_monthly_cost
        annual_saving = monthly_saving * 12

        # 确定可行性和置信度
        is_feasible = new_declared_demand >= percentile_95 * 0.95
        confidence = self._calculate_confidence(
            is_feasible, over_risk, len(demand_history)
        )

        warnings = []
        recommendations = []

        if new_declared_demand < max_demand:
            warnings.append(f"新申报需量({new_declared_demand:.0f}kW)低于历史最大需量({max_demand:.0f}kW)")

        if over_risk > 0.2:
            warnings.append(f"超需量风险较高({over_risk*100:.1f}%)")
            recommendations.append("建议适当提高申报需量或采取需量控制措施")

        if new_declared_demand > max_demand * 1.3:
            recommendations.append("申报需量可能过高，存在浪费空间")

        return SimulationResult(
            simulation_type=SimulationType.DEMAND_ADJUSTMENT,
            is_feasible=is_feasible,
            current_state={
                "declared_demand": current_declared,
                "max_demand": max_demand,
                "avg_demand": round(avg_demand, 2),
                "percentile_95": round(percentile_95, 2),
                "monthly_cost": round(current_monthly_cost, 2)
            },
            simulated_state={
                "declared_demand": new_declared_demand,
                "over_demand_risk": round(over_risk * 100, 2),
                "monthly_cost": round(simulated_monthly_cost, 2)
            },
            benefit={
                "monthly_saving": round(monthly_saving, 2),
                "annual_saving": round(annual_saving, 2),
                "saving_percentage": round(
                    (monthly_saving / current_monthly_cost * 100)
                    if current_monthly_cost > 0 else 0,
                    2
                )
            },
            confidence=round(confidence, 2),
            warnings=warnings,
            recommendations=recommendations
        )

    async def simulate_peak_shift(
        self,
        shift_power: float,
        shift_hours: float,
        source_period: str = "peak",
        target_period: str = "valley",
        working_days_per_year: int = 300
    ) -> SimulationResult:
        """
        模拟峰谷负荷转移

        Args:
            shift_power: 转移功率 kW
            shift_hours: 每天转移时长 h
            source_period: 源时段（高价）
            target_period: 目标时段（低价）
            working_days_per_year: 年工作日

        Returns:
            SimulationResult: 模拟结果
        """
        # 获取电价
        prices = await self.pricing_service.get_all_prices()
        source_price = prices.get(f"{source_period}_price", 0)
        target_price = prices.get(f"{target_period}_price", 0)
        price_diff = source_price - target_price

        if price_diff <= 0:
            return SimulationResult(
                simulation_type=SimulationType.PEAK_SHIFT,
                is_feasible=False,
                current_state={"source_period": source_period, "source_price": source_price},
                simulated_state={"target_period": target_period, "target_price": target_price},
                benefit={"error": "目标时段电价不低于源时段"},
                confidence=0,
                warnings=["无法获得峰谷价差收益"]
            )

        # 获取可转移设备信息
        shiftable_devices = await self._get_shiftable_devices()
        max_shiftable_power = sum(d.get("shiftable_power", 0) for d in shiftable_devices)

        # 验证可行性
        is_feasible = shift_power <= max_shiftable_power
        warnings = []
        recommendations = []

        if shift_power > max_shiftable_power:
            warnings.append(f"请求转移功率({shift_power:.1f}kW)超过可转移总功率({max_shiftable_power:.1f}kW)")
            is_feasible = False

        # 计算收益
        daily_energy = shift_power * shift_hours
        daily_saving = daily_energy * price_diff
        annual_saving = daily_saving * working_days_per_year

        # 计算置信度
        confidence = 0.85 if is_feasible else 0.3
        if shift_hours > 6:
            confidence *= 0.9
            warnings.append("每日转移时间较长，可能影响运营")

        # 选择推荐设备
        recommended_devices = self._select_devices_for_shift(
            shiftable_devices, shift_power
        )

        return SimulationResult(
            simulation_type=SimulationType.PEAK_SHIFT,
            is_feasible=is_feasible,
            current_state={
                "source_period": source_period,
                "source_price": source_price,
                "available_shiftable_power": round(max_shiftable_power, 2),
                "shiftable_device_count": len(shiftable_devices)
            },
            simulated_state={
                "target_period": target_period,
                "target_price": target_price,
                "shift_power": shift_power,
                "shift_hours": shift_hours,
                "price_diff": round(price_diff, 4)
            },
            benefit={
                "daily_energy_shifted": round(daily_energy, 2),
                "daily_saving": round(daily_saving, 2),
                "annual_saving": round(annual_saving, 2),
                "recommended_devices": recommended_devices
            },
            confidence=round(confidence, 2),
            warnings=warnings,
            recommendations=recommendations
        )

    async def simulate_device_regulation(
        self,
        device_id: int,
        target_value: float,
        regulation_type: str = "temperature"
    ) -> SimulationResult:
        """
        模拟设备调节

        Args:
            device_id: 设备ID
            target_value: 目标调节值
            regulation_type: 调节类型（temperature/brightness/load）

        Returns:
            SimulationResult: 模拟结果
        """
        # 获取设备和调节配置
        device = await self._get_device(device_id)
        if not device:
            return SimulationResult(
                simulation_type=SimulationType.DEVICE_REGULATION,
                is_feasible=False,
                current_state={},
                simulated_state={},
                benefit={"error": f"设备ID {device_id} 不存在"},
                confidence=0,
                warnings=["设备不存在"]
            )

        # 获取调节配置
        reg_config = await self._get_regulation_config(device_id, regulation_type)
        if not reg_config:
            return SimulationResult(
                simulation_type=SimulationType.DEVICE_REGULATION,
                is_feasible=False,
                current_state={"device_name": device.device_name},
                simulated_state={},
                benefit={"error": "该设备没有配置调节参数"},
                confidence=0,
                warnings=["未找到调节配置"]
            )

        # 验证目标值范围
        min_val = reg_config.min_value
        max_val = reg_config.max_value
        current_val = reg_config.current_value or reg_config.default_value or min_val

        is_feasible = min_val <= target_value <= max_val
        warnings = []
        recommendations = []

        if not is_feasible:
            warnings.append(f"目标值{target_value}超出允许范围[{min_val}, {max_val}]")

        # 计算功率变化
        power_factor = reg_config.power_factor or 0.1
        base_power = reg_config.base_power or device.rated_power or 0
        value_change = target_value - current_val

        # 简化的功率变化计算
        power_change = value_change * power_factor * base_power / 10

        # 计算节省
        hours_per_day = 8
        working_days = 300
        avg_price = 0.5  # 假设平均电价

        daily_saving = power_change * hours_per_day * avg_price
        annual_saving = daily_saving * working_days

        # 评估影响
        comfort_impact = reg_config.comfort_impact or "low"
        performance_impact = reg_config.performance_impact or "none"

        if comfort_impact in ["high", "critical"]:
            warnings.append("此调节可能显著影响舒适度")
            recommendations.append("建议在非高峰时段实施")

        confidence = 0.75 if is_feasible else 0.2

        return SimulationResult(
            simulation_type=SimulationType.DEVICE_REGULATION,
            is_feasible=is_feasible,
            current_state={
                "device_id": device_id,
                "device_name": device.device_name,
                "device_type": device.device_type,
                "regulation_type": regulation_type,
                "current_value": current_val,
                "current_power_estimate": round(base_power, 2),
                "unit": reg_config.unit
            },
            simulated_state={
                "target_value": target_value,
                "value_change": round(value_change, 2),
                "power_change": round(power_change, 2),
                "comfort_impact": comfort_impact,
                "performance_impact": performance_impact
            },
            benefit={
                "power_saving_kw": round(power_change, 2),
                "daily_saving": round(daily_saving, 2),
                "annual_saving": round(annual_saving, 2)
            },
            confidence=round(confidence, 2),
            warnings=warnings,
            recommendations=recommendations
        )

    async def calculate_benefit_with_confidence(
        self,
        base_benefit: float,
        uncertainty_factors: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        计算带置信区间的收益

        Args:
            base_benefit: 基础收益值
            uncertainty_factors: 不确定性因素
                {
                    "data_quality": 0.9,    # 数据质量 0-1
                    "assumption_risk": 0.8,  # 假设风险 0-1
                    "implementation_risk": 0.7  # 实施风险 0-1
                }

        Returns:
            带置信区间的收益估算
        """
        data_quality = uncertainty_factors.get("data_quality", 0.8)
        assumption_risk = uncertainty_factors.get("assumption_risk", 0.7)
        implementation_risk = uncertainty_factors.get("implementation_risk", 0.7)

        # 综合置信度
        overall_confidence = (
            data_quality * 0.3 +
            assumption_risk * 0.3 +
            implementation_risk * 0.4
        )

        # 计算置信区间
        uncertainty_range = 1 - overall_confidence
        low_estimate = base_benefit * (1 - uncertainty_range)
        high_estimate = base_benefit * (1 + uncertainty_range * 0.5)

        # 最可能值（略保守）
        most_likely = base_benefit * (0.9 + overall_confidence * 0.1)

        return {
            "base_benefit": round(base_benefit, 2),
            "most_likely": round(most_likely, 2),
            "low_estimate": round(low_estimate, 2),
            "high_estimate": round(high_estimate, 2),
            "confidence": round(overall_confidence, 2),
            "confidence_level": self._get_confidence_level(overall_confidence),
            "factors": {
                "data_quality": data_quality,
                "assumption_risk": assumption_risk,
                "implementation_risk": implementation_risk
            }
        }

    async def run_combined_simulation(
        self,
        scenarios: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        运行组合模拟

        Args:
            scenarios: 模拟场景列表
                [
                    {"type": "demand_adjustment", "params": {...}},
                    {"type": "peak_shift", "params": {...}},
                    ...
                ]

        Returns:
            组合模拟结果
        """
        results = []
        total_annual_saving = 0
        overall_feasibility = True
        all_warnings = []

        for scenario in scenarios:
            sim_type = scenario.get("type")
            params = scenario.get("params", {})

            if sim_type == "demand_adjustment":
                result = await self.simulate_demand_adjustment(**params)
            elif sim_type == "peak_shift":
                result = await self.simulate_peak_shift(**params)
            elif sim_type == "device_regulation":
                result = await self.simulate_device_regulation(**params)
            else:
                continue

            results.append({
                "type": sim_type,
                "result": result
            })

            # 累计收益
            if result.is_feasible:
                annual = result.benefit.get("annual_saving", 0)
                total_annual_saving += annual
            else:
                overall_feasibility = False

            all_warnings.extend(result.warnings)

        # 计算组合置信度（取最低）
        confidences = [r["result"].confidence for r in results]
        combined_confidence = min(confidences) if confidences else 0

        return {
            "scenarios_count": len(results),
            "results": results,
            "combined_benefit": {
                "total_annual_saving": round(total_annual_saving, 2),
                "overall_feasibility": overall_feasibility,
                "combined_confidence": round(combined_confidence, 2)
            },
            "all_warnings": list(set(all_warnings)),
            "simulation_time": datetime.now().isoformat()
        }

    # ========== 私有方法 ==========

    async def _get_demand_history(self, days: int) -> List[float]:
        """获取历史需量数据"""
        try:
            start_time = datetime.now() - timedelta(days=days)
            result = await self.db.execute(
                select(PUEHistory.total_power)
                .where(PUEHistory.record_time >= start_time)
                .order_by(PUEHistory.record_time)
            )
            powers = [row[0] for row in result.all() if row[0]]
            return powers if powers else []
        except Exception as e:
            logger.warning(f"Failed to get power history: {e}")
            return []

    def _calculate_demand_cost(
        self,
        declared: float,
        actual_max: float,
        price: float,
        over_multiplier: float
    ) -> float:
        """计算需量电费"""
        if actual_max <= declared:
            return declared * price
        else:
            over_demand = actual_max - declared
            return declared * price + over_demand * price * over_multiplier

    def _calculate_over_demand_risk(
        self,
        declared: float,
        demand_history: List[float]
    ) -> float:
        """计算超需量风险"""
        if not demand_history or declared <= 0:
            return 0.5

        over_count = sum(1 for d in demand_history if d > declared)
        return over_count / len(demand_history)

    def _calculate_confidence(
        self,
        is_feasible: bool,
        over_risk: float,
        sample_size: int
    ) -> float:
        """计算置信度"""
        base = 0.8 if is_feasible else 0.4
        risk_penalty = over_risk * 0.3
        sample_bonus = min(sample_size / 100, 0.2)

        return max(0.1, min(1.0, base - risk_penalty + sample_bonus))

    async def _get_shiftable_devices(self) -> List[Dict]:
        """获取可转移设备"""
        try:
            result = await self.db.execute(
                select(PowerDevice, DeviceShiftConfig)
                .join(DeviceShiftConfig, PowerDevice.id == DeviceShiftConfig.device_id)
                .where(
                    and_(
                        DeviceShiftConfig.is_shiftable == True,
                        PowerDevice.is_enabled == True
                    )
                )
            )
            rows = result.all()

            devices = []
            for device, config in rows:
                shiftable_power = (device.rated_power or 0) * (config.shiftable_power_ratio or 0)
                devices.append({
                    "device_id": device.id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "rated_power": device.rated_power,
                    "shiftable_power": shiftable_power,
                    "allowed_hours": config.allowed_shift_hours or []
                })
            return devices
        except Exception as e:
            logger.warning(f"Failed to get shiftable devices: {e}")
            return []

    def _select_devices_for_shift(
        self,
        devices: List[Dict],
        target_power: float
    ) -> List[Dict]:
        """选择转移设备"""
        # 按可转移功率排序
        sorted_devices = sorted(
            devices,
            key=lambda d: d.get("shiftable_power", 0),
            reverse=True
        )

        selected = []
        accumulated_power = 0

        for dev in sorted_devices:
            if accumulated_power >= target_power:
                break
            selected.append({
                "device_id": dev["device_id"],
                "device_name": dev["device_name"],
                "shiftable_power": dev["shiftable_power"]
            })
            accumulated_power += dev["shiftable_power"]

        return selected

    async def _get_device(self, device_id: int) -> Optional[PowerDevice]:
        """获取设备"""
        result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        return result.scalar_one_or_none()

    async def _get_regulation_config(
        self,
        device_id: int,
        regulation_type: str
    ) -> Optional[LoadRegulationConfig]:
        """获取调节配置"""
        result = await self.db.execute(
            select(LoadRegulationConfig).where(
                and_(
                    LoadRegulationConfig.device_id == device_id,
                    LoadRegulationConfig.regulation_type == regulation_type,
                    LoadRegulationConfig.is_enabled == True
                )
            )
        )
        return result.scalar_one_or_none()

    def _get_confidence_level(self, confidence: float) -> str:
        """获取置信度级别"""
        if confidence >= 0.85:
            return "high"
        elif confidence >= 0.7:
            return "medium"
        elif confidence >= 0.5:
            return "low"
        else:
            return "very_low"
