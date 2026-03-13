"""训练数据异常检测服务 — 对抗样本防护。

Story 26.9: 使用 IsolationForest 对闭环学习训练数据执行异常检测，
防止异常标注数据污染故障树概率参数。

Architecture Reference: Section 18.11 安全加固架构（FR34-35 对抗样本检测）
"""

import logging
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.diagnosis import (
    DiagnosisResult,
    DiagnosisAnnotation,
    DiagnosisSession,
    TrainingDataAudit,
)
from app.models.config import SystemConfig

logger = logging.getLogger(__name__)

# scikit-learn 条件导入
try:
    from sklearn.ensemble import IsolationForest

    _sklearn_available = True
except ImportError:
    _sklearn_available = False
    logger.info("scikit-learn 未安装，训练数据异常检测功能不可用")

# 常量
MIN_SAMPLES = 100
DATA_WINDOW_DAYS = 180
DEFAULT_CONTAMINATION = 0.05


class TrainingDataAuditService:
    """训练数据异常检测服务"""

    async def run_anomaly_detection(self) -> dict:
        """执行异常检测，返回检测结果和过滤后的样本信息。"""
        if not _sklearn_available:
            logger.warning("scikit-learn 未安装，跳过训练数据异常检测")
            return {"status": "skipped", "reason": "sklearn_not_installed"}

        async with async_session() as session:
            contamination = await self._get_contamination(session)
            features, annotation_ids = await self._extract_features(session)

            if len(features) < MIN_SAMPLES:
                logger.info(f"标注样本不足（{len(features)}/{MIN_SAMPLES}），跳过异常检测")
                await self._save_audit(session, len(features), 0, 0.0, "skipped", [], contamination)
                return {
                    "status": "skipped",
                    "reason": "insufficient_samples",
                    "total_samples": len(features),
                }

            # 运行 IsolationForest
            X = np.array(features)
            clf = IsolationForest(contamination=contamination, random_state=42)
            predictions = clf.fit_predict(X)

            # 分离正常/异常样本
            normal_ids = []
            anomaly_ids = []
            for i, pred in enumerate(predictions):
                if pred == -1:
                    anomaly_ids.append(annotation_ids[i])
                else:
                    normal_ids.append(annotation_ids[i])

            anomaly_count = len(anomaly_ids)
            anomaly_rate = anomaly_count / len(features)

            # 三层响应策略
            action, sample_weights = self._apply_response_strategy(anomaly_rate, normal_ids, anomaly_ids)

            # 保存审计记录
            await self._save_audit(
                session,
                len(features),
                anomaly_count,
                anomaly_rate,
                action,
                anomaly_ids,
                contamination,
            )

            return {
                "status": "aborted" if action == "aborted" else "completed",
                "total_samples": len(features),
                "anomaly_count": anomaly_count,
                "anomaly_rate": round(anomaly_rate, 4),
                "action_taken": action,
                "normal_annotation_ids": normal_ids,
                "anomaly_annotation_ids": anomaly_ids,
                "sample_weights": sample_weights,
            }

    async def _extract_features(self, session: AsyncSession) -> tuple[list, list]:
        """提取 6 维特征向量。

        特征维度：
        1. 诊断耗时(ms) — DiagnosisSession.inference_time_ms
        2. 诊断原因数 — len(DiagnosisResult.causes)
        3. 证据节点数 — len(DiagnosisResult.evidence)
        4. 根因概率 — DiagnosisResult.confidence
        5. 叶节点异常比例 — evidence 中 status 为异常的比例
        6. 诊断-标注时间差(秒) — annotated_at - session.start_time
        """
        cutoff = datetime.now() - timedelta(days=DATA_WINDOW_DAYS)

        query = (
            select(
                DiagnosisAnnotation.id,
                DiagnosisAnnotation.annotated_at,
                DiagnosisSession.inference_time_ms,
                DiagnosisSession.start_time,
                DiagnosisResult.causes,
                DiagnosisResult.evidence,
                DiagnosisResult.confidence,
            )
            .join(DiagnosisSession, DiagnosisAnnotation.session_id == DiagnosisSession.id)
            .join(DiagnosisResult, DiagnosisResult.session_id == DiagnosisSession.id)
            .where(
                DiagnosisAnnotation.annotation.in_(["accurate", "inaccurate"]),
                DiagnosisAnnotation.annotated_at >= cutoff,
            )
            .order_by(DiagnosisAnnotation.id, DiagnosisResult.id)
        )

        result = await session.execute(query)
        rows = result.all()

        # 去重: 每个 annotation_id 只取第一条（一对多 result 导致重复行）
        seen_ann_ids = set()
        features = []
        annotation_ids = []
        for row in rows:
            ann_id, annotated_at, inference_time_ms, start_time, causes, evidence, confidence = row

            if ann_id in seen_ann_ids:
                continue
            seen_ann_ids.add(ann_id)

            # 特征 1: 诊断耗时
            feat_time = inference_time_ms or 0

            # 特征 2: 诊断原因数
            feat_cause_count = len(causes) if isinstance(causes, list) else 0

            # 特征 3: 证据节点数
            feat_evidence_count = len(evidence) if isinstance(evidence, dict) else 0

            # 特征 4: 根因概率
            feat_confidence = confidence if confidence is not None else 0.5

            # 特征 5: 叶节点异常比例
            if isinstance(evidence, dict) and len(evidence) > 0:
                abnormal_count = 0
                for v in evidence.values():
                    if isinstance(v, dict):
                        status = v.get("status", "")
                        if status in ("abnormal", "critical", "warning"):
                            abnormal_count += 1
                feat_leaf_anomaly_ratio = abnormal_count / len(evidence)
            else:
                feat_leaf_anomaly_ratio = 0.0

            # 特征 6: 诊断-标注时间差（秒）
            if annotated_at and start_time:
                feat_time_diff = (annotated_at - start_time).total_seconds()
            else:
                feat_time_diff = 0.0

            features.append(
                [
                    feat_time,
                    feat_cause_count,
                    feat_evidence_count,
                    feat_confidence,
                    feat_leaf_anomaly_ratio,
                    feat_time_diff,
                ]
            )
            annotation_ids.append(ann_id)

        return features, annotation_ids

    def _apply_response_strategy(self, anomaly_rate: float, normal_ids: list, anomaly_ids: list) -> tuple[str, dict]:
        """三层响应策略。"""
        sample_weights = {}

        if anomaly_rate <= 0.10:
            for nid in normal_ids:
                sample_weights[nid] = 1.0
            for aid in anomaly_ids:
                sample_weights[aid] = 0.1
            action = "weight_reduced"
            logger.info(f"训练数据异常检测: 异常率 {anomaly_rate:.1%}，降低 {len(anomaly_ids)} 个异常样本权重")

        elif anomaly_rate <= 0.30:
            for nid in normal_ids:
                sample_weights[nid] = 1.0
            action = "removed"
            logger.warning(
                f"训练数据异常检测: 异常率 {anomaly_rate:.1%}（>10%），"
                f"已移除 {len(anomaly_ids)} 个异常样本。异常标注比例偏高，建议检查标注质量"
            )

        else:
            action = "aborted"
            logger.critical(f"训练数据质量严重异常（异常率 {anomaly_rate:.1%}），已中止自动调参，请人工审查标注数据")

        return action, sample_weights

    async def _get_contamination(self, session: AsyncSession) -> float:
        """从 system_configs 获取 contamination 参数。"""
        result = await session.execute(
            select(SystemConfig.config_value).where(
                SystemConfig.config_group == "diagnosis",
                SystemConfig.config_key == "anomaly_contamination",
            )
        )
        row = result.scalar_one_or_none()
        value = DEFAULT_CONTAMINATION
        if row is not None:
            try:
                value = float(row)
            except (ValueError, TypeError):
                pass
        # IsolationForest 要求 contamination ∈ (0, 0.5]
        return max(0.001, min(0.5, value))

    async def _save_audit(
        self,
        session: AsyncSession,
        total: int,
        anomaly_count: int,
        anomaly_rate: float,
        action: str,
        anomaly_ids: list,
        contamination: float,
    ):
        """保存审计记录到 training_data_audits 表。"""
        audit = TrainingDataAudit(
            run_date=datetime.now(),
            total_samples=total,
            anomaly_count=anomaly_count,
            anomaly_rate=round(anomaly_rate, 4),
            contamination=contamination,
            action_taken=action,
            anomaly_sample_ids=anomaly_ids if anomaly_ids else None,
        )
        session.add(audit)
        await session.commit()

    async def list_audits(self, page: int = 1, page_size: int = 20) -> dict:
        """查询历史检测报告（分页）。"""
        async with async_session() as session:
            count_result = await session.execute(select(func.count()).select_from(TrainingDataAudit))
            total = count_result.scalar() or 0

            query = (
                select(TrainingDataAudit)
                .order_by(TrainingDataAudit.run_date.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            audits = result.scalars().all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "id": a.id,
                        "run_date": a.run_date.isoformat() if a.run_date else None,
                        "total_samples": a.total_samples,
                        "anomaly_count": a.anomaly_count,
                        "anomaly_rate": a.anomaly_rate,
                        "contamination": a.contamination,
                        "action_taken": a.action_taken,
                        "anomaly_sample_ids": a.anomaly_sample_ids,
                    }
                    for a in audits
                ],
            }


# 单例
training_data_audit_service = TrainingDataAuditService()
