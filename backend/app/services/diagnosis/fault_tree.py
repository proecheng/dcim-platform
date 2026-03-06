"""
L2 故障树推理引擎

基于 NetworkX 图结构实现故障树因果推理，支持:
- 故障树选择与证据收集
- 概率传播（OR/AND 门）
- 根因路径提取
- 异常容错与性能优化
"""

import asyncio
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import networkx as nx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fault_tree import (
    FaultTree,
    FaultTreeDeviceMapping,
    FaultTreeEdge,
    FaultTreeNode,
)
from app.models.history import PointHistory

logger = logging.getLogger(__name__)


@dataclass
class EvidenceItem:
    """证据项"""
    point_id: Optional[int] = None
    point_name: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: Optional[datetime] = None
    status: str = "normal"  # normal, abnormal, timeout, error


@dataclass
class DiagnosisContext:
    """诊断上下文 - 用于 L2→L3 引擎通信"""
    device_id: int
    device_type: str
    fault_tree_id: int
    fault_tree_name: str
    root_node_probability: float
    root_cause_path: List[int]  # 节点 ID 列表
    evidence: Dict[int, EvidenceItem]  # node_id → EvidenceItem

    # 性能指标
    inference_time_ms: float = 0.0
    evidence_collection_time_ms: float = 0.0
    propagation_time_ms: float = 0.0
    path_extraction_time_ms: float = 0.0

    # 错误追踪
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    degraded: bool = False  # 降级模式标志


class FaultTreeCache:
    """故障树缓存管理器 - 支持引用计数和自动清理"""

    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        self._cache: Dict[int, nx.DiGraph] = {}
        self._ref_count: Dict[int, int] = {}
        self._last_access: Dict[int, float] = {}
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    async def get(self, tree_id: int) -> Optional[nx.DiGraph]:
        """获取缓存的故障树"""
        async with self._lock:
            if tree_id in self._cache:
                self._ref_count[tree_id] += 1
                self._last_access[tree_id] = time.time()
                logger.debug(f"故障树 {tree_id} 缓存命中, 引用计数: {self._ref_count[tree_id]}")
                return self._cache[tree_id]
            return None

    async def put(self, tree_id: int, graph: nx.DiGraph) -> None:
        """存入故障树到缓存"""
        async with self._lock:
            if len(self._cache) >= self.max_size and tree_id not in self._cache:
                await self._evict_lru()

            self._cache[tree_id] = graph
            self._ref_count[tree_id] = 1
            self._last_access[tree_id] = time.time()
            logger.debug(f"故障树 {tree_id} 已缓存, 当前缓存大小: {len(self._cache)}")

    async def release(self, tree_id: int) -> None:
        """释放故障树引用"""
        async with self._lock:
            if tree_id in self._ref_count:
                self._ref_count[tree_id] -= 1
                logger.debug(f"故障树 {tree_id} 引用释放, 剩余引用: {self._ref_count[tree_id]}")

    async def _evict_lru(self) -> None:
        """清理最久未使用的缓存条目"""
        if not self._cache:
            return

        candidates = [
            (tree_id, self._last_access[tree_id])
            for tree_id in self._cache
            if self._ref_count.get(tree_id, 0) == 0
        ]

        if candidates:
            tree_id_to_remove = min(candidates, key=lambda x: x[1])[0]
            del self._cache[tree_id_to_remove]
            del self._ref_count[tree_id_to_remove]
            del self._last_access[tree_id_to_remove]
            logger.info(f"故障树 {tree_id_to_remove} 已从缓存中清理 (LRU)")

    async def cleanup_expired(self) -> None:
        """清理过期的缓存条目"""
        async with self._lock:
            now = time.time()
            expired = [
                tree_id
                for tree_id, last_access in self._last_access.items()
                if now - last_access > self.ttl_seconds and self._ref_count.get(tree_id, 0) == 0
            ]

            for tree_id in expired:
                del self._cache[tree_id]
                del self._ref_count[tree_id]
                del self._last_access[tree_id]
                logger.info(f"故障树 {tree_id} 已从缓存中清理 (TTL 过期)")


# 全局缓存实例
_fault_tree_cache = FaultTreeCache()


def sigmoid_stable(x: float) -> float:
    """数值稳定的 sigmoid 函数

    分段实现避免 exp 溢出:
    - x >= 0: sigmoid(x) = 1 / (1 + exp(-x))
    - x < 0: sigmoid(x) = exp(x) / (1 + exp(x))
    """
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


def or_gate(child_probs: List[float]) -> float:
    """OR 门概率计算: P = 1 - ∏(1 - P(child_i))"""
    if not child_probs:
        return 0.0

    product = 1.0
    for p in child_probs:
        product *= (1.0 - p)

    return 1.0 - product


