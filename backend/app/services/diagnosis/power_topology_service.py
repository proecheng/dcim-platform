# backend/app/services/diagnosis/power_topology_service.py
import asyncio
import copy
import logging
import networkx as nx
from sqlalchemy import select
from prometheus_client import Histogram, Gauge
from app.models.energy import Transformer, DistributionPanel, DistributionCircuit, PowerDevice
from app.core.database import async_session

logger = logging.getLogger(__name__)

# Prometheus 监控指标
topology_graph_build_duration = Histogram(
    "topology_graph_build_duration_seconds", "Time spent building power topology graph"
)
topology_cascade_analysis_duration = Histogram(
    "topology_cascade_analysis_duration_seconds", "Time spent analyzing cascade impact"
)
topology_update_duration = Histogram("topology_update_duration_seconds", "Time spent updating topology graph")
topology_graph_nodes = Gauge("topology_graph_nodes_total", "Total number of nodes in topology graph")
topology_graph_edges = Gauge("topology_graph_edges_total", "Total number of edges in topology graph")

# 全局图缓存（线程安全）
_power_topology_graph: nx.DiGraph | None = None
_graph_lock = asyncio.Lock()

# 节点类型到模型和字段的映射
NODE_TYPE_MAPPING = {
    "transformer": (Transformer, ["transformer_name"], {}),
    "panel": (DistributionPanel, ["panel_name"], {"transformer_id": "transformer_id"}),
    "circuit": (DistributionCircuit, ["circuit_name"], {"panel_id": "panel_id"}),
    "device": (PowerDevice, ["device_name"], {"circuit_id": "circuit_id"}),
}


async def build_power_topology_graph() -> nx.DiGraph:
    """从数据库加载配电拓扑，构建 NetworkX DiGraph"""
    logger.info("开始构建配电拓扑图...")

    with topology_graph_build_duration.time():
        graph = nx.DiGraph()

        try:
            async with async_session() as db:
                # 1. 加载 Transformers
                transformers = await db.execute(select(Transformer))
                for t in transformers.scalars():
                    graph.add_node(f"T-{t.id}", type="transformer", name=t.transformer_name, device_id=t.id)

                # 2. 加载 DistributionPanels
                panels = await db.execute(select(DistributionPanel))
                for p in panels.scalars():
                    graph.add_node(f"P-{p.id}", type="panel", name=p.panel_name, device_id=p.id)
                    if p.transformer_id:
                        graph.add_edge(f"T-{p.transformer_id}", f"P-{p.id}")

                # 3. 加载 DistributionCircuits
                circuits = await db.execute(select(DistributionCircuit))
                for c in circuits.scalars():
                    graph.add_node(f"C-{c.id}", type="circuit", name=c.circuit_name, device_id=c.id)
                    if c.panel_id:
                        graph.add_edge(f"P-{c.panel_id}", f"C-{c.id}")

                # 4. 加载 PowerDevices
                devices = await db.execute(select(PowerDevice))
                for d in devices.scalars():
                    graph.add_node(f"D-{d.id}", type="device", name=d.device_name, device_id=d.id)
                    if d.circuit_id:
                        graph.add_edge(f"C-{d.circuit_id}", f"D-{d.id}")

            # 更新监控指标
            topology_graph_nodes.set(graph.number_of_nodes())
            topology_graph_edges.set(graph.number_of_edges())

            logger.info(f"配电拓扑图构建完成: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")
            return graph
        except Exception as e:
            logger.error(f"构建配电拓扑图失败: {e}")
            raise


async def get_power_topology_graph() -> nx.DiGraph:
    """获取缓存的配电拓扑图"""
    global _power_topology_graph
    if _power_topology_graph is None:
        async with _graph_lock:
            if _power_topology_graph is None:
                _power_topology_graph = await build_power_topology_graph()

    if _power_topology_graph is None:
        raise RuntimeError("配电拓扑图未初始化")

    return _power_topology_graph


