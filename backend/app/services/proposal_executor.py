from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog


class ProposalExecutor:
    """
    方案执行器 - 执行已接受的措施并记录日志

    增强功能 (专利 S4):
    - 执行前自动采集基准值
    - 执行后触发持续监测
    - 监测数据自动推送到 RL 模块
    """

    def __init__(self, db: AsyncSession, enable_monitoring: bool = True):
        self.db = db
        self.enable_monitoring = enable_monitoring
        self._monitoring_service = None

    def _get_monitoring_service(self):
        """延迟加载监测服务"""
        if self._monitoring_service is None and self.enable_monitoring:
            try:
                from app.services.effect_monitoring_service import EffectMonitoringService
                self._monitoring_service = EffectMonitoringService(self.db)
            except Exception as e:
                print(f"监测服务初始化失败: {e}")
        return self._monitoring_service

    async def execute_proposal(self, proposal: EnergySavingProposal) -> Dict[str, Any]:
        """
        执行整个方案（所有已选择的措施）

        增强流程:
        1. 为每个措施采集基准值 (S4a)
        2. 执行措施
        3. 启动持续监测 (S4b)

        返回:
        {
            "proposal_id": int,
            "executed_count": int,
            "success_count": int,
            "results": [...],
            "monitoring_started": bool
        }
        """
        results = []
        success_count = 0
        baselines = {}

        # S4a: 为每个待执行措施采集基准值
        monitoring_service = self._get_monitoring_service()
        if monitoring_service:
            for measure in proposal.measures:
                if measure.is_selected:
                    try:
                        baseline = await monitoring_service.capture_baseline(measure)
                        baselines[measure.id] = baseline
                    except Exception as e:
                        print(f"基准采集失败: {e}")

        # 执行措施
        for measure in proposal.measures:
            if not measure.is_selected:
                continue

            result = await self.execute_measure(measure, baselines.get(measure.id))
            results.append(result)
            if result["success"]:
                success_count += 1

        proposal.status = "executing"
        await self.db.commit()

        # S4b: 启动持续监测
        monitoring_started = False
        if monitoring_service and success_count > 0:
            try:
                session = await monitoring_service.start_monitoring(proposal)
                monitoring_started = True
            except Exception as e:
                print(f"启动监测失败: {e}")

        return {
            "proposal_id": proposal.id,
            "executed_count": len(results),
            "success_count": success_count,
            "results": results,
            "monitoring_started": monitoring_started,
            "baselines_captured": len(baselines)
        }

    async def execute_measure(self, measure: ProposalMeasure, baseline=None) -> Dict[str, Any]:
        """
        执行单个措施

        步骤:
        1. 读取当前设备状态（模拟）
        2. 发送控制指令（模拟）
        3. 验证执行结果
        4. 记录执行日志
        """
        try:
            # 1. 获取执行前状态 (优先使用基准值)
            if baseline:
                power_before = baseline.power_avg
            else:
                power_before = self._get_current_power(measure)

            expected_power_saved = self._calculate_expected_savings(measure)

            # 2. 执行控制动作（模拟）
            success = self._execute_control_action(measure)

            # 3. 获取执行后状态
            power_after = self._get_current_power(measure) if success else power_before
            power_saved = power_before - power_after if success else Decimal("0")

            # 4. 记录日志
            log = MeasureExecutionLog(
                measure_id=measure.id,
                execution_time=datetime.now(),
                power_before=power_before,
                power_after=power_after,
                power_saved=power_saved,
                expected_power_saved=expected_power_saved,
                result="success" if success else "failed",
                result_message="执行成功" if success else "执行失败",
                execution_data={
                    "regulation_object": measure.regulation_object,
                    "target_state": measure.target_state
                }
            )
            self.db.add(log)

            # 5. 更新措施状态
            measure.execution_status = "completed" if success else "failed"
            await self.db.commit()

            return {
                "measure_id": measure.id,
                "measure_code": measure.measure_code,
                "success": success,
                "power_saved": float(power_saved),
                "expected_power_saved": float(expected_power_saved)
            }

        except Exception as e:
            # 记录失败日志
            log = MeasureExecutionLog(
                measure_id=measure.id,
                execution_time=datetime.now(),
                result="failed",
                result_message=str(e)
            )
            self.db.add(log)
            measure.execution_status = "failed"
            await self.db.commit()

            return {
                "measure_id": measure.id,
                "measure_code": measure.measure_code,
                "success": False,
                "error": str(e)
            }

    def _get_current_power(self, measure: ProposalMeasure) -> Decimal:
        """获取当前功率（模拟）"""
        # 实际应从设备或监测系统获取
        current = measure.current_state or {}
        return Decimal(str(current.get("power", 1000)))

    def _calculate_expected_savings(self, measure: ProposalMeasure) -> Decimal:
        """计算预期节省功率"""
        current = measure.current_state or {}
        target = measure.target_state or {}

        current_power = Decimal(str(current.get("power", 1000)))
        target_power = Decimal(str(target.get("power", 800)))

        return max(current_power - target_power, Decimal("0"))

    def _execute_control_action(self, measure: ProposalMeasure) -> bool:
        """执行控制动作（模拟）"""
        # 实际应发送控制指令到设备
        # 这里模拟 95% 成功率
        import random
        return random.random() < 0.95

    async def get_execution_summary(self, proposal_id: int) -> Dict[str, Any]:
        """获取执行摘要"""
        stmt = select(EnergySavingProposal).where(
            EnergySavingProposal.id == proposal_id
        )
        result = await self.db.execute(stmt)
        proposal = result.scalar_one_or_none()

        if not proposal:
            return None

        total_logs = 0
        success_logs = 0
        total_power_saved = Decimal("0")

        for measure in proposal.measures:
            logs_stmt = select(MeasureExecutionLog).where(
                MeasureExecutionLog.measure_id == measure.id
            )
            logs_result = await self.db.execute(logs_stmt)
            logs = logs_result.scalars().all()

            total_logs += len(logs)
            success_logs += len([l for l in logs if l.result == "success"])
            total_power_saved += sum(l.power_saved or Decimal("0") for l in logs)

        return {
            "proposal_id": proposal_id,
            "total_executions": total_logs,
            "success_count": success_logs,
            "success_rate": success_logs / total_logs if total_logs > 0 else 0,
            "total_power_saved_kwh": float(total_power_saved),
            "estimated_annual_savings": float(total_power_saved * Decimal("0.5") / Decimal("10000"))
        }

    async def trigger_rl_feedback(self, proposal_id: int) -> Dict[str, Any]:
        """
        触发 RL 反馈 (S4e)

        计算当前效果达成率并推送到 RL 模块
        """
        monitoring_service = self._get_monitoring_service()
        if not monitoring_service:
            return {"success": False, "reason": "Monitoring service unavailable"}

        try:
            # 生成效果报告
            report = await monitoring_service.generate_daily_report(proposal_id)

            # 推送到 RL
            result = await monitoring_service.feed_to_rl(report)

            return {
                "success": True,
                "report_id": report.id,
                "achievement_rate": float(report.achievement_rate or 0),
                "rl_feedback": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_monitoring_status(self, proposal_id: int) -> Dict[str, Any]:
        """获取方案监测状态"""
        monitoring_service = self._get_monitoring_service()
        if not monitoring_service:
            return {"active": False, "reason": "Monitoring service unavailable"}

        return await monitoring_service.get_monitoring_status(proposal_id)
