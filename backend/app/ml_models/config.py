"""
深度学习模型配置

定义所有模型的超参数和配置
"""
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class TransformerConfig:
    """时序Transformer配置"""
    # 输入特征维度：功率(1) + 时段类型(5) + 工作日(1) + 温度(1) = 8
    input_dim: int = 8
    # 模型维度
    d_model: int = 64
    # 注意力头数
    n_heads: int = 4
    # 编码器层数
    n_layers: int = 3
    # 前馈网络维度
    d_ff: int = 256
    # Dropout率
    dropout: float = 0.1
    # 最大序列长度 (30天 * 96个15分钟 = 2880)
    max_seq_len: int = 2880
    # 时段类型数量 (尖峰/高峰/平段/低谷/深谷)
    num_period_types: int = 5
    # 输出：可转移性概率 + 时段预测 + 容量预测
    num_period_outputs: int = 5  # 各时段转移概率


@dataclass
class GNNConfig:
    """图神经网络配置"""
    # 节点特征维度
    node_input_dim: int = 64
    # 隐藏层维度
    hidden_dim: int = 128
    # 输出维度
    output_dim: int = 64
    # GCN层数
    num_layers: int = 3
    # 边类型数量 (资源共享/因果依赖/收益耦合)
    num_edge_types: int = 3
    # Dropout率
    dropout: float = 0.1
    # 措施类型数量
    num_measure_types: int = 6
    # 设备数量
    num_devices: int = 100
    # 学习率
    learning_rate: float = 1e-3


@dataclass
class RLConfig:
    """强化学习配置"""
    # 状态空间维度
    state_dim: int = 128
    # 动作空间维度（连续动作）
    continuous_action_dim: int = 3  # 优先级权重/安全系数/温度设定
    # 离散动作数量
    discrete_action_dim: int = 5  # 目标时段选择
    # Actor网络隐藏层
    actor_hidden_dims: List[int] = field(default_factory=lambda: [256, 128, 64])
    # Critic网络隐藏层
    critic_hidden_dims: List[int] = field(default_factory=lambda: [256, 128, 64])
    # 学习率
    learning_rate: float = 3e-4
    # 折扣因子
    gamma: float = 0.99
    # GAE lambda
    gae_lambda: float = 0.95
    # PPO clip参数
    clip_epsilon: float = 0.2
    # 经验回放缓冲区大小
    buffer_size: int = 10000
    # 批次大小
    batch_size: int = 64
    # 更新周期
    update_epochs: int = 10
    # 舒适度惩罚系数
    lambda_comfort: float = 0.1
    # 安全约束惩罚系数
    lambda_safety: float = 0.2
    # 初始探索率
    initial_exploration_rate: float = 0.3


@dataclass
class MLConfig:
    """总体ML配置"""
    # 设备 (cpu/cuda)
    device: str = "cpu"
    # 模型检查点目录
    checkpoint_dir: str = "backend/app/ml_models/checkpoints"
    # 随机种子
    seed: int = 42
    # 是否启用深度学习模块
    enabled: bool = True
    # 子配置
    transformer: TransformerConfig = field(default_factory=TransformerConfig)
    gnn: GNNConfig = field(default_factory=GNNConfig)
    rl: RLConfig = field(default_factory=RLConfig)

    @property
    def transformer_checkpoint(self) -> str:
        """Transformer模型检查点路径"""
        return f"{self.checkpoint_dir}/transformer/model.pt"

    @property
    def gnn_checkpoint(self) -> str:
        """GNN模型检查点路径"""
        return f"{self.checkpoint_dir}/gnn/model.pt"

    @property
    def rl_checkpoint(self) -> str:
        """RL模型检查点路径"""
        return f"{self.checkpoint_dir}/rl/model.pt"

    def get_checkpoint_path(self, model_type: str) -> Path:
        """获取模型检查点路径"""
        return Path(self.checkpoint_dir) / model_type / "model.pt"


# 默认配置实例
default_config = MLConfig()
