"""
Actor-Critic 网络实现
基于 PyTorch 的 Actor-Critic 架构，用于能源节约系统的强化学习

参考: S5b - Actor-Critic 网络设计
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Normal, Categorical
from typing import Tuple, Dict


class ActorCriticNetwork(nn.Module):
    """
    Actor-Critic 网络

    Actor 输出:
    - 连续动作: priority (0.5-2.0), safety_coeff (1.0-1.2), temperature (24-28)
    - 离散动作: 5 个时段选择 (peak, high, normal, low, deep_valley)

    Critic 输出:
    - 状态价值 V(s)
    """

    def __init__(self, state_dim: int = 51, hidden_dim: int = 256, num_periods: int = 5, device: str = "cpu"):
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.num_periods = num_periods
        self.device = torch.device(device)

        # 共享编码器
        self.encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
            nn.LayerNorm(hidden_dim // 4),
            nn.ReLU(),
        )

        encoder_out_dim = hidden_dim // 4

        # Actor - 连续动作头 (priority, safety_coeff, temperature)
        # 输出均值和标准差
        self.continuous_mean = nn.Sequential(
            nn.Linear(encoder_out_dim, hidden_dim // 4), nn.ReLU(), nn.Linear(hidden_dim // 4, 3)
        )
        self.continuous_log_std = nn.Parameter(torch.zeros(3))

        # Actor - 离散动作头 (目标时段选择)
        self.discrete_head = nn.Sequential(
            nn.Linear(encoder_out_dim, hidden_dim // 4), nn.ReLU(), nn.Linear(hidden_dim // 4, num_periods)
        )

        # Critic - 状态价值头
        self.value_head = nn.Sequential(
            nn.Linear(encoder_out_dim, hidden_dim // 4), nn.ReLU(), nn.Linear(hidden_dim // 4, 1)
        )

        # 动作范围
        self.action_bounds = {"priority": (0.5, 2.0), "safety_coeff": (1.0, 1.2), "temperature": (24.0, 28.0)}

        self.to(self.device)

    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        前向传播

        Args:
            state: 状态张量 [batch_size, state_dim]

        Returns:
            continuous_mean: 连续动作均值 [batch_size, 3]
            continuous_std: 连续动作标准差 [batch_size, 3]
            discrete_logits: 离散动作logits [batch_size, num_periods]
            value: 状态价值 [batch_size, 1]
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)

        state = state.to(self.device)
        encoded = self.encoder(state)

        # 连续动作
        continuous_mean = self.continuous_mean(encoded)
        continuous_std = torch.exp(self.continuous_log_std).expand_as(continuous_mean)

        # 离散动作
        discrete_logits = self.discrete_head(encoded)

        # 状态价值
        value = self.value_head(encoded)

        return continuous_mean, continuous_std, discrete_logits, value

    def get_action(
        self, state: torch.Tensor, deterministic: bool = False
    ) -> Tuple[Dict[str, float], torch.Tensor, torch.Tensor]:
        """
        获取动作

        Args:
            state: 状态张量
            deterministic: 是否使用确定性策略

        Returns:
            actions: 动作字典
            log_prob: 动作的对数概率
            value: 状态价值
        """
        continuous_mean, continuous_std, discrete_logits, value = self.forward(state)

        # 连续动作采样
        if deterministic:
            continuous_actions = continuous_mean
        else:
            continuous_dist = Normal(continuous_mean, continuous_std)
            continuous_actions = continuous_dist.rsample()

        # 限制到合法范围
        priority = torch.sigmoid(continuous_actions[:, 0]) * 1.5 + 0.5  # [0.5, 2.0]
        safety_coeff = torch.sigmoid(continuous_actions[:, 1]) * 0.2 + 1.0  # [1.0, 1.2]
        temperature = torch.sigmoid(continuous_actions[:, 2]) * 4.0 + 24.0  # [24.0, 28.0]

        # 离散动作采样
        discrete_probs = F.softmax(discrete_logits, dim=-1)
        if deterministic:
            target_period = torch.argmax(discrete_probs, dim=-1)
        else:
            discrete_dist = Categorical(discrete_probs)
            target_period = discrete_dist.sample()

        # 计算对数概率
        continuous_dist = Normal(continuous_mean, continuous_std)
        continuous_log_prob = continuous_dist.log_prob(continuous_actions).sum(dim=-1)

        discrete_dist = Categorical(discrete_probs)
        discrete_log_prob = discrete_dist.log_prob(target_period)

        total_log_prob = continuous_log_prob + discrete_log_prob

        # 构建动作字典
        actions = {
            "priority": float(priority[0].item()),
            "safety_coeff": float(safety_coeff[0].item()),
            "temperature": float(temperature[0].item()),
            "target_period": int(target_period[0].item()),
        }

        return actions, total_log_prob, value.squeeze(-1)

    def evaluate_action(
        self, state: torch.Tensor, actions: torch.Tensor, target_periods: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        评估给定状态-动作对

        Args:
            state: 状态张量 [batch_size, state_dim]
            actions: 连续动作张量 [batch_size, 3]
            target_periods: 离散动作张量 [batch_size]

        Returns:
            log_prob: 动作对数概率
            value: 状态价值
            entropy: 策略熵
        """
        continuous_mean, continuous_std, discrete_logits, value = self.forward(state)

        # 连续动作对数概率
        continuous_dist = Normal(continuous_mean, continuous_std)
        continuous_log_prob = continuous_dist.log_prob(actions).sum(dim=-1)
        continuous_entropy = continuous_dist.entropy().sum(dim=-1)

        # 离散动作对数概率
        discrete_probs = F.softmax(discrete_logits, dim=-1)
        discrete_dist = Categorical(discrete_probs)
        discrete_log_prob = discrete_dist.log_prob(target_periods)
        discrete_entropy = discrete_dist.entropy()

        total_log_prob = continuous_log_prob + discrete_log_prob
        total_entropy = continuous_entropy + discrete_entropy

        return total_log_prob, value.squeeze(-1), total_entropy

    def get_value(self, state: torch.Tensor) -> torch.Tensor:
        """
        获取状态价值

        Args:
            state: 状态张量

        Returns:
            value: 状态价值
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)
        state = state.to(self.device)
        encoded = self.encoder(state)
        value = self.value_head(encoded)
        return value.squeeze(-1)

    def save(self, path: str) -> None:
        """保存模型"""
        torch.save(
            {
                "state_dict": self.state_dict(),
                "state_dim": self.state_dim,
                "hidden_dim": self.hidden_dim,
                "num_periods": self.num_periods,
            },
            path,
        )

    @classmethod
    def load(cls, path: str, device: str = "cpu") -> "ActorCriticNetwork":
        """加载模型"""
        checkpoint = torch.load(path, map_location=device)
        model = cls(
            state_dim=checkpoint["state_dim"],
            hidden_dim=checkpoint["hidden_dim"],
            num_periods=checkpoint["num_periods"],
            device=device,
        )
        model.load_state_dict(checkpoint["state_dict"])
        return model
