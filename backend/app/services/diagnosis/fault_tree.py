"""
L2 故障树推理引擎

基于 NetworkX 图结构实现故障树因果推理，支持:
- 故障树选择与证据收集
- 概率传播（OR/AND 门）
- 根因路径提取
- 异常容错与性能优化
"""

import asyncio
import copy
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

# Sigmoid 默认斜率参数
DEFAULT_SIGMOID_K = 2.0

# L2 推理总超时（秒）— P0-2 修复
L2_INFERENCE_TIMEOUT = 10.0


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
    alarm_type: str
    fault_tree_id: int
    fault_tree_name: str
    root_node_probability: float
    root_cause_path: List[int]  # 节点 ID 列表
    evidence: Dict[int, EvidenceItem]  # node_id → EvidenceItem

    # L3 引擎复用数据
    graph: Optional["nx.DiGraph"] = None  # 修正：使用正确类型标注
    node_probabilities: Dict[int, float] = field(default_factory=dict)
    leaf_probabilities: Dict[int, float] = field(default_factory=dict)

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
    """故障树缓存管理器 - 支持引用计数和自动清理

    注意: get() 返回深拷贝, 避免并发修改共享图对象
    """

    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        self._cache: Dict[int, nx.DiGraph] = {}
        self._ref_count: Dict[int, int] = {}
        self._last_access: Dict[int, float] = {}
        self._pending_delete: set = set()  # 待删除标记（第二轮审查问题 14）
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    async def get(self, tree_id: int) -> Optional[nx.DiGraph]:
        """获取缓存的故障树 (返回深拷贝, 保证并发安全)"""
        async with self._lock:
            if tree_id in self._cache and tree_id not in self._pending_delete:
                self._ref_count[tree_id] += 1
                self._last_access[tree_id] = time.time()
                logger.debug(f"故障树 {tree_id} 缓存命中, 引用计数: {self._ref_count[tree_id]}")
                return copy.deepcopy(self._cache[tree_id])
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
        """释放故障树引用

        如果 ref_count 降为 0 且标记为 pending_delete，自动删除
        """
        async with self._lock:
            if tree_id in self._ref_count:
                self._ref_count[tree_id] -= 1
                logger.debug(f"故障树 {tree_id} 引用释放, 剩余引用: {self._ref_count[tree_id]}")

                # pending_delete 且引用计数归零，自动删除（第二轮审查问题 14）
                if self._ref_count[tree_id] <= 0 and tree_id in self._pending_delete:
                    self._pending_delete.discard(tree_id)
                    if tree_id in self._cache:
                        del self._cache[tree_id]
                    if tree_id in self._ref_count:
                        del self._ref_count[tree_id]
                    if tree_id in self._last_access:
                        del self._last_access[tree_id]
                    logger.info(f"故障树 {tree_id} 已从缓存中删除 (pending_delete 释放)")

    async def invalidate(self, tree_id: int) -> None:
        """使指定故障树缓存失效（用于版本变更）

        如果 ref_count > 0，标记为 pending_delete
        如果 ref_count == 0，立即删除
        """
        async with self._lock:
            if tree_id not in self._cache:
                return

            if self._ref_count.get(tree_id, 0) > 0:
                self._pending_delete.add(tree_id)
                logger.info(f"故障树 {tree_id} 标记为 pending_delete (引用计数: {self._ref_count[tree_id]})")
            else:
                del self._cache[tree_id]
                self._ref_count.pop(tree_id, None)
                self._last_access.pop(tree_id, None)
                logger.info(f"故障树 {tree_id} 已从缓存中立即删除 (invalidate)")

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

    # Clamp 子节点概率到 [0, 1]（第二轮审查要求）
    child_probs = [max(0.0, min(1.0, p)) for p in child_probs]

    product = 1.0
    for p in child_probs:
        product *= (1.0 - p)

    return 1.0 - product


