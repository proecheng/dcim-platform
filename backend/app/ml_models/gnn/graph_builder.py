"""
Graph Builder for Measure Conflict Detection
措施图构建器 - 将措施列表转换为GNN输入图结构
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Set


class MeasureGraphBuilder:
    """
    措施图构建器

    将措施列表转换为图结构数据，用于GNN模型输入。

    边类型:
    - 0: 资源共享 (相同设备或时间重叠)
    - 1: 因果依赖 (措施间的因果关系)
    - 2: 收益耦合 (措施间的收益相互影响)
    """

    EDGE_TYPE_RESOURCE_SHARING = 0
    EDGE_TYPE_CAUSAL_DEPENDENCY = 1
    EDGE_TYPE_BENEFIT_COUPLING = 2

    def __init__(self, num_measure_types: int = 6, num_devices: int = 100, embed_dim: int = 32):
        self.num_measure_types = num_measure_types
        self.num_devices = num_devices
        self.embed_dim = embed_dim

        # 设备ID映射表
        self._device_id_map: Dict[str, int] = {}
        self._next_device_id = 0

    def _get_device_id(self, device_name: str) -> int:
        """将设备名称映射为整数ID"""
        if device_name not in self._device_id_map:
            self._device_id_map[device_name] = self._next_device_id % self.num_devices
            self._next_device_id += 1
        return self._device_id_map[device_name]

    def _parse_hours(self, measure: Dict) -> Set[int]:
        """
        解析措施的执行时间段，返回小时集合

        支持格式:
        - hours: [8, 9, 10, 11]
        - start_hour/end_hour: 8, 12
        - hour: 8
        """
        if "hours" in measure:
            return set(int(h) for h in measure["hours"])
        elif "start_hour" in measure and "end_hour" in measure:
            start = int(measure["start_hour"])
            end = int(measure["end_hour"])
            if start <= end:
                return set(range(start, end))
            else:
                return set(range(start, 24)) | set(range(0, end))
        elif "hour" in measure:
            return {int(measure["hour"])}
        return set()

    def _get_primary_hour(self, measure: Dict) -> int:
        """获取措施的主要执行小时"""
        hours = self._parse_hours(measure)
        if hours:
            return min(hours)
        return 0

    def encode_measures(self, measures: List[Dict]) -> Dict[str, torch.Tensor]:
        """
        将措施列表编码为节点特征张量

        Args:
            measures: 措施字典列表，每个措施包含:
                - type: 措施类型 (int 或 str)
                - device: 设备标识
                - hour/hours/start_hour+end_hour: 执行时间
                - power_direction: 功率方向 (-1 或 1)
                - benefit: 收益值

        Returns:
            node_features: 字典，包含各特征张量
        """
        n = len(measures)

        measure_types = torch.zeros(n, dtype=torch.long)
        device_ids = torch.zeros(n, dtype=torch.long)
        hours = torch.zeros(n, dtype=torch.long)
        power_directions = torch.zeros(n, dtype=torch.float)
        benefits = torch.zeros(n, dtype=torch.float)

        # 收集所有收益值用于归一化
        raw_benefits = []
        for m in measures:
            raw_benefits.append(float(m.get("benefit", 0.0)))

        # 归一化收益
        benefits_array = np.array(raw_benefits)
        if len(benefits_array) > 0 and benefits_array.max() != benefits_array.min():
            norm_benefits = (benefits_array - benefits_array.min()) / (benefits_array.max() - benefits_array.min())
        else:
            norm_benefits = np.zeros_like(benefits_array)

        # 措施类型名称到索引的映射
        type_map = {
            "load_shift": 0,
            "load_shed": 1,
            "generation": 2,
            "storage_charge": 3,
            "storage_discharge": 4,
            "demand_response": 5,
        }

        for i, m in enumerate(measures):
            # 措施类型
            mtype = m.get("type", 0)
            if isinstance(mtype, str):
                mtype = type_map.get(mtype, 0)
            measure_types[i] = int(mtype) % self.num_measure_types

            # 设备ID
            device = m.get("device", "unknown")
            device_ids[i] = self._get_device_id(str(device))

            # 主要执行小时
            hours[i] = self._get_primary_hour(m)

            # 功率方向
            power_directions[i] = float(m.get("power_direction", 1.0))

            # 归一化收益
            benefits[i] = float(norm_benefits[i])

        return {
            "measure_type": measure_types,
            "device_id": device_ids,
            "hour": hours,
            "power_direction": power_directions,
            "benefit": benefits,
        }

    def build_edges(self, measures: List[Dict]) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        根据措施间关系构建边

        Args:
            measures: 措施字典列表

        Returns:
            edge_index: [2, num_edges] 边的源和目标节点索引
            edge_type: [num_edges] 边类型

        边类型说明:
            0 - 资源共享：相同设备或执行时间重叠
            1 - 因果依赖：措施间存在先后逻辑关系
            2 - 收益耦合：措施收益之间存在相互影响
        """
        n = len(measures)
        sources = []
        targets = []
        edge_types = []

        # 预解析所有措施的小时和设备
        all_hours = [self._parse_hours(m) for m in measures]
        all_devices = [str(m.get("device", "unknown")) for m in measures]

        type_map = {
            "load_shift": 0,
            "load_shed": 1,
            "generation": 2,
            "storage_charge": 3,
            "storage_discharge": 4,
            "demand_response": 5,
        }
        all_types = []
        for m in measures:
            mtype = m.get("type", 0)
            if isinstance(mtype, str):
                mtype = type_map.get(mtype, 0)
            all_types.append(int(mtype))

        for i in range(n):
            for j in range(i + 1, n):
                # ---- 边类型0: 资源共享 ----
                same_device = all_devices[i] == all_devices[j]
                time_overlap = bool(all_hours[i] & all_hours[j])

                if same_device or time_overlap:
                    # 双向边
                    sources.extend([i, j])
                    targets.extend([j, i])
                    edge_types.extend([self.EDGE_TYPE_RESOURCE_SHARING, self.EDGE_TYPE_RESOURCE_SHARING])

                # ---- 边类型1: 因果依赖 ----
                has_causal = self._check_causal_dependency(
                    measures[i], measures[j], all_types[i], all_types[j], all_hours[i], all_hours[j]
                )
                if has_causal:
                    sources.append(i)
                    targets.append(j)
                    edge_types.append(self.EDGE_TYPE_CAUSAL_DEPENDENCY)

                # ---- 边类型2: 收益耦合 ----
                has_coupling = self._check_benefit_coupling(
                    measures[i], measures[j], all_types[i], all_types[j], same_device
                )
                if has_coupling:
                    # 双向边
                    sources.extend([i, j])
                    targets.extend([j, i])
                    edge_types.extend([self.EDGE_TYPE_BENEFIT_COUPLING, self.EDGE_TYPE_BENEFIT_COUPLING])

        if len(sources) == 0:
            edge_index = torch.zeros(2, 0, dtype=torch.long)
            edge_type = torch.zeros(0, dtype=torch.long)
        else:
            edge_index = torch.tensor([sources, targets], dtype=torch.long)
            edge_type = torch.tensor(edge_types, dtype=torch.long)

        return edge_index, edge_type

    def _check_causal_dependency(
        self, m1: Dict, m2: Dict, type1: int, type2: int, hours1: Set[int], hours2: Set[int]
    ) -> bool:
        """检查两个措施间是否存在因果依赖"""
        # 储能充电(3) -> 储能放电(4)
        if type1 == 3 and type2 == 4:
            if hours1 and hours2 and max(hours1) <= min(hours2):
                return True

        # 负荷转移(0) -> 需求响应(5)
        if type1 == 0 and type2 == 5:
            return True

        # 发电(2) -> 储能充电(3)
        if type1 == 2 and type2 == 3:
            if hours1 and hours2 and bool(hours1 & hours2):
                return True

        # 检查显式依赖
        deps1 = m1.get("depends_on", [])
        m2_id = m2.get("id", None)
        if m2_id and m2_id in deps1:
            return True

        return False

    def _check_benefit_coupling(self, m1: Dict, m2: Dict, type1: int, type2: int, same_device: bool) -> bool:
        """检查两个措施间是否存在收益耦合"""
        # 相同设备上的不同类型措施
        if same_device and type1 != type2:
            return True

        # 功率方向相反的措施
        dir1 = float(m1.get("power_direction", 1.0))
        dir2 = float(m2.get("power_direction", 1.0))
        if dir1 * dir2 < 0:
            return True

        # 负荷削减(1) 和 发电(2) 总是有收益耦合
        if {type1, type2} == {1, 2}:
            return True

        return False

    def build_graph(self, measures: List[Dict]) -> Dict:
        """
        构建完整的图数据

        Args:
            measures: 措施字典列表

        Returns:
            graph_data: 包含以下键的字典:
                - node_features: 节点特征字典 (各特征张量)
                - edge_index: [2, num_edges] 边索引
                - edge_type: [num_edges] 边类型
                - num_nodes: 节点数量
                - num_edges: 边数量
                - measures: 原始措施列表引用
        """
        node_features = self.encode_measures(measures)
        edge_index, edge_type = self.build_edges(measures)

        return {
            "node_features": node_features,
            "edge_index": edge_index,
            "edge_type": edge_type,
            "num_nodes": len(measures),
            "num_edges": edge_index.size(1) if edge_index.size(1) > 0 else 0,
            "measures": measures,
        }
