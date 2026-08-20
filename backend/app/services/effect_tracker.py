"""
效果追踪定时服务
自动为已完成的执行计划生成效果追踪记录
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from ..models.energy import ExecutionPlan, ExecutionResult, EnergyDaily, ElectricityPricing

logger = logging.getLogger(__name__)


class EffectTracker:
    """效果追踪定时服务 - 自动为已完成计划生成效果追踪记录"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_tracking(self) -> Dict[str, Any]:
        """主入口"""
        # 1. 为需要追踪的计划创建追踪记录
        new_tracking = await self._create_tracking_for_completed_plans()
        # 2. 标记追踪期结束的记录为 completed
        marked_completed = await self._mark_completed_tracking()
        return {"new_tracking": new_tracking, "marked_completed": marked_completed}

    async def _create_tracking_for_completed_plans(self) -> int:
        """为已完成且无追踪记录的计划创建追踪"""
        plans = await self._find_plans_needing_tracking()
        count = 0
        for plan in plans:
            try:
                device_ids = self._extract_device_ids(plan)
                effect = await self._calculate_effect(plan, device_ids)
                if effect:
                    await self._save_tracking_result(plan, effect)
                    count += 1
            except Exception as e:
                logger.error(f"追踪计划 {plan.id} 失败: {e}")
        if count > 0:
            await self.db.commit()
        return count

    async def _find_plans_needing_tracking(self) -> List:
        """查找需要追踪的计划: status='completed', completed_at 距今 >= 7天, 无 ExecutionResult"""
        # Keep the cutoff as a Python date. PostgreSQL's ``date(timestamp)``
        # expression returns DATE and rejects a VARCHAR comparison.
        seven_days_ago = date.today() - timedelta(days=7)
        result = await self.db.execute(
            select(ExecutionPlan)
            .outerjoin(ExecutionResult)
            .where(
                and_(
                    ExecutionPlan.status == "completed",
                    func.date(ExecutionPlan.completed_at) <= seven_days_ago,
                    ExecutionResult.id == None,
                )
            )
            .options(selectinload(ExecutionPlan.opportunity), selectinload(ExecutionPlan.tasks))
        )
        return result.scalars().all()

    def _extract_device_ids(self, plan) -> List[int]:
        """从计划的任务中提取设备ID列表"""
        device_ids: Set[int] = set()
        for task in plan.tasks or []:
            params = task.parameters or {}
            # 从 selected_devices 提取
            for dev in params.get("selected_devices", []):
                if isinstance(dev, int):
                    device_ids.add(dev)
                elif isinstance(dev, dict):
                    did = dev.get("device_id", 0)
                    if did:
                        device_ids.add(int(did))
            # 从 target_object 提取 "device:123" 格式
            target = task.target_object or ""
            if target.startswith("device:"):
                try:
                    device_ids.add(int(target.split(":")[1]))
                except (ValueError, IndexError):
                    pass
            # 从 parameters.device_id 提取
            if "device_id" in params and params["device_id"]:
                try:
                    device_ids.add(int(params["device_id"]))
                except (ValueError, TypeError):
                    pass
        device_ids.discard(0)
        return list(device_ids)

    async def _calculate_effect(self, plan, device_ids: List[int], tracking_days: int = 7) -> Optional[Dict]:
        """计算效果 - 区分负荷转移和能耗对比"""
        if not plan.completed_at:
            return None

        tracking_start = plan.completed_at.date() if hasattr(plan.completed_at, "date") else plan.completed_at
        tracking_end = tracking_start + timedelta(days=tracking_days)

        source_plugin = plan.opportunity.source_plugin if plan.opportunity else None
        analysis_data = plan.opportunity.analysis_data if plan.opportunity else {}

        if source_plugin == "peak_valley_optimizer" and analysis_data:
            return await self._calculate_load_shift_effect(analysis_data, tracking_days, tracking_start, tracking_end)
        else:
            return await self._calculate_energy_comparison_effect(
                device_ids, tracking_start, tracking_end, tracking_days
            )

    async def _calculate_energy_comparison_effect(
        self, device_ids, tracking_start, tracking_end, tracking_days
    ) -> Dict:
        """能耗对比计算 - 带设备过滤"""
        before_start = tracking_start - timedelta(days=tracking_days)
        before_end = tracking_start - timedelta(days=1)

        # 构建查询条件
        before_conditions = [
            EnergyDaily.stat_date >= before_start,
            EnergyDaily.stat_date <= before_end,
        ]
        after_conditions = [
            EnergyDaily.stat_date >= tracking_start,
            EnergyDaily.stat_date <= tracking_end,
        ]

        # 设备过滤 (H3)
        if device_ids:
            before_conditions.append(EnergyDaily.device_id.in_(device_ids))
            after_conditions.append(EnergyDaily.device_id.in_(device_ids))

        # 按日聚合 - 执行前
        before_result = await self.db.execute(
            select(EnergyDaily.stat_date, func.sum(EnergyDaily.total_energy), func.sum(EnergyDaily.energy_cost))
            .where(and_(*before_conditions))
            .group_by(EnergyDaily.stat_date)
            .order_by(EnergyDaily.stat_date)
        )
        before_rows = before_result.all()

        # 按日聚合 - 执行后
        after_result = await self.db.execute(
            select(EnergyDaily.stat_date, func.sum(EnergyDaily.total_energy), func.sum(EnergyDaily.energy_cost))
            .where(and_(*after_conditions))
            .group_by(EnergyDaily.stat_date)
            .order_by(EnergyDaily.stat_date)
        )
        after_rows = after_result.all()

        # 汇总
        before_total_energy = sum(float(r[1] or 0) for r in before_rows)
        after_total_energy = sum(float(r[1] or 0) for r in after_rows)
        before_total_cost = sum(float(r[2] or 0) for r in before_rows)
        after_total_cost = sum(float(r[2] or 0) for r in after_rows)

        energy_saved = before_total_energy - after_total_energy
        cost_saved = before_total_cost - after_total_cost

        # 如果没有 cost 数据，用平均电价估算
        if cost_saved == 0 and energy_saved != 0:
            avg_price = await self._get_average_price()
            cost_saved = energy_saved * avg_price

        # 年化
        actual_annual = (cost_saved / tracking_days) * 250 if tracking_days > 0 else 0

        return {
            "energy_saved": energy_saved,
            "cost_saved": cost_saved,
            "actual_annual": actual_annual,
            "calculation_method": "energy_comparison",
            "device_filtered": len(device_ids) > 0,
            "energy_before": [
                {"date": str(r[0]), "energy": float(r[1] or 0), "cost": float(r[2] or 0)} for r in before_rows
            ],
            "energy_after": [
                {"date": str(r[0]), "energy": float(r[1] or 0), "cost": float(r[2] or 0)} for r in after_rows
            ],
            "tracking_start": tracking_start,
            "tracking_end": tracking_end,
            "tracking_days": tracking_days,
        }

    async def _calculate_load_shift_effect(self, analysis_data, tracking_days, tracking_start, tracking_end) -> Dict:
        """负荷转移方案效果计算"""
        default_prices = {"sharp": 1.20, "peak": 0.95, "flat": 0.65, "valley": 0.35, "deep_valley": 0.20}
        period_prices = await self._get_period_prices()
        if not period_prices:
            period_prices = default_prices

        daily_saving = 0.0
        energy_shifted = 0.0

        device_rules = analysis_data.get("device_rules", [])
        for device_rule in device_rules:
            rules = device_rule.get("rules", [])
            for rule in rules:
                source_period = rule.get("source_period", "peak")
                target_period = rule.get("target_period", "valley")
                power = float(rule.get("power", 0))
                hours = float(rule.get("hours", 0))
                source_price = period_prices.get(source_period, 0.95)
                target_price = period_prices.get(target_period, 0.35)
                energy = power * hours
                price_diff = source_price - target_price
                daily_saving += energy * price_diff
                energy_shifted += energy

        working_ratio = 5 / 7
        cost_saved = daily_saving * tracking_days * working_ratio
        annual_saving = daily_saving * 250

        return {
            "energy_saved": energy_shifted * tracking_days * working_ratio,
            "cost_saved": cost_saved,
            "actual_annual": annual_saving,
            "calculation_method": "load_shift",
            "device_filtered": True,
            "energy_before": [],
            "energy_after": [],
            "tracking_start": tracking_start,
            "tracking_end": tracking_end,
            "tracking_days": tracking_days,
        }

    async def _save_tracking_result(self, plan, effect: Dict):
        """保存追踪结果"""
        expected_saving = float(plan.expected_saving or 0)
        actual_annual = effect["actual_annual"]
        achievement_rate = (actual_annual / expected_saving * 100) if expected_saving > 0 else 0
        # C3: clamp to Numeric(5,2) max
        achievement_rate = min(achievement_rate, 999.99)

        tracking_start = effect["tracking_start"]
        tracking_end = effect["tracking_end"]

        result = ExecutionResult(
            plan_id=plan.id,
            tracking_period=effect.get("tracking_days", 7),
            tracking_start=tracking_start,
            tracking_end=tracking_end,
            actual_saving=actual_annual,
            achievement_rate=achievement_rate,
            energy_before=effect.get("energy_before", []),
            energy_after=effect.get("energy_after", []),
            status="completed" if date.today() > tracking_end else "tracking",
            analysis_conclusion=self._generate_conclusion(achievement_rate),
        )
        self.db.add(result)

    async def _mark_completed_tracking(self) -> int:
        """标记追踪期结束的记录为 completed"""
        today = date.today()
        result = await self.db.execute(
            select(ExecutionResult).where(
                and_(ExecutionResult.status == "tracking", ExecutionResult.tracking_end <= today)
            )
        )
        records = result.scalars().all()
        for record in records:
            record.status = "completed"
            record.updated_at = datetime.now()
        if records:
            await self.db.commit()
        return len(records)

    async def _get_period_prices(self) -> Optional[Dict[str, float]]:
        """从电价配置获取分时电价"""
        try:
            result = await self.db.execute(select(ElectricityPricing).where(ElectricityPricing.is_enabled == True))
            rows = result.scalars().all()
            if rows:
                prices = {}
                for row in rows:
                    prices[row.period_type] = float(row.price)
                return prices if prices else None
        except Exception as e:
            logger.warning(f"获取分时电价失败: {e}")
        return None

    async def _get_average_price(self) -> float:
        """获取平均电价"""
        period_prices = await self._get_period_prices()
        if period_prices:
            weights = {"sharp": 0.05, "peak": 0.25, "flat": 0.40, "valley": 0.25, "deep_valley": 0.05}
            return sum(period_prices.get(p, 0.6) * w for p, w in weights.items())
        return 0.6

    def _generate_conclusion(self, achievement_rate: float) -> str:
        """生成效果结论"""
        if achievement_rate >= 100:
            return "执行效果优秀，超额完成预期目标"
        elif achievement_rate >= 80:
            return "执行效果良好，基本达成预期目标"
        elif achievement_rate >= 50:
            return "执行效果一般，部分达成预期目标，建议优化执行方案"
        elif achievement_rate > 0:
            return "执行效果不佳，未能达成预期目标，需要分析原因并调整策略"
        else:
            return "暂无效果数据，请等待追踪周期结束"
