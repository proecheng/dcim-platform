from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from app.models.energy import EnergySavingProposal, ProposalMeasure, MeasureExecutionLog


class ProposalExecutor:
    """方案执行器 - 执行已接受的措施并记录日志"""

    def __init__(self, db: Session):
        self.db = db

    def execute_proposal(self, proposal: EnergySavingProposal) -> Dict[str, Any]:
        """
        执行整个方案（所有已选择的措施）

        返回:
        {
            "proposal_id": int,
            "executed_count": int,
            "success_count": int,
            "results": [...]
        }
        """
        results = []
        success_count = 0

        for measure in proposal.measures:
            if not measure.is_selected:
                continue

            result = self.execute_measure(measure)
            results.append(result)
            if result["success"]:
                success_count += 1

        proposal.status = "executing"
        self.db.commit()

        return {
            "proposal_id": proposal.id,
            "executed_count": len(results),
            "success_count": success_count,
            "results": results
        }

    def execute_measure(self, measure: ProposalMeasure) -> Dict[str, Any]:
        """
        执行单个措施

        步骤:
        1. 读取当前设备状态（模拟）
        2. 发送控制指令（模拟）
        3. 验证执行结果
        4. 记录执行日志
        """
        try:
            # 1. 获取执行前状态
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
            self.db.commit()

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
            self.db.commit()

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

    def get_execution_summary(self, proposal_id: int) -> Dict[str, Any]:
        """获取执行摘要"""
        proposal = self.db.query(EnergySavingProposal).filter(
            EnergySavingProposal.id == proposal_id
        ).first()

        if not proposal:
            return None

        total_logs = 0
        success_logs = 0
        total_power_saved = Decimal("0")

        for measure in proposal.measures:
            logs = self.db.query(MeasureExecutionLog).filter(
                MeasureExecutionLog.measure_id == measure.id
            ).all()

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