def and_gate(child_probs: List[float]) -> float:
    """AND 门概率计算: P = ∏ P(child_i)"""
    if not child_probs:
        return 0.0

    product = 1.0
    for p in child_probs:
        product *= p

    return product


async def validate_fault_tree(graph: nx.DiGraph) -> List[str]:
    """验证故障树结构

    检查:
    - 是否为 DAG (无环)
    - 是否有唯一根节点
    - 所有节点是否有有效的 gate_type
    """
    warnings = []

    if not nx.is_directed_acyclic_graph(graph):
        warnings.append("故障树包含环路,不是有效的 DAG")
        return warnings

    # 根节点: 出度为 0 的节点 (child→parent 边方向下, 根节点没有出边)
    root_nodes = [node for node in graph.nodes() if graph.out_degree(node) == 0]
    if len(root_nodes) == 0:
        warnings.append("故障树没有根节点")
    elif len(root_nodes) > 1:
        warnings.append(f"故障树有多个根节点: {root_nodes}")

    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        if "gate_type" not in node_data:
            warnings.append(f"节点 {node_id} 缺少 gate_type 属性")
        elif node_data["gate_type"] not in ("OR", "AND", "LEAF", None):
            warnings.append(f"节点 {node_id} 的 gate_type 无效: {node_data['gate_type']}")

    return warnings


