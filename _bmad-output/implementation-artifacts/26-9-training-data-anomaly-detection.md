# Story 26.9: 训练数据异常检测（对抗样本防护）

Status: done

## Story

As a 管理员,
I want 系统自动检测闭环学习训练数据中的异常和潜在对抗样本,
So that 异常标注数据不会污染故障树概率参数，保障诊断准确率长期稳定。

## 依赖

- Story 26.3（闭环学习自动调参）— done
- Story 26.8（SBOM 管理）— done（scikit-learn 已在 SBOM 标注为"计划引入"）

## Acceptance Criteria

1. Given 闭环学习（Story 26.3）准备执行概率调参
   When 调参任务启动前执行数据质量检查
   Then 使用 scikit-learn 的 IsolationForest 对训练数据执行异常检测
   And scikit-learn 未安装时静默跳过检测，正常执行调参

2. Given 异常检测需要特征向量
   When 从标注数据中提取特征
   Then 构建 6 维特征向量：诊断耗时(ms)、诊断原因数、证据节点数、根因概率、叶节点异常比例、诊断-标注时间差(秒)
   And 不包含标注结果本身（避免循环逻辑）
   And 使用最近 180 天全部标注数据
   And 样本不足 100 条时跳过检测并记录日志

3. Given IsolationForest 异常检测完成
   When 异常率 ≤ 10%
   Then 降低异常样本权重至 0.1（正常样本权重 1.0），异常样本参与调参但影响被抑制

4. Given IsolationForest 异常检测完成
   When 异常率 > 10% 且 ≤ 30%
   Then 移除全部异常样本，仅用正常样本调参
   And 通过 logger.warning() 通知"异常标注比例偏高，建议检查标注质量"

5. Given IsolationForest 异常检测完成
   When 异常率 > 30%
   Then 中止本次调参
   And 通过 logger.critical() 生成告警"训练数据质量严重异常（异常率 {X}%），已中止自动调参"

6. Given 异常检测执行完成
   When 记录检测结果
   Then 存储到 `training_data_audits` 表
   And 字段包含：audit_id, run_date, total_samples, anomaly_count, anomaly_rate, action_taken, anomaly_sample_ids (JSON), contamination

7. Given IsolationForest contamination 参数
   When 管理员需要调整
   Then contamination 默认值 0.05 存储在 `system_configs` 表（config_group='diagnosis', config_key='anomaly_contamination'）
   And 可通过现有系统配置 API 修改

8. Given 管理员查看异常检测历史
   When 调用 `GET /api/v1/diagnosis/training-audit`
   Then 返回历史检测报告列表（分页）
   And 每条包含：运行日期、总样本数、异常数、异常率、执行动作

9. Given 所有新增代码
   When 运行测试
   Then 单元测试全部通过（15+ 个）

## Tasks / Subtasks

