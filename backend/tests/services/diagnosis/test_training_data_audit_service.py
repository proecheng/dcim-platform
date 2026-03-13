"""训练数据异常检测服务测试。

Story 26.9 — AC #1~#7, #9
"""
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np

from app.services.diagnosis.training_data_audit_service import (
    TrainingDataAuditService,
    MIN_SAMPLES,
    DEFAULT_CONTAMINATION,
)


def _make_mock_rows(count, anomaly_rate_hint=0.0):
    """生成 mock 查询行数据。"""
    rows = []
    now = datetime.now()
    for i in range(count):
        rows.append((
            i + 1,                        # annotation_id
            now - timedelta(hours=i),     # annotated_at
            100 + i * 10,                 # inference_time_ms
            now - timedelta(hours=i + 1), # start_time
            [{"cause": "test", "confidence": 80}],  # causes (JSON list of dicts)
            {"node_1": {"status": "abnormal", "value": 30}, "node_2": {"status": "normal", "value": 22}},  # evidence
            0.85,                         # confidence
        ))
    return rows


class TestTrainingDataAuditService:
    """训练数据异常检测服务测试"""

    @pytest.mark.asyncio
    async def test_sklearn_not_installed_returns_skipped(self):
        """scikit-learn 未安装时返回 skipped"""
        service = TrainingDataAuditService()
        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", False):
            result = await service.run_anomaly_detection()
        assert result["status"] == "skipped"
        assert result["reason"] == "sklearn_not_installed"

    @pytest.mark.asyncio
    async def test_insufficient_samples_returns_skipped(self):
        """样本不足 100 条时返回 skipped"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()

        # _get_contamination mock
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = "0.05"

        # _extract_features: 只有 50 条
        mock_feature_result = MagicMock()
        mock_feature_result.all.return_value = _make_mock_rows(50)

        # _save_audit mock
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        call_count = 0
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_config_result
            return mock_feature_result

        mock_session.execute = mock_execute

        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", True), \
             patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await service.run_anomaly_detection()

        assert result["status"] == "skipped"
        assert result["reason"] == "insufficient_samples"
        assert result["total_samples"] == 50

    @pytest.mark.asyncio
    async def test_no_anomalies_weight_reduced(self):
        """无异常时: action=weight_reduced, anomaly_count=0"""
        service = TrainingDataAuditService()
        rows = _make_mock_rows(120)

        # Mock IsolationForest 返回全部正常 (1)
        mock_predictions = np.ones(120, dtype=int)

        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", True), \
             patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_session = AsyncMock()

            config_result = MagicMock()
            config_result.scalar_one_or_none.return_value = "0.05"

            feature_result = MagicMock()
            feature_result.all.return_value = rows

            call_count = 0
            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return config_result
                return feature_result

            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("app.services.diagnosis.training_data_audit_service.IsolationForest", create=True) as mock_clf_class:
                mock_clf = MagicMock()
                mock_clf.fit_predict.return_value = mock_predictions
                mock_clf_class.return_value = mock_clf

                result = await service.run_anomaly_detection()

        assert result["status"] == "completed"
        assert result["anomaly_count"] == 0
        assert result["action_taken"] == "weight_reduced"

    @pytest.mark.asyncio
    async def test_low_anomaly_rate_weight_reduced(self):
        """异常率 5%: action=weight_reduced, 异常样本权重 0.1"""
        service = TrainingDataAuditService()
        rows = _make_mock_rows(120)

        # 6/120 = 5% 异常
        predictions = np.ones(120, dtype=int)
        predictions[:6] = -1

        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", True), \
             patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_session = AsyncMock()
            config_result = MagicMock()
            config_result.scalar_one_or_none.return_value = "0.05"
            feature_result = MagicMock()
            feature_result.all.return_value = rows
            call_count = 0
            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return config_result
                return feature_result
            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("app.services.diagnosis.training_data_audit_service.IsolationForest", create=True) as mock_clf_class:
                mock_clf = MagicMock()
                mock_clf.fit_predict.return_value = predictions
                mock_clf_class.return_value = mock_clf
                result = await service.run_anomaly_detection()

        assert result["action_taken"] == "weight_reduced"
        assert result["anomaly_count"] == 6
        # 异常样本权重为 0.1
        for aid in result["anomaly_annotation_ids"]:
            assert result["sample_weights"][aid] == 0.1
        # 正常样本权重为 1.0
        for nid in result["normal_annotation_ids"]:
            assert result["sample_weights"][nid] == 1.0

    @pytest.mark.asyncio
    async def test_medium_anomaly_rate_removed(self):
        """异常率 20%: action=removed, 异常样本不在 weights 中"""
        service = TrainingDataAuditService()
        rows = _make_mock_rows(120)

        # 24/120 = 20% 异常
        predictions = np.ones(120, dtype=int)
        predictions[:24] = -1

        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", True), \
             patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_session = AsyncMock()
            config_result = MagicMock()
            config_result.scalar_one_or_none.return_value = "0.05"
            feature_result = MagicMock()
            feature_result.all.return_value = rows
            call_count = 0
            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return config_result
                return feature_result
            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("app.services.diagnosis.training_data_audit_service.IsolationForest", create=True) as mock_clf_class:
                mock_clf = MagicMock()
                mock_clf.fit_predict.return_value = predictions
                mock_clf_class.return_value = mock_clf
                result = await service.run_anomaly_detection()

        assert result["action_taken"] == "removed"
        assert result["anomaly_count"] == 24
        # 异常样本不在 weights 中
        for aid in result["anomaly_annotation_ids"]:
            assert aid not in result["sample_weights"]

    @pytest.mark.asyncio
    async def test_high_anomaly_rate_aborted(self):
        """异常率 40%: action=aborted, status=aborted"""
        service = TrainingDataAuditService()
        rows = _make_mock_rows(120)

        # 48/120 = 40% 异常
        predictions = np.ones(120, dtype=int)
        predictions[:48] = -1

        with patch("app.services.diagnosis.training_data_audit_service._sklearn_available", True), \
             patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_session = AsyncMock()
            config_result = MagicMock()
            config_result.scalar_one_or_none.return_value = "0.05"
            feature_result = MagicMock()
            feature_result.all.return_value = rows
            call_count = 0
            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return config_result
                return feature_result
            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("app.services.diagnosis.training_data_audit_service.IsolationForest", create=True) as mock_clf_class:
                mock_clf = MagicMock()
                mock_clf.fit_predict.return_value = predictions
                mock_clf_class.return_value = mock_clf
                result = await service.run_anomaly_detection()

        assert result["status"] == "aborted"
        assert result["action_taken"] == "aborted"
        assert result["anomaly_count"] == 48

    @pytest.mark.asyncio
    async def test_extract_features_returns_6_dimensions(self):
        """特征向量应为 6 维"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()

        rows = _make_mock_rows(5)
        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        features, ann_ids = await service._extract_features(mock_session)

        assert len(features) == 5
        assert len(ann_ids) == 5
        for feat in features:
            assert len(feat) == 6

    @pytest.mark.asyncio
    async def test_extract_features_deduplication(self):
        """重复 annotation_id 应被去重"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()

        now = datetime.now()
        # 两行有相同 annotation_id=1（一对多 JOIN 导致）
        rows = [
            (1, now, 100, now - timedelta(hours=1), [{"cause": "a"}], {"n1": {"status": "normal"}}, 0.8),
            (1, now, 100, now - timedelta(hours=1), [{"cause": "b"}], {"n2": {"status": "abnormal"}}, 0.9),
            (2, now, 200, now - timedelta(hours=2), [{"cause": "c"}], {"n3": {"status": "normal"}}, 0.7),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        features, ann_ids = await service._extract_features(mock_session)

        assert len(features) == 2
        assert ann_ids == [1, 2]

    @pytest.mark.asyncio
    async def test_get_contamination_from_config(self):
        """从 system_configs 获取 contamination"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "0.10"
        mock_session.execute = AsyncMock(return_value=mock_result)

        value = await service._get_contamination(mock_session)
        assert value == 0.10

    @pytest.mark.asyncio
    async def test_get_contamination_default(self):
        """config 不存在时返回默认值"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        value = await service._get_contamination(mock_session)
        assert value == DEFAULT_CONTAMINATION

    @pytest.mark.asyncio
    async def test_get_contamination_bounds_enforcement(self):
        """contamination 超出范围时自动裁剪"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()

        # 测试超上界
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "0.99"
        mock_session.execute = AsyncMock(return_value=mock_result)
        value = await service._get_contamination(mock_session)
        assert value == 0.5

        # 测试超下界
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = "0.0"
        mock_session.execute = AsyncMock(return_value=mock_result2)
        value = await service._get_contamination(mock_session)
        assert value == 0.001

    @pytest.mark.asyncio
    async def test_save_audit_record(self):
        """验证审计记录被正确保存"""
        service = TrainingDataAuditService()
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        await service._save_audit(mock_session, 100, 5, 0.05, "weight_reduced", [1, 2, 3, 4, 5], 0.05)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        audit = mock_session.add.call_args[0][0]
        assert audit.total_samples == 100
        assert audit.anomaly_count == 5
        assert audit.action_taken == "weight_reduced"

    @pytest.mark.asyncio
    async def test_list_audits_pagination(self):
        """验证分页查询"""
        service = TrainingDataAuditService()

        mock_audit = MagicMock()
        mock_audit.id = 1
        mock_audit.run_date = datetime(2026, 3, 14)
        mock_audit.total_samples = 200
        mock_audit.anomaly_count = 10
        mock_audit.anomaly_rate = 0.05
        mock_audit.contamination = 0.05
        mock_audit.action_taken = "weight_reduced"
        mock_audit.anomaly_sample_ids = [1, 2]

        with patch("app.services.diagnosis.training_data_audit_service.async_session") as mock_as:
            mock_session = AsyncMock()

            count_result = MagicMock()
            count_result.scalar.return_value = 1

            audit_result = MagicMock()
            audit_result.scalars.return_value.all.return_value = [mock_audit]

            call_count = 0
            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return count_result
                return audit_result

            mock_session.execute = mock_execute
            mock_as.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_as.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.list_audits(page=1, page_size=10)

        assert result["total"] == 1
        assert result["page"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["action_taken"] == "weight_reduced"

    def test_apply_response_strategy_boundary_10_percent(self):
        """边界值: 正好 10% 应为 weight_reduced"""
        service = TrainingDataAuditService()
        action, weights = service._apply_response_strategy(
            0.10, list(range(90)), list(range(90, 100))
        )
        assert action == "weight_reduced"

    def test_apply_response_strategy_boundary_30_percent(self):
        """边界值: 正好 30% 应为 removed"""
        service = TrainingDataAuditService()
        action, weights = service._apply_response_strategy(
            0.30, list(range(70)), list(range(70, 100))
        )
        assert action == "removed"

    def test_apply_response_strategy_above_30_percent(self):
        """超过 30% 应为 aborted"""
        service = TrainingDataAuditService()
        action, weights = service._apply_response_strategy(
            0.31, list(range(69)), list(range(69, 100))
        )
        assert action == "aborted"