def and_gate(child_probs: List[float]) -> float:
    """AND 门概率计算: P = ∏ P(child_i)"""
    if not child_probs:
        return 0.0

    # Clamp 子节点概率到 [0, 1]（第二轮审查要求）
    child_probs = [max(0.0, min(1.0, p)) for p in child_probs]

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
    - 孤立节点检查
    - 叶节点证据关联检查
    """
    warnings = []

    # 检查是否为 DAG（不立即返回，继续收集其他警告 - 第二轮审查问题 9）
    if not nx.is_directed_acyclic_graph(graph):
        warnings.append("故障树包含环路,不是有效的 DAG")

    # 根节点: 出度为 0 的节点 (child→parent 边方向下, 根节点没有出边)
    root_nodes = [node for node in graph.nodes() if graph.out_degree(node) == 0]
    if len(root_nodes) == 0:
        warnings.append("故障树没有根节点")
    elif len(root_nodes) > 1:
        warnings.append(f"故障树有多个根节点: {root_nodes}")

    # 孤立节点检查
    isolated = list(nx.isolates(graph))
    if isolated:
        warnings.append(f"故障树有孤立节点: {isolated}")

    for node_id in graph.nodes():
        node_data = graph.nodes[node_id]
        if "gate_type" not in node_data:
            warnings.append(f"节点 {node_id} 缺少 gate_type 属性")
        elif node_data["gate_type"] not in ("OR", "AND", "LEAF", None):
            warnings.append(f"节点 {node_id} 的 gate_type 无效: {node_data['gate_type']}")

    # 叶节点证据关联检查
    leaf_nodes = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    for leaf in leaf_nodes:
        if graph.nodes[leaf].get("evidence_point_id") is None:
            warnings.append(f"叶节点 {leaf} 没有关联证据点位")

    return warnings


class FaultTreeInferenceEngine:
    """L2 故障树推理引擎"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = _fault_tree_cache

    async def select_fault_tree(
        self, device_type: str, alarm_type: Optional[str] = None
    ) -> Optional[int]:
        """选择适用的故障树

        优先级 (数值越小越优先):
        1. device_type + alarm_type 精确匹配
        2. device_type 匹配 (alarm_type 为 NULL)
        3. 通用映射 (device_type = 'generic')
        4. 未找到时返回 None（不回退到任意故障树，避免误匹配）
        """
        # 1. 精确匹配 device_type + alarm_type
        if alarm_type:
            result = await self.session.execute(
                select(FaultTreeDeviceMapping)
                .join(FaultTree, FaultTree.id == FaultTreeDeviceMapping.tree_id)
                .where(FaultTreeDeviceMapping.device_type == device_type)
                .where(FaultTreeDeviceMapping.alarm_type == alarm_type)
                .where(FaultTree.status == "active")
                .order_by(
                    FaultTreeDeviceMapping.priority.asc(),
                    FaultTreeDeviceMapping.tree_id.desc(),
                )
            )
            mapping = result.scalars().first()
            if mapping:
                logger.info(
                    f"精确匹配 device_type={device_type} alarm_type={alarm_type}, "
                    f"使用故障树: {mapping.tree_id}"
                )
                return mapping.tree_id

        # 2. 仅 device_type 匹配
        result = await self.session.execute(
            select(FaultTreeDeviceMapping)
            .join(FaultTree, FaultTree.id == FaultTreeDeviceMapping.tree_id)
            .where(FaultTreeDeviceMapping.device_type == device_type)
            .where(FaultTreeDeviceMapping.alarm_type == None)  # noqa: E711
            .where(FaultTree.status == "active")
            .order_by(
                FaultTreeDeviceMapping.priority.asc(),
                FaultTreeDeviceMapping.tree_id.desc(),
            )
        )
        mapping = result.scalars().first()
        if mapping:
            logger.info(f"设备类型 {device_type} 匹配映射, 使用故障树: {mapping.tree_id}")
            return mapping.tree_id

        # 3. 通用映射
        result = await self.session.execute(
            select(FaultTreeDeviceMapping)
            .join(FaultTree, FaultTree.id == FaultTreeDeviceMapping.tree_id)
            .where(FaultTreeDeviceMapping.device_type == "generic")
            .where(FaultTree.status == "active")
            .order_by(
                FaultTreeDeviceMapping.priority.asc(),
                FaultTreeDeviceMapping.tree_id.desc(),
            )
        )
        mapping = result.scalars().first()
        if mapping:
            logger.info(f"使用通用映射故障树: {mapping.tree_id}")
            return mapping.tree_id

        # 未找到故障树，返回 None（第二轮审查问题 15：不回退到任意故障树）
        logger.warning(f"没有适用的故障树: device_type={device_type}, alarm_type={alarm_type}")
        return None

    async def load_fault_tree_to_networkx(self, tree_id: int) -> nx.DiGraph:
        """加载故障树到 NetworkX 图结构

        边方向: child → parent (数据库存储 parent → child, 需要反转)
        注意: 返回的图是缓存的深拷贝, 可安全修改
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
            # 解析 config JSON (可能包含 threshold, sigmoid_k 等配置)
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
                sigmoid_k=config.get("sigmoid_k", DEFAULT_SIGMOID_K),
                config=config,
                probability=0.0,
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
        # put 存入原图, 返回深拷贝供调用方使用
        return copy.deepcopy(graph)

    async def collect_evidence(
        self, graph: nx.DiGraph, time_window_minutes: int = 5
    ) -> Dict[int, EvidenceItem]:
        """并发收集叶节点证据

        超时保护:
        - 总超时: 3 秒
        - 单个证据超时: 1 秒
        """
        leaf_nodes = [node for node in graph.nodes() if graph.in_degree(node) == 0]
        evidence: Dict[int, EvidenceItem] = {}

        async def collect_single_evidence(node_id: int) -> None:
            """收集单个节点的证据"""
            node_data = graph.nodes[node_id]
            try:
                point_id = node_data.get("evidence_point_id")

                if point_id is None:
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

                # 聚合策略：基于 point_type 字段（第二轮审查问题 5）
                point_type = node_data.get("config", {}).get("point_type")
                valid_values = [h.value for h in history if h.value is not None]

                if not valid_values:
                    value = 0.0
                elif point_type == "temperature" or point_type == "gauge":
                    # AVG（平均值）
                    value = sum(valid_values) / len(valid_values)
                elif point_type == "voltage":
                    # MAX（最大值）
                    value = max(valid_values)
                elif point_type == "switch":
                    # ANY（任意一次 > 0.5 则为 1.0）
                    value = 1.0 if any(v > 0.5 for v in valid_values) else 0.0
                elif point_type == "counter":
                    # DIFF（时间窗口内最后一个值减第一个值，即累计增量）
                    if len(valid_values) >= 2:
                        # history 按 recorded_at DESC 排序，所以 [0] 是最新的，[-1] 是最早的
                        value = valid_values[0] - valid_values[-1]
                    else:
                        value = valid_values[0]
                else:
                    # 其他或 point_type 为 NULL：LAST（取最新值）
                    value = valid_values[0]

                threshold = node_data.get("threshold")
                status = "abnormal" if threshold is not None and abs(value) > abs(threshold) else "normal"

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
                    point_id=node_data.get("evidence_point_id"),
                    point_name=node_data.get("name"),
                    status="timeout",
                )
            except Exception as e:
                logger.error(f"收集节点 {node_id} 证据失败: {e}")
                evidence[node_id] = EvidenceItem(
                    point_id=node_data.get("evidence_point_id"),
                    point_name=node_data.get("name"),
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

        # Story 25.7: 集成多传感器融合和趋势预警
        try:
            await self._integrate_sensor_fusion_and_trends(graph, evidence)
        except Exception as e:
            logger.error(f"多传感器融合和趋势预警集成失败: {e}", exc_info=True)

        return evidence

    async def _integrate_sensor_fusion_and_trends(
        self,
        graph: nx.DiGraph,
        evidence: Dict[int, EvidenceItem]
    ) -> None:
        """集成多传感器融合和趋势预警到证据收集 - Story 25.7"""
        try:
            from app.services.diagnosis.sensor_fusion_service import get_sensor_fusion_service
            from app.services.diagnosis.trend_analysis_service import get_trend_analysis_service

            # 1. 多传感器融合（需要 zone_id）
            # 从图中提取 zone_id（如果有）
            zone_id = None
            for node_id in graph.nodes():
                node_data = graph.nodes[node_id]
                if node_data.get("zone_id"):
                    zone_id = node_data["zone_id"]
                    break

            if zone_id:
                fusion_service = get_sensor_fusion_service(self.session)

                # 温度标准差证据
                temp_fusion = await fusion_service.calculate_temperature_variance(zone_id)
                # 保存融合记录到数据库
                await fusion_service.save_fusion_record(temp_fusion)

                if temp_fusion.is_evidence:
                    # 查找对应的故障树节点（如"气流不均匀"节点）
                    for node_id in graph.nodes():
                        node_data = graph.nodes[node_id]
                        if node_data.get("evidence_type") == "airflow_uneven":
                            # 添加融合证据
                            evidence[node_id] = EvidenceItem(
                                point_id=None,
                                point_name=node_data.get("name", "气流不均匀"),
                                value=temp_fusion.std_dev,
                                threshold=None,
                                timestamp=datetime.now(),
                                status="abnormal"
                            )
                            # 直接设置节点概率
                            graph.nodes[node_id]["fusion_probability"] = temp_fusion.probability
                            logger.info(f"添加气流不均匀证据: 概率 {temp_fusion.probability}")
                            break

                # 压差传感器证据
                pressure_fusion = await fusion_service.check_differential_pressure(zone_id)
                if pressure_fusion:
                    # 保存融合记录到数据库
                    await fusion_service.save_fusion_record(pressure_fusion)

                    if pressure_fusion.is_evidence:
                        for node_id in graph.nodes():
                            node_data = graph.nodes[node_id]
                            if node_data.get("evidence_type") == "air_supply_abnormal":
                                evidence[node_id] = EvidenceItem(
                                    point_id=None,
                                    point_name=node_data.get("name", "送风系统异常"),
                                    value=None,
                                    threshold=None,
                                    timestamp=datetime.now(),
                                    status="abnormal"
                                )
                                graph.nodes[node_id]["fusion_probability"] = pressure_fusion.probability
                                logger.info(f"添加送风系统异常证据: 概率 {pressure_fusion.probability}")
                                break

            # 2. 趋势预警证据
            trend_service = get_trend_analysis_service(self.session)
            recent_warnings = await trend_service.get_recent_warnings(zone_id=zone_id, hours=24)

            if recent_warnings:
                # 趋势预警作为补充证据，提升相关节点概率
                for warning in recent_warnings:
                    for node_id in graph.nodes():
                        node_data = graph.nodes[node_id]
                        if node_data.get("evidence_point_id") == warning.point_id:
                            # 如果节点已有证据，提升其概率权重
                            if node_id in evidence:
                                # 标记有趋势预警
                                graph.nodes[node_id]["has_trend_warning"] = True
                                graph.nodes[node_id]["trend_change"] = warning.total_change
                                logger.info(f"节点 {node_id} 有趋势预警，变化量: {warning.total_change}")
                            break

        except ImportError as e:
            logger.warning(f"多传感器融合或趋势分析服务未安装: {e}")
        except Exception as e:
            logger.error(f"集成多传感器融合和趋势预警失败: {e}", exc_info=True)

    def compute_leaf_probability(self, node_data: dict, evidence: EvidenceItem) -> float:
        """计算叶节点概率

        异常情况: P = prior + (1.0 - prior) × sigmoid(k × (value - threshold))
        正常情况: P = prior × sigmoid(k × (threshold - value))

        Story 25.7: 支持融合证据和趋势预警
        """
        # Story 25.7: 如果有融合概率，直接使用
        if "fusion_probability" in node_data:
            return node_data["fusion_probability"]

        prior = node_data.get("prior_probability", 0.5)
        k = node_data.get("sigmoid_k", DEFAULT_SIGMOID_K)

        # 前置条件检查（第二轮审查要求）
        if evidence.value is None or evidence.threshold is None:
            return prior

        if evidence.status == "abnormal":
            deviation = evidence.value - evidence.threshold
            sigmoid_value = sigmoid_stable(k * deviation)
            prob = prior + (1.0 - prior) * sigmoid_value

            # Story 25.7: 如果有趋势预警，根据变化量动态调整权重
            if node_data.get("has_trend_warning"):
                trend_change = node_data.get("trend_change", 0)
                # 变化量越大，权重越高，范围 0.05-0.15
                weight_boost = min(0.05 + abs(trend_change) * 0.02, 0.15)
                prob = min(prob + weight_boost, 0.95)  # 不超过 0.95
                logger.debug(f"节点有趋势预警，概率提升 {weight_boost:.3f} → {prob:.3f}")

            return prob

        elif evidence.status == "normal":
            # 正常情况使用不同公式（第二轮审查问题 6）
            deviation = evidence.threshold - evidence.value
            sigmoid_value = sigmoid_stable(k * deviation)
            return prior * sigmoid_value

        else:  # timeout, error — 不确定性, 使用先验概率
            return prior

    async def propagate_probabilities(
        self, graph: nx.DiGraph, evidence: Dict[int, EvidenceItem]
    ) -> Dict[int, float]:
        """从叶到根传播概率

        使用拓扑排序确保子节点先于父节点计算。
        返回所有节点的概率字典。
        """
        node_probs: Dict[int, float] = {}

        # 初始化叶节点概率
        for node_id in graph.nodes():
            if graph.in_degree(node_id) == 0:  # 叶节点
                node_data = graph.nodes[node_id]
                if node_id in evidence:
                    prob = self.compute_leaf_probability(node_data, evidence[node_id])
                else:
                    prob = node_data.get("prior_probability", 0.5)
                graph.nodes[node_id]["probability"] = prob
                node_probs[node_id] = prob

        try:
            topo_order = list(nx.topological_sort(graph))
        except nx.NetworkXError as e:
            logger.error(f"拓扑排序失败 (图可能有环): {e}")
            return node_probs

        for node_id in topo_order:
            # 跳过叶节点 (已初始化)
            if graph.in_degree(node_id) == 0:
                continue

            node_data = graph.nodes[node_id]
            gate_type = node_data.get("gate_type")

            child_nodes = list(graph.predecessors(node_id))
            child_probs = [graph.nodes[child].get("probability", 0.0) for child in child_nodes]

            if gate_type == "OR":
                prob = or_gate(child_probs)
            elif gate_type == "AND":
                prob = and_gate(child_probs)
            else:
                logger.warning(f"节点 {node_id} 的 gate_type 未知: {gate_type}, 使用 OR 门")
                prob = or_gate(child_probs)

            graph.nodes[node_id]["probability"] = prob
            node_probs[node_id] = prob

        logger.debug("概率传播完成")
        return node_probs

    async def extract_root_cause_path(self, graph: nx.DiGraph, root_node_id: int) -> List[int]:
        """提取根因路径

        从根节点开始向下回溯:
        - OR 门: 选概率最大的子节点
        - AND 门: 选偏离先验最大的子节点 (概率与先验差值最大)
        """
        path = [root_node_id]
        current_node = root_node_id
        visited = set()

        while True:
            if current_node in visited:
                logger.warning(f"根因路径检测到环，节点 {current_node}，终止回溯")
                break
            visited.add(current_node)
            child_nodes = list(graph.predecessors(current_node))

            if not child_nodes:
                break

            gate_type = graph.nodes[current_node].get("gate_type")

            if gate_type == "AND":
                # AND 门：优先正向偏离策略（第二轮审查问题 1）
                # 1. 优先选择概率高于先验的子节点
                positive_deviations = [
                    n for n in child_nodes
                    if graph.nodes[n]["probability"] > graph.nodes[n].get("prior_probability", 0.5)
                ]
                if positive_deviations:
                    # 2. 多个正向偏离，选偏离最大的
                    best_child = max(
                        positive_deviations,
                        key=lambda n: (
                            graph.nodes[n]["probability"]
                            - graph.nodes[n].get("prior_probability", 0.5)
                        ),
                    )
                else:
                    # 3. 所有子节点都低于或等于先验，选概率最高的
                    best_child = max(
                        child_nodes, key=lambda n: graph.nodes[n]["probability"]
                    )
            else:
                # OR 门 / 默认: 选概率最大的子节点
                best_child = max(
                    child_nodes, key=lambda n: graph.nodes[n]["probability"]
                )

            path.append(best_child)
            current_node = best_child

        logger.debug(f"根因路径: {path}")
        return path

    async def diagnose_l2(
        self,
        device_id: int,
        device_type: str,
        alarm_type: Optional[str] = None,
        time_window_minutes: int = 5,
    ) -> DiagnosisContext:
        """L2 故障树推理主流程（带超时保护）— P0-2 修复"""
        try:
            # 整个推理流程设置 10 秒超时
            return await asyncio.wait_for(
                self._diagnose_l2_impl(device_id, device_type, alarm_type, time_window_minutes),
                timeout=L2_INFERENCE_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"L2 推理超时 ({L2_INFERENCE_TIMEOUT}s): 设备 {device_id}")
            context = DiagnosisContext(
                device_id=device_id,
                device_type=device_type,
                alarm_type=alarm_type or "",
                fault_tree_id=0,
                fault_tree_name="",
                root_node_probability=0.0,
                root_cause_path=[],
                evidence={},
            )
            context.errors.append(f"推理超时 ({L2_INFERENCE_TIMEOUT}s)")
            context.degraded = True
            return context

    async def _diagnose_l2_impl(
        self,
        device_id: int,
        device_type: str,
        alarm_type: Optional[str],
        time_window_minutes: int,
    ) -> DiagnosisContext:
        """L2 故障树推理实现（原 diagnose_l2 逻辑）"""
        start_time = time.time()
        context = DiagnosisContext(
            device_id=device_id,
            device_type=device_type,
            alarm_type=alarm_type or "",
            fault_tree_id=0,
            fault_tree_name="",
            root_node_probability=0.0,
            root_cause_path=[],
            evidence={},
        )

        tree_id = None
        try:
            # 1. 选择故障树
            tree_id = await self.select_fault_tree(device_type, alarm_type)
            if tree_id is None:
                context.errors.append("没有适用的故障树")
                return context

            context.fault_tree_id = tree_id

            # 获取故障树名称
            result = await self.session.execute(
                select(FaultTree).where(FaultTree.id == tree_id)
            )
            tree = result.scalars().first()
            if tree:
                context.fault_tree_name = tree.name

            # 2. 加载故障树 (返回深拷贝, 可安全修改)
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
            node_probs = await self.propagate_probabilities(graph, evidence)
            context.propagation_time_ms = (time.time() - propagation_start) * 1000
            context.node_probabilities = node_probs

            # 记录叶节点概率
            context.leaf_probabilities = {
                nid: prob for nid, prob in node_probs.items()
                if graph.in_degree(nid) == 0
            }

            # 5. 提取根因路径
            path_start = time.time()
            root_nodes = [node for node in graph.nodes() if graph.out_degree(node) == 0]

            if not root_nodes:
                context.errors.append("故障树没有根节点")
                return context

            if len(root_nodes) > 1:
                logger.warning(f"故障树存在 {len(root_nodes)} 个根节点，使用第一个: {root_nodes[0]}")

            root_node_id = root_nodes[0]
            context.root_node_probability = graph.nodes[root_node_id]["probability"]
            context.root_cause_path = await self.extract_root_cause_path(graph, root_node_id)
            context.path_extraction_time_ms = (time.time() - path_start) * 1000

            # 6. 冗余检测 (Story 25.4)
            # 如果故障涉及配电设备，检查是否有活跃的冗余备用路径
            from app.services.diagnosis.redundancy_service import check_redundancy_backup
            from app.models.energy import PowerDevice

            # 查询设备是否为配电设备
            result = await self.session.execute(
                select(PowerDevice).where(PowerDevice.id == device_id)
            )
            power_device = result.scalar_one_or_none()

            if power_device:
                # 检查冗余备用路径
                redundancy_status = await check_redundancy_backup(device_id, self.session)

                if redundancy_status.has_backup:
                    # 有活跃备用路径，降低故障影响等级
                    # 建议的等级降级映射（记录到 warnings，不修改告警表）
                    # critical → major, major → warning, warning/info 不降级
                    suggested_downgrade = {
                        "critical": "major",
                        "major": "warning",
                        "warning": "warning",
                        "info": "info"
                    }

                    # 记录到 context 的 warnings 中
                    context.warnings.append(
                        f"已有备用路径自动切换（冗余类型: {redundancy_status.redundancy_type}，"
                        f"备用设备: {redundancy_status.backup_devices}）"
                    )

                    # 降低根节点概率（模拟故障等级降低）
                    # 原概率 * 0.7（降低 30%）
                    original_prob = context.root_node_probability
                    context.root_node_probability *= 0.7

                    logger.info(
                        f"设备 {device_id} 有冗余备用路径，故障概率从 {original_prob:.3f} 降低至 {context.root_node_probability:.3f}"
                    )

            # 保存图引用供 L3 引擎使用
            context.graph = graph

        except asyncio.TimeoutError:
            # 超时异常（第二轮审查问题 2、7）
            logger.error(f"L2 推理超时: 设备 {device_id}")
            context.errors.append("推理超时，已终止")
            context.degraded = True

        except nx.NetworkXError as e:
            # NetworkX 图结构异常（第二轮审查问题 7）
            logger.error(f"L2 推理图结构异常: {e}")
            context.errors.append(f"图结构异常: {str(e)}")

        except Exception as e:
            # 未知异常：记录 ERROR 级别日志，重新抛出（第二轮审查问题 7）
            from sqlalchemy.exc import DatabaseError, OperationalError
            if isinstance(e, (DatabaseError, OperationalError)):
                logger.error(f"L2 推理数据库错误: {e}")
                context.errors.append(f"数据库错误: {str(e)}")
                context.degraded = True
            else:
                logger.error(f"L2 推理未知异常: {e}", exc_info=True)
                raise

        finally:
            context.inference_time_ms = (time.time() - start_time) * 1000
            # 无论成功或失败都释放缓存引用
            if tree_id is not None:
                await self.cache.release(tree_id)

        logger.info(
            f"L2 推理完成: 设备 {device_id}, 根节点概率 {context.root_node_probability:.3f}, "
            f"耗时 {context.inference_time_ms:.1f}ms"
        )

        return context