- [ ] Task 1: 数据模型 — TrainingDataAudit 表 (AC: #6)
  - [ ] 1.1 在 `backend/app/models/diagnosis.py` 追加 `TrainingDataAudit` 模型
  - [ ] 1.2 创建 Alembic 迁移脚本
  - [ ] 1.3 在 `backend/app/models/__init__.py` 注册导出

- [ ] Task 2: 异常检测服务核心 (AC: #1, #2, #3, #4, #5, #6, #7)
  - [ ] 2.1 新建 `backend/app/services/diagnosis/training_data_audit_service.py`
  - [ ] 2.2 实现特征提取方法 `_extract_features()`
  - [ ] 2.3 实现异常检测方法 `run_anomaly_detection()`
  - [ ] 2.4 实现三层响应策略

- [ ] Task 3: 集成到概率调参流程 (AC: #1)
  - [ ] 3.1 修改 `probability_tuning_service.py` 的 `analyze_all_trees()` 方法，添加前置质量检查

- [ ] Task 4: API 端点 (AC: #8)
  - [ ] 4.1 在 `backend/app/api/v1/diagnosis.py` 追加 `GET /training-audit` 端点
  - [ ] 4.2 在 `backend/app/schemas/diagnosis.py` 追加响应 Schema

- [ ] Task 5: 初始配置数据 (AC: #7)
  - [ ] 5.1 在种子数据或迁移脚本中插入 contamination 默认配置

- [ ] Task 6: 单元测试 (AC: #9)
  - [ ] 6.1 新建 `backend/tests/services/diagnosis/test_training_data_audit_service.py`
  - [ ] 6.2 新建 `backend/tests/api/test_training_audit_api.py`

## Dev Notes

### Task 1: TrainingDataAudit 数据模型

**文件**: `backend/app/models/diagnosis.py`

在文件末尾追加：

```python
class TrainingDataAudit(Base):
    """训练数据异常检测审计表 — Story 26.9"""

    __tablename__ = "training_data_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(DateTime, nullable=False, default=datetime.now, comment="运行日期")
    total_samples = Column(Integer, nullable=False, comment="总样本数")
    anomaly_count = Column(Integer, nullable=False, default=0, comment="异常样本数")
    anomaly_rate = Column(Float, nullable=False, default=0.0, comment="异常率")
    contamination = Column(Float, nullable=False, default=0.05, comment="IsolationForest contamination 参数")
    action_taken = Column(String(50), nullable=False, comment="执行动作: weight_reduced/removed/aborted/skipped")
    anomaly_sample_ids = Column(JSON, nullable=True, comment="异常样本 annotation ID 列表")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
```

**⚠️ 导入约束**：`diagnosis.py` 已有 `Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey` 导入。确认 `JSON` 和 `Float` 已在导入列表中。

**⚠️ 表命名**: 使用复数 `training_data_audits`（项目惯例：`diagnosis_results`, `diagnosis_annotations`, `diagnosis_sessions`）。

**⚠️ `__init__.py` 注册**: 在 `backend/app/models/__init__.py` 的 `from .diagnosis import ...` 行追加 `TrainingDataAudit`，并在 `__all__` 列表追加。

### Task 1.2: Alembic 迁移

```bash
cd backend
alembic revision --autogenerate -m "add_training_data_audit_table"
alembic upgrade head
```

**⚠️ 不要手写迁移脚本**：使用 `--autogenerate`，Alembic 会自动检测新模型。

### Task 2: 异常检测服务

**文件**: `backend/app/services/diagnosis/training_data_audit_service.py`

```python
"""训练数据异常检测服务 — 对抗样本防护。

Story 26.9: 使用 IsolationForest 对闭环学习训练数据执行异常检测，
防止异常标注数据污染故障树概率参数。

Architecture Reference: Section 18.11 安全加固架构（FR34-35 对抗样本检测）
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import select, and_, func
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
MIN_SAMPLES = 100           # 最少样本数
DATA_WINDOW_DAYS = 180      # 数据窗口天数
DEFAULT_CONTAMINATION = 0.05  # 默认异常率预设


class TrainingDataAuditService:
    """训练数据异常检测服务"""

    async def run_anomaly_detection(self) -> dict:
        """执行异常检测，返回检测结果和过滤后的样本信息。

        Returns:
            dict: {
                "status": "completed" | "skipped" | "aborted",
                "total_samples": int,
                "anomaly_count": int,
                "anomaly_rate": float,
                "action_taken": str,
                "normal_annotation_ids": list[int],  # 正常样本 ID
                "anomaly_annotation_ids": list[int],  # 异常样本 ID
                "sample_weights": dict[int, float],   # annotation_id -> weight
            }
        """
        if not _sklearn_available:
            logger.warning("scikit-learn 未安装，跳过训练数据异常检测")
            return {"status": "skipped", "reason": "sklearn_not_installed"}

        async with async_session() as session:
            # 获取 contamination 参数
            contamination = await self._get_contamination(session)

            # 提取特征
            features, annotation_ids = await self._extract_features(session)

            if len(features) < MIN_SAMPLES:
                logger.info(f"标注样本不足（{len(features)}/{MIN_SAMPLES}），跳过异常检测")
                await self._save_audit(
                    session, len(features), 0, 0.0, "skipped", [], contamination
                )
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
            action, sample_weights = self._apply_response_strategy(
                anomaly_rate, normal_ids, anomaly_ids
            )

            # 保存审计记录
            await self._save_audit(
                session, len(features), anomaly_count, anomaly_rate,
                action, anomaly_ids, contamination,
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
        2. 诊断原因数 — len(DiagnosisResult.causes)，causes 是 JSON list of dicts
        3. 证据节点数 — len(DiagnosisResult.evidence)，evidence 是 JSON dict
        4. 根因概率 — DiagnosisResult.confidence or 0.5
        5. 叶节点异常比例 — 从 evidence dict values 中统计 probability>0.5 的比例
        6. 诊断-标注时间差(秒) — annotated_at - session.start_time

        Returns:
            tuple: (features_list, annotation_id_list)
        """
        cutoff = datetime.now() - timedelta(days=DATA_WINDOW_DAYS)

        # JOIN: annotation → session → result
        # 注意: DiagnosisResult.session_id 非唯一（一对多），使用 DISTINCT ON annotation_id
        # 取每个 annotation 对应的第一条 result（按 result.id 升序）
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

        # 去重: 每个 annotation_id 只取第一条（一对多 result 导致重复）
        seen_ann_ids = set()

        features = []
        annotation_ids = []
        for row in rows:
            ann_id, annotated_at, inference_time_ms, start_time, causes, evidence, confidence = row

            # 去重: 跳过已处理的 annotation_id（一对多 JOIN 可能产生重复行）
            if ann_id in seen_ann_ids:
                continue
            seen_ann_ids.add(ann_id)

            # 特征 1: 诊断耗时
            feat_time = inference_time_ms or 0

            # 特征 2: 诊断原因数（causes 是 JSON list of dicts: [{"cause":..., "confidence":...}]）
            feat_cause_count = len(causes) if isinstance(causes, list) else 0

            # 特征 3: 证据节点数（evidence 是 JSON dict: {"node_name": {"status":..., "probability":...}}）
            feat_evidence_count = len(evidence) if isinstance(evidence, dict) else 0

            # 特征 4: 根因概率
            feat_confidence = confidence if confidence is not None else 0.5

            # 特征 5: 叶节点异常比例
            # evidence values 是 EvidenceItem dict: {"status":"abnormal"/"normal", "value":..., "threshold":...}
            # 注意: key 是 node_id (int→str via JSON), value 中有 status 字段
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

            features.append([
                feat_time,
                feat_cause_count,
                feat_evidence_count,
                feat_confidence,
                feat_leaf_anomaly_ratio,
                feat_time_diff,
            ])
            annotation_ids.append(ann_id)

        return features, annotation_ids

    def _apply_response_strategy(
        self, anomaly_rate: float, normal_ids: list, anomaly_ids: list
    ) -> tuple[str, dict]:
        """三层响应策略。

        Returns:
            tuple: (action_taken, sample_weights)
        """
        sample_weights = {}

        if anomaly_rate <= 0.10:
            # 层级 1: 降低异常样本权重
            for nid in normal_ids:
                sample_weights[nid] = 1.0
            for aid in anomaly_ids:
                sample_weights[aid] = 0.1
            action = "weight_reduced"
            logger.info(f"训练数据异常检测: 异常率 {anomaly_rate:.1%}，降低 {len(anomaly_ids)} 个异常样本权重")

        elif anomaly_rate <= 0.30:
            # 层级 2: 移除异常样本
            for nid in normal_ids:
                sample_weights[nid] = 1.0
            # 异常样本不在 weights 中 = 不参与调参
            action = "removed"
            logger.warning(
                f"训练数据异常检测: 异常率 {anomaly_rate:.1%}（>{10}%），"
                f"已移除 {len(anomaly_ids)} 个异常样本。异常标注比例偏高，建议检查标注质量"
            )

        else:
            # 层级 3: 中止调参
            action = "aborted"
            logger.critical(
                f"训练数据质量严重异常（异常率 {anomaly_rate:.1%}），"
                f"已中止自动调参，请人工审查标注数据"
            )

        return action, sample_weights

    async def _get_contamination(self, session: AsyncSession) -> float:
        """从 system_configs 获取 contamination 参数。

        IsolationForest 要求 contamination ∈ (0, 0.5]，超出范围时自动裁剪。
        """
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
        self, session: AsyncSession, total: int, anomaly_count: int,
        anomaly_rate: float, action: str, anomaly_ids: list, contamination: float,
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
            # 总数
            count_result = await session.execute(
                select(func.count()).select_from(TrainingDataAudit)
            )
            total = count_result.scalar() or 0

            # 分页查询
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
```

**⚠️ scikit-learn 条件导入**: 使用 `try/except ImportError` 模式，与项目中 ML 模块条件加载模式一致（参考 `backend/app/api/v1/__init__.py` 的 torch 条件加载）。`_sklearn_available` 标志控制是否执行检测。

**⚠️ 不包含标注结果作为特征**: 特征向量 6 维全部来自诊断过程数据（耗时、告警数、证据数、概率、异常比例、时间差），不包含 `annotation` 字段值（避免循环逻辑）。

**⚠️ NumPy 已安装**: `numpy>=1.24.0` 在 `requirements.txt` 中，无需额外安装。

**⚠️ IsolationForest random_state=42**: 确保可复现性。

### Task 3: 集成到概率调参流程

**修改文件**: `backend/app/services/diagnosis/probability_tuning_service.py`

在 `analyze_all_trees()` 方法开头添加前置质量检查：

```python
async def analyze_all_trees(self) -> dict:
    """分析所有活跃故障树，生成调参建议"""
    # Story 26.9: 前置训练数据质量检查
    audit_result = None
    try:
        from app.services.diagnosis.training_data_audit_service import training_data_audit_service
        audit_result = await training_data_audit_service.run_anomaly_detection()
        if audit_result.get("status") == "aborted":
            logger.critical("训练数据质量检查未通过，中止概率调参")
            result = {
                "analyzed_trees": 0,
                "total_adjustments": 0,
                "pending_approvals": 0,
            }
            result["audit_result"] = audit_result
            return result
    except ImportError:
        logger.info("training_data_audit_service 不可用，跳过数据质量检查")
    except Exception as e:
        logger.error(f"训练数据质量检查失败: {e}", exc_info=True)
        # 检查失败不阻塞调参，但记录错误

    # ... 原有调参逻辑继续 ...
```

**⚠️ 不阻塞原有流程**: 质量检查失败（异常）时记录错误但不中止调参。只有 `status == "aborted"` 时才中止。

**⚠️ ImportError 处理**: scikit-learn 未安装时 `training_data_audit_service` 的 `run_anomaly_detection()` 返回 `{"status": "skipped"}`，不会中止调参。

### Task 4: API 端点

**修改文件**: `backend/app/api/v1/diagnosis.py`

追加端点：

```python
@router.get("/training-audit", summary="查询训练数据异常检测历史")
async def list_training_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
):
    """查询训练数据异常检测历史报告（仅管理员可访问）"""
    try:
        from app.services.diagnosis.training_data_audit_service import training_data_audit_service
        result = await training_data_audit_service.list_audits(page, page_size)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询训练数据审计历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {e}")
```

**⚠️ 仅 admin 角色**：训练数据审计属于高级诊断管理功能。使用 `require_admin`（非 `require_role`），与 diagnosis.py 现有导入一致（`from ..deps import require_admin`）。

**⚠️ 端点位置**: 在 `diagnosis.py` 的 `router` 上追加，不需要新建路由文件。现有 import 已有 `Query`, `Depends`, `HTTPException`, `logger`。

**⚠️ 错误处理**: 使用 `raise HTTPException(status_code=500, detail=...)` 而非 dict 返回，与 diagnosis.py 现有模式一致。

### Task 5: 初始配置数据

在 Alembic 迁移脚本中（Task 1.2 生成的脚本）追加数据插入：

```python
# 在 upgrade() 方法末尾追加
op.execute(
    "INSERT INTO system_configs (config_group, config_key, config_value, value_type, description, is_editable) "
    "VALUES ('diagnosis', 'anomaly_contamination', '0.05', 'number', "
    "'IsolationForest contamination 参数（异常率预设）', 1)"  -- SQLite用1, PostgreSQL改为TRUE
)
```

**⚠️ 如果 Alembic 插入数据不方便**：也可以在 `training_data_audit_service._get_contamination()` 中 fallback 到 `DEFAULT_CONTAMINATION = 0.05`，已实现此逻辑。配置记录可在首次手动创建或通过系统配置页面添加。

### Task 6: 单元测试

#### test_training_data_audit_service.py（约 12 个测试）

```python
class TestTrainingDataAuditService:
    # 1. test_sklearn_not_installed — patch _sklearn_available=False, 返回 skipped
    # 2. test_insufficient_samples — mock 查询返回 50 条数据, 返回 skipped + insufficient_samples
    # 3. test_no_anomalies — mock IsolationForest 全返回 1, anomaly_count==0
    # 4. test_low_anomaly_rate_weight_reduced — 异常率 5%, action=="weight_reduced", 权重 0.1
    # 5. test_medium_anomaly_rate_removed — 异常率 20%, action=="removed", 异常样本不在 weights 中
    # 6. test_high_anomaly_rate_aborted — 异常率 40%, action=="aborted"
    # 7. test_extract_features_dimensions — 验证返回 6 维特征
    # 8. test_get_contamination_from_config — mock system_configs 返回 0.10
    # 9. test_get_contamination_default — config 不存在时返回 0.05
    # 10. test_save_audit_record — 验证 TrainingDataAudit 被创建
    # 11. test_list_audits_pagination — 验证分页返回
    # 12. test_apply_response_strategy_boundary — 测试 10%/30% 边界值

class TestTrainingAuditAPI:
    # 13. test_list_audits_endpoint_success — admin 可查询
    # 14. test_list_audits_requires_admin — operator 被拒绝
    # 15. test_list_audits_service_error — 服务异常返回 500
```

**⚠️ Mock 模式**: 使用 `unittest.mock.patch` mock `IsolationForest` 和数据库查询。不实际运行 scikit-learn（CI 环境可能未安装）。

**⚠️ 测试 _sklearn_available 标志**: 使用 `patch("app.services.diagnosis.training_data_audit_service._sklearn_available", False)` 测试降级行为。

### scikit-learn 安装

**修改文件**: `backend/requirements.txt`

追加：
```
# 异常检测 (训练数据质量检测)
scikit-learn>=1.3.0,<2.0
```

**⚠️ 同时更新 SBOM.md**: 将 scikit-learn 状态从"计划引入（Story 26.9）"改为"已安装"。

### Project Structure Notes

- **新建文件:**
  - `backend/app/services/diagnosis/training_data_audit_service.py` — 异常检测服务
  - `backend/tests/services/diagnosis/test_training_data_audit_service.py` — 服务测试
  - `backend/tests/api/test_training_audit_api.py` — API 测试
  - `backend/alembic/versions/xxx_add_training_data_audit_table.py` — 迁移脚本（autogenerate）

- **修改文件:**
  - `backend/app/models/diagnosis.py` — 追加 TrainingDataAudit 模型
  - `backend/app/models/__init__.py` — 追加模型导出
  - `backend/app/services/diagnosis/probability_tuning_service.py` — 追加前置质量检查
  - `backend/app/api/v1/diagnosis.py` — 追加 training-audit 端点
  - `backend/requirements.txt` — 追加 scikit-learn
  - `SBOM.md` — 更新 scikit-learn 状态

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 26.9]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 18.11 安全加固架构 FR34-35]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 18.10 闭环学习架构]
- [Source: backend/app/services/diagnosis/probability_tuning_service.py — 概率调参服务]
- [Source: backend/app/services/diagnosis/annotation_anomaly.py — 现有异常检测模式]
- [Source: backend/app/models/diagnosis.py — DiagnosisAnnotation, DiagnosisResult, DiagnosisSession]
- [Source: backend/app/models/config.py — SystemConfig 配置模式]
- [Source: 26-8-edge-inference-reservation-and-sbom.md — 前序 Story SBOM 管理]
