"""
L2 故障树推理引擎单元测试
"""

import asyncio
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Mock redis_client 模块 (scheduler 依赖它,但测试环境不需要)
sys.modules.setdefault('redis', MagicMock())
sys.modules.setdefault('redis.asyncio', MagicMock())
if "app.core.redis_client" not in sys.modules:
    _mock_redis = types.ModuleType("app.core.redis_client")
    _mock_redis.get_redis = MagicMock()
    sys.modules["app.core.redis_client"] = _mock_redis

from app.services.diagnosis.fault_tree import (
    DEFAULT_SIGMOID_K,
    DiagnosisContext,
    EvidenceItem,
    FaultTreeCache,
    FaultTreeInferenceEngine,
    and_gate,
    or_gate,
    sigmoid_stable,
    validate_fault_tree,
)


class TestSigmoidStable:
    """测试数值稳定的 sigmoid 函数"""

    def test_zero_input(self):
        result = sigmoid_stable(0.0)
        assert abs(result - 0.5) < 1e-6

    def test_positive_input(self):
        result = sigmoid_stable(10.0)
        assert result > 0.99

    def test_negative_input(self):
        result = sigmoid_stable(-10.0)
        assert result < 0.01

    def test_large_positive(self):
        """大正数不会溢出"""
        result = sigmoid_stable(100.0)
        assert 0.0 <= result <= 1.0

    def test_large_negative(self):
        """大负数不会溢出"""
        result = sigmoid_stable(-100.0)
        assert 0.0 <= result <= 1.0

    def test_symmetry(self):
        """sigmoid(x) + sigmoid(-x) = 1"""
        for x in [0.5, 1.0, 5.0, 20.0]:
            assert abs(sigmoid_stable(x) + sigmoid_stable(-x) - 1.0) < 1e-10


class TestGateFunctions:
    """测试门逻辑函数"""

    def test_or_gate_empty(self):
        assert or_gate([]) == 0.0

    def test_or_gate_single(self):
        assert or_gate([0.5]) == 0.5

    def test_or_gate_multiple(self):
        result = or_gate([0.3, 0.4])
        assert abs(result - 0.58) < 1e-6

    def test_or_gate_all_zero(self):
        assert or_gate([0.0, 0.0, 0.0]) == 0.0

    def test_or_gate_one_certain(self):
        assert or_gate([1.0, 0.0]) == 1.0

    def test_and_gate_empty(self):
        assert and_gate([]) == 0.0

    def test_and_gate_single(self):
        assert and_gate([0.5]) == 0.5

    def test_and_gate_multiple(self):
        result = and_gate([0.3, 0.4])
        assert abs(result - 0.12) < 1e-6

    def test_and_gate_one_zero(self):
        assert and_gate([0.5, 0.0]) == 0.0


class TestValidateFaultTree:
    """测试故障树验证"""

    @pytest.mark.asyncio
    async def test_valid_tree(self):
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", evidence_point_id=10)
        graph.add_node(2, gate_type="LEAF", evidence_point_id=20)
        graph.add_node(3, gate_type="OR")
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        warnings = await validate_fault_tree(graph)
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_cyclic_tree(self):
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="OR")
        graph.add_node(2, gate_type="OR")
        graph.add_edge(1, 2)
        graph.add_edge(2, 1)

        warnings = await validate_fault_tree(graph)
        assert any("环路" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_invalid_gate_type(self):
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="INVALID")

        warnings = await validate_fault_tree(graph)
        assert any("gate_type 无效" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_isolated_node(self):
        """测试孤立节点检测"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", evidence_point_id=10)
        graph.add_node(2, gate_type="LEAF")  # 孤立节点

        warnings = await validate_fault_tree(graph)
        assert any("孤立节点" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_leaf_without_evidence(self):
        """测试叶节点缺少证据点位"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", evidence_point_id=None)
        graph.add_node(2, gate_type="OR")
        graph.add_edge(1, 2)

        warnings = await validate_fault_tree(graph)
        assert any("没有关联证据点位" in w for w in warnings)


