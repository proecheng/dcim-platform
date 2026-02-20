"""
ML 增强的模板生成器
在 TemplateGenerator 基础上集成深度学习能力

专利 S2 实现:
- 使用 Transformer 识别可转移负荷，增强 A1 峰谷套利方案
- 使用 GNN 分析措施冲突，优化多措施组合
- 将 ML 分析结果写入追溯链
"""

import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from .template_generator import TemplateGenerator
from .ml_traced_calculator import MLTracedFormulaCalculator
from .ml_service import MLEnergySavingService
from ..models.energy import EnergySavingProposal
from ..ml_models.config import MLConfig

logger = logging.getLogger(__name__)


class MLTemplateGenerator(TemplateGenerator):
    """
    ML 增强的模板生成器

    在传统模板生成基础上增加深度学习能力:
    1. A1 峰谷套利: 使用 Transformer 识别真正可转移的负荷
    2. 所有方案: 使用 GNN 优化措施组合，避免冲突和重复计算收益
    3. 自适应优化: 使用 RL 根据历史效果调整方案参数
    """

    def __init__(self, db: Session, enable_trace: bool = True, enable_ml: bool = True):
        super().__init__(db, enable_trace)
        self.enable_ml = enable_ml
        self._ml_service: Optional[MLEnergySavingService] = None
        self._ml_calculator: Optional[MLTracedFormulaCalculator] = None
        self._ml_available = False

        if enable_ml:
            self._init_ml_modules()

    def _init_ml_modules(self):
        """初始化 ML 模块"""
        try:
            self._ml_service = MLEnergySavingService(MLConfig())
            self._ml_available = True
            logger.info("ML 模块初始化成功")
        except Exception as e:
            logger.warning(f"ML 模块初始化失败，将使用传统方法: {e}")
            self._ml_available = False

    def _get_ml_traced_calculator(self, proposal_id: int = None, measure_id: int = None) -> MLTracedFormulaCalculator:
        """获取 ML 增强的追溯计算器"""
        if self._ml_calculator is None or self._ml_calculator.proposal_id != proposal_id:
            self._ml_calculator = MLTracedFormulaCalculator(
                self.db, proposal_id=proposal_id, measure_id=measure_id, enable_ml=self.enable_ml
            )
        else:
            self._ml_calculator.measure_id = measure_id
        return self._ml_calculator

    # ==================== 主入口 ====================

    def generate_ml_enhanced_proposal(
        self, template_id: str, analysis_days: int = 30, device_power_data: Dict[int, Dict[str, List]] = None
    ) -> EnergySavingProposal:
        """
        生成 ML 增强的节能方案

        参数:
            template_id: 模板ID (A1/A2/A3/A4/A5/B1)
            analysis_days: 分析天数
            device_power_data: 设备功率数据 (用于 ML 分析)
                {device_id: {"power": [], "period_types": [], "is_weekday": [], "temperature": []}}

        返回:
            包含 ML 增强分析的 EnergySavingProposal
        """
        # 1. 生成基础方案
        proposal = self.generate_proposal(template_id, analysis_days)

        if not self._ml_available or not proposal.measures:
            return proposal

        # 2. 对 A1 方案使用 Transformer 增强
        if template_id == "A1" and device_power_data:
            proposal = self._enhance_with_transformer(proposal, device_power_data)

        # 3. 使用 GNN 优化措施组合
        proposal = self._optimize_with_gnn(proposal)

        # 4. 使用 RL 调整方案参数 (可选)
        # proposal = self._adjust_with_rl(proposal)

        # 5. 更新追溯汇总
        if self.enable_trace and self._ml_calculator:
            proposal.trace_summary = self._ml_calculator.get_trace_summary()
            self.db.flush()

        return proposal

    # ==================== Transformer 增强 (A1 峰谷套利) ====================

    def _enhance_with_transformer(
        self, proposal: EnergySavingProposal, device_power_data: Dict[int, Dict[str, List]]
    ) -> EnergySavingProposal:
        """
        使用 Transformer 增强 A1 峰谷套利方案

        1. 分析每个设备的可转移性
        2. 根据 ML 预测调整措施收益
        3. 记录 ML 追溯信息
        """
        if not self._ml_available:
            return proposal

        try:
            ml_calc = self._get_ml_traced_calculator(proposal_id=proposal.id)
            ml_analysis_results = []

            # 分析每个设备的可转移负荷
            for device_id, data in device_power_data.items():
                result = ml_calc.ml_analyze_transferable_load(
                    device_id=device_id,
                    power_data=data.get("power", []),
                    period_types=data.get("period_types", []),
                    is_weekday=data.get("is_weekday", []),
                    temperature=data.get("temperature", []),
                )
                ml_analysis_results.append(result)

            # 汇总可转移负荷
            total_transferable = sum(
                r.get("capacity_kw", Decimal("0")) for r in ml_analysis_results if r.get("is_transferable", False)
            )
            avg_confidence = (
                sum(r.get("confidence", 0) for r in ml_analysis_results) / len(ml_analysis_results)
                if ml_analysis_results
                else 0
            )

            # 更新方案的 ML 分析信息
            ml_summary = {
                "transformer_analysis": {
                    "devices_analyzed": len(ml_analysis_results),
                    "transferable_devices": sum(1 for r in ml_analysis_results if r.get("is_transferable")),
                    "total_transferable_kw": float(total_transferable),
                    "avg_confidence": avg_confidence,
                }
            }

            # 合并到追溯汇总
            if proposal.trace_summary:
                proposal.trace_summary.update(ml_summary)
            else:
                proposal.trace_summary = ml_summary

            logger.info(f"Transformer 分析完成: {len(ml_analysis_results)} 设备, 可转移 {total_transferable}kW")

        except Exception as e:
            logger.error(f"Transformer 增强失败: {e}")

        return proposal

    # ==================== GNN 优化 (措施冲突分析) ====================

    def _optimize_with_gnn(self, proposal: EnergySavingProposal) -> EnergySavingProposal:
        """
        使用 GNN 优化措施组合

        1. 分析措施间的冲突和收益耦合
        2. 调整总收益计算
        3. 标记高冲突措施
        """
        if not self._ml_available or not proposal.measures:
            return proposal

        try:
            ml_calc = self._get_ml_traced_calculator(proposal_id=proposal.id)

            # 构建措施列表
            measures_for_gnn = []
            for m in proposal.measures:
                measures_for_gnn.append(
                    {
                        "measure_id": m.id,
                        "measure_type": m.measure_code.split("-")[0] if m.measure_code else "unknown",
                        "device_ids": [],  # 从 current_state 提取
                        "time_periods": [],  # 从 target_state 提取
                        "expected_benefit": float(m.annual_benefit or 0),
                    }
                )

            # GNN 分析
            gnn_result = ml_calc.ml_analyze_measure_conflicts(measures_for_gnn)

            conflict_matrix = gnn_result.get("conflict_matrix", [])
            recommended = gnn_result.get("recommended_combination", [])
            adjusted_benefit = gnn_result.get("adjusted_total_benefit", proposal.total_benefit)

            # 更新方案
            original_benefit = proposal.total_benefit
            proposal.total_benefit = adjusted_benefit

            # 记录 GNN 分析结果
            gnn_summary = {
                "gnn_analysis": {
                    "measures_analyzed": len(proposal.measures),
                    "recommended_count": len(recommended),
                    "original_benefit": float(original_benefit),
                    "adjusted_benefit": float(adjusted_benefit),
                    "benefit_adjustment": float(adjusted_benefit - original_benefit) if original_benefit else 0,
                    "has_conflicts": any(
                        conflict_matrix[i][j] > 0.5
                        for i in range(len(conflict_matrix))
                        for j in range(i + 1, len(conflict_matrix))
                    )
                    if conflict_matrix
                    else False,
                }
            }

            if proposal.trace_summary:
                proposal.trace_summary.update(gnn_summary)
            else:
                proposal.trace_summary = gnn_summary

            logger.info(f"GNN 优化完成: 原收益 {original_benefit} → 调整后 {adjusted_benefit}")

        except Exception as e:
            logger.error(f"GNN 优化失败: {e}")

        return proposal

    # ==================== RL 自适应调整 (Phase 5) ====================

    def _adjust_with_rl(self, proposal: EnergySavingProposal) -> EnergySavingProposal:
        """
        使用 RL 根据历史效果调整方案参数

        (S5 实现，当前为占位符，后续扩展)
        """
        if not self._ml_available:
            return proposal

        try:
            # 获取 RL 建议的参数调整
            # optimization_actions = self._ml_service.get_optimization_actions(current_state)
            # 应用调整...

            rl_summary = {"rl_adjustment": {"enabled": False, "reason": "Phase 5 - 待后续扩展"}}

            if proposal.trace_summary:
                proposal.trace_summary.update(rl_summary)
            else:
                proposal.trace_summary = rl_summary

        except Exception as e:
            logger.error(f"RL 调整失败: {e}")

        return proposal

    # ==================== 状态查询 ====================

    def get_ml_status(self) -> Dict[str, Any]:
        """获取 ML 模块状态"""
        return {
            "ml_enabled": self.enable_ml,
            "ml_available": self._ml_available,
            "modules": {"transformer": self._ml_available, "gnn": self._ml_available, "rl": self._ml_available},
            "calculator_initialized": self._ml_calculator is not None,
        }
