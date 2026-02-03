"""
机会分析引擎
Opportunity Analysis Engine

整合现有分析插件，提供统一的机会发现和分析接口
根据能源中心重新设计方案，将6种模板整合为4大类别

注: 需量分析统一使用 DemandAnalysisService 确保数据源一致
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from .analysis_plugins import (
    plugin_manager,
    register_all_plugins,
    AnalysisContext,
    SuggestionResult,
    LoadShiftingPlugin,
    DemandOptimizationPlugin,
    PeakValleyOptimizationPlugin,
    EquipmentEfficiencyPlugin,
    PUEOptimizationPlugin,
    PowerFactorPlugin
)
from .pricing_service import PricingService
from .demand_analysis_service import DemandAnalysisService
from ..models.energy import (
    PowerDevice, EnergySuggestion, ElectricityPricing,
    EnergyDaily, PUEHistory
)

logger = logging.getLogger(__name__)

# 默认值常量
DEFAULT_MAX_DEMAND_KW = 500  # 默认最大需量 (kW)
DEFAULT_AVG_DEMAND_KW = 350  # 默认平均需量 (kW)


class OpportunityCategory(str, Enum):
    """机会类别（整合后的4大类）"""
    BILL_OPTIMIZATION = "bill_optimization"  # 电费结构优化（原A1+A2+A4）
    DEVICE_OPERATION = "device_operation"    # 设备运行优化（原A3+A5）
    EQUIPMENT_UPGRADE = "equipment_upgrade"  # 设备改造升级（原B1）
    COMPREHENSIVE = "comprehensive"          # 综合能效提升（新增）


# 插件到类别的映射
PLUGIN_CATEGORY_MAPPING = {
    "peak_valley_optimization": OpportunityCategory.BILL_OPTIMIZATION,
    "demand_optimization": OpportunityCategory.BILL_OPTIMIZATION,
    "power_factor": OpportunityCategory.BILL_OPTIMIZATION,
    "load_shifting": OpportunityCategory.DEVICE_OPERATION,
    "pue_optimization": OpportunityCategory.DEVICE_OPERATION,
    "equipment_efficiency": OpportunityCategory.EQUIPMENT_UPGRADE,
}


class OpportunityEngine:
    """
    机会分析引擎

    核心功能:
    1. 整合现有6种分析插件
    2. 提供统一的机会发现接口
    3. 按4大类别组织输出结果
    4. 支持增量分析和全量分析
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.pricing_service = PricingService(db)
        # 确保插件已注册
        register_all_plugins()

    async def generate_opportunities(
        self,
        categories: Optional[List[OpportunityCategory]] = None,
        device_ids: Optional[List[int]] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        生成节能机会分析

        Args:
            categories: 要分析的类别（None则分析全部）
            device_ids: 限定分析的设备ID列表
            days: 分析数据天数

        Returns:
            {
                "opportunities": [...],  # 机会列表
                "summary": {...},        # 汇总统计
                "by_category": {...}     # 按类别分组
            }
        """
        # 确定要执行的插件
        plugin_ids = self._get_plugin_ids_for_categories(categories)

        # 执行分析
        results = await plugin_manager.run_analysis(
            db=self.db,
            plugin_ids=plugin_ids,
            days=days,
            save_results=False  # 不自动保存，由调用方决定
        )

        # 处理结果
        opportunities = []
        for result in results:
            opportunity = self._convert_to_opportunity(result)
            # 设备过滤
            if device_ids and opportunity.get("device_id"):
                if opportunity["device_id"] not in device_ids:
                    continue
            opportunities.append(opportunity)

        # 按类别分组
        by_category = self._group_by_category(opportunities)

        # 汇总统计
        summary = self._calculate_summary(opportunities)

        return {
            "opportunities": opportunities,
            "summary": summary,
            "by_category": by_category,
            "analysis_time": datetime.now().isoformat(),
            "analysis_days": days
        }

    async def analyze_demand_opportunity(
        self,
        meter_point_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        分析需量优化机会

        使用统一的 DemandAnalysisService 确保数据源和计算逻辑一致

        返回需量配置优化建议、预期节省等
        """
        # 使用统一的需量分析服务
        demand_service = DemandAnalysisService(self.db)
        result = await demand_service.analyze(meter_point_id)

        if not result.get("has_opportunity"):
            return {
                "has_opportunity": False,
                "message": result.get("message", "未发现需量优化机会"),
                "suggestions": []
            }

        stats = result["statistics"]
        rec = result["recommendation"]
        demand_price = result["demand_price"]

        # 构建建议
        suggestions = []

        if rec["type"] == "reduce":
            suggestions.append({
                "type": "reduce_declared_demand",
                "title": "降低申报需量",
                "description": rec["description"],
                "recommendation": f"建议将申报需量调整为{rec['suggested_demand']:.0f}kW",
                "potential_saving_monthly": rec["monthly_saving"],
                "potential_saving_annual": rec["annual_saving"],
                "confidence": rec["confidence"]
            })

        elif rec["type"] == "increase":
            suggestions.append({
                "type": "increase_declared_demand",
                "title": "提高申报需量或控制峰值",
                "description": rec["description"],
                "recommendation": "建议提高申报需量或采取需量控制措施",
                "over_risk_cost": abs(rec["annual_saving"]),
                "confidence": rec["confidence"]
            })

        elif rec["type"] == "shave":
            suggestions.append({
                "type": "peak_shaving",
                "title": "实施需量削峰",
                "description": rec["description"],
                "recommendation": "建议安装需量控制系统或优化设备启动策略",
                "potential_saving_annual": rec["annual_saving"],
                "confidence": rec["confidence"]
            })

        return {
            "has_opportunity": True,
            "current_status": {
                "declared_demand": stats["declared_demand"],
                "max_demand": stats["max_demand_12m"],
                "avg_demand": stats["avg_demand_12m"],
                "utilization_rate": stats["utilization_rate"] * 100,  # 转换为百分比
                "demand_price": demand_price
            },
            "suggestions": suggestions,
            "potential_saving_annual": abs(rec["annual_saving"])
        }

    async def analyze_peak_valley_opportunity(self) -> Dict[str, Any]:
        """
        分析峰谷套利机会

        返回峰谷电价差、可转移负荷、预期收益等
        """
        # 获取峰谷电价差
        spread = await self.pricing_service.get_peak_valley_spread()

        # 获取可转移设备
        shiftable_devices = await self._get_shiftable_devices()

        # 计算转移潜力
        total_shiftable_power = sum(d.get("shiftable_power", 0) for d in shiftable_devices)

        # 估算节省（假设每天转移4小时，每年300工作日）
        peak_valley_diff = spread.get("peak_valley_diff", 0)
        daily_energy = total_shiftable_power * 4  # kWh
        daily_saving = daily_energy * peak_valley_diff
        annual_saving = daily_saving * 300

        suggestions = []
        if peak_valley_diff > 0.3 and total_shiftable_power > 10:
            suggestions.append({
                "type": "peak_to_valley_shift",
                "title": "峰谷负荷转移",
                "description": f"峰谷电价差{peak_valley_diff:.3f}元/kWh，可转移功率{total_shiftable_power:.1f}kW",
                "recommendation": "建议将部分峰时负荷转移至谷时运行",
                "potential_saving_daily": daily_saving,
                "potential_saving_annual": annual_saving,
                "confidence": 0.8,
                "shiftable_devices": shiftable_devices[:5]  # 显示前5个
            })

        return {
            "has_opportunity": len(suggestions) > 0,
            "price_spread": spread,
            "shiftable_power": total_shiftable_power,
            "shiftable_device_count": len(shiftable_devices),
            "suggestions": suggestions,
            "potential_saving_annual": annual_saving
        }

    async def analyze_device_efficiency(
        self,
        device_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        分析设备效率提升机会

        返回低效设备列表、改造建议等
        """
        # 获取设备数据
        query = select(PowerDevice).where(PowerDevice.is_enabled == True)
        if device_ids:
            query = query.where(PowerDevice.id.in_(device_ids))

        result = await self.db.execute(query)
        devices = result.scalars().all()

        # 分析每个设备
        inefficient_devices = []
        for device in devices:
            # 简化分析：基于设备类型判断效率
            efficiency_score = self._estimate_device_efficiency(device)
            if efficiency_score < 0.7:
                inefficient_devices.append({
                    "device_id": device.id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "rated_power": device.rated_power,
                    "efficiency_score": efficiency_score,
                    "improvement_potential": f"{(0.85 - efficiency_score) * 100:.1f}%"
                })

        # 估算改造收益
        total_potential_saving = 0
        suggestions = []

        for dev in inefficient_devices:
            rated_power = dev.get("rated_power", 0) or 0
            if rated_power > 0:
                # 假设提升15%效率，每年运行5000小时
                energy_saving = rated_power * 0.15 * 5000  # kWh
                cost_saving = energy_saving * 0.5  # 假设平均电价0.5元/kWh
                total_potential_saving += cost_saving
                dev["potential_saving_annual"] = cost_saving

        if inefficient_devices:
            suggestions.append({
                "type": "equipment_upgrade",
                "title": "低效设备改造",
                "description": f"发现{len(inefficient_devices)}台设备效率偏低",
                "recommendation": "建议对低效设备进行改造或更换",
                "inefficient_count": len(inefficient_devices),
                "potential_saving_annual": total_potential_saving,
                "confidence": 0.7
            })

        return {
            "has_opportunity": len(inefficient_devices) > 0,
            "inefficient_devices": inefficient_devices[:10],  # 最多显示10个
            "total_device_count": len(devices),
            "inefficient_count": len(inefficient_devices),
            "suggestions": suggestions,
            "potential_saving_annual": total_potential_saving
        }

    async def get_opportunity_summary(self) -> Dict[str, Any]:
        """
        获取机会概览（用于仪表盘展示）
        """
        # 并行分析各类机会
        demand_result = await self.analyze_demand_opportunity()
        peak_valley_result = await self.analyze_peak_valley_opportunity()
        efficiency_result = await self.analyze_device_efficiency()

        # 汇总
        total_opportunities = (
            len(demand_result.get("suggestions", [])) +
            len(peak_valley_result.get("suggestions", [])) +
            len(efficiency_result.get("suggestions", []))
        )

        total_potential_saving = (
            demand_result.get("potential_saving_annual", 0) +
            peak_valley_result.get("potential_saving_annual", 0) +
            efficiency_result.get("potential_saving_annual", 0)
        )

        return {
            "total_opportunities": total_opportunities,
            "total_potential_saving_annual": round(total_potential_saving, 2),
            "by_category": {
                OpportunityCategory.BILL_OPTIMIZATION: {
                    "count": len(demand_result.get("suggestions", [])) + len(peak_valley_result.get("suggestions", [])),
                    "saving": demand_result.get("potential_saving_annual", 0) + peak_valley_result.get("potential_saving_annual", 0)
                },
                OpportunityCategory.DEVICE_OPERATION: {
                    "count": 0,  # 待实现
                    "saving": 0
                },
                OpportunityCategory.EQUIPMENT_UPGRADE: {
                    "count": len(efficiency_result.get("suggestions", [])),
                    "saving": efficiency_result.get("potential_saving_annual", 0)
                }
            },
            "top_opportunities": self._get_top_opportunities([
                demand_result,
                peak_valley_result,
                efficiency_result
            ]),
            "analysis_time": datetime.now().isoformat()
        }

    # ========== 私有方法 ==========

    def _get_plugin_ids_for_categories(
        self,
        categories: Optional[List[OpportunityCategory]]
    ) -> Optional[List[str]]:
        """根据类别获取要执行的插件ID"""
        if not categories:
            return None  # 执行全部

        plugin_ids = []
        for plugin_id, category in PLUGIN_CATEGORY_MAPPING.items():
            if category in categories:
                plugin_ids.append(plugin_id)
        return plugin_ids if plugin_ids else None

    def _convert_to_opportunity(self, result: SuggestionResult) -> Dict[str, Any]:
        """将插件结果转换为统一的机会格式"""
        plugin_id = result.plugin_id if hasattr(result, 'plugin_id') else 'unknown'
        category = PLUGIN_CATEGORY_MAPPING.get(plugin_id, OpportunityCategory.COMPREHENSIVE)

        return {
            "id": f"{plugin_id}_{datetime.now().timestamp()}",
            "category": category,
            "plugin_id": plugin_id,
            "title": result.title if hasattr(result, 'title') else str(result),
            "description": result.description if hasattr(result, 'description') else "",
            "priority": result.priority.value if hasattr(result, 'priority') else 3,
            "potential_saving": result.potential_saving if hasattr(result, 'potential_saving') else 0,
            "confidence": result.confidence if hasattr(result, 'confidence') else 0.5,
            "device_id": result.device_id if hasattr(result, 'device_id') else None,
            "implementation_steps": result.implementation_steps if hasattr(result, 'implementation_steps') else [],
            "created_at": datetime.now().isoformat()
        }

    def _group_by_category(self, opportunities: List[Dict]) -> Dict[str, List[Dict]]:
        """按类别分组"""
        grouped = {cat: [] for cat in OpportunityCategory}
        for opp in opportunities:
            category = opp.get("category", OpportunityCategory.COMPREHENSIVE)
            if isinstance(category, str):
                category = OpportunityCategory(category)
            grouped[category].append(opp)
        return {k.value: v for k, v in grouped.items()}

    def _calculate_summary(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """计算汇总统计"""
        total_saving = sum(o.get("potential_saving", 0) for o in opportunities)
        high_priority = len([o for o in opportunities if o.get("priority", 3) <= 2])

        return {
            "total_count": len(opportunities),
            "high_priority_count": high_priority,
            "total_potential_saving": round(total_saving, 2),
            "avg_confidence": round(
                sum(o.get("confidence", 0.5) for o in opportunities) / len(opportunities)
                if opportunities else 0,
                2
            )
        }

    async def _get_max_demand_from_history(self, days: int = 30) -> float:
        """从历史数据获取最大需量估算"""
        try:
            result = await self.db.execute(
                select(func.max(PUEHistory.total_power))
                .where(PUEHistory.record_time >= datetime.now().replace(hour=0, minute=0, second=0) - __import__('datetime').timedelta(days=days))
            )
            max_power = result.scalar()
            return max_power or 0
        except Exception as e:
            logger.warning(f"Failed to get max demand from history: {e}")
            return DEFAULT_MAX_DEMAND_KW

    async def _get_avg_demand_from_history(self, days: int = 30) -> float:
        """从历史数据获取平均需量"""
        try:
            result = await self.db.execute(
                select(func.avg(PUEHistory.total_power))
                .where(PUEHistory.record_time >= datetime.now().replace(hour=0, minute=0, second=0) - __import__('datetime').timedelta(days=days))
            )
            avg_power = result.scalar()
            return avg_power or 0
        except Exception as e:
            logger.warning(f"Failed to get avg demand from history: {e}")
            return DEFAULT_AVG_DEMAND_KW

    async def _get_shiftable_devices(self) -> List[Dict]:
        """获取可转移负荷设备"""
        from ..models.energy import DeviceShiftConfig

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
                "allowed_shift_hours": config.allowed_shift_hours or []
            })

        return devices

    def _estimate_device_efficiency(self, device: PowerDevice) -> float:
        """估算设备效率分数"""
        # 简化的效率估算
        device_type = (device.device_type or "").upper()

        # 基于设备类型的基础效率
        base_efficiency = {
            "AC": 0.75,
            "LIGHTING": 0.65,
            "UPS": 0.92,
            "IT": 0.85,
            "PDU": 0.95
        }.get(device_type, 0.8)

        return base_efficiency

    def _get_top_opportunities(self, results: List[Dict]) -> List[Dict]:
        """获取最优先的机会"""
        all_suggestions = []
        for r in results:
            for s in r.get("suggestions", []):
                all_suggestions.append(s)

        # 按节省金额排序
        all_suggestions.sort(
            key=lambda x: x.get("potential_saving_annual", 0),
            reverse=True
        )

        return all_suggestions[:5]
