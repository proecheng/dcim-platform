"""
执行计划服务
Execution Service

提供执行计划管理、任务执行、效果追踪等功能
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from ..models.energy import ExecutionPlan, ExecutionTask, ExecutionResult, EnergyOpportunity, EnergyDaily
from .device_control_service import DeviceControlService, ControlResult

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    执行计划服务

    核心功能:
    1. 获取执行计划及任务详情
    2. 执行自动控制任务
    3. 完成手动任务
    4. 更新计划状态
    5. 生成执行清单
    6. 效果追踪分析
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.device_control = DeviceControlService(db)

    async def get_plan_with_tasks(self, plan_id: int) -> Optional[Dict[str, Any]]:
        """
        获取执行计划及任务详情

        Returns:
            完整的计划信息，包括任务列表和追踪结果
        """
        result = await self.db.execute(
            select(ExecutionPlan)
            .options(
                selectinload(ExecutionPlan.tasks),
                selectinload(ExecutionPlan.results),
                selectinload(ExecutionPlan.opportunity),
            )
            .where(ExecutionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return None

        # 统计任务状态
        task_stats = {"total": len(plan.tasks), "pending": 0, "executing": 0, "completed": 0, "failed": 0}
        for task in plan.tasks:
            if task.status in task_stats:
                task_stats[task.status] += 1

        # 统计自动/手动任务
        auto_tasks = [t for t in plan.tasks if t.execution_mode == "auto"]
        manual_tasks = [t for t in plan.tasks if t.execution_mode == "manual"]

        return {
            "plan": {
                "id": plan.id,
                "opportunity_id": plan.opportunity_id,
                "plan_name": plan.plan_name,
                "expected_saving": float(plan.expected_saving or 0),
                "status": plan.status,
                "started_at": plan.started_at.isoformat() if plan.started_at else None,
                "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
                "created_at": plan.created_at.isoformat(),
            },
            "opportunity": {
                "id": plan.opportunity.id,
                "title": plan.opportunity.title,
                "category": plan.opportunity.category,
                "priority": plan.opportunity.priority,
                "source_plugin": plan.opportunity.source_plugin,
                "analysis_data": plan.opportunity.analysis_data,
            }
            if plan.opportunity
            else None,
            "tasks": [
                {
                    "id": t.id,
                    "task_type": t.task_type,
                    "task_name": t.task_name,
                    "target_object": t.target_object,
                    "execution_mode": t.execution_mode,
                    "parameters": t.parameters,
                    "status": t.status,
                    "assigned_to": t.assigned_to,
                    "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                    "result": t.result,
                    "error_message": t.error_message,
                    "sort_order": t.sort_order,
                }
                for t in sorted(plan.tasks, key=lambda x: x.sort_order)
            ],
            "task_stats": task_stats,
            "auto_task_count": len(auto_tasks),
            "manual_task_count": len(manual_tasks),
            "results": [
                {
                    "id": r.id,
                    "tracking_period": r.tracking_period,
                    "tracking_start": r.tracking_start.isoformat() if r.tracking_start else None,
                    "tracking_end": r.tracking_end.isoformat() if r.tracking_end else None,
                    "actual_saving": float(r.actual_saving or 0),
                    "achievement_rate": float(r.achievement_rate or 0),
                    "status": r.status,
                    "analysis_conclusion": r.analysis_conclusion,
                }
                for r in plan.results
            ],
            "progress_percentage": round(
                task_stats["completed"] / task_stats["total"] * 100 if task_stats["total"] > 0 else 0, 1
            ),
        }

    async def execute_auto_task(self, task_id: int, force: bool = False) -> Dict[str, Any]:
        """
        执行自动控制任务

        Args:
            task_id: 任务ID
            force: 是否强制执行

        Returns:
            执行结果
        """
        # 获取任务
        result = await self.db.execute(select(ExecutionTask).where(ExecutionTask.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return {"success": False, "error": f"任务ID {task_id} 不存在"}

        if task.execution_mode != "auto":
            return {"success": False, "error": "此任务不是自动任务"}

        if task.status == "completed":
            return {"success": False, "error": "任务已完成"}

        # 更新任务状态
        task.status = "executing"
        await self.db.commit()

        # 解析参数执行控制
        params = task.parameters or {}
        target_state = params.get("target_state", {})
        selected_devices = params.get("selected_devices", [])

        control_results = []
        all_success = True

        # 为每个设备执行控制
        if isinstance(selected_devices, list) and selected_devices:
            for device_id in selected_devices:
                if isinstance(device_id, dict):
                    device_id = device_id.get("device_id", device_id)

                # 根据任务类型确定调节参数
                reg_type = self._get_regulation_type(task.task_type)
                target_value = target_state.get("value") or target_state.get(reg_type)

                if target_value is not None:
                    action = await self.device_control.control_device_regulation(
                        device_id=int(device_id),
                        regulation_type=reg_type,
                        target_value=float(target_value),
                        force=force,
                    )
                    control_results.append(
                        {"device_id": device_id, "result": action.result.value, "message": action.message}
                    )

                    if action.result not in [ControlResult.SUCCESS, ControlResult.SIMULATED]:
                        all_success = False

        # 更新任务结果
        task.executed_at = datetime.now()
        task.result = {"control_results": control_results, "all_success": all_success}

        if all_success:
            task.status = "completed"
        else:
            task.status = "failed"
            task.error_message = "部分设备控制失败"

        await self.db.commit()

        # 检查是否需要更新计划状态
        await self.update_plan_status(task.plan_id)

        return {
            "success": all_success,
            "task_id": task_id,
            "status": task.status,
            "control_results": control_results,
            "executed_at": task.executed_at.isoformat(),
        }

    async def complete_manual_task(
        self, task_id: int, completed_by: Optional[str] = None, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        标记手动任务完成

        Args:
            task_id: 任务ID
            completed_by: 完成人
            notes: 备注

        Returns:
            更新结果
        """
        result = await self.db.execute(select(ExecutionTask).where(ExecutionTask.id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return {"success": False, "error": f"任务ID {task_id} 不存在"}

        if task.status == "completed":
            return {"success": False, "error": "任务已完成"}

        # 更新任务
        task.status = "completed"
        task.executed_at = datetime.now()
        task.result = {"completed_by": completed_by, "notes": notes, "completed_manually": True}
        if completed_by:
            task.assigned_to = completed_by

        await self.db.commit()

        # 检查是否需要更新计划状态
        await self.update_plan_status(task.plan_id)

        return {"success": True, "task_id": task_id, "status": task.status, "executed_at": task.executed_at.isoformat()}

    async def update_plan_status(self, plan_id: int) -> str:
        """
        更新计划状态（根据任务完成情况自动判断）

        Returns:
            新状态
        """
        result = await self.db.execute(
            select(ExecutionPlan).options(selectinload(ExecutionPlan.tasks)).where(ExecutionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return "unknown"

        # 统计任务状态
        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks if t.status == "completed")
        failed = sum(1 for t in plan.tasks if t.status == "failed")
        executing = sum(1 for t in plan.tasks if t.status == "executing")

        old_status = plan.status

        # 判断新状态
        if total == 0:
            new_status = "pending"
        elif completed == total:
            new_status = "completed"
            plan.completed_at = datetime.now()
        elif failed > 0 and completed + failed == total:
            new_status = "failed"
        elif executing > 0 or completed > 0:
            new_status = "executing"
            if not plan.started_at:
                plan.started_at = datetime.now()
        else:
            new_status = "pending"

        if new_status != old_status:
            plan.status = new_status
            plan.updated_at = datetime.now()

            # 如果计划完成，更新机会状态
            if new_status == "completed":
                await self._update_opportunity_status(plan.opportunity_id, "completed")
            elif new_status == "failed":
                await self._update_opportunity_status(plan.opportunity_id, "ready")

            await self.db.commit()

        return new_status

    async def generate_task_checklist(self, plan_id: int) -> Dict[str, Any]:
        """
        生成执行清单（用于导出PDF或创建工单）

        Returns:
            格式化的执行清单
        """
        plan_data = await self.get_plan_with_tasks(plan_id)
        if not plan_data:
            return {"error": f"计划ID {plan_id} 不存在"}

        checklist = {
            "title": plan_data["plan"]["plan_name"],
            "expected_saving": plan_data["plan"]["expected_saving"],
            "created_at": plan_data["plan"]["created_at"],
            "sections": [],
        }

        # 按执行方式分组
        auto_tasks = [t for t in plan_data["tasks"] if t["execution_mode"] == "auto"]
        manual_tasks = [t for t in plan_data["tasks"] if t["execution_mode"] == "manual"]

        if auto_tasks:
            checklist["sections"].append(
                {
                    "title": "自动执行任务",
                    "description": "以下任务可通过系统自动执行",
                    "tasks": [
                        {
                            "序号": i + 1,
                            "任务名称": t["task_name"],
                            "目标对象": t["target_object"],
                            "状态": self._get_status_text(t["status"]),
                            "执行时间": t["executed_at"] or "-",
                        }
                        for i, t in enumerate(auto_tasks)
                    ],
                }
            )

        if manual_tasks:
            checklist["sections"].append(
                {
                    "title": "人工执行任务",
                    "description": "以下任务需要人工操作完成",
                    "tasks": [
                        {
                            "序号": i + 1,
                            "任务名称": t["task_name"],
                            "目标对象": t["target_object"],
                            "负责人": t["assigned_to"] or "待分配",
                            "状态": self._get_status_text(t["status"]),
                            "完成时间": t["executed_at"] or "-",
                        }
                        for i, t in enumerate(manual_tasks)
                    ],
                }
            )

        checklist["summary"] = {
            "total_tasks": len(plan_data["tasks"]),
            "auto_tasks": len(auto_tasks),
            "manual_tasks": len(manual_tasks),
            "completed": plan_data["task_stats"]["completed"],
            "progress": plan_data["progress_percentage"],
        }

        return checklist

    async def track_execution_effect(self, plan_id: int, tracking_days: int = 7) -> Dict[str, Any]:
        """
        效果追踪分析

        Args:
            plan_id: 计划ID
            tracking_days: 追踪天数

        Returns:
            效果分析结果

        计算逻辑说明：
        1. 对于负荷转移方案（source_plugin='peak_valley_optimizer'）：
           - 基于配置中的转移参数和实际电价差计算
           - 节省 = 转移功率 × 转移时长 × 峰谷电价差 × 执行天数
           - 年化 = 节省 / 追踪天数 × 250工作日
        2. 对于其他方案：
           - 基于执行前后能耗对比计算
           - 使用分时电价加权计算成本差异
        """
        # 获取计划和关联的机会
        result = await self.db.execute(
            select(ExecutionPlan).options(selectinload(ExecutionPlan.opportunity)).where(ExecutionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()

        if not plan:
            return {"error": f"计划ID {plan_id} 不存在"}

        if plan.status != "completed":
            return {"error": "计划尚未完成执行", "current_status": plan.status}

        # 计算追踪周期
        tracking_start = plan.completed_at.date() if plan.completed_at else date.today()
        tracking_end = tracking_start + timedelta(days=tracking_days)

        # 获取方案类型和配置
        source_plugin = plan.opportunity.source_plugin if plan.opportunity else None
        analysis_data = plan.opportunity.analysis_data if plan.opportunity else {}

        # 根据方案类型计算实际节省
        if source_plugin == "peak_valley_optimizer" and analysis_data:
            # 负荷转移方案：基于配置参数计算
            actual_saving_result = await self._calculate_load_shift_saving(analysis_data, tracking_days)
            cost_saved = actual_saving_result["cost_saved"]
            actual_annual = actual_saving_result["annual_saving"]
            energy_saved = actual_saving_result.get("energy_shifted", 0)
            before_data = None
            after_data = None
        else:
            # 其他方案：基于能耗对比计算
            # 获取执行前后的能耗数据
            before_start = tracking_start - timedelta(days=tracking_days)
            before_end = tracking_start - timedelta(days=1)

            # 查询执行前数据
            before_result = await self.db.execute(
                select(
                    func.sum(EnergyDaily.total_energy), func.avg(EnergyDaily.avg_power), func.max(EnergyDaily.max_power)
                ).where(and_(EnergyDaily.stat_date >= before_start, EnergyDaily.stat_date <= before_end))
            )
            before_data = before_result.one_or_none()

            # 查询执行后数据
            after_result = await self.db.execute(
                select(
                    func.sum(EnergyDaily.total_energy), func.avg(EnergyDaily.avg_power), func.max(EnergyDaily.max_power)
                ).where(and_(EnergyDaily.stat_date >= tracking_start, EnergyDaily.stat_date <= tracking_end))
            )
            after_data = after_result.one_or_none()

            # 计算效果
            before_energy = before_data[0] or 0 if before_data else 0
            after_energy = after_data[0] or 0 if after_data else 0
            energy_saved = before_energy - after_energy

            # 获取平均电价（尝试从电价配置获取，否则使用默认值）
            avg_price = await self._get_average_price()
            cost_saved = energy_saved * avg_price

            # 年化实际节省
            actual_annual = (cost_saved / tracking_days) * 250 if tracking_days > 0 else 0

        expected_saving = float(plan.expected_saving or 0)
        achievement_rate = (actual_annual / expected_saving * 100) if expected_saving > 0 else 0

        # 创建或更新追踪记录 - 保存年化节省值
        tracking_result = ExecutionResult(
            plan_id=plan_id,
            tracking_period=tracking_days,
            tracking_start=tracking_start,
            tracking_end=tracking_end,
            actual_saving=actual_annual,  # 保存年化节省值
            achievement_rate=achievement_rate,
            energy_before={"total_energy": before_data[0] if before_data else 0}
            if not source_plugin == "peak_valley_optimizer"
            else {},
            energy_after={"total_energy": after_data[0] if after_data else 0}
            if not source_plugin == "peak_valley_optimizer"
            else {},
            status="completed" if date.today() > tracking_end else "tracking",
            analysis_conclusion=self._generate_conclusion(achievement_rate),
        )
        self.db.add(tracking_result)
        await self.db.commit()

        return {
            "plan_id": plan_id,
            "tracking_period": {
                "days": tracking_days,
                "start": tracking_start.isoformat(),
                "end": tracking_end.isoformat(),
            },
            "before_execution": {
                "period": f"{tracking_start - timedelta(days=tracking_days)} ~ {tracking_start - timedelta(days=1)}",
                "total_energy_kwh": round(before_data[0] or 0, 2) if before_data else 0,
                "avg_power_kw": round(before_data[1] or 0, 2) if before_data else 0,
                "max_power_kw": round(before_data[2] or 0, 2) if before_data else 0,
            }
            if before_data
            else None,
            "after_execution": {
                "period": f"{tracking_start} ~ {tracking_end}",
                "total_energy_kwh": round(after_data[0] or 0, 2) if after_data else 0,
                "avg_power_kw": round(after_data[1] or 0, 2) if after_data else 0,
                "max_power_kw": round(after_data[2] or 0, 2) if after_data else 0,
            }
            if after_data
            else None,
            "effect": {
                "energy_saved_kwh": round(energy_saved, 2),
                "cost_saved_yuan": round(cost_saved, 2),
                "expected_annual_saving": expected_saving,
                "actual_annual_saving": round(actual_annual, 2),
                "achievement_rate": round(achievement_rate, 1),
            },
            "calculation_method": "load_shift" if source_plugin == "peak_valley_optimizer" else "energy_comparison",
            "conclusion": self._generate_conclusion(achievement_rate),
            "status": "tracking" if date.today() <= tracking_end else "completed",
        }

    # ========== 私有方法 ==========

    async def _calculate_load_shift_saving(self, analysis_data: dict, tracking_days: int) -> Dict[str, float]:
        """
        计算负荷转移方案的实际节省

        计算公式：
        - 日节省 = Σ(转移功率 × 转移时长 × (源时段电价 - 目标时段电价))
        - 追踪期节省 = 日节省 × 追踪天数
        - 年化节省 = 日节省 × 250工作日

        Args:
            analysis_data: 方案配置数据（包含device_rules、strategy等）
            tracking_days: 追踪天数

        Returns:
            包含 cost_saved（追踪期节省）和 annual_saving（年化节省）的字典
        """
        # 默认分时电价（元/kWh）
        default_prices = {
            "sharp": 1.20,  # 尖峰
            "peak": 0.95,  # 峰时
            "flat": 0.65,  # 平时
            "valley": 0.35,  # 谷时
            "deep_valley": 0.20,  # 深谷
        }

        # 尝试从电价配置获取实际电价
        period_prices = await self._get_period_prices()
        if not period_prices:
            period_prices = default_prices

        # 计算日节省
        daily_saving = 0.0
        energy_shifted = 0.0  # 转移的电量（kWh）

        device_rules = analysis_data.get("device_rules", [])
        for device_rule in device_rules:
            rules = device_rule.get("rules", [])
            for rule in rules:
                source_period = rule.get("source_period", "peak")
                target_period = rule.get("target_period", "valley")
                power = float(rule.get("power", 0))  # kW
                hours = float(rule.get("hours", 0))  # 小时

                source_price = period_prices.get(source_period, 0.95)
                target_price = period_prices.get(target_period, 0.35)

                # 单条规则的节省
                energy = power * hours  # kWh
                price_diff = source_price - target_price  # 元/kWh
                rule_saving = energy * price_diff  # 元

                daily_saving += rule_saving
                energy_shifted += energy

        # 追踪期节省（假设追踪期内每个工作日都在执行）
        # 扣除周末，追踪天数中约有 5/7 是工作日
        working_ratio = 5 / 7
        cost_saved = daily_saving * tracking_days * working_ratio

        # 年化节省（250个工作日）
        annual_saving = daily_saving * 250

        return {
            "cost_saved": cost_saved,
            "annual_saving": annual_saving,
            "daily_saving": daily_saving,
            "energy_shifted": energy_shifted,
        }

    async def _get_period_prices(self) -> Optional[Dict[str, float]]:
        """
        从电价配置表获取分时电价

        Returns:
            分时电价字典，如果没有配置返回None
        """
        try:
            from ..models.energy import PricingConfig

            result = await self.db.execute(
                select(PricingConfig).where(PricingConfig.is_active == True).order_by(PricingConfig.id.desc()).limit(1)
            )
            config = result.scalar_one_or_none()
            if config and config.period_prices:
                return config.period_prices
        except Exception as e:
            logger.warning(f"Failed to get period prices: {e}")
        return None

    async def _get_average_price(self) -> float:
        """
        获取平均电价

        尝试从电价配置获取加权平均电价，否则返回默认值0.6元/kWh
        """
        period_prices = await self._get_period_prices()
        if period_prices:
            # 假设各时段占比：尖峰5%、峰时25%、平时40%、谷时25%、深谷5%
            weights = {"sharp": 0.05, "peak": 0.25, "flat": 0.40, "valley": 0.25, "deep_valley": 0.05}
            weighted_avg = sum(period_prices.get(period, 0.6) * weight for period, weight in weights.items())
            return weighted_avg
        return 0.6  # 默认平均电价

    def _get_regulation_type(self, task_type: str) -> str:
        """根据任务类型获取调节类型"""
        mapping = {
            "temp_adjust": "temperature",
            "temperature_adjust": "temperature",
            "brightness_adjust": "brightness",
            "load_adjust": "load",
            "device_control": "temperature",  # 默认
        }
        return mapping.get(task_type, "temperature")

    def _get_status_text(self, status: str) -> str:
        """获取状态文本"""
        texts = {
            "pending": "⏳ 待执行",
            "executing": "🔄 执行中",
            "completed": "✅ 已完成",
            "failed": "❌ 失败",
            "skipped": "⏭️ 已跳过",
        }
        return texts.get(status, status)

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

    async def _update_opportunity_status(self, opportunity_id: int, status: str) -> None:
        """更新机会状态"""
        result = await self.db.execute(select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id))
        opportunity = result.scalar_one_or_none()
        if opportunity:
            opportunity.status = status
            opportunity.updated_at = datetime.now()
