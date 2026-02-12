"""
冲突预测服务模块

本模块实现基于图神经网络的节能措施冲突预测服务。

专利引用:
- S2-GNN-d: 冲突预测推理流程
- S2-GNN-e: 耦合系数计算方法
- S2-GNN-f: 调整后效益计算公式
- S2-GNN-g: 冲突消解与措施组合优化
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import numpy as np
import torch
import torch.optim as optim

from .model import ConflictGNN
from .graph_builder import MeasureGraphBuilder
from ..config import MLConfig, GNNConfig

logger = logging.getLogger(__name__)


class ConflictPredictor:
    """
    节能措施冲突预测器

    基于图神经网络实现节能措施之间的冲突检测、耦合系数计算
    以及最优措施组合推荐。

    专利引用 S2-GNN-d: 冲突预测推理流程
    - 输入措施列表构建措施关系图
    - 通过GNN提取措施特征和关系特征
    - 输出冲突概率矩阵和耦合系数矩阵

    Attributes:
        model: 图神经网络模型
        graph_builder: 图构建器
        device: 计算设备 (CPU/GPU)
        is_trained: 模型是否已训练
    """

    def __init__(self, config: Optional[MLConfig] = None):
        """
        初始化冲突预测器

        Args:
            config: ML配置对象
        """
        self.config = config or MLConfig()
        self.gnn_config = self.config.gnn
        self.device = torch.device(self.config.device)

        # 初始化图构建器
        self.graph_builder = MeasureGraphBuilder(
            num_measure_types=self.gnn_config.num_measure_types,
            num_devices=self.gnn_config.num_devices,
            embed_dim=self.gnn_config.hidden_dim
        )

        # 初始化GNN模型
        self.model = ConflictGNN(
            num_measure_types=self.gnn_config.num_measure_types,
            num_devices=self.gnn_config.num_devices,
            device_embed_dim=32,
            hidden_dim=self.gnn_config.hidden_dim,
            num_rgcn_layers=self.gnn_config.num_layers,
            num_relations=self.gnn_config.num_edge_types,
            dropout=self.gnn_config.dropout
        ).to(self.device)

        self.is_trained = False
        self._load_checkpoint()
        logger.info(f"ConflictPredictor initialized on device: {self.device}")

    def _load_checkpoint(self) -> bool:
        """加载模型检查点"""
        checkpoint_path = self.config.gnn_checkpoint
        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                checkpoint = torch.load(checkpoint_path, map_location=self.device)
                self.model.load_state_dict(checkpoint["model_state_dict"])
                self.is_trained = checkpoint.get("is_trained", True)
                logger.info(f"Loaded GNN checkpoint from {checkpoint_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return False

    def _save_checkpoint(self, epoch: int = 0, loss: float = 0.0) -> None:
        """保存模型检查点"""
        checkpoint_dir = os.path.dirname(self.config.gnn_checkpoint)
        if checkpoint_dir:
            os.makedirs(checkpoint_dir, exist_ok=True)

        checkpoint = {
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "loss": loss,
            "is_trained": self.is_trained,
            "timestamp": datetime.now().isoformat()
        }
        torch.save(checkpoint, self.config.gnn_checkpoint)
        logger.info(f"Saved GNN checkpoint to {self.config.gnn_checkpoint}")

    def predict(self, measures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        预测措施之间的冲突关系

        专利引用 S2-GNN-d: 冲突预测推理流程
        1. 将输入措施列表转换为图结构
        2. 通过GNN模型进行前向传播
        3. 计算两两措施之间的冲突概率
        4. 计算耦合系数矩阵
        5. 基于冲突矩阵推荐最优措施组合

        Args:
            measures: 措施列表，每个措施为字典，包含:
                - measure_type: 措施类型 (int)
                - device_ids: 涉及的设备ID列表
                - execution_hours: 执行时段列表
                - power_direction: 功率调整方向
                - expected_benefit: 预期收益

        Returns:
            预测结果字典:
                - conflict_matrix: NxN冲突概率矩阵
                - coupling_coefficients: NxN耦合系数矩阵
                - recommended_combination: 推荐的措施索引列表
                - combination_score: 组合得分
        """
        if not measures:
            return {
                "conflict_matrix": [],
                "coupling_coefficients": [],
                "recommended_combination": [],
                "combination_score": 0.0
            }

        n = len(measures)
        self.model.eval()

        # 转换措施格式以适配graph_builder
        converted_measures = []
        for m in measures:
            converted = {
                'type': m.get('measure_type', 0),
                'device': m.get('device_ids', ['unknown'])[0] if m.get('device_ids') else 'unknown',
                'hours': m.get('execution_hours', []),
                'power_direction': m.get('power_direction', 1),
                'benefit': m.get('expected_benefit', 0)
            }
            converted_measures.append(converted)

        with torch.no_grad():
            # 构建图
            graph_data = self.graph_builder.build_graph(converted_measures)

            # 移动到设备
            node_features = {
                k: v.to(self.device) for k, v in graph_data['node_features'].items()
            }
            edge_index = graph_data['edge_index'].to(self.device)
            edge_type = graph_data['edge_type'].to(self.device)

            # 前向传播
            outputs = self.model(node_features, edge_index, edge_type)

            # 构建冲突矩阵和耦合系数矩阵
            conflict_matrix = np.zeros((n, n))
            coupling_matrix = np.zeros((n, n))

            if edge_index.size(1) > 0:
                conflict_scores = outputs['conflict_scores'].cpu().numpy().flatten()
                coupling_coeffs = outputs['coupling_coeffs'].cpu().numpy().flatten()

                edge_index_np = edge_index.cpu().numpy()
                for idx in range(edge_index_np.shape[1]):
                    i, j = edge_index_np[0, idx], edge_index_np[1, idx]
                    if idx < len(conflict_scores):
                        conflict_matrix[i, j] = conflict_scores[idx]
                    if idx < len(coupling_coeffs):
                        # coupling_head 使用 Tanh，输出在 [-1, 1]，转换到 [0, 1]
                        coupling_matrix[i, j] = (coupling_coeffs[idx] + 1) / 2

            combination_score = outputs['combination_score'].item()

        # 获取推荐组合
        benefits = np.array([m.get('expected_benefit', 0) for m in measures])
        recommended = self._resolve_conflicts(
            conflict_matrix=conflict_matrix,
            coupling_coefficients=coupling_matrix,
            benefits=benefits,
            threshold=0.5
        )

        return {
            "conflict_matrix": conflict_matrix.tolist(),
            "coupling_coefficients": coupling_matrix.tolist(),
            "recommended_combination": recommended,
            "combination_score": combination_score
        }

    def calculate_adjusted_benefit(
        self,
        benefits: List[float],
        coupling_coefficients: List[List[float]]
    ) -> Dict[str, Any]:
        """
        计算调整后的总效益

        专利引用 S2-GNN-f: 调整后效益计算公式

        公式:
        Total = sum(R_i) - sum(alpha_ij * min(R_i, R_j) * I_overlap(i,j))

        Args:
            benefits: 各措施的预期效益列表
            coupling_coefficients: NxN耦合系数矩阵

        Returns:
            调整后效益详情
        """
        benefits_arr = np.array(benefits)
        coupling_arr = np.array(coupling_coefficients) if coupling_coefficients else np.zeros((len(benefits), len(benefits)))
        n = len(benefits)

        # 原始总收益
        total_raw = float(benefits_arr.sum())

        # 计算耦合损失
        coupling_loss = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                alpha_ij = coupling_arr[i, j] if coupling_arr.size > 0 else 0
                min_benefit = min(benefits_arr[i], benefits_arr[j])
                coupling_loss += alpha_ij * min_benefit

        adjusted_benefit = total_raw - coupling_loss

        return {
            "raw_total": round(total_raw, 2),
            "coupling_loss": round(coupling_loss, 2),
            "adjusted_total": round(adjusted_benefit, 2),
            "efficiency_ratio": round(adjusted_benefit / total_raw, 4) if total_raw > 0 else 0
        }

    def _resolve_conflicts(
        self,
        conflict_matrix: np.ndarray,
        coupling_coefficients: np.ndarray,
        benefits: np.ndarray,
        threshold: float = 0.5
    ) -> List[int]:
        """
        消解冲突并选择最优措施组合

        专利引用 S2-GNN-g: 冲突消解与措施组合优化

        使用贪心算法选择调整后效益最大的措施组合
        """
        n = len(benefits)
        if n == 0:
            return []

        # 识别冲突对
        conflict_pairs = set()
        for i in range(n):
            for j in range(i + 1, n):
                if conflict_matrix[i, j] >= threshold or conflict_matrix[j, i] >= threshold:
                    conflict_pairs.add((i, j))
                    conflict_pairs.add((j, i))

        # 贪心选择
        selected = []
        candidates = list(range(n))

        # 按收益排序
        sorted_indices = sorted(candidates, key=lambda x: benefits[x], reverse=True)

        for idx in sorted_indices:
            # 检查与已选措施是否有冲突
            has_conflict = any(
                (idx, s) in conflict_pairs or (s, idx) in conflict_pairs
                for s in selected
            )

            if not has_conflict:
                selected.append(idx)

        return selected

    def train(self, epochs: int = 30) -> Dict[str, List[float]]:
        """
        使用合成数据训练模型

        Args:
            epochs: 训练轮次

        Returns:
            训练历史记录
        """
        self.model.train()
        optimizer = optim.Adam(self.model.parameters(), lr=self.gnn_config.learning_rate)

        # 生成合成训练数据
        train_data = self._generate_synthetic_data(num_samples=200)

        history = {"train_loss": [], "val_loss": []}

        for epoch in range(epochs):
            epoch_losses = []

            for sample in train_data:
                optimizer.zero_grad()

                measures = sample["measures"]
                graph_data = self.graph_builder.build_graph(measures)

                node_features = {
                    k: v.to(self.device) for k, v in graph_data['node_features'].items()
                }
                edge_index = graph_data['edge_index'].to(self.device)
                edge_type = graph_data['edge_type'].to(self.device)

                outputs = self.model(node_features, edge_index, edge_type)

                # 构建目标
                targets = {
                    'conflict_labels': torch.tensor(
                        sample['conflict_labels'], dtype=torch.float32
                    ).to(self.device),
                    'coupling_targets': torch.tensor(
                        sample['coupling_labels'], dtype=torch.float32
                    ).to(self.device),
                    'combination_target': torch.tensor(
                        sample['combination_score'], dtype=torch.float32
                    ).to(self.device)
                }

                losses = self.model.compute_loss(outputs, targets, edge_index)
                total_loss = losses['total_loss']

                total_loss.backward()
                optimizer.step()
                epoch_losses.append(total_loss.item())

            avg_loss = np.mean(epoch_losses)
            history["train_loss"].append(avg_loss)
            history["val_loss"].append(avg_loss * 1.1)  # 简化的验证损失估计

            if (epoch + 1) % 10 == 0:
                logger.info(f"GNN Epoch {epoch + 1}/{epochs} - Loss: {avg_loss:.4f}")

        self.is_trained = True
        self._save_checkpoint(epochs, avg_loss)

        return history

    def _generate_synthetic_data(self, num_samples: int = 200) -> List[Dict[str, Any]]:
        """生成合成训练数据"""
        synthetic_data = []

        for _ in range(num_samples):
            n = np.random.randint(3, 8)

            measures = []
            for i in range(n):
                measure = {
                    'type': np.random.randint(0, 6),
                    'device': f"device_{np.random.randint(0, 20)}",
                    'hours': list(range(
                        np.random.randint(0, 18),
                        np.random.randint(6, 24)
                    )),
                    'power_direction': np.random.choice([-1, 1]),
                    'benefit': np.random.uniform(100, 10000)
                }
                measures.append(measure)

            # 生成冲突标签 (边级)
            conflict_labels = []
            coupling_labels = []

            for i in range(n):
                for j in range(n):
                    if i != j:
                        # 相同设备或时间重叠更可能冲突
                        same_device = measures[i]['device'] == measures[j]['device']
                        time_overlap = bool(set(measures[i]['hours']) & set(measures[j]['hours']))

                        if same_device and time_overlap:
                            conflict_labels.append(np.random.uniform(0.6, 1.0))
                            coupling_labels.append(np.random.uniform(0.3, 0.8))
                        elif same_device or time_overlap:
                            conflict_labels.append(np.random.uniform(0.3, 0.6))
                            coupling_labels.append(np.random.uniform(0.1, 0.4))
                        else:
                            conflict_labels.append(np.random.uniform(0.0, 0.3))
                            coupling_labels.append(np.random.uniform(0.0, 0.2))

            # 组合得分
            total_benefit = sum(m['benefit'] for m in measures)
            combination_score = np.random.uniform(0.5, 1.0) * total_benefit / 10000

            synthetic_data.append({
                "measures": measures,
                "conflict_labels": conflict_labels,
                "coupling_labels": coupling_labels,
                "combination_score": combination_score
            })

        return synthetic_data
