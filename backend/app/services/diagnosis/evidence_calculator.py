# backend/app/services/diagnosis/evidence_calculator.py
"""
Story 25.2: 电气参数证据概率计算模块
使用 Sigmoid 连续映射函数计算电气参数的证据概率
"""

import math
import logging
from prometheus_client import Histogram, Counter, REGISTRY

logger = logging.getLogger(__name__)

# Prometheus 监控指标（条件注册，避免测试时重复）
try:
    electrical_param_evidence_duration = Histogram(
        "electrical_param_evidence_duration_seconds", "Time spent calculating electrical parameter evidence"
    )
except ValueError:
    electrical_param_evidence_duration = REGISTRY._names_to_collectors["electrical_param_evidence_duration_seconds"]

try:
    electrical_param_evidence_total = Counter(
        "electrical_param_evidence_total", "Total electrical parameter evidence calculations", ["point_type"]
    )
except ValueError:
    electrical_param_evidence_total = REGISTRY._names_to_collectors["electrical_param_evidence_total"]

try:
    electrical_param_evidence_errors = Counter(
        "electrical_param_evidence_errors_total", "Total electrical parameter evidence calculation errors"
    )
except ValueError:
    electrical_param_evidence_errors = REGISTRY._names_to_collectors["electrical_param_evidence_errors_total"]


def calc_evidence_probability(
    value: float, threshold: float, threshold_type: str, sigmoid_k: float = 2.0, prior: float = 0.5
) -> float:
    """
    计算电气参数的证据概率（Sigmoid 连续映射）

    Args:
        value: 点位实际值
        threshold: 阈值
        threshold_type: 阈值类型 ('ABOVE' 或 'BELOW')
        sigmoid_k: Sigmoid 斜率参数（默认 2.0）
        prior: 先验概率（默认 0.5）

    Returns:
        证据概率 [0, 1]

    公式:
        - ABOVE: P = 1 / (1 + exp(-k * (value - threshold) / threshold))
        - BELOW: P = 1 / (1 + exp(-k * (threshold - value) / threshold))
    """
    with electrical_param_evidence_duration.time():
        try:
            # 边界情况处理
            if not math.isfinite(value) or value < 0:
                logger.error(f"无效的点位值: {value}，返回先验概率")
                electrical_param_evidence_errors.inc()
                return prior

            if threshold <= 0:
                logger.warning(f"阈值为 0 或负数: {threshold}，返回先验概率")
                return prior

            if threshold_type not in ("ABOVE", "BELOW"):
                logger.warning(f"未知的阈值类型: {threshold_type}，返回先验概率")
                return prior

            # 计算偏离度（归一化）
            if threshold_type == "ABOVE":
                deviation = (value - threshold) / threshold
            else:  # BELOW
                deviation = (threshold - value) / threshold

            # Sigmoid 映射
            try:
                exponent = -sigmoid_k * deviation
                # 防止溢出
                if exponent > 100:
                    probability = 0.0
                elif exponent < -100:
                    probability = 1.0
                else:
                    probability = 1.0 / (1.0 + math.exp(exponent))
            except OverflowError:
                logger.warning(f"Sigmoid 计算溢出: deviation={deviation}, k={sigmoid_k}")
                probability = 1.0 if deviation > 0 else 0.0

            # 限制在 [0, 1] 范围
            probability = max(0.0, min(1.0, probability))

            return probability

        except Exception as e:
            logger.error(f"计算证据概率失败: {e}")
            electrical_param_evidence_errors.inc()
            return prior
