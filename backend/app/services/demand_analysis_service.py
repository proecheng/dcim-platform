"""
统一需量分析服务
Unified Demand Analysis Service

解决需量分析中数据源不一致的问题：
- 统一申报需量获取 (MeterPoint.declared_demand)
- 统一需量历史获取 (DemandHistory)
- 统一需量电价获取 (PricingConfig.demand_price)
- 统一建议需量计算公式
- 统一利用率阈值配置
"""

import math
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_


def subtract_months(dt: datetime, months: int) -> datetime:
    """
    [V2.9-FIX] 精确的月份减法，使用标准库实现

    Args:
        dt: 起始日期时间
        months: 要减去的月数

    Returns:
        减去指定月数后的日期时间
    """
    year = dt.year
    month = dt.month - months

    while month <= 0:
        month += 12
        year -= 1

    # 处理月末日期（如1月31日减1个月应该是12月31日，而不是报错）
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])

    return dt.replace(year=year, month=month, day=day)

from ..models.energy import (
    MeterPoint, DemandHistory, PricingConfig, Transformer
)

logger = logging.getLogger(__name__)


@dataclass
class DemandThresholds:
    """需量分析阈值配置"""
    low_utilization: float = 0.80       # 低利用率阈值 (80%)
    high_utilization: float = 1.05      # 高利用率阈值 (105%)
    optimal_utilization: float = 0.90   # 最优利用率 (90%)
    safety_margin: float = 0.10         # 安全裕度 (10%)
    min_saving: float = 5000            # 最小年节省金额 (元)


@dataclass
class DemandStatistics:
    """需量统计数据"""
    meter_point_id: Optional[int]
    meter_code: str
    meter_name: str
    declared_demand: float          # 申报需量 (kW)
    demand_type: str                # 需量类型 (kW/kVA)
    max_demand_12m: float           # 12月最大需量
    avg_demand_12m: float           # 12月平均需量
    demand_95th: float              # 95分位数需量
    std_dev: float                  # 标准差
    utilization_rate: float         # 利用率
    over_declared_count: int        # 超申报次数
    transformer_name: Optional[str] # 变压器名称


@dataclass
class DemandRecommendation:
    """需量优化建议"""
    recommendation_type: str        # reduce/increase/shave/none
    suggested_demand: float         # 建议需量
    demand_reduction: float         # 需量调整量
    monthly_saving: float           # 月节省 (元)
    annual_saving: float            # 年节省 (元)
    risk_level: str                 # low/medium/high
    confidence: float               # 置信度 (0-1)
    description: str                # 描述


