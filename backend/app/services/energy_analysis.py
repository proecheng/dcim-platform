"""
能耗分析服务
Energy Analysis Service

提供需量配置分析、负荷转移分析功能

注: 需量配置分析已统一到 demand_analysis_service.DemandAnalysisService
    本文件的 DemandAnalysisService 类保留向后兼容，但使用统一阈值
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models.energy import MeterPoint, DeviceShiftConfig, DemandHistory, EnergyDaily

# 导入统一的阈值配置
from .demand_analysis_service import DemandThresholds


class DemandAnalysisService:
    """需量配置分析服务"""

    @staticmethod
    async def analyze_demand_config(db: AsyncSession, meter_point_id: int, months: int = 12) -> Dict[str, Any]:
        """
        分析计量点需量配置合理性

        Args:
            meter_point_id: 计量点ID
            months: 分析月份数

        Returns:
            分析结果，包含配置建议
        """
        # 获取计量点信息
        meter_result = await db.execute(select(MeterPoint).where(MeterPoint.id == meter_point_id))
        meter_point = meter_result.scalar_one_or_none()
        if not meter_point:
            return {"error": "计量点不存在"}

        # 获取需量历史数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        demand_result = await db.execute(
            select(DemandHistory)
            .where(DemandHistory.meter_point_id == meter_point_id, DemandHistory.stat_year >= start_date.year)
            .order_by(DemandHistory.stat_year, DemandHistory.stat_month)
        )
        demand_history = demand_result.scalars().all()

        if not demand_history:
            # 生成模拟数据进行分析
            return await DemandAnalysisService._generate_mock_analysis(meter_point)

        # 计算统计指标
        max_demands = [h.max_demand for h in demand_history if h.max_demand]
        avg_demands = [h.avg_demand for h in demand_history if h.avg_demand]

        if not max_demands:
            return await DemandAnalysisService._generate_mock_analysis(meter_point)

        max_demand = max(max_demands)
        avg_demand = sum(avg_demands) / len(avg_demands) if avg_demands else 0
        demand_95th = sorted(max_demands)[int(len(max_demands) * 0.95)] if len(max_demands) > 1 else max_demand

        declared_demand = meter_point.declared_demand or 0
        utilization_rate = (max_demand / declared_demand * 100) if declared_demand > 0 else 0

        # 超限次数统计
        over_declared_times = sum(h.over_declared_times for h in demand_history if h.over_declared_times)

        # 使用统一阈值配置
        thresholds = DemandThresholds()

        # 计算建议需量 (统一使用95分位数 + 安全裕度)
        recommended_demand = DemandAnalysisService._calculate_recommended_demand(
            max_demand, demand_95th, avg_demand, thresholds.safety_margin
        )

        # 计算费用优化 (使用统一默认电价)
        demand_price = 38.0  # 默认需量电价，与统一服务一致
        current_cost = declared_demand * demand_price
        recommended_cost = recommended_demand * demand_price
        annual_saving = (current_cost - recommended_cost) * 12

        # 分析状态 (使用统一阈值: low=80%, high=105%)
        # utilization_rate 在此处是百分比值 (如 85.0)
        low_pct = thresholds.low_utilization * 100  # 80
        high_pct = thresholds.high_utilization * 100  # 105

        if utilization_rate > high_pct:
            status = "high_risk"
            status_text = "风险较高"
        elif utilization_rate >= low_pct:
            status = "optimal"
            status_text = "配置合理"
        elif utilization_rate >= 60:
            status = "can_optimize"
            status_text = "可优化"
        else:
            status = "over_declared"
            status_text = "明显偏高"

        return {
            "meter_point_id": meter_point_id,
            "meter_code": meter_point.meter_code,
            "meter_name": meter_point.meter_name,
            "analysis_period": f"最近{months}个月",
            "current_config": {"declared_demand": declared_demand, "demand_type": meter_point.demand_type},
            "statistics": {
                "max_demand": round(max_demand, 1),
                "avg_demand": round(avg_demand, 1),
                "demand_95th": round(demand_95th, 1),
                "utilization_rate": round(utilization_rate, 1),
                "over_declared_times": over_declared_times,
                "surplus_capacity": round(declared_demand - max_demand, 1) if declared_demand > max_demand else 0,
            },
            "recommendation": {
                "status": status,
                "status_text": status_text,
                "recommended_demand": round(recommended_demand, 0),
                "adjustment": round(recommended_demand - declared_demand, 0),
                "adjustment_ratio": round((recommended_demand - declared_demand) / declared_demand * 100, 1)
                if declared_demand > 0
                else 0,
            },
            "cost_analysis": {
                "current_monthly_cost": round(current_cost, 2),
                "recommended_monthly_cost": round(recommended_cost, 2),
                "monthly_saving": round(current_cost - recommended_cost, 2),
                "annual_saving": round(annual_saving, 2),
                "demand_price": demand_price,
            },
            "optimization_options": [
                {
                    "name": "conservative",
                    "label": "保守方案",
                    "demand": round(max_demand * 1.1, 0),
                    "monthly_cost": round(max_demand * 1.1 * demand_price, 2),
                    "risk_level": "极低",
                },
                {
                    "name": "recommended",
                    "label": "推荐方案",
                    "demand": round(recommended_demand, 0),
                    "monthly_cost": round(recommended_cost, 2),
                    "risk_level": "低",
                },
                {
                    "name": "aggressive",
                    "label": "激进方案",
                    "demand": round(demand_95th, 0),
                    "monthly_cost": round(demand_95th * demand_price, 2),
                    "risk_level": "中",
                },
            ],
            "history": [
                {
                    "month": f"{h.stat_year}-{h.stat_month:02d}",
                    "max_demand": h.max_demand,
                    "avg_demand": h.avg_demand,
                    "over_declared_times": h.over_declared_times or 0,
                }
                for h in demand_history[-12:]  # 最近12个月
            ],
        }

    @staticmethod
    def _calculate_recommended_demand(
        max_demand: float, demand_95th: float, avg_demand: float, safety_margin: float = 0.10
    ) -> float:
        """
        计算推荐需量

        统一使用: 95分位数 * (1 + 安全裕度)，按5的倍数取整
        与 demand_analysis_service.calculate_optimal_demand 保持一致
        """
        import math

        # 基于95%分位数 + 安全裕度 (统一10%)
        optimal = demand_95th * (1 + safety_margin)

        # 按5的倍数向上取整 (kW)
        optimal = math.ceil(optimal / 5) * 5

        return optimal

    @staticmethod
    async def _generate_mock_analysis(meter_point: MeterPoint) -> Dict[str, Any]:
        """生成模拟分析数据（无历史数据时使用）"""
        declared_demand = meter_point.declared_demand or 800
        # 模拟数据：假设实际使用约85%
        simulated_max = declared_demand * 0.85
        simulated_avg = declared_demand * 0.65
        simulated_95th = declared_demand * 0.82

        recommended_demand = DemandAnalysisService._calculate_recommended_demand(
            simulated_max, simulated_95th, simulated_avg
        )

        demand_price = 38.0
        current_cost = declared_demand * demand_price
        recommended_cost = recommended_demand * demand_price

        return {
            "meter_point_id": meter_point.id,
            "meter_code": meter_point.meter_code,
            "meter_name": meter_point.meter_name,
            "analysis_period": "模拟数据",
            "current_config": {"declared_demand": declared_demand, "demand_type": meter_point.demand_type},
            "statistics": {
                "max_demand": round(simulated_max, 1),
                "avg_demand": round(simulated_avg, 1),
                "demand_95th": round(simulated_95th, 1),
                "utilization_rate": 85.0,
                "over_declared_times": 0,
                "surplus_capacity": round(declared_demand - simulated_max, 1),
            },
            "recommendation": {
                "status": "can_optimize",
                "status_text": "可优化（模拟数据）",
                "recommended_demand": round(recommended_demand, 0),
                "adjustment": round(recommended_demand - declared_demand, 0),
                "adjustment_ratio": round((recommended_demand - declared_demand) / declared_demand * 100, 1),
            },
            "cost_analysis": {
                "current_monthly_cost": round(current_cost, 2),
                "recommended_monthly_cost": round(recommended_cost, 2),
                "monthly_saving": round(current_cost - recommended_cost, 2),
                "annual_saving": round((current_cost - recommended_cost) * 12, 2),
                "demand_price": demand_price,
            },
            "optimization_options": [
                {
                    "name": "conservative",
                    "label": "保守方案",
                    "demand": round(simulated_max * 1.1, 0),
                    "monthly_cost": round(simulated_max * 1.1 * demand_price, 2),
                    "risk_level": "极低",
                },
                {
                    "name": "recommended",
                    "label": "推荐方案",
                    "demand": round(recommended_demand, 0),
                    "monthly_cost": round(recommended_cost, 2),
                    "risk_level": "低",
                },
                {
                    "name": "aggressive",
                    "label": "激进方案",
                    "demand": round(simulated_95th, 0),
                    "monthly_cost": round(simulated_95th * demand_price, 2),
                    "risk_level": "中",
                },
            ],
            "history": [],
            "_note": "无历史数据，使用模拟值分析",
        }


class LoadShiftAnalysisService:
    """负荷转移分析服务"""

    @staticmethod
    async def analyze_load_shift(db: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """
        分析负荷转移潜力

        Args:
            days: 分析天数

        Returns:
            分析结果，包含可转移设备和建议
        """
        # 获取可转移设备
        shift_result = await db.execute(
            select(DeviceShiftConfig)
            .options(selectinload(DeviceShiftConfig.device))
            .where(DeviceShiftConfig.is_shiftable == True, DeviceShiftConfig.is_critical == False)
        )
        shift_configs = shift_result.scalars().all()

        # 获取峰谷用电分布
        peak_valley_distribution = await LoadShiftAnalysisService._get_peak_valley_distribution(db, days)

        # 分析各设备转移潜力
        device_potentials = []
        total_shiftable_power = 0
        total_monthly_saving = 0

        for config in shift_configs:
            if not config.device or not config.device.is_enabled:
                continue

            potential = await LoadShiftAnalysisService._analyze_device_potential(db, config, days)
            if potential:
                device_potentials.append(potential)
                total_shiftable_power += potential.get("shiftable_power", 0)
                total_monthly_saving += potential.get("monthly_saving", 0)

        # 生成转移建议
        suggestions = LoadShiftAnalysisService._generate_shift_suggestions(device_potentials, peak_valley_distribution)

        return {
            "analysis_period": f"最近{days}天",
            "peak_valley_distribution": peak_valley_distribution,
            "summary": {
                "shiftable_device_count": len(device_potentials),
                "total_shiftable_power": round(total_shiftable_power, 1),
                "total_monthly_saving": round(total_monthly_saving, 2),
                "total_annual_saving": round(total_monthly_saving * 12, 2),
            },
            "device_potentials": device_potentials,
            "suggestions": suggestions,
            "expected_effect": {
                "peak_ratio_before": peak_valley_distribution.get("peak_ratio", 0),
                "peak_ratio_after": max(
                    peak_valley_distribution.get("peak_ratio", 0)
                    - sum(d.get("peak_reduction_ratio", 0) for d in device_potentials),
                    0,
                ),
                "valley_ratio_before": peak_valley_distribution.get("valley_ratio", 0),
                "valley_ratio_after": min(
                    peak_valley_distribution.get("valley_ratio", 0)
                    + sum(d.get("valley_increase_ratio", 0) for d in device_potentials),
                    100,
                ),
            },
        }

    @staticmethod
    async def _get_peak_valley_distribution(db: AsyncSession, days: int) -> Dict[str, Any]:
        """获取峰谷用电分布"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        # 查询日能耗数据
        result = await db.execute(
            select(EnergyDaily).where(EnergyDaily.stat_date >= start_date, EnergyDaily.stat_date <= end_date)
        )
        daily_data = result.scalars().all()

        if not daily_data:
            # 返回模拟数据
            return {
                "peak_energy": 13560,
                "flat_energy": 9750,
                "valley_energy": 6690,
                "total_energy": 30000,
                "peak_ratio": 45.2,
                "flat_ratio": 32.5,
                "valley_ratio": 22.3,
                "peak_cost": 16272,
                "flat_cost": 7800,
                "valley_cost": 2676,
                "total_cost": 26748,
                "_note": "模拟数据",
            }

        total_peak = sum(d.peak_energy or 0 for d in daily_data)
        total_flat = sum(d.normal_energy or 0 for d in daily_data)
        total_valley = sum(d.valley_energy or 0 for d in daily_data)
        total_energy = total_peak + total_flat + total_valley

        # 注意：此处为 fallback 默认电价，实际应从 PricingService 获取
        # 五时段电价中，sharp+peak 合并为 peak_price，valley+deep_valley 合并为 valley_price
        peak_price = 1.2
        flat_price = 0.8
        valley_price = 0.4

        return {
            "peak_energy": round(total_peak, 1),
            "flat_energy": round(total_flat, 1),
            "valley_energy": round(total_valley, 1),
            "total_energy": round(total_energy, 1),
            "peak_ratio": round(total_peak / total_energy * 100, 1) if total_energy > 0 else 0,
            "flat_ratio": round(total_flat / total_energy * 100, 1) if total_energy > 0 else 0,
            "valley_ratio": round(total_valley / total_energy * 100, 1) if total_energy > 0 else 0,
            "peak_cost": round(total_peak * peak_price, 2),
            "flat_cost": round(total_flat * flat_price, 2),
            "valley_cost": round(total_valley * valley_price, 2),
            "total_cost": round(total_peak * peak_price + total_flat * flat_price + total_valley * valley_price, 2),
        }

    @staticmethod
    async def _analyze_device_potential(
        db: AsyncSession, config: DeviceShiftConfig, days: int
    ) -> Optional[Dict[str, Any]]:
        """分析单个设备的转移潜力"""
        device = config.device
        if not device:
            return None

        # 获取设备日能耗数据
        result = await db.execute(
            select(EnergyDaily).where(
                EnergyDaily.device_id == device.id,
                EnergyDaily.stat_date >= datetime.now().date() - timedelta(days=days),
            )
        )
        daily_data = result.scalars().all()

        # 计算峰谷比例
        if daily_data:
            total_peak = sum(d.peak_energy or 0 for d in daily_data)
            total_valley = sum(d.valley_energy or 0 for d in daily_data)
            total_energy = sum(d.total_energy or 0 for d in daily_data)

            peak_ratio = (total_peak / total_energy * 100) if total_energy > 0 else 50
            valley_ratio = (total_valley / total_energy * 100) if total_energy > 0 else 20
        else:
            # 模拟数据
            peak_ratio = 50
            valley_ratio = 20
            total_energy = device.rated_power * 24 * days * 0.6  # 假设60%负载率

        # 计算可调节容量 (shiftable_power_ratio 已经是小数形式，如 0.17 表示 17%)
        shiftable_ratio = config.shiftable_power_ratio or 0
        shiftable_power = device.rated_power * shiftable_ratio if device.rated_power else 0

        # 注意：此处为 fallback 默认电价，实际应从 PricingService 获取
        # 五时段电价中，sharp+peak 合并为 peak_price，valley+deep_valley 合并为 valley_price
        peak_price = 1.2
        valley_price = 0.4
        price_diff = peak_price - valley_price

        # 假设每天可转移4小时
        daily_shift_hours = 4
        monthly_shift_energy = shiftable_power * daily_shift_hours * 30 * 0.8  # 80%转移效率
        monthly_saving = monthly_shift_energy * price_diff

        # 确定建议类型
        if device.device_type in ["HVAC", "hvac"]:
            suggestion_type = "降载"
            suggestion_icon = "⬇"
        elif device.device_type in ["LIGHTING", "lighting", "PUMP", "pump"]:
            suggestion_type = "调时"
            suggestion_icon = "⏰"
        else:
            suggestion_type = "转移"
            suggestion_icon = "🔄"

        return {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "rated_power": device.rated_power,
            "peak_ratio": round(peak_ratio, 1),
            "valley_ratio": round(valley_ratio, 1),
            "shiftable_ratio": shiftable_ratio,
            "shiftable_power": round(shiftable_power, 1),
            "monthly_saving": round(monthly_saving, 2),
            "annual_saving": round(monthly_saving * 12, 2),
            "suggestion_type": suggestion_type,
            "suggestion_icon": suggestion_icon,
            "peak_reduction_ratio": round(shiftable_power / device.rated_power * peak_ratio / 100, 1)
            if device.rated_power
            else 0,
            "valley_increase_ratio": round(shiftable_power / device.rated_power * (100 - valley_ratio) / 100, 1)
            if device.rated_power
            else 0,
        }

    @staticmethod
    def _generate_shift_suggestions(
        device_potentials: List[Dict[str, Any]], distribution: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """生成转移建议"""
        suggestions = []

        # 按设备类型分组
        hvac_devices = [d for d in device_potentials if d["device_type"] in ["HVAC", "hvac"]]
        lighting_devices = [d for d in device_potentials if d["device_type"] in ["LIGHTING", "lighting"]]
        other_devices = [d for d in device_potentials if d not in hvac_devices and d not in lighting_devices]

        # HVAC设备建议
        if hvac_devices:
            total_saving = sum(d["monthly_saving"] for d in hvac_devices)
            suggestions.append(
                {
                    "id": 1,
                    "priority": "high",
                    "title": "精密空调错峰运行",
                    "description": f"峰时(10:00-12:00)将设定温度提高2℃，降低{hvac_devices[0]['shiftable_ratio']}%制冷功率",
                    "devices": [d["device_name"] for d in hvac_devices],
                    "shift_period": "峰时 → 平时/谷时",
                    "conditions": "室内温度不超过26℃，服务器进风温度不超过24℃",
                    "monthly_saving": round(total_saving, 2),
                    "annual_saving": round(total_saving * 12, 2),
                }
            )

        # 照明设备建议
        if lighting_devices:
            total_saving = sum(d["monthly_saving"] for d in lighting_devices)
            suggestions.append(
                {
                    "id": 2,
                    "priority": "medium",
                    "title": "照明系统定时控制",
                    "description": "将部分照明从峰时段调整至谷时段提前开启",
                    "devices": [d["device_name"] for d in lighting_devices],
                    "shift_period": "峰时 → 谷时",
                    "conditions": "保证必要照明区域亮度",
                    "monthly_saving": round(total_saving, 2),
                    "annual_saving": round(total_saving * 12, 2),
                }
            )

        # 其他设备建议
        for i, device in enumerate(other_devices):
            suggestions.append(
                {
                    "id": len(suggestions) + 1,
                    "priority": "low",
                    "title": f"{device['device_name']}运行时间优化",
                    "description": f"将{device['device_name']}的部分运行时间从峰时转移至谷时",
                    "devices": [device["device_name"]],
                    "shift_period": "峰时 → 谷时",
                    "conditions": "确保不影响正常业务运行",
                    "monthly_saving": device["monthly_saving"],
                    "annual_saving": device["annual_saving"],
                }
            )

        return suggestions


# 单例服务实例
demand_analysis_service = DemandAnalysisService()
load_shift_analysis_service = LoadShiftAnalysisService()