class FaultTreeInferenceEngine:
    """L2 故障树推理引擎"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = _fault_tree_cache

    async def select_fault_tree(self, device_id: int, device_type: str) -> Optional[int]:
        """选择适用的故障树

        优先级:
        1. 设备类型精确匹配的设备映射 (priority 最高)
        2. 通用故障树 (device_type = 'generic')
        3. 第一个 active 状态的故障树
        """
        # 查询设备映射 (按 device_type 匹配, priority 降序)
        result = await self.session.execute(
            select(FaultTreeDeviceMapping)
            .where(FaultTreeDeviceMapping.device_type == device_type)
            .order_by(FaultTreeDeviceMapping.priority.desc())
        )
        mapping = result.scalars().first()

        if mapping:
            logger.info(f"设备类型 {device_type} 匹配映射, 使用故障树: {mapping.tree_id}")
            return mapping.tree_id

        # 查询通用映射
        result = await self.session.execute(
            select(FaultTreeDeviceMapping)
            .where(FaultTreeDeviceMapping.device_type == "generic")
            .order_by(FaultTreeDeviceMapping.priority.desc())
        )
        mapping = result.scalars().first()

        if mapping:
            logger.info(f"设备 {device_id} 使用通用映射故障树: {mapping.tree_id}")
            return mapping.tree_id

        # 回退: 查询 active 状态的故障树
        result = await self.session.execute(
            select(FaultTree)
            .where(FaultTree.status == "active")
            .order_by(FaultTree.updated_at.desc())
        )
        tree = result.scalars().first()

        if tree:
            logger.info(f"设备 {device_id} 使用回退故障树: {tree.id}")
            return tree.id

        logger.warning(f"设备 {device_id} (类型: {device_type}) 没有可用的故障树")
        return None

    async def load_fault_tree_to_networkx(self, tree_id: int) -> nx.DiGraph:
        """加载故障树到 NetworkX 图结构

        边方向: child → parent (数据库存储 parent → child, 需要反转)
        """
        cached_graph = await self.cache.get(tree_id)
        if cached_graph is not None:
            return cached_graph

        graph = nx.DiGraph()

        # 加载节点
        result = await self.session.execute(
            select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
        )
        nodes = result.scalars().all()

        for node in nodes:
            # 解析 config JSON (可能包含 threshold 等配置)
            config = {}
            if node.config:
                try:
                    config = json.loads(node.config) if isinstance(node.config, str) else node.config
                except (json.JSONDecodeError, TypeError):
                    pass

            graph.add_node(
                node.id,
                name=node.name,
                node_type=node.node_type,
                gate_type=node.gate_type,
                evidence_point_id=node.evidence_point_id,
                prior_probability=node.prior_probability,
                threshold=config.get("threshold"),
                config=config,
                probability=0.0,  # 初始概率
            )

        # 加载边 (反转方向: child → parent)
        result = await self.session.execute(
            select(FaultTreeEdge).where(FaultTreeEdge.tree_id == tree_id)
        )
        edges = result.scalars().all()

        for edge in edges:
            graph.add_edge(edge.child_node_id, edge.parent_node_id)

        # 验证故障树结构
        warnings = await validate_fault_tree(graph)
        if warnings:
            logger.warning(f"故障树 {tree_id} 结构警告: {warnings}")

        await self.cache.put(tree_id, graph)

        logger.info(f"故障树 {tree_id} 已加载: {len(nodes)} 节点, {len(edges)} 边")
        return graph

    async def collect_evidence(
        self, graph: nx.DiGraph, time_window_minutes: int = 5
    ) -> Dict[int, EvidenceItem]:
        """并发收集叶节点证据

        超时保护:
        - 总超时: 3 秒
        - 单个证据超时: 1 秒
        """
        # 叶节点: 入度为 0 的节点 (在 child→parent 方向下没有子节点指向它)
        leaf_nodes = [node for node in graph.nodes() if graph.in_degree(node) == 0]
        evidence: Dict[int, EvidenceItem] = {}

        async def collect_single_evidence(node_id: int) -> None:
            """收集单个节点的证据"""
            try:
                node_data = graph.nodes[node_id]
                point_id = node_data.get("evidence_point_id")

                if point_id is None:
                    # 没有关联点位,使用先验概率
                    evidence[node_id] = EvidenceItem(
                        point_id=None,
                        point_name=node_data.get("name"),
                        status="error",
                    )
                    return

                # 查询时间窗口内的历史数据
                end_time = datetime.now()
                start_time = end_time - timedelta(minutes=time_window_minutes)

                result = await self.session.execute(
                    select(PointHistory)
                    .where(PointHistory.point_id == point_id)
                    .where(PointHistory.recorded_at >= start_time)
                    .where(PointHistory.recorded_at <= end_time)
                    .order_by(PointHistory.recorded_at.desc())
                )
                history = result.scalars().all()

                if not history:
                    evidence[node_id] = EvidenceItem(
                        point_id=point_id,
                        point_name=node_data.get("name"),
                        status="timeout",
                    )
                    return

                # 聚合策略: AVG (温度), MAX (电压), ANY (开关)
                point_name = node_data.get("name", "")
                if "温度" in point_name or "temp" in point_name.lower():
                    value = sum(h.value for h in history) / len(history)
                elif "电压" in point_name or "voltage" in point_name.lower():
                    value = max(h.value for h in history)
                elif "开关" in point_name or "switch" in point_name.lower():
                    value = 1.0 if any(h.value > 0.5 for h in history) else 0.0
                else:
                    value = history[0].value

                threshold = node_data.get("threshold")
                status = "abnormal" if threshold and value > threshold else "normal"

                evidence[node_id] = EvidenceItem(
                    point_id=point_id,
                    point_name=node_data.get("name"),
                    value=value,
                    threshold=threshold,
                    timestamp=history[0].recorded_at,
                    status=status,
                )

            except asyncio.TimeoutError:
                evidence[node_id] = EvidenceItem(
                    point_id=graph.nodes[node_id].get("evidence_point_id"),
                    point_name=graph.nodes[node_id].get("name"),
                    status="timeout",
                )
            except Exception as e:
                logger.error(f"收集节点 {node_id} 证据失败: {e}")
                evidence[node_id] = EvidenceItem(
                    point_id=graph.nodes[node_id].get("evidence_point_id"),
                    point_name=graph.nodes[node_id].get("name"),
                    status="error",
                )

        # 并发收集所有证据,总超时 3 秒
        tasks = [
            asyncio.wait_for(collect_single_evidence(node_id), timeout=1.0)
            for node_id in leaf_nodes
        ]

        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("证据收集总超时 (3秒)")

        logger.info(f"收集了 {len(evidence)} 个叶节点证据")
        return evidence

    def compute_leaf_probability(self, evidence: EvidenceItem) -> float:
        """计算叶节点概率

        映射规则:
        - status = 'abnormal': sigmoid((value - threshold) / threshold * 10)
        - status = 'normal': 0.01 (基线概率)
        - status = 'timeout' / 'error': 0.5 (不确定性)
        """
        if evidence.status == "abnormal":
            if evidence.value is not None and evidence.threshold is not None and evidence.threshold != 0:
                deviation = (evidence.value - evidence.threshold) / evidence.threshold
                x = deviation * 10.0
                return sigmoid_stable(x)
            else:
                return 0.5

        elif evidence.status == "normal":
            return 0.01

        else:  # timeout, error
            return 0.5

    async def propagate_probabilities(
        self, graph: nx.DiGraph, evidence: Dict[int, EvidenceItem]
    ) -> None:
        """从叶到根传播概率

        使用拓扑排序确保子节点先于父节点计算
        """
        # 初始化叶节点概率
        for node_id, ev in evidence.items():
            if node_id in graph.nodes:
                graph.nodes[node_id]["probability"] = self.compute_leaf_probability(ev)

        # 对没有证据的叶节点使用先验概率
        for node_id in graph.nodes():
            if graph.in_degree(node_id) == 0 and node_id not in evidence:
                graph.nodes[node_id]["probability"] = graph.nodes[node_id].get("prior_probability", 0.5)

        try:
            topo_order = list(nx.topological_sort(graph))
        except nx.NetworkXError as e:
            logger.error(f"拓扑排序失败 (图可能有环): {e}")
            return

        for node_id in topo_order:
            node_data = graph.nodes[node_id]
            gate_type = node_data.get("gate_type")

            # 跳过叶节点 (已初始化)
            if graph.in_degree(node_id) == 0:
                continue

            # 获取子节点概率
            child_nodes = list(graph.predecessors(node_id))
            child_probs = [graph.nodes[child]["probability"] for child in child_nodes]

            if gate_type == "OR":
                prob = or_gate(child_probs)
            elif gate_type == "AND":
                prob = and_gate(child_probs)
            else:
                logger.warning(f"节点 {node_id} 的 gate_type 未知: {gate_type}, 使用 OR 门")
                prob = or_gate(child_probs)

            graph.nodes[node_id]["probability"] = prob

        logger.debug("概率传播完成")

    async def extract_root_cause_path(self, graph: nx.DiGraph, root_node_id: int) -> List[int]:
        """提取根因路径

        从根节点开始,每次选择概率最高的子节点,直到叶节点
        """
        path = [root_node_id]
        current_node = root_node_id

        while True:
            child_nodes = list(graph.predecessors(current_node))

            if not child_nodes:
                break

            best_child = max(
                child_nodes, key=lambda node: graph.nodes[node]["probability"]
            )
            path.append(best_child)
            current_node = best_child

        logger.debug(f"根因路径: {path}")
        return path

    async def diagnose_l2(
        self, device_id: int, device_type: str, time_window_minutes: int = 5
    ) -> Optional[DiagnosisContext]:
        """L2 故障树推理主流程

        返回 DiagnosisContext 供 L3 引擎使用
        """
        start_time = time.time()
        context = DiagnosisContext(
            device_id=device_id,
            device_type=device_type,
            fault_tree_id=0,
            fault_tree_name="",
            root_node_probability=0.0,
            root_cause_path=[],
            evidence={},
        )

        try:
            # 1. 选择故障树
            tree_id = await self.select_fault_tree(device_id, device_type)
            if tree_id is None:
                context.errors.append("没有可用的故障树")
                return context

            context.fault_tree_id = tree_id

            # 获取故障树名称
            result = await self.session.execute(
                select(FaultTree).where(FaultTree.id == tree_id)
            )
            tree = result.scalars().first()
            if tree:
                context.fault_tree_name = tree.name

            # 2. 加载故障树
            graph = await self.load_fault_tree_to_networkx(tree_id)

            # 3. 收集证据
            evidence_start = time.time()
            evidence = await self.collect_evidence(graph, time_window_minutes)
            context.evidence_collection_time_ms = (time.time() - evidence_start) * 1000
            context.evidence = evidence

            # 检查证据质量
            timeout_count = sum(1 for ev in evidence.values() if ev.status == "timeout")
            error_count = sum(1 for ev in evidence.values() if ev.status == "error")

            if evidence and (timeout_count + error_count > len(evidence) * 0.5):
                context.warnings.append(f"证据质量差: {timeout_count} 超时, {error_count} 错误")
                context.degraded = True

            # 4. 传播概率
            propagation_start = time.time()
            await self.propagate_probabilities(graph, evidence)
            context.propagation_time_ms = (time.time() - propagation_start) * 1000

            # 5. 提取根因路径
            path_start = time.time()
            root_nodes = [node for node in graph.nodes() if graph.out_degree(node) == 0]

            if not root_nodes:
                context.errors.append("故障树没有根节点")
                return context

            root_node_id = root_nodes[0]
            context.root_node_probability = graph.nodes[root_node_id]["probability"]
            context.root_cause_path = await self.extract_root_cause_path(graph, root_node_id)
            context.path_extraction_time_ms = (time.time() - path_start) * 1000

            # 6. 释放缓存引用
            await self.cache.release(tree_id)

        except Exception as e:
            logger.error(f"L2 推理失败: {e}", exc_info=True)
            context.errors.append(f"推理异常: {str(e)}")
            context.degraded = True

        finally:
            context.inference_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"L2 推理完成: 设备 {device_id}, 根节点概率 {context.root_node_probability:.3f}, "
            f"耗时 {context.inference_time_ms:.1f}ms"
        )

        return context
