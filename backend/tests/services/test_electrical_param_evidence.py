# backend/tests/services/test_electrical_param_evidence.py
"""
Story 25.2: 电气参数证据计算测试
"""
import pytest
import math
from app.services.diagnosis.evidence_calculator import calc_evidence_probability
from app.models.fault_tree import FaultTreeNode
from app.models import Point
from unittest.mock import AsyncMock, patch


def test_sigmoid_above_threshold():
    """测试 ABOVE 类型阈值（三相不平衡度）"""
    # 超过阈值（12% > 10%）
    prob = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob > 0.5  # 异常概率应大于 0.5
    assert 0.55 < prob < 0.65  # 实际约 0.598

    # 低于阈值（8% < 10%）
    prob = calc_evidence_probability(8.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob < 0.5  # 正常概率应小于 0.5


def test_sigmoid_below_threshold():
    """测试 BELOW 类型阈值（功率因数）"""
    # 低于阈值（0.85 < 0.9）
    prob = calc_evidence_probability(0.85, 0.9, "BELOW", sigmoid_k=2.0)
    assert prob > 0.5  # 异常概率应大于 0.5

    # 高于阈值（0.95 > 0.9）
    prob = calc_evidence_probability(0.95, 0.9, "BELOW", sigmoid_k=2.0)
    assert prob < 0.5  # 正常概率应小于 0.5


def test_sigmoid_k_parameter():
    """测试斜率参数影响"""
    # 斜率越大，曲线越陡峭
    prob_k2 = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=2.0)
    prob_k5 = calc_evidence_probability(12.0, 10.0, "ABOVE", sigmoid_k=5.0)

    # k=5 时曲线更陡，相同偏离度下概率更接近 1
    assert prob_k5 > prob_k2


def test_edge_cases():
    """测试边界情况"""
    # 阈值为 0
    prob = calc_evidence_probability(10.0, 0.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # 极端偏离（防止溢出）
    prob = calc_evidence_probability(1000.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 1.0  # 应限制在 1.0

    # 负数点位值
    prob = calc_evidence_probability(-5.0, 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # NaN 点位值
    prob = calc_evidence_probability(float('nan'), 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # Infinity 点位值
    prob = calc_evidence_probability(float('inf'), 10.0, "ABOVE", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率

    # 未知 threshold_type
    prob = calc_evidence_probability(12.0, 10.0, "UNKNOWN", sigmoid_k=2.0)
    assert prob == 0.5  # 返回先验概率


@pytest.mark.asyncio
async def test_electrical_param_integration():
    """测试电气参数集成到 L2 推理流程（完整 mock 实现）"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    # 创建测试故障树节点（三相不平衡度）
    node = FaultTreeNode(
        id=1,
        tree_id=1,
        node_type="LEAF",
        evidence_point_id=100,
        threshold_type="ABOVE",
        threshold_value=10.0,
        sigmoid_k=2.0,
        prior_probability=0.5
    )

    # Mock get_point_latest_value 返回 12%（超过阈值）
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = 12.0

        # Mock get_point_by_id 返回 Point 对象
        mock_point = Point(id=100, point_type="PHASE_IMBALANCE", point_name="三相不平衡度")
        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.return_value = mock_point

            # 执行证据收集
            probability = await collect_leaf_evidence(node, time_window=300)

            # 验证结果
            assert probability > 0.5  # 异常概率应大于 0.5
            assert 0.55 < probability < 0.65  # 实际约 0.598

            # 验证 mock 调用
            mock_get_value.assert_called_once_with(100, 300)
            mock_get_point.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_electrical_param_default_threshold():
    """测试使用默认阈值"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    # 创建节点，不配置阈值（使用默认值）
    node = FaultTreeNode(
        id=2,
        tree_id=1,
        node_type="LEAF",
        evidence_point_id=101,
        threshold_type=None,  # 未配置
        threshold_value=None,  # 未配置
        sigmoid_k=None,  # 使用默认 2.0
        prior_probability=0.5
    )

    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = 6.0  # THD 6% (默认阈值 5%)

        mock_point = Point(id=101, point_type="THD", point_name="谐波畸变率")
        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.return_value = mock_point

            probability = await collect_leaf_evidence(node, time_window=300)

            # 应使用默认阈值 5%，6% 超过阈值
            assert probability > 0.5


@pytest.mark.asyncio
async def test_electrical_param_no_data():
    """测试点位无数据情况"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence

    node = FaultTreeNode(
        id=3,
        tree_id=1,
        node_type="LEAF",
        evidence_point_id=102,
        threshold_type="ABOVE",
        threshold_value=10.0,
        sigmoid_k=2.0,
        prior_probability=0.3
    )

    # Mock 返回 None（无数据）
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.return_value = None

        probability = await collect_leaf_evidence(node, time_window=300)

        # 应返回先验概率
        assert probability == 0.3


@pytest.mark.asyncio
async def test_concurrent_evidence_calculation():
    """测试并发证据计算（模拟多个诊断任务同时运行）"""
    from app.services.diagnosis.l2_inference_engine import collect_leaf_evidence
    import asyncio

    # 创建多个节点
    nodes = [
        FaultTreeNode(
            id=i,
            tree_id=1,
            node_type="LEAF",
            evidence_point_id=100 + i,
            threshold_type="ABOVE",
            threshold_value=10.0,
            sigmoid_k=2.0,
            prior_probability=0.5
        )
        for i in range(10)
    ]

    # Mock 返回不同的点位值
    with patch('app.services.diagnosis.l2_inference_engine.get_point_latest_value',
               new_callable=AsyncMock) as mock_get_value:
        mock_get_value.side_effect = lambda point_id, _: float(point_id % 20)

        with patch('app.services.diagnosis.l2_inference_engine.get_point_by_id',
                   new_callable=AsyncMock) as mock_get_point:
            mock_get_point.side_effect = lambda point_id: Point(
                id=point_id,
                point_type="PHASE_IMBALANCE",
                point_name=f"Point-{point_id}"
            )

            # 并发执行证据收集
            tasks = [collect_leaf_evidence(node, time_window=300) for node in nodes]
            results = await asyncio.gather(*tasks)

            # 验证所有结果都有效
            assert len(results) == 10
            assert all(0 <= prob <= 1 for prob in results)
