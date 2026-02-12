"""
深度学习节能优化服务

整合三个深度学习模块，提供统一的节能方案智能生成接口

模块:
1. 时序Transformer - 可转移负荷识别
2. 图神经网络 - 多措施协同优化
3. 深度强化学习 - 自适应方案优化
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import numpy as np

from ..ml_models.config import MLConfig
from ..ml_models.transformer.predictor import TransferabilityPredictor
from ..ml_models.gnn.predictor import ConflictPredictor
from ..ml_models.rl.agent import AdaptiveOptimizer

logger = logging.getLogger(__name__)


class MLEnergySavingService:
    """
    深度学习节能优化服务

    整合专利中的三个核心模块:
    - S2-TF: 时序Transformer可转移负荷识别
    - S2-GNN: 图神经网络多措施协同
    - S5: 深度强化学习自适应优化
    """

    def __init__(self, config: Optional[MLConfig] = None):
        self.config = config or MLConfig()
        self._initialized = False

        # 延迟初始化模块
        self._transformer: Optional[TransferabilityPredictor] = None
        self._gnn: Optional[ConflictPredictor] = None
        self._rl: Optional[AdaptiveOptimizer] = None

    def _ensure_initialized(self):
        """确保模块已初始化"""
        if self._initialized:
            return

        try:
            logger.info("初始化深度学习模块...")
            self._transformer = TransferabilityPredictor(self.config)
            self._gnn = ConflictPredictor(self.config)
            self._rl = AdaptiveOptimizer(self.config)
            self._initialized = True
            logger.info("深度学习模块初始化完成")
        except Exception as e:
            logger.error(f"深度学习模块初始化失败: {e}")
            raise

    def analyze_transferable_loads(
        self,
        power_data: List[List[float]],
        period_types: List[List[int]],
        is_weekday: List[List[int]],
        temperature: List[List[float]]
    ) -> Dict[str, Any]:
        """
        分析可转移负荷 (S2-TF)

        Args:
            power_data: 功率时序数据列表，每个元素是一个设备的时序
            period_types: 时段类型列表
            is_weekday: 工作日标志列表
            temperature: 温度数据列表

        Returns:
            包含可转移性分析结果的字典
        """
        self._ensure_initialized()

        results = []
        for i in range(len(power_data)):
            result = self._transformer.predict(
                np.array(power_data[i]),
                np.array(period_types[i]),
                np.array(is_weekday[i]),
                np.array(temperature[i])
            )
            result['load_index'] = i
            results.append(result)

        # 统计汇总
        transferable_count = sum(1 for r in results if r.get('is_transferable', False))
        total_capacity = sum(r.get('capacity_kw', 0) for r in results if r.get('is_transferable', False))

        return {
            'predictions': results,
            'summary': {
                'total_loads': len(results),
                'transferable_count': transferable_count,
                'transferable_ratio': transferable_count / len(results) if results else 0,
                'total_transferable_capacity_kw': round(total_capacity, 2)
            },
            'model_info': {
                'model_type': 'TimeSeriesTransformer',
                'is_trained': self._transformer.is_trained
            },
            'analysis_time': datetime.now().isoformat()
        }

    def calculate_peak_valley_saving(
        self,
        predictions: List[Dict[str, Any]],
        price_diff: float,
        shift_hours: float = 2.0,
        working_days: int = 250
    ) -> Dict[str, Any]:
        """
        计算峰谷套利收益 (S2-TF-f)

        Args:
            predictions: analyze_transferable_loads的输出
            price_diff: 峰谷电价差 (元/kWh)
            shift_hours: 每日转移时长 (小时)
            working_days: 年工作日数

        Returns:
            收益计算详情
        """
        self._ensure_initialized()
        return self._transformer.calculate_peak_valley_saving(
            predictions, price_diff, shift_hours, working_days
        )

    def analyze_measure_conflicts(
        self,
        measures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        分析措施间的冲突和耦合关系 (S2-GNN)

        Args:
            measures: 措施列表，每个措施包含:
                - measure_type: 措施类型
                - device_ids: 涉及的设备ID列表
                - execution_hours: 执行时段
                - power_direction: 功率调整方向 (+1/-1/0)
                - expected_benefit: 预期收益

        Returns:
            包含冲突矩阵、耦合系数、推荐组合的字典
        """
        self._ensure_initialized()
        return self._gnn.predict(measures)

    def calculate_adjusted_benefit(
        self,
        measures: List[Dict[str, Any]],
        conflict_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        计算调整后的总收益 (S2-GNN-f)

        公式: 总收益 = Σ R_i - Σ α_ij * min(R_i, R_j) * I_overlap(i,j)

        Args:
            measures: 措施列表
            conflict_result: analyze_measure_conflicts的输出

        Returns:
            调整后的收益详情
        """
        self._ensure_initialized()
        benefits = [m.get('expected_benefit', 0) for m in measures]
        return self._gnn.calculate_adjusted_benefit(
            benefits,
            conflict_result.get('coupling_coefficients', [])
        )

    def get_optimization_actions(
        self,
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取优化动作建议 (S5)

        Args:
            current_state: 当前系统状态

        Returns:
            优化动作建议
        """
        self._ensure_initialized()
        return self._rl.optimize_scheme(current_state)

    def update_rl_agent(
        self,
        actual_saving: float,
        expected_saving: float,
        comfort_violation: float = 0.0,
        safety_violation: float = 0.0,
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        更新强化学习代理 (S5)

        根据实际效果反馈进行在线学习

        Args:
            actual_saving: 实际节能收益
            expected_saving: 预期节能收益
            comfort_violation: 舒适度违反程度
            safety_violation: 安全约束违反

        Returns:
            训练信息
        """
        self._ensure_initialized()
        return self._rl.train_step(
            actual_saving, expected_saving,
            comfort_violation, safety_violation,
            current_state
        )

    def generate_intelligent_scheme(
        self,
        power_data: List[List[float]],
        period_types: List[List[int]],
        is_weekday: List[List[int]],
        temperature: List[List[float]],
        candidate_measures: List[Dict[str, Any]],
        price_diff: float,
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        智能生成节能方案 (完整流程)

        整合三个模块的完整智能方案生成流程

        Returns:
            完整的节能方案，包含可转移负荷分析、措施协同优化、参数调整建议
        """
        self._ensure_initialized()

        # Step 1: 可转移负荷识别
        load_analysis = self.analyze_transferable_loads(
            power_data, period_types, is_weekday, temperature
        )

        # Step 2: 计算峰谷套利潜力
        saving_calculation = self.calculate_peak_valley_saving(
            load_analysis['predictions'], price_diff
        )

        # Step 3: 措施冲突分析
        conflict_analysis = self.analyze_measure_conflicts(candidate_measures)

        # Step 4: 计算调整后收益
        adjusted_benefit = self.calculate_adjusted_benefit(
            candidate_measures, conflict_analysis
        )

        # Step 5: 获取RL优化建议
        optimization_actions = self.get_optimization_actions(current_state)

        # 组装完整方案
        return {
            'scheme_id': f"SCHEME_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'generation_time': datetime.now().isoformat(),

            # 负荷分析结果
            'load_analysis': load_analysis,

            # 峰谷套利计算
            'peak_valley_saving': saving_calculation,

            # 措施协同分析
            'measure_analysis': {
                'conflicts': conflict_analysis,
                'adjusted_benefit': adjusted_benefit,
                'recommended_measures': conflict_analysis.get('recommended_combination', [])
            },

            # RL优化建议
            'optimization_advice': optimization_actions,

            # 数据追溯
            'data_trace': {
                'transformer_model': 'LoadTransferabilityTransformer',
                'gnn_model': 'MeasureConflictGNN',
                'rl_model': 'PPO_ActorCritic',
                'models_trained': {
                    'transformer': self._transformer.is_trained,
                    'gnn': self._gnn.is_trained if hasattr(self._gnn, 'is_trained') else False,
                    'rl': self._rl.is_trained
                }
            }
        }

    def train_models(
        self,
        transformer_epochs: int = 50,
        gnn_epochs: int = 30,
        rl_steps: int = 1000
    ) -> Dict[str, Any]:
        """
        训练所有模型

        使用合成数据进行初始训练

        Returns:
            各模型的训练结果
        """
        self._ensure_initialized()

        results = {}

        # 训练Transformer
        logger.info("开始训练Transformer模型...")
        tf_history = self._transformer.train(epochs=transformer_epochs)
        results['transformer'] = {
            'final_train_loss': tf_history['train_loss'][-1] if tf_history['train_loss'] else None,
            'final_val_loss': tf_history['val_loss'][-1] if tf_history.get('val_loss') else None,
            'epochs': transformer_epochs
        }

        # 训练GNN
        logger.info("开始训练GNN模型...")
        if hasattr(self._gnn, 'train'):
            gnn_history = self._gnn.train(epochs=gnn_epochs)
            results['gnn'] = gnn_history
        else:
            results['gnn'] = {'status': 'skipped', 'reason': 'no train method'}

        # RL不需要预训练，在线学习

        return {
            'training_results': results,
            'training_time': datetime.now().isoformat()
        }

    def get_model_status(self) -> Dict[str, Any]:
        """获取模型状态"""
        if not self._initialized:
            return {'initialized': False}

        return {
            'initialized': True,
            'transformer': {
                'loaded': self._transformer is not None,
                'trained': self._transformer.is_trained if self._transformer else False
            },
            'gnn': {
                'loaded': self._gnn is not None,
                'trained': getattr(self._gnn, 'is_trained', False) if self._gnn else False
            },
            'rl': {
                'loaded': self._rl is not None,
                'trained': self._rl.is_trained if self._rl else False
            },
            'device': self.config.device
        }


# 全局服务实例
_ml_service: Optional[MLEnergySavingService] = None


def get_ml_service() -> MLEnergySavingService:
    """获取全局ML服务实例"""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLEnergySavingService()
    return _ml_service
