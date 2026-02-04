"""
反馈学习服务模块
分析计划与实际执行偏差，自动调整预测参数，生成优化效果报告
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from enum import Enum


class DeviationType(Enum):
    """偏差类型"""
    UNDER_FORECAST = 'under_forecast'    # 预测偏低
    OVER_FORECAST = 'over_forecast'      # 预测偏高
    TIMING_ERROR = 'timing_error'        # 时间偏差
    EXECUTION_FAILURE = 'execution_failure'  # 执行失败


@dataclass
class DeviationRecord:
    """偏差记录"""
    timestamp: datetime
    planned_value: float
    actual_value: float
    deviation: float              # 绝对偏差
    deviation_percent: float      # 百分比偏差
    deviation_type: DeviationType
    source: str                   # 来源：forecast/schedule/storage


@dataclass
class LearningMetrics:
    """学习指标"""
    period: str                   # 统计周期
    total_records: int
    mae: float                    # 平均绝对误差
    mape: float                   # 平均百分比误差
    rmse: float                   # 均方根误差
    bias: float                   # 偏差（正=预测偏高，负=预测偏低）
    max_deviation: float          # 最大偏差
    accuracy_rate: float          # 准确率（偏差<10%的比例）


@dataclass
class OptimizationReport:
    """优化效果报告"""
    period: str                   # 报告周期
    start_date: str
    end_date: str

    # 成本节省
    planned_saving: float         # 计划节省
    actual_saving: float          # 实际节省
    saving_achievement: float     # 节省达成率

    # 调度执行
    total_schedules: int          # 总调度数
    executed_schedules: int       # 已执行数
    success_rate: float           # 成功率

    # 需量控制
    demand_violations: int        # 超需量次数
    max_demand_reached: float     # 达到的最大需量
    demand_target: float          # 需量目标
    demand_utilization: float     # 需量利用率

    # 预测质量
    forecast_metrics: LearningMetrics

    # 改进建议
    recommendations: List[str]


class FeedbackLearner:
    """反馈学习器"""

    # 预测调整参数边界
    ADJUSTMENT_BOUNDS = {
        'base_load': (0.8, 1.2),      # 基础负荷调整系数
        'peak_factor': (0.8, 1.2),     # 峰值因子调整
        'seasonal_factor': (0.9, 1.1), # 季节因子调整
    }

    def __init__(self):
        # 学习参数
        self.adjustment_params = {
            'base_load_factor': 1.0,
            'peak_factor': 1.0,
            'seasonal_factor': 1.0,
            'workday_factor': 1.0,
            'weekend_factor': 1.0,
        }

        # 历史偏差记录
        self.deviation_history: List[DeviationRecord] = []

        # 学习率
        self.learning_rate = 0.1

    def add_comparison_data(
        self,
        timestamp: datetime,
        planned: float,
        actual: float,
        source: str = 'forecast'
    ) -> DeviationRecord:
        """
        添加计划vs实际对比数据

        Args:
            timestamp: 时间戳
            planned: 计划值
            actual: 实际值
            source: 数据来源

        Returns:
            偏差记录
        """
        deviation = actual - planned
        deviation_percent = (deviation / planned * 100) if planned != 0 else 0

        # 判断偏差类型
        if deviation_percent > 10:
            deviation_type = DeviationType.UNDER_FORECAST
        elif deviation_percent < -10:
            deviation_type = DeviationType.OVER_FORECAST
        else:
            deviation_type = DeviationType.TIMING_ERROR

        record = DeviationRecord(
            timestamp=timestamp,
            planned_value=planned,
            actual_value=actual,
            deviation=deviation,
            deviation_percent=deviation_percent,
            deviation_type=deviation_type,
            source=source
        )

        self.deviation_history.append(record)
        return record

    def calculate_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> LearningMetrics:
        """
        计算学习指标

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            学习指标
        """
        # 筛选时间范围内的记录
        records = self.deviation_history
        if start_date:
            records = [r for r in records if r.timestamp >= start_date]
        if end_date:
            records = [r for r in records if r.timestamp <= end_date]

        if not records:
            return LearningMetrics(
                period="N/A",
                total_records=0,
                mae=0, mape=0, rmse=0, bias=0,
                max_deviation=0, accuracy_rate=0
            )

        # 计算各项指标
        deviations = [r.deviation for r in records]
        planned = [r.planned_value for r in records]
        actual = [r.actual_value for r in records]

        mae = np.mean(np.abs(deviations))
        mape = np.mean([abs(r.deviation_percent) for r in records])
        rmse = np.sqrt(np.mean(np.square(deviations)))
        bias = np.mean(deviations)
        max_deviation = max(np.abs(deviations))

        # 准确率：偏差<10%的比例
        accurate_count = sum(1 for r in records if abs(r.deviation_percent) < 10)
        accuracy_rate = accurate_count / len(records) * 100

        period = "全部"
        if start_date and end_date:
            period = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"

        return LearningMetrics(
            period=period,
            total_records=len(records),
            mae=round(mae, 2),
            mape=round(mape, 2),
            rmse=round(rmse, 2),
            bias=round(bias, 2),
            max_deviation=round(max_deviation, 2),
            accuracy_rate=round(accuracy_rate, 2)
        )

    def learn_and_adjust(self) -> Dict[str, float]:
        """
        基于历史偏差学习并调整参数

        Returns:
            调整后的参数
        """
        if len(self.deviation_history) < 10:
            return self.adjustment_params

        # 分析最近的偏差趋势
        recent_records = self.deviation_history[-50:]  # 最近50条记录

        # 计算平均偏差
        avg_deviation_percent = np.mean([r.deviation_percent for r in recent_records])

        # 根据偏差方向调整参数
        if avg_deviation_percent > 5:  # 预测偏低
            adjustment = 1 + self.learning_rate * (avg_deviation_percent / 100)
            adjustment = min(adjustment, self.ADJUSTMENT_BOUNDS['base_load'][1])
            self.adjustment_params['base_load_factor'] *= adjustment
        elif avg_deviation_percent < -5:  # 预测偏高
            adjustment = 1 + self.learning_rate * (avg_deviation_percent / 100)
            adjustment = max(adjustment, self.ADJUSTMENT_BOUNDS['base_load'][0])
            self.adjustment_params['base_load_factor'] *= adjustment

        # 分析不同时段的偏差
        workday_records = [r for r in recent_records if r.timestamp.weekday() < 5]
        weekend_records = [r for r in recent_records if r.timestamp.weekday() >= 5]

        if workday_records:
            workday_bias = np.mean([r.deviation_percent for r in workday_records])
            if abs(workday_bias) > 5:
                self.adjustment_params['workday_factor'] *= (1 + self.learning_rate * workday_bias / 100)

        if weekend_records:
            weekend_bias = np.mean([r.deviation_percent for r in weekend_records])
            if abs(weekend_bias) > 5:
                self.adjustment_params['weekend_factor'] *= (1 + self.learning_rate * weekend_bias / 100)

        # 限制参数范围
        for key in self.adjustment_params:
            self.adjustment_params[key] = max(0.7, min(1.3, self.adjustment_params[key]))

        return self.adjustment_params

    def generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
        execution_data: Optional[Dict] = None
    ) -> OptimizationReport:
        """
        生成优化效果报告

        Args:
            start_date: 开始日期
            end_date: 结束日期
            execution_data: 执行数据（可选）

        Returns:
            优化效果报告
        """
        # 计算预测指标
        metrics = self.calculate_metrics(start_date, end_date)

        # 模拟执行数据（如果没有提供）
        if execution_data is None:
            execution_data = self._generate_mock_execution_data(start_date, end_date)

        # 生成建议
        recommendations = self._generate_recommendations(metrics, execution_data)

        return OptimizationReport(
            period=f"{start_date.strftime('%Y-%m')}",
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            planned_saving=execution_data.get('planned_saving', 0),
            actual_saving=execution_data.get('actual_saving', 0),
            saving_achievement=execution_data.get('saving_achievement', 0),
            total_schedules=execution_data.get('total_schedules', 0),
            executed_schedules=execution_data.get('executed_schedules', 0),
            success_rate=execution_data.get('success_rate', 0),
            demand_violations=execution_data.get('demand_violations', 0),
            max_demand_reached=execution_data.get('max_demand_reached', 0),
            demand_target=execution_data.get('demand_target', 800),
            demand_utilization=execution_data.get('demand_utilization', 0),
            forecast_metrics=metrics,
            recommendations=recommendations
        )

    def _generate_mock_execution_data(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """生成模拟执行数据（仅在 Demo 模式下使用）

        使用确定性算法基于日期生成可预测的模拟数据，避免使用随机数。
        """
        import math
        from ..core.config import get_settings

        settings = get_settings()
        if not settings.simulation_enabled:
            # 非模拟模式返回空数据
            return {
                'planned_saving': 0,
                'actual_saving': 0,
                'saving_achievement': 0,
                'total_schedules': 0,
                'executed_schedules': 0,
                'success_rate': 0,
                'demand_violations': 0,
                'max_demand_reached': 0,
                'demand_target': 800.0,
                'demand_utilization': 0,
                'is_demo_data': False
            }

        days = (end_date - start_date).days
        demand_target = 800.0

        # 使用日期作为种子生成确定性数值
        seed = start_date.toordinal() + end_date.toordinal()

        def deterministic_value(offset: int, min_val: float, max_val: float) -> float:
            """基于种子生成确定性数值"""
            phase = ((seed + offset) * 0.1) % (2 * math.pi)
            normalized = (math.sin(phase) + 1) / 2  # 0-1 范围
            return min_val + (max_val - min_val) * normalized

        planned_saving = round(deterministic_value(1, 8000, 15000) * (days / 30), 2)
        actual_saving = round(deterministic_value(2, 6000, 12000) * (days / 30), 2)
        total_schedules = int(days * deterministic_value(3, 3, 8))
        executed_schedules = int(days * deterministic_value(4, 2, 7))

        return {
            'planned_saving': planned_saving,
            'actual_saving': actual_saving,
            'saving_achievement': round(deterministic_value(5, 75, 95), 1),
            'total_schedules': total_schedules,
            'executed_schedules': min(executed_schedules, total_schedules),
            'success_rate': round(deterministic_value(6, 85, 98), 1),
            'demand_violations': int(deterministic_value(7, 0, 3)),
            'max_demand_reached': round(demand_target * deterministic_value(8, 0.88, 1.02), 1),
            'demand_target': demand_target,
            'demand_utilization': round(deterministic_value(9, 85, 98), 1),
            'is_demo_data': True
        }

    def _generate_recommendations(
        self,
        metrics: LearningMetrics,
        execution_data: Dict
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 预测准确性建议
        if metrics.mape > 15:
            recommendations.append(
                f"预测准确率较低(MAPE={metrics.mape}%)，建议增加历史数据训练样本或调整预测模型参数"
            )

        if metrics.bias > 20:
            recommendations.append(
                f"预测存在系统性偏低(偏差={metrics.bias}kW)，建议上调基础负荷预测系数"
            )
        elif metrics.bias < -20:
            recommendations.append(
                f"预测存在系统性偏高(偏差={metrics.bias}kW)，建议下调基础负荷预测系数"
            )

        # 执行效率建议
        if execution_data.get('success_rate', 100) < 90:
            recommendations.append(
                f"调度执行成功率较低({execution_data['success_rate']}%)，"
                "建议检查设备通讯状态或优化调度时间安排"
            )

        # 需量控制建议
        violations = execution_data.get('demand_violations', 0)
        if violations > 0:
            recommendations.append(
                f"本期发生{violations}次需量超标，建议增加削减型设备或提高储能放电功率"
            )

        utilization = execution_data.get('demand_utilization', 0)
        if utilization < 80:
            recommendations.append(
                f"需量利用率较低({utilization}%)，可考虑降低申报需量以节省基本电费"
            )
        elif utilization > 95:
            recommendations.append(
                f"需量利用率较高({utilization}%)，超标风险大，建议增加需量控制裕度"
            )

        # 节省达成建议
        achievement = execution_data.get('saving_achievement', 0)
        if achievement < 80:
            recommendations.append(
                f"节省达成率较低({achievement}%)，"
                "建议分析未达成原因，可能是设备可调度性受限或预测偏差导致"
            )

        if not recommendations:
            recommendations.append("本期优化效果良好，建议继续保持当前策略")

        return recommendations


# 全局学习器实例
_learner_instance: Optional[FeedbackLearner] = None


def get_feedback_learner() -> FeedbackLearner:
    """获取反馈学习器实例"""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = FeedbackLearner()
    return _learner_instance


def generate_sample_history(days: int = 30) -> List[DeviationRecord]:
    """
    生成样本历史数据（仅用于 Demo 演示）

    使用确定性算法生成可预测的样本数据。
    仅在 SIMULATION_ENABLED=True 时生成数据。

    Args:
        days: 天数

    Returns:
        偏差记录列表
    """
    import math
    from ..core.config import get_settings

    settings = get_settings()
    if not settings.simulation_enabled:
        return []  # 非模拟模式返回空列表

    learner = get_feedback_learner()
    records = []

    base_date = datetime.now() - timedelta(days=days)

    def deterministic_value(seed: int, base: float, variation: float) -> float:
        """基于种子生成确定性波动值"""
        phase = (seed * 0.1) % (2 * math.pi)
        normalized = math.sin(phase)  # -1 到 1
        return base + variation * normalized

    for day in range(days):
        current_date = base_date + timedelta(days=day)

        # 每天生成96个点（15分钟间隔）
        for slot in range(96):
            timestamp = current_date + timedelta(minutes=slot * 15)

            # 使用时间戳作为种子
            seed = day * 96 + slot

            # 模拟计划值和实际值
            hour = timestamp.hour
            if 8 <= hour <= 22:
                planned = deterministic_value(seed, 600, 50)
            else:
                planned = deterministic_value(seed, 300, 30)

            # 实际值有一定偏差（使用正弦波模拟高斯分布的波动）
            bias_seed = seed + 10000
            bias = deterministic_value(bias_seed, 0, planned * 0.08)
            actual = planned + bias

            record = learner.add_comparison_data(
                timestamp=timestamp,
                planned=round(planned, 1),
                actual=round(actual, 1),
                source='forecast'
            )
            records.append(record)

    return records
