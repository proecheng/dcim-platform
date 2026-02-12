"""
ML 增强的追溯公式计算器
在 TracedFormulaCalculator 基础上增加深度学习预测能力

专利 S2 实现:
- S2-TF: 使用 Transformer 识别可转移负荷
- S2-GNN: 使用 GNN 分析措施冲突和收益耦合
"""
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal
from sqlalchemy.orm import Session

from .traced_formula_calculator import TracedFormulaCalculator, TracedValue
from .ml_service import MLEnergySavingService
from ..models.trace import TraceRecord, MappingType, MLModelType
from ..ml_models.config import MLConfig

logger = logging.getLogger(__name__)


class MLTracedFormulaCalculator(TracedFormulaCalculator):
    """
    ML 增强的追溯公式计算器

    在 TracedFormulaCalculator 基础上集成深度学习模块:
    1. Transformer: 可转移负荷智能识别
    2. GNN: 多措施协同优化
    3. RL: 方案参数自适应调整 (Phase 5)
    """

    def __init__(
        self,
        db: Session,
        proposal_id: int = None,
        measure_id: int = None,
        enable_ml: bool = True
    ):
        super().__init__(db, proposal_id, measure_id)
        self.enable_ml = enable_ml
        self._ml_service: Optional[MLEnergySavingService] = None
        self._ml_available = False

        if enable_ml:
            self._init_ml_service()

    def _init_ml_service(self):
        """初始化 ML 服务"""
        try:
            self._ml_service = MLEnergySavingService(MLConfig())
            self._ml_available = True
            logger.info("ML 服务初始化成功")
        except Exception as e:
            logger.warning(f"ML 服务初始化失败，将使用传统计算: {e}")
            self._ml_available = False

    # ==================== ML 追溯记录创建 ====================

    def _create_ml_trace(
        self,
        param_code: str,
        param_name: str,
        ml_model_type: str,
        value: Decimal,
        value_unit: str = "",
        ml_confidence: float = None,
        ml_input_features: Dict = None,
        ml_output_raw: Dict = None,
        ml_model_version: str = "1.0.0",
        parent_trace_id: str = None
    ) -> TraceRecord:
        """创建 ML 预测追溯记录"""
        trace_id = self._gen_trace_id("ML")
        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=self.proposal_id,
            measure_id=self.measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.ML_PREDICTION.value,
            raw_value=value,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            ml_model_type=ml_model_type,
            ml_model_version=ml_model_version,
            ml_confidence=ml_confidence,
            ml_input_features=ml_input_features,
            ml_output_raw=ml_output_raw,
            parent_trace_id=parent_trace_id,
            depth=0 if parent_trace_id is None else 1,
            calculated_at=datetime.now()
        )
        self.db.add(trace)
        self._traces.append(trace)
        self._trace_map[trace_id] = trace
        return trace

    # ==================== S2-TF: Transformer 可转移负荷识别 ====================

    def ml_analyze_transferable_load(
        self,
        device_id: int,
        power_data: List[float],
        period_types: List[int],
        is_weekday: List[int],
        temperature: List[float]
    ) -> Dict[str, Any]:
        """
        使用 Transformer 分析单个设备的可转移负荷

        参数:
            device_id: 设备ID
            power_data: 功率时序数据
            period_types: 时段类型 (0-4: 深谷/谷/平/峰/尖峰)
            is_weekday: 是否工作日
            temperature: 温度数据

        返回:
            {
                "is_transferable": bool,
                "transferability_prob": float,
                "optimal_target_period": int,
                "capacity_kw": float,
                "confidence": float,
                "_trace": TraceRecord
            }
        """
        if not self._ml_available:
            # 降级到传统计算
            return self._fallback_transferable_analysis(device_id, power_data)

        try:
            result = self._ml_service.analyze_transferable_loads(
                power_data=[power_data],
                period_types=[period_types],
                is_weekday=[is_weekday],
                temperature=[temperature]
            )

            prediction = result['predictions'][0] if result['predictions'] else {}

            is_transferable = prediction.get('is_transferable', False)
            prob = prediction.get('transferability_prob', 0.0)
            capacity = Decimal(str(prediction.get('capacity_kw', 0)))
            optimal_period = prediction.get('optimal_target_period', 1)
            confidence = prediction.get('confidence', 0.0)

            # 创建 ML 追溯记录
            trace = self._create_ml_trace(
                param_code=f"transferability_{device_id}",
                param_name=f"设备{device_id}可转移性",
                ml_model_type=MLModelType.TRANSFORMER.value,
                value=capacity,
                value_unit="kW",
                ml_confidence=confidence,
                ml_input_features={
                    "device_id": device_id,
                    "data_points": len(power_data),
                    "avg_power": sum(power_data) / len(power_data) if power_data else 0
                },
                ml_output_raw={
                    "is_transferable": is_transferable,
                    "transferability_prob": prob,
                    "optimal_target_period": optimal_period,
                    "capacity_kw": float(capacity)
                }
            )

            return {
                "device_id": device_id,
                "is_transferable": is_transferable,
                "transferability_prob": prob,
                "optimal_target_period": optimal_period,
                "capacity_kw": capacity,
                "confidence": confidence,
                "_trace": trace
            }

        except Exception as e:
            logger.error(f"ML 可转移性分析失败: {e}")
            return self._fallback_transferable_analysis(device_id, power_data)

    def _fallback_transferable_analysis(
        self,
        device_id: int,
        power_data: List[float]
    ) -> Dict[str, Any]:
        """传统方法分析可转移负荷 (降级方案)"""
        if not power_data:
            return {
                "device_id": device_id,
                "is_transferable": False,
                "transferability_prob": 0.0,
                "optimal_target_period": 1,
                "capacity_kw": Decimal("0"),
                "confidence": 0.0,
                "_trace": None
            }

        avg_power = sum(power_data) / len(power_data)
        max_power = max(power_data)
        min_power = min(power_data)

        # 简单规则: 波动越大，可转移性越高
        volatility = (max_power - min_power) / max_power if max_power > 0 else 0
        is_transferable = volatility > 0.2
        prob = min(volatility * 2, 0.9)
        capacity = Decimal(str((max_power - min_power) * 0.5))

        # 创建追溯记录 (非 ML)
        trace = self._create_composite_trace(
            param_code=f"transferability_fallback_{device_id}",
            param_name=f"设备{device_id}可转移性(规则)",
            formula="volatility = (max - min) / max",
            formula_display=f"({max_power:.1f} - {min_power:.1f}) / {max_power:.1f} = {volatility:.2f}",
            child_traces=[],
            value=capacity,
            value_unit="kW"
        )

        return {
            "device_id": device_id,
            "is_transferable": is_transferable,
            "transferability_prob": prob,
            "optimal_target_period": 1,
            "capacity_kw": capacity,
            "confidence": 0.5,  # 规则方法置信度固定为 0.5
            "_trace": trace
        }

    # ==================== S2-GNN: GNN 措施冲突分析 ====================

    def ml_analyze_measure_conflicts(
        self,
        measures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        使用 GNN 分析措施间的冲突和收益耦合

        参数:
            measures: 措施列表，每个措施包含:
                - measure_id: 措施ID
                - measure_type: 措施类型
                - device_ids: 涉及设备ID列表
                - time_periods: 执行时段列表
                - expected_benefit: 预期收益

        返回:
            {
                "conflict_matrix": List[List[float]],  # 冲突概率矩阵
                "coupling_coefficients": List[List[float]],  # 耦合系数矩阵
                "recommended_combination": List[int],  # 推荐措施组合
                "adjusted_total_benefit": Decimal,  # 调整后总收益
                "_traces": Dict[str, TraceRecord]
            }
        """
        if not self._ml_available or not measures:
            return self._fallback_conflict_analysis(measures)

        try:
            result = self._ml_service.analyze_measure_conflicts(measures)

            conflict_matrix = result.get('conflict_matrix', [])
            coupling_coefficients = result.get('coupling_coefficients', [])
            recommended = result.get('recommended_combination', list(range(len(measures))))

            # 计算调整后总收益
            total_benefit = Decimal("0")
            for i, m in enumerate(measures):
                if i in recommended:
                    benefit = Decimal(str(m.get('expected_benefit', 0)))
                    # 应用耦合系数
                    for j in recommended:
                        if j > i and coupling_coefficients:
                            alpha = coupling_coefficients[i][j] if i < len(coupling_coefficients) and j < len(coupling_coefficients[i]) else 0
                            if alpha > 0:
                                overlap = min(benefit, Decimal(str(measures[j].get('expected_benefit', 0))))
                                benefit -= Decimal(str(alpha)) * overlap
                    total_benefit += benefit

            # 创建追溯记录
            traces = {}
            trace = self._create_ml_trace(
                param_code="conflict_analysis",
                param_name="措施冲突分析",
                ml_model_type=MLModelType.GNN.value,
                value=total_benefit,
                value_unit="万元",
                ml_confidence=result.get('confidence', 0.8),
                ml_input_features={
                    "measure_count": len(measures),
                    "measure_types": [m.get('measure_type') for m in measures]
                },
                ml_output_raw={
                    "conflict_matrix_shape": [len(conflict_matrix), len(conflict_matrix[0]) if conflict_matrix else 0],
                    "recommended_count": len(recommended)
                }
            )
            traces["conflict_analysis"] = trace

            return {
                "conflict_matrix": conflict_matrix,
                "coupling_coefficients": coupling_coefficients,
                "recommended_combination": recommended,
                "adjusted_total_benefit": total_benefit,
                "_traces": traces
            }

        except Exception as e:
            logger.error(f"GNN 冲突分析失败: {e}")
            return self._fallback_conflict_analysis(measures)

    def _fallback_conflict_analysis(
        self,
        measures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """传统方法分析措施冲突 (降级方案)"""
        n = len(measures)

        # 简单规则: 相同设备或时段的措施有冲突
        conflict_matrix = [[0.0] * n for _ in range(n)]
        coupling_coefficients = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                devices_i = set(measures[i].get('device_ids', []))
                devices_j = set(measures[j].get('device_ids', []))
                periods_i = set(measures[i].get('time_periods', []))
                periods_j = set(measures[j].get('time_periods', []))

                # 设备重叠检测
                device_overlap = len(devices_i & devices_j) / max(len(devices_i | devices_j), 1)
                period_overlap = len(periods_i & periods_j) / max(len(periods_i | periods_j), 1)

                conflict_prob = device_overlap * 0.6 + period_overlap * 0.4
                conflict_matrix[i][j] = conflict_prob
                conflict_matrix[j][i] = conflict_prob

                # 收益耦合系数
                if device_overlap > 0 or period_overlap > 0:
                    coupling_coefficients[i][j] = min(device_overlap + period_overlap, 0.5)
                    coupling_coefficients[j][i] = coupling_coefficients[i][j]

        # 推荐所有非高冲突措施
        recommended = list(range(n))
        for i in range(n):
            for j in range(i + 1, n):
                if conflict_matrix[i][j] > 0.7:
                    # 保留收益更高的
                    if measures[i].get('expected_benefit', 0) < measures[j].get('expected_benefit', 0):
                        if i in recommended:
                            recommended.remove(i)
                    else:
                        if j in recommended:
                            recommended.remove(j)

        # 计算调整后总收益
        total_benefit = sum(
            Decimal(str(measures[i].get('expected_benefit', 0)))
            for i in recommended
        )

        return {
            "conflict_matrix": conflict_matrix,
            "coupling_coefficients": coupling_coefficients,
            "recommended_combination": recommended,
            "adjusted_total_benefit": total_benefit,
            "_traces": {}
        }

    # ==================== ML 增强的收益计算 ====================

    def traced_ml_peak_shift_benefit(
        self,
        device_id: int,
        power_data: List[float],
        period_types: List[int],
        is_weekday: List[int],
        temperature: List[float],
        sharp_price: Decimal,
        valley_price: Decimal,
        working_days: int = 300
    ) -> Dict[str, Any]:
        """
        使用 ML 增强的峰谷转移收益计算

        结合 Transformer 预测的可转移性来调整收益估算
        """
        # 1. 使用 ML 分析可转移性
        ml_result = self.ml_analyze_transferable_load(
            device_id, power_data, period_types, is_weekday, temperature
        )

        # 2. 获取 ML 预测值
        transferability_prob = Decimal(str(ml_result.get('transferability_prob', 0.5)))
        capacity_kw = ml_result.get('capacity_kw', Decimal("0"))
        optimal_period = ml_result.get('optimal_target_period', 1)
        confidence = ml_result.get('confidence', 0.5)

        # 3. 假设每日转移 2 小时
        shift_hours = Decimal("2")

        # 4. 计算 ML 调整后的收益 (专利公式)
        # 年节省金额 = Σ(p_transferable × P_transfer × Δt) × Δprice × N_days
        price_diff = sharp_price - valley_price
        daily_benefit = transferability_prob * capacity_kw * shift_hours * price_diff
        annual_benefit = (daily_benefit * working_days / Decimal("10000")).quantize(Decimal("0.01"))

        # 5. 创建复合追溯记录
        child_traces = [ml_result.get('_trace')] if ml_result.get('_trace') else []

        t_prob = self._create_ml_trace(
            param_code=f"ml_transferability_prob_{device_id}",
            param_name="可转移性概率",
            ml_model_type=MLModelType.TRANSFORMER.value,
            value=transferability_prob,
            value_unit="",
            ml_confidence=confidence
        )
        child_traces.append(t_prob)

        t_benefit = self._create_composite_trace(
            param_code=f"ml_peak_shift_benefit_{device_id}",
            param_name="ML增强峰谷套利收益",
            formula="p_transferable × capacity × hours × price_diff × days / 10000",
            formula_display=f"{transferability_prob:.2f} × {capacity_kw} × {shift_hours} × {price_diff} × {working_days} / 10000 = {annual_benefit}",
            child_traces=child_traces,
            value=annual_benefit,
            value_unit="万元/年"
        )

        return {
            "device_id": device_id,
            "transferability_prob": float(transferability_prob),
            "capacity_kw": float(capacity_kw),
            "optimal_target_period": optimal_period,
            "annual_benefit": annual_benefit,
            "confidence": confidence,
            "ml_enhanced": self._ml_available,
            "_traces": {
                "可转移性概率": t_prob,
                "年收益": t_benefit
            }
        }

    # ==================== 模块状态 ====================

    def get_ml_status(self) -> Dict[str, Any]:
        """获取 ML 模块状态"""
        return {
            "ml_enabled": self.enable_ml,
            "ml_available": self._ml_available,
            "modules": {
                "transformer": self._ml_available,
                "gnn": self._ml_available,
                "rl": self._ml_available
            }
        }
