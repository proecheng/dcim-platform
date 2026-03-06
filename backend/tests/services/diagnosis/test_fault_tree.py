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
if "app.core.redis_client" not in sys.modules:
    _mock_redis = types.ModuleType("app.core.redis_client")
    _mock_redis.get_redis = MagicMock()
    sys.modules["app.core.redis_client"] = _mock_redis

from app.services.diagnosis.fault_tree import (
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
        """测试零输入"""
        result = sigmoid_stable(0.0)
        assert abs(result - 0.5) < 1e-6

    def test_positive_input(self):
        """测试正数输入"""
        result = sigmoid_stable(10.0)
        assert result > 0.99

    def test_negative_input(self):
        """测试负数输入"""
        result = sigmoid_stable(-10.0)
        assert result < 0.01

    def test_large_positive(self):
        """测试大正数不会溢出"""
        result = sigmoid_stable(100.0)
        assert 0.0 <= result <= 1.0

    def test_large_negative(self):
        """测试大负数不会溢出"""
        result = sigmoid_stable(-100.0)
        assert 0.0 <= result <= 1.0


class TestGateFunctions:
    """测试门逻辑函数"""

    def test_or_gate_empty(self):
        assert or_gate([]) == 0.0

    def test_or_gate_single(self):
        assert or_gate([0.5]) == 0.5

    def test_or_gate_multiple(self):
        # P = 1 - (1-0.3) * (1-0.4) = 1 - 0.42 = 0.58
        result = or_gate([0.3, 0.4])
        assert abs(result - 0.58) < 1e-6

    def test_and_gate_empty(self):
        assert and_gate([]) == 0.0

    def test_and_gate_single(self):
        assert and_gate([0.5]) == 0.5

    def test_and_gate_multiple(self):
        # P = 0.3 * 0.4 = 0.12
        result = and_gate([0.3, 0.4])
        assert abs(result - 0.12) < 1e-6


class TestValidateFaultTree:
    """测试故障树验证"""

    @pytest.mark.asyncio
    async def test_valid_tree(self):
        """测试有效的故障树"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF")
        graph.add_node(2, gate_type="LEAF")
        graph.add_node(3, gate_type="OR")
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        warnings = await validate_fault_tree(graph)
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_cyclic_tree(self):
        """测试包含环路的故障树"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="OR")
        graph.add_node(2, gate_type="OR")
        graph.add_edge(1, 2)
        graph.add_edge(2, 1)

        warnings = await validate_fault_tree(graph)
        assert any("环路" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_invalid_gate_type(self):
        """测试无效的门类型"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="INVALID")

        warnings = await validate_fault_tree(graph)
        assert any("gate_type 无效" in w for w in warnings)


class TestFaultTreeCache:
    """测试故障树缓存"""

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        cache = FaultTreeCache(max_size=10)
        result = await cache.get(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        cache = FaultTreeCache(max_size=10)
        graph = nx.DiGraph()
        graph.add_node(1)

        await cache.put(1, graph)
        result = await cache.get(1)
        assert result is not None
        assert 1 in result.nodes()

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
        await cache.release(1)  # ref_count = 0

        await cache.put(2, g2)
        await cache.release(2)  # ref_count = 0

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
        # 使用独立缓存避免测试之间互相影响
        eng.cache = FaultTreeCache(max_size=10)
        return eng

    def test_compute_leaf_probability_abnormal(self, engine):
        """测试异常状态的叶节点概率计算"""
        evidence = EvidenceItem(
            point_id=1,
            value=110.0,
            threshold=100.0,
            status="abnormal",
        )
        prob = engine.compute_leaf_probability(evidence)
        assert prob > 0.5

    def test_compute_leaf_probability_normal(self, engine):
        """测试正常状态的叶节点概率计算"""
        evidence = EvidenceItem(
            point_id=1,
            value=90.0,
            threshold=100.0,
            status="normal",
        )
        prob = engine.compute_leaf_probability(evidence)
        assert prob == 0.01

    def test_compute_leaf_probability_timeout(self, engine):
        """测试超时状态的叶节点概率计算"""
        evidence = EvidenceItem(point_id=1, status="timeout")
        prob = engine.compute_leaf_probability(evidence)
        assert prob == 0.5

    def test_compute_leaf_probability_zero_threshold(self, engine):
        """测试阈值为 0 时不会除零"""
        evidence = EvidenceItem(
            point_id=1,
            value=10.0,
            threshold=0.0,
            status="abnormal",
        )
        prob = engine.compute_leaf_probability(evidence)
        assert prob == 0.5  # 降级为不确定性

    @pytest.mark.asyncio
    async def test_propagate_probabilities_or_gate(self, engine):
        """测试 OR 门概率传播"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.5)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.5)
        graph.add_node(3, gate_type="OR", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        evidence = {
            1: EvidenceItem(point_id=1, value=110.0, threshold=100.0, status="abnormal"),
            2: EvidenceItem(point_id=2, value=90.0, threshold=100.0, status="normal"),
        }

        await engine.propagate_probabilities(graph, evidence)

        assert graph.nodes[1]["probability"] > 0.5
        assert graph.nodes[2]["probability"] == 0.01

        p1 = graph.nodes[1]["probability"]
        p2 = graph.nodes[2]["probability"]
        expected = 1.0 - (1.0 - p1) * (1.0 - p2)
        assert abs(graph.nodes[3]["probability"] - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_propagate_probabilities_and_gate(self, engine):
        """测试 AND 门概率传播"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.5)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.5)
        graph.add_node(3, gate_type="AND", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        evidence = {
            1: EvidenceItem(point_id=1, value=110.0, threshold=100.0, status="abnormal"),
            2: EvidenceItem(point_id=2, value=90.0, threshold=100.0, status="normal"),
        }

        await engine.propagate_probabilities(graph, evidence)

        p1 = graph.nodes[1]["probability"]
        p2 = graph.nodes[2]["probability"]
        expected = p1 * p2
        assert abs(graph.nodes[3]["probability"] - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_extract_root_cause_path(self, engine):
        """测试根因路径提取"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.8)
        graph.add_node(2, gate_type="LEAF", probability=0.2)
        graph.add_node(3, gate_type="OR", probability=0.84)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        path = await engine.extract_root_cause_path(graph, root_node_id=3)
        assert path == [3, 1]

    @pytest.mark.asyncio
    async def test_diagnose_l2_no_fault_tree(self, engine, mock_session):
        """测试没有可用故障树的情况"""
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        context = await engine.diagnose_l2(device_id=1, device_type="UPS")

        assert context is not None
        assert "没有可用的故障树" in context.errors
        assert context.fault_tree_id == 0

    @pytest.mark.asyncio
    async def test_propagate_with_missing_evidence(self, engine):
        """测试缺少证据的叶节点使用先验概率"""
        graph = nx.DiGraph()
        graph.add_node(1, gate_type="LEAF", probability=0.0, prior_probability=0.3)
        graph.add_node(2, gate_type="LEAF", probability=0.0, prior_probability=0.5)
        graph.add_node(3, gate_type="OR", probability=0.0)
        graph.add_edge(1, 3)
        graph.add_edge(2, 3)

        # 只给节点 1 证据,节点 2 缺少证据
        evidence = {
            1: EvidenceItem(point_id=1, value=110.0, threshold=100.0, status="abnormal"),
        }

        await engine.propagate_probabilities(graph, evidence)

        # 节点 2 应使用先验概率 0.5
        assert graph.nodes[2]["probability"] == 0.5