class TestFaultTreeCache:
    """测试故障树缓存"""

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        cache = FaultTreeCache(max_size=10)
        result = await cache.get(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_deep_copy(self):
        """缓存命中返回深拷贝, 修改不影响原图"""
        cache = FaultTreeCache(max_size=10)
        graph = nx.DiGraph()
        graph.add_node(1, probability=0.0)

        await cache.put(1, graph)
        copy1 = await cache.get(1)
        copy1.nodes[1]["probability"] = 0.99  # 修改拷贝

        copy2 = await cache.get(1)
        assert copy2.nodes[1]["probability"] == 0.0  # 原图未被影响

    @pytest.mark.asyncio
    async def test_reference_counting(self):
        cache = FaultTreeCache(max_size=10)
        graph = nx.DiGraph()

        await cache.put(1, graph)       # ref_count = 1
        await cache.get(1)              # ref_count = 2
        await cache.release(1)          # ref_count = 1
        await cache.release(1)          # ref_count = 0

        assert cache._ref_count[1] == 0

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        cache = FaultTreeCache(max_size=2)
        g1, g2, g3 = nx.DiGraph(), nx.DiGraph(), nx.DiGraph()

        await cache.put(1, g1)
        await cache.release(1)

        await cache.put(2, g2)
        await cache.release(2)

        await cache.put(3, g3)
        assert len(cache._cache) == 2


class TestFaultTreeInferenceEngine:
    """测试故障树推理引擎"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def engine(self, mock_session):
        eng = FaultTreeInferenceEngine(mock_session)
        eng.cache = FaultTreeCache(max_size=10)
        return eng

    def test_compute_leaf_probability_abnormal_with_prior(self, engine):
        """测试异常状态: P = prior + (1 - prior) * sigmoid(k * deviation)"""
        node_data = {"prior_probability": 0.1, "sigmoid_k": 2.0}
        evidence = EvidenceItem(
            point_id=1, value=55.0, threshold=50.0, status="abnormal"
        )

        prob = engine.compute_leaf_probability(node_data, evidence)
        # deviation = 55 - 50 = 5, sigmoid(2*5) ≈ 0.9999
        # P = 0.1 + 0.9 * 0.9999 ≈ 0.99+
        assert prob > 0.9

    def test_compute_leaf_probability_normal_below_threshold(self, engine):
        """测试正常状态: 值低于阈值, sigmoid 给出较低概率"""
        node_data = {"prior_probability": 0.1, "sigmoid_k": 2.0}
        evidence = EvidenceItem(
            point_id=1, value=45.0, threshold=50.0, status="normal"
        )

        prob = engine.compute_leaf_probability(node_data, evidence)
        # deviation = 45 - 50 = -5, sigmoid(2*-5) ≈ 0.0001
        # P = 0.1 + 0.9 * 0.0001 ≈ 0.1
        assert prob < 0.2

    def test_compute_leaf_probability_timeout_uses_prior(self, engine):
        """测试超时状态: 使用先验概率"""
        node_data = {"prior_probability": 0.3, "sigmoid_k": 2.0}
        evidence = EvidenceItem(point_id=1, status="timeout")

        prob = engine.compute_leaf_probability(node_data, evidence)
        assert prob == 0.3

    def test_compute_leaf_probability_at_threshold(self, engine):
        """测试值等于阈值: P = prior + (1-prior) * 0.5"""
        node_data = {"prior_probability": 0.1, "sigmoid_k": 2.0}
        evidence = EvidenceItem(
            point_id=1, value=50.0, threshold=50.0, status="abnormal"
        )

        prob = engine.compute_leaf_probability(node_data, evidence)
        expected = 0.1 + 0.9 * 0.5  # = 0.55
        assert abs(prob - expected) < 1e-6

    def test_compute_leaf_probability_default_k(self, engine):
        """测试默认 sigmoid_k = 2.0"""
        node_data = {"prior_probability": 0.2}  # 不指定 sigmoid_k
        evidence = EvidenceItem(
            point_id=1, value=55.0, threshold=50.0, status="abnormal"
        )

        prob = engine.compute_leaf_probability(node_data, evidence)
        assert prob > 0.5

    @pytest.mark.asyncio
    async def test_propagate_probabilities_or_gate(self, engine):
        """测试 OR 门概率传播"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.1, sigmoid_k=2.0)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.1, sigmoid_k=2.0)
        graph.add_node(3, gate_type="OR", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        evidence = {
            1: EvidenceItem(point_id=1, value=55.0, threshold=50.0, status="abnormal"),
            2: EvidenceItem(point_id=2, value=45.0, threshold=50.0, status="normal"),
        }

        node_probs = await engine.propagate_probabilities(graph, evidence)

        p1 = node_probs[1]
        p2 = node_probs[2]
        expected = 1.0 - (1.0 - p1) * (1.0 - p2)
        assert abs(node_probs[3] - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_propagate_probabilities_and_gate(self, engine):
        """测试 AND 门概率传播"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.1, sigmoid_k=2.0)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.1, sigmoid_k=2.0)
        graph.add_node(3, gate_type="AND", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        evidence = {
            1: EvidenceItem(point_id=1, value=55.0, threshold=50.0, status="abnormal"),
            2: EvidenceItem(point_id=2, value=45.0, threshold=50.0, status="normal"),
        }

        node_probs = await engine.propagate_probabilities(graph, evidence)

        p1 = node_probs[1]
        p2 = node_probs[2]
        expected = p1 * p2
        assert abs(node_probs[3] - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_propagate_returns_all_probs(self, engine):
        """测试 propagate 返回完整概率字典"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.5, sigmoid_k=2.0)
        graph.add_node(2, gate_type="OR", probability=0.0)
        graph.add_edge(1, 2)

        evidence = {
            1: EvidenceItem(point_id=1, value=55.0, threshold=50.0, status="abnormal"),
        }

        node_probs = await engine.propagate_probabilities(graph, evidence)

        assert 1 in node_probs
        assert 2 in node_probs
        assert len(node_probs) == 2

    @pytest.mark.asyncio
    async def test_extract_root_cause_path_or_gate(self, engine):
        """OR 门: 选概率最大的子节点"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.8, prior_probability=0.1)
        graph.add_node(2, gate_type="LEAF", probability=0.2, prior_probability=0.1)
        graph.add_node(3, gate_type="OR", probability=0.84)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        path = await engine.extract_root_cause_path(graph, root_node_id=3)
        assert path == [3, 1]

    @pytest.mark.asyncio
    async def test_extract_root_cause_path_and_gate(self, engine):
        """AND 门: 选偏离先验最大的子节点"""
        graph = nx.DiGraph()
        # 节点 1: prob=0.8, prior=0.1, 偏离=0.7
        # 节点 2: prob=0.9, prior=0.8, 偏离=0.1
        # AND 门应选偏离最大的节点 1
        graph.add_node(1, gate_type="LEAF", probability=0.8, prior_probability=0.1)
        graph.add_node(2, gate_type="LEAF", probability=0.9, prior_probability=0.8)
        graph.add_node(3, gate_type="AND", probability=0.72)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        path = await engine.extract_root_cause_path(graph, root_node_id=3)
        assert path == [3, 1]  # 偏离先验最大的是节点 1

    @pytest.mark.asyncio
    async def test_diagnose_l2_no_fault_tree(self, engine, mock_session):
        """测试没有可用故障树的情况"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        context = await engine.diagnose_l2(device_id=1, device_type="UPS")

        assert context is not None
        assert "没有适用的故障树" in context.errors
        assert context.fault_tree_id == 0

    @pytest.mark.asyncio
    async def test_diagnose_l2_has_alarm_type(self, engine, mock_session):
        """测试 DiagnosisContext 包含 alarm_type"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        context = await engine.diagnose_l2(
            device_id=1, device_type="UPS", alarm_type="over_temperature"
        )
        assert context.alarm_type == "over_temperature"

    @pytest.mark.asyncio
    async def test_propagate_with_missing_evidence(self, engine):
        """测试缺少证据的叶节点使用先验概率"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.3, sigmoid_k=2.0)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.5, sigmoid_k=2.0)
        graph.add_node(3, gate_type="OR", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        evidence = {
            1: EvidenceItem(point_id=1, value=55.0, threshold=50.0, status="abnormal"),
        }

        node_probs = await engine.propagate_probabilities(graph, evidence)
        assert node_probs[2] == 0.5  # 使用先验概率

    @pytest.mark.asyncio
    async def test_deep_tree_10_layers(self, engine):
        """测试 10 层深度故障树"""
        graph = nx.DiGraph()
        # 构建一条直线: leaf → n2 → n3 → ... → root (10层)
        for i in range(1, 11):
            if i == 1:
                graph.add_node(i, gate_type="LEAF", probability=0.0, prior_probability=0.5, sigmoid_k=2.0)
            else:
                graph.add_node(i, gate_type="OR", probability=0.0)
            if i > 1:
                graph.add_edge(i - 1, i)

        evidence = {
            1: EvidenceItem(point_id=1, value=55.0, threshold=50.0, status="abnormal"),
        }

        node_probs = await engine.propagate_probabilities(graph, evidence)
        # 每层 OR 门只有一个子节点, 概率应不变
        root_prob = node_probs[10]
        leaf_prob = node_probs[1]
        assert abs(root_prob - leaf_prob) < 1e-6