async def initialize_power_topology_graph():
    """在 FastAPI lifespan 中调用，初始化全局图"""
    global _power_topology_graph
    async with _graph_lock:
        _power_topology_graph = await build_power_topology_graph()


async def _load_node_data(node_id: str, node_type: str) -> dict:
    """从数据库加载节点数据"""
    if node_type not in NODE_TYPE_MAPPING:
        raise ValueError(f"未知的节点类型: {node_type}")

    Model, base_fields, relation_fields = NODE_TYPE_MAPPING[node_type]

    parts = node_id.split("-")
    if len(parts) != 2:
        raise ValueError(f"无效的节点 ID 格式: {node_id}")

    try:
        obj_id = int(parts[1])
    except ValueError:
        raise ValueError(f"无效的节点 ID: {node_id}")

    async with async_session() as db:
        result = await db.execute(select(Model).where(Model.id == obj_id))
        obj = result.scalar_one_or_none()

        if not obj:
            raise ValueError(f"节点 {node_id} (类型: {node_type}) 未找到")

        # 构建返回数据
        data = {"type": node_type, "device_id": obj.id}
        for field in base_fields:
            data[field] = getattr(obj, field)
        for key, attr in relation_fields.items():
            data[key] = getattr(obj, attr, None)

        return data


async def update_topology_node(node_id: str, node_type: str, action: str):
    """增量更新拓扑图（copy-on-write）"""
    global _power_topology_graph

    with topology_update_duration.time():
        async with _graph_lock:
            if _power_topology_graph is None:
                logger.warning("拓扑图未初始化，跳过增量更新")
                return

            # 1. 创建新图副本（深拷贝以确保线程安全）
            new_graph = copy.deepcopy(_power_topology_graph)

            # 2. 修改副本
            try:
                if action == "add":
                    # 从数据库重新加载节点数据
                    node_data = await _load_node_data(node_id, node_type)
                    new_graph.add_node(node_id, **node_data)

                    # 添加边
                    if node_type == "panel" and node_data.get("transformer_id"):
                        new_graph.add_edge(f"T-{node_data['transformer_id']}", node_id)
                    elif node_type == "circuit" and node_data.get("panel_id"):
                        new_graph.add_edge(f"P-{node_data['panel_id']}", node_id)
                    elif node_type == "device" and node_data.get("circuit_id"):
                        new_graph.add_edge(f"C-{node_data['circuit_id']}", node_id)

                elif action == "delete":
                    if node_id in new_graph:
                        new_graph.remove_node(node_id)

                elif action == "update":
                    node_data = await _load_node_data(node_id, node_type)
                    if node_id in new_graph:
                        new_graph.nodes[node_id].update(node_data)

                        # 更新边（先删除旧边，再添加新边）
                        old_edges = list(new_graph.in_edges(node_id))
                        for edge in old_edges:
                            new_graph.remove_edge(*edge)

                        if node_type == "panel" and node_data.get("transformer_id"):
                            new_graph.add_edge(f"T-{node_data['transformer_id']}", node_id)
                        elif node_type == "circuit" and node_data.get("panel_id"):
                            new_graph.add_edge(f"P-{node_data['panel_id']}", node_id)
                        elif node_type == "device" and node_data.get("circuit_id"):
                            new_graph.add_edge(f"C-{node_data['circuit_id']}", node_id)

                # 3. 原子替换引用
                _power_topology_graph = new_graph

                # 更新监控指标
                topology_graph_nodes.set(new_graph.number_of_nodes())
                topology_graph_edges.set(new_graph.number_of_edges())

                logger.info(f"拓扑图更新成功: {action} {node_id}")

            except Exception as e:
                logger.error(f"拓扑图更新失败: {action} {node_id}, 错误: {e}")
                raise


