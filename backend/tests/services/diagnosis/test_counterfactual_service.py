"""
反事实分析服务单元测试
Story 26.1: 反事实分析
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.services.diagnosis.counterfactual_service import (
    calculate_evidence_weight,
    _get_evidence_cascade,
    _simulate_confidence_without_evidence,
    analyze_counterfactual,
)


class TestEvidenceWeightCalculation:
    """测试证据权重计算"""

    def test_basic_weight_calculation(self):
        """测试基本权重计算"""
        evidence = {
            "probability": 0.8,
            "sensor_weight": 1.0,
            "path_length": 1
        }
        path_decay_factor = 0.8

        weight = calculate_evidence_weight(evidence, path_decay_factor)

        # weight = 0.8 * 1.0 * (0.8 ** 1) = 0.64
        assert weight == pytest.approx(0.64, rel=1e-6)

    def test_weight_with_path_decay(self):
        """测试路径衰减"""
        evidence = {
            "probability": 0.9,
            "sensor_weight": 1.0,
            "path_length": 3
        }
        path_decay_factor = 0.8

        weight = calculate_evidence_weight(evidence, path_decay_factor)

        # weight = 0.9 * 1.0 * (0.8 ** 3) = 0.9 * 0.512 = 0.4608
        assert weight == pytest.approx(0.4608, rel=1e-6)

    def test_weight_with_sensor_degradation(self):
        """测试传感器权重降级"""
        evidence = {
            "probability": 0.7,
            "sensor_weight": 0.6,  # 校准过期
            "path_length": 1
        }
        path_decay_factor = 0.8

        weight = calculate_evidence_weight(evidence, path_decay_factor)

        # weight = 0.7 * 0.6 * 0.8 = 0.336
        assert weight == pytest.approx(0.336, rel=1e-6)

    def test_weight_with_default_values(self):
        """测试默认值"""
        evidence = {
            "probability": 0.5
            # sensor_weight 和 path_length 使用默认值
        }
        path_decay_factor = 0.8

        weight = calculate_evidence_weight(evidence, path_decay_factor)

        # weight = 0.5 * 1.0 * 0.8 = 0.4
        assert weight == pytest.approx(0.4, rel=1e-6)


class TestEvidenceCascade:
    """测试证据级联删除"""

    def test_single_evidence_no_dependencies(self):
        """测试单个证据无依赖"""
        node_id = 10
        reasoning_path = [
            {"node_id": 1, "dependencies": []},
            {"node_id": 2, "dependencies": []},
        ]

        removed_ids = _get_evidence_cascade(node_id, reasoning_path)

        assert removed_ids == [10]

    def test_evidence_with_dependencies(self):
        """测试证据有依赖"""
        node_id = 10
        reasoning_path = [
            {"node_id": 1, "dependencies": [10]},
            {"node_id": 2, "dependencies": [10, 1]},
            {"node_id": 3, "dependencies": [2]},
        ]

        removed_ids = _get_evidence_cascade(node_id, reasoning_path)

        # 应该包含 10, 1, 2（因为 1 依赖 10，2 依赖 10）
        assert 10 in removed_ids
        assert 1 in removed_ids
        assert 2 in removed_ids

    def test_empty_reasoning_path(self):
        """测试空推理路径"""
        node_id = 10
        reasoning_path = []

        removed_ids = _get_evidence_cascade(node_id, reasoning_path)

        assert removed_ids == [10]


class TestConfidenceSimulation:
    """测试置信度模拟"""

    def test_confidence_drop_with_high_weight(self):
        """测试高权重证据移除导致置信度下降"""
        original_confidence = 0.9
        evidence_weight = 0.8
        removed_evidence_ids = [10]
        reasoning_path = []

        new_confidence = _simulate_confidence_without_evidence(
            original_confidence,
            evidence_weight,
            removed_evidence_ids,
            reasoning_path
        )

        # 置信度应该下降
        assert new_confidence < original_confidence
        # 下降幅度应该与权重成正比
        assert new_confidence >= 0.0

    def test_confidence_drop_with_low_weight(self):
        """测试低权重证据移除导致小幅下降"""
        original_confidence = 0.8
        evidence_weight = 0.2
        removed_evidence_ids = [10]
        reasoning_path = []

        new_confidence = _simulate_confidence_without_evidence(
            original_confidence,
            evidence_weight,
            removed_evidence_ids,
            reasoning_path
        )

        # 置信度应该下降，但幅度较小
        assert new_confidence < original_confidence
        assert new_confidence > 0.7  # 下降不超过 0.1

    def test_confidence_floor_at_zero(self):
        """测试置信度下限为 0"""
        original_confidence = 0.1
        evidence_weight = 1.0
        removed_evidence_ids = [10]
        reasoning_path = []

        new_confidence = _simulate_confidence_without_evidence(
            original_confidence,
            evidence_weight,
            removed_evidence_ids,
            reasoning_path
        )

        # 置信度不应该低于 0
        assert new_confidence >= 0.0


@pytest.mark.asyncio
class TestCounterfactualAnalysis:
    """测试反事实分析主流程"""

    async def test_analysis_with_no_session(self):
        """测试会话不存在"""
        with patch('app.services.diagnosis.counterfactual_service.async_session') as mock_session:
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
            mock_session.return_value.__aenter__.return_value = mock_db

            result = await analyze_counterfactual(session_id=999, top_n=5)

            assert result is None

    async def test_analysis_with_low_confidence(self):
        """测试低置信度会话跳过分析"""
        with patch('app.services.diagnosis.counterfactual_service.async_session') as mock_session:
            mock_db = AsyncMock()

            # Mock 会话存在
            mock_session_obj = AsyncMock()
            mock_session_obj.id = 1

            # Mock 诊断结果存在但置信度低
            mock_result = AsyncMock()
            mock_result.confidence = 0.2
            mock_result.evidence = []

            mock_db.execute = AsyncMock(side_effect=[
                AsyncMock(scalar_one_or_none=AsyncMock(return_value=mock_session_obj)),
                AsyncMock(scalar_one_or_none=AsyncMock(return_value=mock_result)),
            ])
            mock_session.return_value.__aenter__.return_value = mock_db

            result = await analyze_counterfactual(session_id=1, top_n=5)

            assert result is None

    async def test_analysis_timeout(self):
        """测试分析超时"""
        with patch('app.services.diagnosis.counterfactual_service.async_session') as mock_session:
            with patch('app.services.diagnosis.counterfactual_service.asyncio.wait_for') as mock_wait_for:
                mock_db = AsyncMock()

                # Mock 会话和结果存在
                mock_session_obj = AsyncMock()
                mock_session_obj.id = 1

                mock_result = AsyncMock()
                mock_result.confidence = 0.8
                mock_result.evidence = [
                    {"node_id": 1, "probability": 0.9, "sensor_weight": 1.0, "path_length": 1}
                ]
                mock_result.root_cause = "测试根因"
                mock_result.reasoning_path = []
                mock_result.fault_tree_version = "1.0"

                mock_db.execute = AsyncMock(side_effect=[
                    AsyncMock(scalar_one_or_none=AsyncMock(return_value=mock_session_obj)),
                    AsyncMock(scalar_one_or_none=AsyncMock(return_value=mock_result)),
                ])
                mock_session.return_value.__aenter__.return_value = mock_db

                # Mock 超时
                import asyncio
                mock_wait_for.side_effect = asyncio.TimeoutError()

                result = await analyze_counterfactual(session_id=1, top_n=5)

                assert result is None
