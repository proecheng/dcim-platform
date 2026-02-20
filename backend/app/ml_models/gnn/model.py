"""
GNN Model for Measure Conflict Detection
基于关系图卷积网络的措施冲突检测模型
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, Optional


class MeasureEmbedding(nn.Module):
    """
    措施特征编码器
    将措施的各种特征编码为统一的向量表示

    输入特征:
    - type: one-hot编码 (6维)
    - device_id: 设备嵌入
    - hour: 小时编码 (24维)
    - power_direction: 功率方向 (1维)
    - benefit: 归一化收益 (1维)
    """

    def __init__(
        self,
        num_measure_types: int = 6,
        num_devices: int = 100,
        device_embed_dim: int = 32,
        hour_dim: int = 24,
        output_dim: int = 64,
    ):
        super().__init__()

        self.num_measure_types = num_measure_types
        self.num_devices = num_devices
        self.device_embed_dim = device_embed_dim
        self.hour_dim = hour_dim

        # 设备嵌入层
        self.device_embedding = nn.Embedding(num_devices, device_embed_dim)

        # 计算输入特征总维度
        # type_one_hot(6) + device_embed(32) + hour_encoding(24) + power_direction(1) + benefit(1)
        input_dim = num_measure_types + device_embed_dim + hour_dim + 1 + 1

        # 特征投影层
        self.projection = nn.Sequential(
            nn.Linear(input_dim, output_dim * 2),
            nn.LayerNorm(output_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(output_dim * 2, output_dim),
            nn.LayerNorm(output_dim),
        )

        self.output_dim = output_dim

    def encode_hour(self, hour: torch.Tensor) -> torch.Tensor:
        """
        将小时编码为24维one-hot向量
        """
        if hour.dim() == 2:
            hour = hour.squeeze(-1)
        hour = hour.long().clamp(0, 23)
        return F.one_hot(hour, num_classes=24).float()

    def forward(
        self,
        measure_type: torch.Tensor,
        device_id: torch.Tensor,
        hour: torch.Tensor,
        power_direction: torch.Tensor,
        benefit: torch.Tensor,
    ) -> torch.Tensor:
        """
        前向传播
        """
        measure_type.size(0)

        # 措施类型 one-hot 编码
        type_one_hot = F.one_hot(
            measure_type.long().clamp(0, self.num_measure_types - 1), num_classes=self.num_measure_types
        ).float()

        # 设备嵌入
        device_embed = self.device_embedding(device_id.long().clamp(0, self.num_devices - 1))

        # 小时编码
        hour_encoding = self.encode_hour(hour)

        # 确保维度正确
        if power_direction.dim() == 1:
            power_direction = power_direction.unsqueeze(-1)
        if benefit.dim() == 1:
            benefit = benefit.unsqueeze(-1)

        # 拼接所有特征
        features = torch.cat([type_one_hot, device_embed, hour_encoding, power_direction, benefit], dim=-1)

        return self.projection(features)


class RelationalGraphConv(nn.Module):
    """
    关系图卷积层 (R-GCN)
    支持多种边类型的图卷积操作
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        num_relations: int = 3,
        num_bases: Optional[int] = None,
        bias: bool = True,
        aggr: str = "mean",
    ):
        super().__init__()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.num_relations = num_relations
        self.aggr = aggr

        if num_bases is None:
            num_bases = min(num_relations, 4)
        self.num_bases = num_bases

        # 基权重矩阵
        self.weight_bases = nn.Parameter(torch.Tensor(num_bases, in_channels, out_channels))

        # 每种关系的基组合系数
        self.weight_comp = nn.Parameter(torch.Tensor(num_relations, num_bases))

        # 自环变换
        self.root_weight = nn.Parameter(torch.Tensor(in_channels, out_channels))

        if bias:
            self.bias = nn.Parameter(torch.Tensor(out_channels))
        else:
            self.register_parameter("bias", None)

        self.reset_parameters()

    def reset_parameters(self):
        nn.init.xavier_uniform_(self.weight_bases)
        nn.init.xavier_uniform_(self.weight_comp)
        nn.init.xavier_uniform_(self.root_weight)
        if self.bias is not None:
            nn.init.zeros_(self.bias)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, edge_type: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        Args:
            x: 节点特征 [num_nodes, in_channels]
            edge_index: 边索引 [2, num_edges]
            edge_type: 边类型 [num_edges]

        Returns:
            out: 更新后的节点特征 [num_nodes, out_channels]
        """
        num_nodes = x.size(0)

        # 计算每种关系的权重矩阵
        relation_weights = torch.einsum("rb,bio->rio", self.weight_comp, self.weight_bases)

        out = torch.zeros(num_nodes, self.out_channels, device=x.device)

        for rel in range(self.num_relations):
            mask = edge_type == rel
            if not mask.any():
                continue

            rel_edge_index = edge_index[:, mask]
            source_idx = rel_edge_index[0]
            target_idx = rel_edge_index[1]

            source_features = x[source_idx]
            messages = torch.matmul(source_features, relation_weights[rel])

            if self.aggr == "mean":
                ones = torch.ones(target_idx.size(0), device=x.device)
                degree = torch.zeros(num_nodes, device=x.device)
                degree.scatter_add_(0, target_idx, ones)
                degree = degree.clamp(min=1)

                out.scatter_add_(0, target_idx.unsqueeze(-1).expand_as(messages), messages)
                norm = degree.unsqueeze(-1)
                out = out / norm.clamp(min=1)
            else:
                out.scatter_add_(0, target_idx.unsqueeze(-1).expand_as(messages), messages)

        out = out + torch.matmul(x, self.root_weight)

        if self.bias is not None:
            out = out + self.bias

        return out


class ConflictGNN(nn.Module):
    """
    措施冲突检测图神经网络

    包含三个预测头:
    1. conflict_head: 预测成对措施之间的冲突概率
    2. coupling_head: 预测措施之间的耦合系数
    3. combination_head: 预测措施组合的综合得分
    """

    def __init__(
        self,
        num_measure_types: int = 6,
        num_devices: int = 100,
        device_embed_dim: int = 32,
        hidden_dim: int = 64,
        num_rgcn_layers: int = 3,
        num_relations: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_rgcn_layers = num_rgcn_layers

        # 措施嵌入模块
        self.measure_embedding = MeasureEmbedding(
            num_measure_types=num_measure_types,
            num_devices=num_devices,
            device_embed_dim=device_embed_dim,
            output_dim=hidden_dim,
        )

        # R-GCN层
        self.rgcn_layers = nn.ModuleList()
        for i in range(num_rgcn_layers):
            self.rgcn_layers.append(
                RelationalGraphConv(in_channels=hidden_dim, out_channels=hidden_dim, num_relations=num_relations)
            )

        # 层归一化
        self.layer_norms = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(num_rgcn_layers)])

        self.dropout = nn.Dropout(dropout)

        # 冲突预测头 (pairwise)
        self.conflict_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

        # 耦合系数预测头 (pairwise)
        self.coupling_head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Tanh(),
        )

        # 组合得分预测头 (graph-level)
        self.combination_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(
        self, node_features: Dict[str, torch.Tensor], edge_index: torch.Tensor, edge_type: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        前向传播

        Args:
            node_features: 节点特征字典
            edge_index: 边索引 [2, num_edges]
            edge_type: 边类型 [num_edges]

        Returns:
            outputs: 包含 node_embeddings, conflict_scores, coupling_coeffs, combination_score
        """
        # 1. 计算初始节点嵌入
        x = self.measure_embedding(
            measure_type=node_features["measure_type"],
            device_id=node_features["device_id"],
            hour=node_features["hour"],
            power_direction=node_features["power_direction"],
            benefit=node_features["benefit"],
        )

        # 2. R-GCN消息传递 (带残差连接)
        for i, (rgcn, ln) in enumerate(zip(self.rgcn_layers, self.layer_norms)):
            x_new = rgcn(x, edge_index, edge_type)
            x_new = F.relu(x_new)
            x_new = self.dropout(x_new)
            x_new = ln(x_new)
            x = x + x_new

        # 3. 边级预测 (pairwise)
        if edge_index.size(1) > 0:
            source_embed = x[edge_index[0]]
            target_embed = x[edge_index[1]]
            edge_features = torch.cat([source_embed, target_embed], dim=-1)

            conflict_scores = self.conflict_head(edge_features)
            coupling_coeffs = self.coupling_head(edge_features)
        else:
            conflict_scores = torch.zeros(0, 1, device=x.device)
            coupling_coeffs = torch.zeros(0, 1, device=x.device)

        # 4. 图级组合得分 (mean pooling)
        graph_embed = x.mean(dim=0, keepdim=True)
        combination_score = self.combination_head(graph_embed)

        return {
            "node_embeddings": x,
            "conflict_scores": conflict_scores,
            "coupling_coeffs": coupling_coeffs,
            "combination_score": combination_score.squeeze(),
        }

    def compute_loss(
        self, outputs: Dict[str, torch.Tensor], targets: Dict[str, torch.Tensor], edge_index: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        计算多任务损失

        Args:
            outputs: forward的输出
            targets: 目标值字典 (conflict_labels, coupling_targets, combination_target)
            edge_index: 边索引

        Returns:
            losses: 损失字典，包含各分项和 total_loss
        """
        losses = {}
        total_loss = torch.tensor(0.0, device=edge_index.device, requires_grad=True)

        # 冲突预测损失 (BCE)
        if "conflict_labels" in targets and outputs["conflict_scores"].size(0) > 0:
            conflict_loss = F.binary_cross_entropy(
                outputs["conflict_scores"].squeeze(-1), targets["conflict_labels"].float()
            )
            losses["conflict_loss"] = conflict_loss
            total_loss = total_loss + conflict_loss

        # 耦合系数损失 (MSE)
        if "coupling_targets" in targets and outputs["coupling_coeffs"].size(0) > 0:
            coupling_loss = F.mse_loss(outputs["coupling_coeffs"].squeeze(-1), targets["coupling_targets"])
            losses["coupling_loss"] = coupling_loss
            total_loss = total_loss + coupling_loss

        # 组合得分损失 (MSE)
        if "combination_target" in targets:
            combination_loss = F.mse_loss(outputs["combination_score"], targets["combination_target"])
            losses["combination_loss"] = combination_loss
            total_loss = total_loss + combination_loss

        losses["total_loss"] = total_loss
        return losses

    def predict_conflicts(
        self,
        node_features: Dict[str, torch.Tensor],
        edge_index: torch.Tensor,
        edge_type: torch.Tensor,
        threshold: float = 0.5,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        预测措施之间的冲突

        Returns:
            conflict_pairs: 冲突的边索引
            conflict_probs: 对应的冲突概率
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(node_features, edge_index, edge_type)
            conflict_probs = outputs["conflict_scores"].squeeze(-1)
            conflict_mask = conflict_probs > threshold
            conflict_pairs = edge_index[:, conflict_mask]
            return conflict_pairs, conflict_probs[conflict_mask]