async def _get_device_status(node_id: str) -> dict:
    """查询设备当前状态（从 Redis 或数据库）"""
    # 优先从 Redis 查询实时状态
    redis_client = None
    try:
        from app.core.config import get_settings
        import redis.asyncio as redis

        settings = get_settings()
        redis_client = redis.from_url(settings.effective_redis_url)

        # 从 Redis 查询设备状态（假设 key 格式: device:status:{device_id}）
        parts = node_id.split("-")
        if len(parts) != 2:
            raise ValueError(f"无效的节点 ID 格式: {node_id}")
        device_id = parts[1]
        status_key = f"device:status:{device_id}"
        status_data = await redis_client.get(status_key)

        if status_data:
            import json

            return json.loads(status_data)

    except Exception as e:
        logger.warning(f"从 Redis 查询设备状态失败: {e}, 降级到数据库查询")
    finally:
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"关闭 Redis 客户端失败: {e}")

    # 降级：从数据库查询
    async with async_session() as db:
        parts = node_id.split("-")
        if len(parts) != 2:
            return {"status": "unknown"}

        node_type = parts[0]
        try:
            device_id = int(parts[1])
        except ValueError:
            return {"status": "unknown"}

        if node_type == "T":
            result = await db.execute(select(Transformer).where(Transformer.id == device_id))
            obj = result.scalar_one_or_none()
        elif node_type == "P":
            result = await db.execute(select(DistributionPanel).where(DistributionPanel.id == device_id))
            obj = result.scalar_one_or_none()
        elif node_type == "C":
            result = await db.execute(select(DistributionCircuit).where(DistributionCircuit.id == device_id))
            obj = result.scalar_one_or_none()
        elif node_type == "D":
            result = await db.execute(select(PowerDevice).where(PowerDevice.id == device_id))
            obj = result.scalar_one_or_none()
        else:
            return {"status": "unknown"}

        if obj:
            return {"status": getattr(obj, "status", "unknown"), "online": getattr(obj, "online", True)}

    return {"status": "unknown"}


async def analyze_downstream_impact(fault_node_id: str) -> dict:
    """向下级联分析：列出受影响的下游设备"""
    with topology_cascade_analysis_duration.time():
        graph = await get_power_topology_graph()

        if fault_node_id not in graph:
            logger.warning(f"节点 {fault_node_id} 不存在于拓扑图中")
            return {"error": "Node not found", "fault_node": fault_node_id}

        # 使用 NetworkX 获取所有下游节点
        downstream_nodes = nx.descendants(graph, fault_node_id)

        # 查询每个设备的当前状态
        affected_devices = []
        for node_id in downstream_nodes:
            node_data = graph.nodes[node_id]
            status = await _get_device_status(node_id)
            affected_devices.append(
                {"node_id": node_id, "type": node_data["type"], "name": node_data["name"], "status": status}
            )

        logger.info(f"级联分析完成: {fault_node_id} 影响 {len(affected_devices)} 个下游设备")
        return {
            "fault_node": fault_node_id,
            "affected_count": len(affected_devices),
            "affected_devices": affected_devices,
        }


async def analyze_upstream_path(device_id: int) -> dict:
    """向上溯源：列出供电链路上的所有上游设备

    Args:
        device_id: PowerDevice 的数据库 ID（整数）
    """
    graph = await get_power_topology_graph()

    node_id = f"D-{device_id}"
    if node_id not in graph:
        logger.warning(f"设备 {device_id} 不存在于拓扑图中")
        return {"error": "Device not found", "device_id": device_id}

    # 使用 NetworkX 获取所有上游节点
    upstream_nodes = nx.ancestors(graph, node_id)

    # 构建供电链路（按层级排序）
    power_path = []
    for node_id in upstream_nodes:
        node_data = graph.nodes[node_id]
        status = await _get_device_status(node_id)
        power_path.append({"node_id": node_id, "type": node_data["type"], "name": node_data["name"], "status": status})

    # 按层级排序: Transformer → Panel → Circuit
    power_path.sort(key=lambda x: {"transformer": 0, "panel": 1, "circuit": 2}.get(x["type"], 3))

    logger.info(f"溯源分析完成: 设备 {device_id} 的供电链路包含 {len(power_path)} 个上游设备")
    return {"device_id": device_id, "power_path": power_path}