class DemandAnalysisService:
    """
    统一的需量分析服务

    解决的问题：
    1. 数据源统一 - 所有需量数据从 DemandHistory 表获取
    2. 申报需量统一 - 从 MeterPoint.declared_demand 获取
    3. 电价统一 - 从 PricingConfig.demand_price 获取
    4. 计算公式统一 - 使用 calculate_optimal_demand 方法
    5. 阈值统一 - 使用 DemandThresholds 配置
    """

    # 默认值常量
    DEFAULT_DEMAND_PRICE = 38.0         # 默认需量电价 (元/kW·月)
    DEFAULT_DECLARED_DEMAND = 800.0     # 默认申报需量 (kW)
    DEFAULT_OVER_MULTIPLIER = 2.0       # 默认超需量加价倍数

    def __init__(self, db: AsyncSession):
        self.db = db
        self.thresholds = DemandThresholds()

    # ==================== 数据获取方法 ====================

    async def get_demand_price(self) -> float:
        """
        统一获取需量电价

        数据源: PricingConfig.demand_price
        回退: 默认值 38.0 元/kW·月
        """
        try:
            result = await self.db.execute(
                select(PricingConfig)
                .where(PricingConfig.is_active == True)
                .order_by(PricingConfig.id.desc())
                .limit(1)
            )
            config = result.scalar_one_or_none()
            if config and config.demand_price:
                return float(config.demand_price)
        except Exception as e:
            logger.warning(f"获取需量电价失败: {e}")

        return self.DEFAULT_DEMAND_PRICE

    async def get_over_demand_multiplier(self) -> float:
        """获取超需量加价倍数"""
        try:
            result = await self.db.execute(
                select(PricingConfig)
                .where(PricingConfig.is_active == True)
                .order_by(PricingConfig.id.desc())
                .limit(1)
            )
            config = result.scalar_one_or_none()
            if config and config.over_demand_multiplier:
                return float(config.over_demand_multiplier)
        except Exception as e:
            logger.warning(f"获取超需量倍数失败: {e}")

        return self.DEFAULT_OVER_MULTIPLIER

    async def get_declared_demand(
        self,
        meter_point_id: Optional[int] = None
    ) -> float:
        """
        统一获取申报需量

        数据源: MeterPoint.declared_demand
        如果 meter_point_id 为 None，返回所有计量点的总和
        """
        try:
            if meter_point_id:
                result = await self.db.execute(
                    select(MeterPoint)
                    .where(MeterPoint.id == meter_point_id)
                )
                mp = result.scalar_one_or_none()
                if mp and mp.declared_demand:
                    return float(mp.declared_demand)
            else:
                # 全站：返回所有计量点申报需量之和
                result = await self.db.execute(
                    select(func.sum(MeterPoint.declared_demand))
                    .where(MeterPoint.is_enabled == True)
                )
                total = result.scalar()
                if total:
                    return float(total)
        except Exception as e:
            logger.warning(f"获取申报需量失败: {e}")

        return self.DEFAULT_DECLARED_DEMAND

    async def get_meter_point_info(
        self,
        meter_point_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取计量点信息"""
        try:
            result = await self.db.execute(
                select(MeterPoint, Transformer)
                .outerjoin(Transformer, MeterPoint.transformer_id == Transformer.id)
                .where(MeterPoint.id == meter_point_id)
            )
            row = result.first()
            if row:
                mp, transformer = row
                return {
                    "id": mp.id,
                    "meter_code": mp.meter_code,
                    "meter_name": mp.meter_name or mp.meter_code,
                    "declared_demand": float(mp.declared_demand or 0),
                    "demand_type": getattr(mp, 'demand_type', 'kW') or 'kW',
                    "transformer_name": transformer.transformer_name if transformer else None
                }
        except Exception as e:
            logger.warning(f"获取计量点信息失败: {e}")

        return None

    async def get_demand_history(
        self,
        meter_point_id: Optional[int] = None,
        months: int = 12
    ) -> List[DemandHistory]:
        """
        统一获取需量历史数据

        数据源: DemandHistory 表

        Args:
            meter_point_id: 计量点ID，None则获取全站数据
            months: 获取的月数，默认12个月

        [V2.9-FIX] 使用 subtract_months 进行精确的月份计算
        """
        end_date = datetime.now()
        start_date = subtract_months(end_date, months)  # 精确月份计算

        query = select(DemandHistory).where(
            and_(
                DemandHistory.stat_year * 100 + DemandHistory.stat_month >=
                    start_date.year * 100 + start_date.month,
                DemandHistory.stat_year * 100 + DemandHistory.stat_month <=
                    end_date.year * 100 + end_date.month
            )
        ).order_by(DemandHistory.stat_year, DemandHistory.stat_month)

        if meter_point_id:
            query = query.where(DemandHistory.meter_point_id == meter_point_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_demand_statistics(
        self,
        meter_point_id: Optional[int] = None,
        months: int = 12
    ) -> Optional[DemandStatistics]:
        """
        获取需量统计数据

        统一的需量统计计算入口
        """
        import statistics as stat_lib

        # 获取需量历史
        history = await self.get_demand_history(meter_point_id, months)
        if len(history) < 3:
            return None

        # 获取计量点信息
        if meter_point_id:
            mp_info = await self.get_meter_point_info(meter_point_id)
            if not mp_info:
                return None
            declared_demand = mp_info["declared_demand"]
            meter_code = mp_info["meter_code"]
            meter_name = mp_info["meter_name"]
            demand_type = mp_info["demand_type"]
            transformer_name = mp_info["transformer_name"]
        else:
            # 全站数据
            declared_demand = await self.get_declared_demand()
            meter_code = "ALL"
            meter_name = "全站"
            demand_type = "kW"
            transformer_name = None

        if declared_demand <= 0:
            return None

        # 计算统计数据
        max_demands = [h.max_demand for h in history if h.max_demand and h.max_demand > 0]
        if not max_demands:
            return None

        max_demand_12m = max(max_demands)
        avg_demand_12m = stat_lib.mean(max_demands)
        std_dev = stat_lib.stdev(max_demands) if len(max_demands) > 1 else 0

        # 计算95%分位数
        sorted_demands = sorted(max_demands)
        idx_95 = int(len(sorted_demands) * 0.95)
        demand_95th = sorted_demands[min(idx_95, len(sorted_demands) - 1)]

        # 计算利用率
        utilization_rate = max_demand_12m / declared_demand

        # 计算超申报次数
        over_declared_count = sum(
            h.over_declared_times or 0 for h in history
        )

        return DemandStatistics(
            meter_point_id=meter_point_id,
            meter_code=meter_code,
            meter_name=meter_name,
            declared_demand=declared_demand,
            demand_type=demand_type,
            max_demand_12m=max_demand_12m,
            avg_demand_12m=avg_demand_12m,
            demand_95th=demand_95th,
            std_dev=std_dev,
            utilization_rate=utilization_rate,
            over_declared_count=over_declared_count,
            transformer_name=transformer_name
        )

    # ==================== 计算方法 ====================

    def calculate_optimal_demand(
        self,
        reference_demand: float,
        safety_margin: Optional[float] = None,
        demand_type: str = "kW"
    ) -> float:
        """
        统一的建议需量计算方法

        计算公式:
        1. 基于参考需量(通常是95分位数)加安全裕度
        2. 按供电局要求取整 (kW按5取整，kVA按10取整)

        Args:
            reference_demand: 参考需量 (通常使用95分位数需量)
            safety_margin: 安全裕度，默认使用阈值配置的10%
            demand_type: 需量类型 (kW/kVA)

        Returns:
            建议申报需量
        """
        if safety_margin is None:
            safety_margin = self.thresholds.safety_margin

        # 添加安全裕度
        optimal = reference_demand * (1 + safety_margin)

        # 按照供电局要求取整
        if demand_type.upper() == 'KVA':
            # kVA通常按10取整
            optimal = math.ceil(optimal / 10) * 10
        else:
            # kW按5取整
            optimal = math.ceil(optimal / 5) * 5

        return optimal

    async def generate_recommendation(
        self,
        stats: DemandStatistics
    ) -> DemandRecommendation:
        """
        生成需量优化建议

        使用统一的阈值和计算逻辑
        """
        demand_price = await self.get_demand_price()

        low_threshold = self.thresholds.low_utilization
        high_threshold = self.thresholds.high_utilization

        # 情况1: 需量配置过高 (利用率低)
        if stats.utilization_rate < low_threshold:
            # 使用95分位数作为参考
            suggested_demand = self.calculate_optimal_demand(
                stats.demand_95th,
                self.thresholds.safety_margin,
                stats.demand_type
            )

            demand_reduction = stats.declared_demand - suggested_demand
            monthly_saving = demand_reduction * demand_price
            annual_saving = monthly_saving * 12

            risk_level = 'low' if stats.utilization_rate < 0.70 else 'medium'
            confidence = 0.90 if risk_level == 'low' else 0.80

            return DemandRecommendation(
                recommendation_type='reduce',
                suggested_demand=suggested_demand,
                demand_reduction=demand_reduction,
                monthly_saving=monthly_saving,
                annual_saving=annual_saving,
                risk_level=risk_level,
                confidence=confidence,
                description=f"当前申报需量{stats.declared_demand:.0f}kW，"
                           f"实际利用率仅{stats.utilization_rate:.1%}，"
                           f"建议降至{suggested_demand:.0f}kW"
            )

        # 情况2: 需量配置过低 (超申报风险)
        elif stats.utilization_rate > high_threshold:
            # 使用最大需量 + 更大裕度
            suggested_demand = self.calculate_optimal_demand(
                stats.max_demand_12m,
                self.thresholds.safety_margin * 1.5,  # 更大裕度
                stats.demand_type
            )

            over_multiplier = await self.get_over_demand_multiplier()
            over_amount = stats.max_demand_12m - stats.declared_demand
            penalty_estimate = over_amount * demand_price * over_multiplier * 12

            return DemandRecommendation(
                recommendation_type='increase',
                suggested_demand=suggested_demand,
                demand_reduction=suggested_demand - stats.declared_demand,
                monthly_saving=-penalty_estimate / 12,  # 负数表示避免损失
                annual_saving=-penalty_estimate,
                risk_level='high',
                confidence=0.95,
                description=f"当前申报需量{stats.declared_demand:.0f}kW，"
                           f"实际已超{(stats.utilization_rate-1)*100:.1f}%，"
                           f"存在超需量罚款风险"
            )

        # 情况3: 需量配置合理但波动大，可削峰
        elif stats.std_dev > stats.avg_demand_12m * 0.15:
            peak_shave_target = stats.max_demand_12m - stats.demand_95th
            potential_saving = peak_shave_target * demand_price * 12

            return DemandRecommendation(
                recommendation_type='shave',
                suggested_demand=stats.demand_95th,
                demand_reduction=peak_shave_target,
                monthly_saving=potential_saving / 12,
                annual_saving=potential_saving,
                risk_level='medium',
                confidence=0.75,
                description=f"需量波动较大，通过削峰可降低{peak_shave_target:.1f}kW需量"
            )

        # 情况4: 配置合理，无需调整
        return DemandRecommendation(
            recommendation_type='none',
            suggested_demand=stats.declared_demand,
            demand_reduction=0,
            monthly_saving=0,
            annual_saving=0,
            risk_level='low',
            confidence=1.0,
            description=f"需量配置合理，利用率{stats.utilization_rate:.1%}"
        )

    # ==================== 完整分析入口 ====================

    async def analyze(
        self,
        meter_point_id: Optional[int] = None,
        months: int = 12
    ) -> Dict[str, Any]:
        """
        统一的需量分析入口

        供 DemandOptimizationPlugin、OpportunityEngine、demand.py API 调用

        Returns:
            {
                "has_opportunity": bool,
                "statistics": DemandStatistics,
                "recommendation": DemandRecommendation,
                "demand_price": float,
                "thresholds": DemandThresholds
            }
        """
        stats = await self.get_demand_statistics(meter_point_id, months)

        if not stats:
            return {
                "has_opportunity": False,
                "message": "需量历史数据不足，无法进行分析",
                "statistics": None,
                "recommendation": None
            }

        recommendation = await self.generate_recommendation(stats)
        demand_price = await self.get_demand_price()

        has_opportunity = (
            recommendation.recommendation_type != 'none' and
            abs(recommendation.annual_saving) >= self.thresholds.min_saving
        )

        return {
            "has_opportunity": has_opportunity,
            "statistics": {
                "meter_point_id": stats.meter_point_id,
                "meter_code": stats.meter_code,
                "meter_name": stats.meter_name,
                "declared_demand": stats.declared_demand,
                "demand_type": stats.demand_type,
                "max_demand_12m": round(stats.max_demand_12m, 1),
                "avg_demand_12m": round(stats.avg_demand_12m, 1),
                "demand_95th": round(stats.demand_95th, 1),
                "utilization_rate": round(stats.utilization_rate, 3),
                "over_declared_count": stats.over_declared_count,
                "transformer_name": stats.transformer_name
            },
            "recommendation": {
                "type": recommendation.recommendation_type,
                "suggested_demand": recommendation.suggested_demand,
                "demand_reduction": round(recommendation.demand_reduction, 1),
                "monthly_saving": round(recommendation.monthly_saving, 2),
                "annual_saving": round(recommendation.annual_saving, 2),
                "risk_level": recommendation.risk_level,
                "confidence": recommendation.confidence,
                "description": recommendation.description
            },
            "demand_price": demand_price,
            "thresholds": {
                "low_utilization": self.thresholds.low_utilization,
                "high_utilization": self.thresholds.high_utilization,
                "safety_margin": self.thresholds.safety_margin
            }
        }

    async def get_comparison_data(
        self,
        meter_point_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取需量配置对比数据

        供 /demand/comparison API 使用
        与 analyze() 方法使用相同的数据源和计算逻辑
        """
        result = await self.analyze(meter_point_id)

        if not result.get("statistics"):
            # 返回默认数据
            return {
                "meter_point_id": meter_point_id,
                "meter_point_name": "全站" if not meter_point_id else f"计量点#{meter_point_id}",
                "current_declared": self.DEFAULT_DECLARED_DEMAND,
                "max_demand_12m": 0,
                "avg_demand_12m": 0,
                "utilization_rate": 0,
                "over_declared": 0,
                "recommendation": {
                    "suggested_demand": 0,
                    "reduce_amount": 0,
                    "monthly_saving": 0,
                    "risk_level": "unknown"
                }
            }

        stats = result["statistics"]
        rec = result["recommendation"]

        return {
            "meter_point_id": meter_point_id,
            "meter_point_name": stats["meter_name"],
            "current_declared": stats["declared_demand"],
            "max_demand_12m": stats["max_demand_12m"],
            "avg_demand_12m": stats["avg_demand_12m"],
            "utilization_rate": stats["utilization_rate"],
            "over_declared": stats["declared_demand"] - stats["max_demand_12m"],
            "recommendation": {
                "suggested_demand": rec["suggested_demand"],
                "reduce_amount": abs(rec["demand_reduction"]),
                "monthly_saving": abs(rec["monthly_saving"]),
                "risk_level": rec["risk_level"]
            }
        }

    # ==================== 统一模拟数据生成方法 ====================

    @staticmethod
    def generate_mock_demand_curve(
        meter_point_id: Optional[int],
        months: int,
        base_demand: float = 650.0,
        declared_demand: float = 800.0
    ) -> List[Dict[str, Any]]:
        """
        生成确定性的需量曲线模拟数据

        [V2.9] 统一的模拟数据生成，确保各 API 返回一致的数据

        Args:
            meter_point_id: 计量点ID，用于生成确定性种子
            months: 月数
            base_demand: 基础需量
            declared_demand: 申报需量

        Returns:
            月度需量数据列表
        """
        from datetime import datetime, timedelta

        end_date = datetime.now()
        data = []
        seed = (meter_point_id or 0) % 10

        for i in range(months):
            month_date = end_date - timedelta(days=(months - i - 1) * 30)
            month_str = month_date.strftime("%Y-%m")
            month_num = month_date.month

            # 确定性的月度波动 - 与 energy.py 保持一致的算法
            # 基于 meter_point_id 的确定性因子
            seed_factor = (seed + 1) / 10  # 0.1-1.0
            base_ratio = 0.75 + seed_factor * 0.2  # 0.77-0.95

            # 季节性波动
            month_factor = 1.0 + (month_num - 6) * 0.015
            if month_num in [7, 8, 1, 2]:  # 夏季和冬季高峰
                month_factor += 0.04

            max_demand = base_demand * base_ratio * month_factor
            avg_demand = max_demand * 0.72

            data.append({
                "month": month_str,
                "max_demand": round(max_demand, 1),
                "avg_demand": round(avg_demand, 1),
                "declared_demand": declared_demand
            })

        return data

    @staticmethod
    def generate_mock_hourly_load(
        meter_point_id: Optional[int],
        target_date: 'date',
        period_map: Dict[int, str]
    ) -> List[Dict[str, Any]]:
        """
        生成确定性的24小时负荷模拟数据

        Args:
            meter_point_id: 计量点ID
            target_date: 目标日期
            period_map: 时段映射 {hour: period_type}

        Returns:
            24小时负荷数据列表
        """
        base_powers = {
            'deep_valley': 380,
            'valley': 450,
            'flat': 550,
            'peak': 680,
            'sharp': 750
        }

        seed = ((meter_point_id or 0) + target_date.day) % 20
        hourly_data = []

        for hour in range(24):
            period = period_map.get(hour, 'flat')
            # 确定性的小时波动
            hour_offset = ((hour * 7 + seed) % 41) - 20  # -20 到 +20
            power = base_powers.get(period, 550) + hour_offset

            hourly_data.append({
                "hour": hour,
                "power": round(power, 1),
                "period": period
            })

        return hourly_data

    @staticmethod
    def generate_mock_power_factor(
        meter_point_id: Optional[int],
        days: int,
        baseline: float = 0.90
    ) -> List[Dict[str, Any]]:
        """
        生成确定性的功率因数趋势模拟数据

        Args:
            meter_point_id: 计量点ID
            days: 天数
            baseline: 基准功率因数

        Returns:
            功率因数趋势数据列表
        """
        from datetime import datetime, timedelta

        end_date = datetime.now()
        data = []
        seed = (meter_point_id or 0) % 10

        for i in range(days):
            day = end_date - timedelta(days=days - i - 1)
            # 确定性的功率因数波动（基于日期和seed）
            day_offset = (day.day * 7 + seed + i) % 100
            pf = 0.87 + day_offset * 0.001  # 0.87-0.97之间

            data.append({
                "date": day.strftime("%Y-%m-%d"),
                "power_factor": round(pf, 3),
                "status": "good" if pf >= baseline else ("warning" if pf >= 0.85 else "bad")
            })

        return data
