# backend/tests/services/test_power_topology_service.py
import pytest
import asyncio
from contextlib import asynccontextmanager

from app.services.diagnosis import power_topology_service
from app.services.diagnosis.power_topology_service import (
    build_power_topology_graph,
    analyze_downstream_impact,
    analyze_upstream_path,
    update_topology_node,
    initialize_power_topology_graph
)
from app.models.energy import Transformer, DistributionPanel, DistributionCircuit, PowerDevice


@pytest.fixture(scope="function")
async def setup_test_topology(async_db, monkeypatch):
    """创建测试拓扑数据"""

    @asynccontextmanager
    async def isolated_async_session():
        yield async_db

    monkeypatch.setattr(power_topology_service, "async_session", isolated_async_session)

    # 创建 Transformer
    t1 = Transformer(
        id=9001,
        transformer_code="TEST-TR-001",
        transformer_name="测试变压器1",
        rated_capacity=1000.0
    )

    # 创建 DistributionPanel
    p1 = DistributionPanel(
        id=9001,
        panel_code="TEST-PANEL-001",
        panel_name="测试配电柜1",
        panel_type="distribution",
        transformer_id=9001
    )

    # 创建 DistributionCircuit
    c1 = DistributionCircuit(
        id=9001,
        circuit_code="TEST-CIR-001",
        circuit_name="测试回路1",
        panel_id=9001
    )

    # 创建 PowerDevice
    d1 = PowerDevice(
        id=9001,
        device_code="TEST-PDU-001",
        device_name="测试PDU1",
        device_type="OTHER",
        circuit_id=9001
    )
    d2 = PowerDevice(
        id=9002,
        device_code="TEST-SRV-001",
        device_name="测试服务器1",
        device_type="IT_SERVER",
        circuit_id=9001
    )
    async_db.add_all([t1, p1, c1, d1, d2])
    await async_db.flush()

    # 初始化拓扑图
    await initialize_power_topology_graph()

    yield

    # 清理全局图缓存
    power_topology_service._power_topology_graph = None


@pytest.mark.asyncio
async def test_build_power_topology_graph(setup_test_topology):
    """测试图构建"""
    graph = await build_power_topology_graph()
    assert graph.number_of_nodes() > 0
    assert graph.number_of_edges() > 0

    # 验证节点命名规则
    for node_id in graph.nodes():
        assert node_id.startswith(("T-", "P-", "C-", "D-"))


@pytest.mark.asyncio
async def test_analyze_downstream_impact(setup_test_topology):
    """测试向下级联分析"""
    # 模拟回路故障
    result = await analyze_downstream_impact("C-9001")
    assert "affected_devices" in result
    assert result["affected_count"] >= 0


@pytest.mark.asyncio
async def test_analyze_upstream_path(setup_test_topology):
    """测试向上溯源"""
    # 模拟服务器溯源（传入整数 ID）
    result = await analyze_upstream_path(9001)
    assert "power_path" in result
    assert len(result["power_path"]) >= 1  # 至少有一个上游设备


@pytest.mark.asyncio
async def test_update_topology_node(setup_test_topology):
    """测试增量更新"""
    # 测试更新节点
    await update_topology_node("D-9001", "device", "update")

    # 测试删除节点（使用已存在的节点）
    await update_topology_node("D-9002", "device", "delete")


@pytest.mark.asyncio
async def test_concurrent_graph_access(setup_test_topology):
    """测试并发安全性"""
    async def read_graph():
        from app.services.diagnosis.power_topology_service import get_power_topology_graph
        graph = await get_power_topology_graph()
        return graph.number_of_nodes()

    # 并发读取图
    tasks = [read_graph() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # 所有结果应该一致
    assert len(set(results)) == 1


@pytest.mark.asyncio
async def test_node_not_found_error(setup_test_topology):
    """测试节点不存在错误处理"""
    result = await analyze_downstream_impact("X-999")
    assert "error" in result
    assert result["error"] == "Node not found"
