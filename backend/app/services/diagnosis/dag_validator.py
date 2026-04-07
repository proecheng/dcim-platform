"""
故障树 DAG 验证器 - Story 24.3
"""

import networkx as nx
from typing import List, Dict, Tuple


class DAGValidator:
    """故障树 DAG 验证器"""

    @staticmethod
    def validate(nodes: List[Dict], edges: List[Dict]) -> Tuple[bool, str]:
        """
        验证故障树是否为有效的 DAG

        Args:
            nodes: 节点列表 [{"id": 1, "node_type": "root", "gate_type": "AND", ...}, ...]
            edges: 边列表 [{"parent_node_id": 1, "child_node_id": 2}, ...]

        Returns:
            (is_valid, error_message)
        """
        if not nodes:
            return False, "故障树至少需要一个节点"

        # 构建 NetworkX 有向图
        G = nx.DiGraph()

        # 添加节点
        node_ids = set()
        root_nodes = []
        leaf_nodes = []
        intermediate_nodes = []

        for node in nodes:
            if "id" not in node:
                return False, "节点缺少 id 字段"
            node_id = node["id"]
            node_ids.add(node_id)
            G.add_node(node_id, **node)

            node_type = node.get("node_type")
            if node_type == "root":
                root_nodes.append(node_id)
            elif node_type == "leaf":
                leaf_nodes.append(node_id)
            elif node_type == "intermediate":
                intermediate_nodes.append(node_id)

        # 检查根节点数量
        if len(root_nodes) == 0:
            return False, "故障树必须有一个根节点"
        if len(root_nodes) > 1:
            return False, f"故障树只能有一个根节点，当前有 {len(root_nodes)} 个"

        # 添加边
        for edge in edges:
            if "parent_node_id" not in edge or "child_node_id" not in edge:
                return False, "边缺少 parent_node_id 或 child_node_id 字段"
            parent_id = edge["parent_node_id"]
            child_id = edge["child_node_id"]

            # 检查端点是否存在
            if parent_id not in node_ids:
                return False, f"边的父节点 {parent_id} 不存在"
            if child_id not in node_ids:
                return False, f"边的子节点 {child_id} 不存在"

            # 检查自环
            if parent_id == child_id:
                return False, f"检测到自环: 节点 {parent_id} 指向自己"

            G.add_edge(parent_id, child_id)

        # 检查是否为 DAG（无环）
        if not nx.is_directed_acyclic_graph(G):
            # 找出环
            try:
                cycle = nx.find_cycle(G)
                cycle_str = " → ".join([str(u) for u, v in cycle] + [str(cycle[0][0])])
                return False, f"检测到环: {cycle_str}"
            except nx.NetworkXNoCycle:
                # 理论上不应该到这里，但如果到了说明 is_directed_acyclic_graph 有误判
                return False, "检测到环，但无法定位具体环路"

        # 检查节点连通性
        root_id = root_nodes[0]

        # 根节点：无入边，有出边
        if G.in_degree(root_id) > 0:
            return False, f"根节点 {root_id} 不应有入边"
        if G.out_degree(root_id) == 0:
            return False, f"根节点 {root_id} 必须有出边"

        # 叶节点：有入边，无出边
        for leaf_id in leaf_nodes:
            if G.in_degree(leaf_id) == 0:
                return False, f"叶节点 {leaf_id} 必须有入边"
            if G.out_degree(leaf_id) > 0:
                return False, f"叶节点 {leaf_id} 不应有出边"

        # 中间节点：既有入边又有出边
        for inter_id in intermediate_nodes:
            if G.in_degree(inter_id) == 0:
                return False, f"中间节点 {inter_id} 必须有入边"
            if G.out_degree(inter_id) == 0:
                return False, f"中间节点 {inter_id} 必须有出边"

        # 业务逻辑验证：gate_type
        for node in nodes:
            node_id = node["id"]
            node_type = node.get("node_type")
            gate_type = node.get("gate_type")

            if node_type == "intermediate":
                # 中间节点必须有 gate_type，且只能是 AND 或 OR
                if not gate_type:
                    return False, f"中间节点 {node_id} 必须指定 gate_type (AND 或 OR)"
                if gate_type not in ["AND", "OR"]:
                    return False, f"中间节点 {node_id} 的 gate_type 必须是 AND 或 OR，当前为 {gate_type}"
            elif node_type in ["root", "leaf"]:
                # 根节点和叶节点的 gate_type 应该为 NULL
                if gate_type:
                    return False, f"{node_type} 节点 {node_id} 不应有 gate_type"

        # 业务逻辑验证：evidence_point_id
        for node in nodes:
            node_id = node["id"]
            node_type = node.get("node_type")
            evidence_point_id = node.get("evidence_point_id")

            if node_type == "leaf":
                # 叶节点必须关联 evidence_point_id
                if not evidence_point_id:
                    return False, f"叶节点 {node_id} 必须关联 evidence_point_id"

        # 检查连通性（从根节点能到达所有节点）
        reachable = nx.descendants(G, root_id)
        reachable.add(root_id)
        if len(reachable) != len(node_ids):
            unreachable = node_ids - reachable
            return False, f"以下节点从根节点不可达: {unreachable}"

        return True, ""

    @staticmethod
    def build_graph(nodes: List[Dict], edges: List[Dict]) -> nx.DiGraph:
        """构建 NetworkX 图（用于推理引擎）"""
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node["id"], **node)
        for edge in edges:
            G.add_edge(edge["parent_node_id"], edge["child_node_id"])
        return G
