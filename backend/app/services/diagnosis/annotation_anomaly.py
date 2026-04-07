"""
标注偏差检测服务 - Story 24.8
"""

import logging
from typing import List, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import DiagnosisAnnotation
from app.models.user import User

logger = logging.getLogger(__name__)


class AnnotationAnomalyDetector:
    """标注偏差检测器"""

    # 样本量阈值
    MIN_SAMPLE_SIZE = 30
    ADAPTIVE_THRESHOLD_SIZE = 100

    # 绝对阈值（样本量 < 100 时使用）
    ABSOLUTE_THRESHOLD = 0.3  # 30%

    @staticmethod
    async def detect_anomalies(db: AsyncSession) -> List[Dict]:
        """
        检测标注偏差

        算法：
        - 样本量 < 30: 不检测
        - 30 <= 样本量 < 100: 使用绝对阈值（标注率 > 30%）
        - 样本量 >= 100: 使用 P95 百分位数

        Returns:
            List[Dict]: 异常用户列表
        """
        # 查询总标注数
        total_stmt = select(func.count(DiagnosisAnnotation.id))
        total_result = await db.execute(total_stmt)
        total_annotations = total_result.scalar() or 0

        if total_annotations < AnnotationAnomalyDetector.MIN_SAMPLE_SIZE:
            logger.info(
                f"Sample size {total_annotations} < {AnnotationAnomalyDetector.MIN_SAMPLE_SIZE}, skip detection"
            )
            return []

        # 查询每个用户的标注数和标注率
        user_stats_stmt = (
            select(
                DiagnosisAnnotation.annotator_id,
                User.username,
                func.count(DiagnosisAnnotation.id).label("annotation_count"),
            )
            .join(User, DiagnosisAnnotation.annotator_id == User.id, isouter=True)
            .group_by(DiagnosisAnnotation.annotator_id, User.username)
        )

        user_stats_result = await db.execute(user_stats_stmt)
        user_stats = user_stats_result.all()

        if not user_stats:
            return []

        # 计算每个用户的标注率
        user_rates = [
            {
                "user_id": row.annotator_id,
                "username": row.username or "Unknown",
                "annotation_count": row.annotation_count,
                "annotation_rate": row.annotation_count / total_annotations,
            }
            for row in user_stats
        ]

        # 根据样本量选择检测算法
        if total_annotations < AnnotationAnomalyDetector.ADAPTIVE_THRESHOLD_SIZE:
            # 使用绝对阈值
            threshold = AnnotationAnomalyDetector.ABSOLUTE_THRESHOLD
            anomalies = [
                {
                    **user,
                    "threshold": threshold,
                    "deviation_factor": (user["annotation_rate"] - threshold) / threshold if threshold > 0 else 0,
                }
                for user in user_rates
                if user["annotation_rate"] > threshold
            ]
            logger.info(f"Using absolute threshold {threshold}, found {len(anomalies)} anomalies")
        else:
            # 使用 P95 百分位数
            rates = sorted([u["annotation_rate"] for u in user_rates])
            p95_index = int(len(rates) * 0.95)
            threshold = rates[p95_index] if p95_index < len(rates) else rates[-1]

            anomalies = [
                {
                    **user,
                    "threshold": threshold,
                    "deviation_factor": (user["annotation_rate"] - threshold) / threshold if threshold > 0 else 0,
                }
                for user in user_rates
                if user["annotation_rate"] > threshold
            ]
            logger.info(f"Using P95 threshold {threshold:.4f}, found {len(anomalies)} anomalies")

        return anomalies
