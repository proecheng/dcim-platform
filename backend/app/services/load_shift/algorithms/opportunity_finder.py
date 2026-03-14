"""
Opportunity Finder - 转移机会发现算法
自动分析历史数据，识别负荷转移机会
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load_shift import ShiftOpportunity
from app.models.energy import PowerDevice
from app.models.history import PointHistory
from app.schemas.load_shift import (
    ShiftOpportunityResponse,
    ShiftPeriodType,
    OpportunityPriority
)


class OpportunityFinder:
    """
    转移机会发现器
    
    核心功能:
    1. 分析历史用电数据，识别峰谷差异
    2. 推荐可转移设备组合
    3. 计算预期收益和置信度
    4. 生成转移机会记录
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # 电价配置 (元/kWh)
        self.pricing = {
            "sharp": Decimal("1.2"),    # 尖峰
            "peak": Decimal("0.9"),     # 峰时
            "flat": Decimal("0.6"),     # 平时
            "valley": Decimal("0.3"),   # 谷时
        }
        
        # 机会识别阈值
        self.min_price_diff = Decimal("0.3")  # 最小电价差 (元/kWh)
        self.min_shift_power = 50.0           # 最小转移功率 (kW)
        self.min_confidence = 0.6             # 最小置信度
        
    async def find_daily_opportunities(
        self,
        analysis_date: date,
        lookback_days: int = 30
    ) -> List[ShiftOpportunity]:
        """
        发现指定日期的转移机会
        
        Args:
            analysis_date: 分析日期
            lookback_days: 回溯天数（用于计算典型负荷曲线）
            
        Returns:
            转移机会列表
        """
        opportunities = []
        
        # 1. 分析峰谷差异
        peak_valley_analysis = await self._analyze_peak_valley_diff(
            analysis_date,
            lookback_days
        )
        
        if not peak_valley_analysis:
            return opportunities
        
        # 2. 识别高价时段 → 低价时段的转移机会
        shift_pairs = self._identify_shift_pairs(peak_valley_analysis)
        
        # 3. 为每个转移对推荐设备和计算收益
        for shift_pair in shift_pairs:
            opportunity = await self._create_opportunity(
                analysis_date,
                shift_pair,
                lookback_days
            )
            if opportunity:
                opportunities.append(opportunity)
        
        return opportunities
    
    async def _analyze_peak_valley_diff(
        self,
        target_date: date,
        lookback_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        分析峰谷差异
        
        Returns:
            {
                "peak_avg_power": float,      # 峰时平均功率
                "valley_avg_power": float,    # 谷时平均功率
                "available_capacity": float,  # 可用容量
                "confidence": float           # 置信度
            }
        """
        start_date = target_date - timedelta(days=lookback_days)
        
        # 查询历史功率数据（简化版 - 实际应从 point_history 聚合）
        # 这里假设有一个总功率点位
        stmt = select(
            func.avg(PointHistory.value).label("avg_power"),
            func.max(PointHistory.value).label("max_power"),
            func.min(PointHistory.value).label("min_power"),
            func.count(PointHistory.id).label("data_count")
        ).where(
            and_(
                PointHistory.recorded_at >= start_date,
                PointHistory.recorded_at < target_date,
                # 假设点位 ID 1 是总功率
                PointHistory.point_id == 1
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.first()
        
        if not row or row.data_count < 100:  # 数据不足
            return None
        
        # 简化计算 - 实际应按时段分组统计
        peak_avg = float(row.max_power) * 0.8  # 峰时约为最大功率的 80%
        valley_avg = float(row.min_power) * 1.2  # 谷时约为最小功率的 120%
        
        # 可用转移容量 = 峰时功率 - 谷时功率
        available_capacity = max(0, peak_avg - valley_avg)
        
        # 置信度 = min(数据天数 / 30, 1.0)
        confidence = min(lookback_days / 30.0, 1.0)
        
        return {
            "peak_avg_power": peak_avg,
            "valley_avg_power": valley_avg,
            "available_capacity": available_capacity,
            "confidence": confidence,
            "data_days": lookback_days
        }
    
    def _identify_shift_pairs(
        self,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        识别转移对（源时段 → 目标时段）
        
        Returns:
            [
                {
                    "from_period": "peak",
                    "to_period": "valley",
                    "price_diff": Decimal,
                    "recommended_power": float
                }
            ]
        """
        pairs = []
        available_power = analysis["available_capacity"]
        
        if available_power < self.min_shift_power:
            return pairs
        
        # 定义转移对优先级（按电价差排序）
        shift_combinations = [
            ("sharp", "valley", self.pricing["sharp"] - self.pricing["valley"]),
            ("peak", "valley", self.pricing["peak"] - self.pricing["valley"]),
            ("sharp", "flat", self.pricing["sharp"] - self.pricing["flat"]),
            ("peak", "flat", self.pricing["peak"] - self.pricing["flat"]),
        ]
        
        for from_period, to_period, price_diff in shift_combinations:
            if price_diff >= self.min_price_diff:
                # 推荐功率 = 可用容量的 70%（保守策略）
                recommended_power = available_power * 0.7
                
                pairs.append({
                    "from_period": from_period,
                    "to_period": to_period,
                    "price_diff": price_diff,
                    "recommended_power": recommended_power
                })
        
        return pairs
    
    async def _create_opportunity(
        self,
        analysis_date: date,
        shift_pair: Dict[str, Any],
        lookback_days: int
    ) -> Optional[ShiftOpportunity]:
        """
        创建转移机会记录
        """
        # 推荐设备
        recommended_devices = await self._recommend_shift_devices(
            shift_pair["recommended_power"]
        )
        
        if not recommended_devices:
            return None
        
        # 计算预期收益
        predicted_saving = self._calculate_predicted_saving(
            shift_pair["recommended_power"],
            shift_pair["price_diff"],
            duration_hours=4  # 假设转移 4 小时
        )
        
        # 计算置信度
        confidence = self._calculate_confidence_score(
            lookback_days,
            len(recommended_devices)
        )
        
        if confidence < self.min_confidence:
            return None
        
        # 生成机会编号
        opportunity_code = f"OPP-{analysis_date.strftime('%Y%m%d')}-{shift_pair['from_period'].upper()[:1]}{shift_pair['to_period'].upper()[:1]}"
        
        # 创建机会对象
        opportunity = ShiftOpportunity(
            opportunity_code=opportunity_code,
            opportunity_name=f"{shift_pair['from_period']}→{shift_pair['to_period']} 转移机会",
            analysis_date=analysis_date,
            recommended_shift_from=shift_pair["from_period"],
            recommended_shift_to=shift_pair["to_period"],
            recommended_shift_power=shift_pair["recommended_power"],
            estimated_cost_saving=predicted_saving,
            confidence_score=confidence,
            status="pending",
            priority=self._determine_priority(predicted_saving, confidence),
            recommended_devices=recommended_devices,
            analysis_data={
                "price_diff": float(shift_pair["price_diff"]),
                "lookback_days": lookback_days,
                "device_count": len(recommended_devices)
            }
        )
        
        self.db.add(opportunity)
        await self.db.flush()
        
        return opportunity
    
    async def _recommend_shift_devices(
        self,
        target_power: float
    ) -> List[Dict[str, Any]]:
        """
        推荐可转移设备组合
        
        策略:
        1. 优先选择柔性系数高的设备
        2. 避免关键负荷设备
        3. 功率总和接近目标功率
        """
        # 查询可转移设备
        stmt = select(PowerDevice).where(
            and_(
                PowerDevice.is_shiftable == True,
                PowerDevice.is_critical == False,
                PowerDevice.rated_power > 0
            )
        ).order_by(PowerDevice.flexibility_factor.desc())
        
        result = await self.db.execute(stmt)
        devices = result.scalars().all()
        
        if not devices:
            return []
        
        # 贪心算法选择设备
        selected_devices = []
        accumulated_power = 0.0
        
        for device in devices:
            if accumulated_power >= target_power:
                break
            
            # 计算设备可转移功率
            shiftable_power = device.rated_power * device.shiftable_power_ratio
            
            if shiftable_power > 0:
                selected_devices.append({
                    "device_id": device.id,
                    "device_name": device.device_name,
                    "device_type": device.device_type,
                    "rated_power": float(device.rated_power),
                    "shiftable_power": float(shiftable_power),
                    "flexibility_factor": float(device.flexibility_factor)
                })
                accumulated_power += shiftable_power
        
        return selected_devices
    
    def _calculate_predicted_saving(
        self,
        shift_power: float,
        price_diff: Decimal,
        duration_hours: int
    ) -> Decimal:
        """
        计算预期成本节省
        
        公式: 节省 = 转移功率 × 电价差 × 转移时长
        """
        energy_shifted = Decimal(str(shift_power)) * Decimal(str(duration_hours))
        cost_saving = energy_shifted * price_diff
        return cost_saving.quantize(Decimal("0.01"))
    
    def _calculate_confidence_score(
        self,
        lookback_days: int,
        device_count: int
    ) -> float:
        """
        计算置信度分数
        
        因素:
        1. 历史数据天数（越多越可靠）
        2. 推荐设备数量（越多越灵活）
        """
        # 数据天数因子 (0-0.7)
        data_factor = min(lookback_days / 30.0, 1.0) * 0.7
        
        # 设备数量因子 (0-0.3)
        device_factor = min(device_count / 5.0, 1.0) * 0.3
        
        confidence = data_factor + device_factor
        return round(confidence, 2)
    
    def _determine_priority(
        self,
        predicted_saving: Decimal,
        confidence: float
    ) -> str:
        """
        确定机会优先级
        
        规则:
        - 高优先级: 节省 > 500 且置信度 > 0.8
        - 中优先级: 节省 > 200 且置信度 > 0.6
        - 低优先级: 其他
        """
        if predicted_saving > 500 and confidence > 0.8:
            return "high"
        elif predicted_saving > 200 and confidence > 0.6:
            return "medium"
        else:
            return "low"
