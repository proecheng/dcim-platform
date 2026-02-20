"""
近端策略优化 (PPO) 算法实现

参考专利:
- S5c: 采用近端策略优化算法进行策略更新
- S5d: 经验回放缓冲区，持续收集四元组进行网络训练

PPO目标函数:
L^CLIP(theta) = E_t[min(r_t(theta)*A_t, clip(r_t(theta), 1-eps, 1+eps)*A_t)]
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, List, Tuple


class ExperienceBuffer:
    """
    经验回放缓冲区 (S5d)

    存储最近N步的 (state, action, reward, next_state, done, log_prob) 四元组
    """

    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.states: List[np.ndarray] = []
        self.continuous_actions: List[np.ndarray] = []
        self.discrete_actions: List[int] = []
        self.rewards: List[float] = []
        self.next_states: List[np.ndarray] = []
        self.dones: List[bool] = []
        self.log_probs: List[float] = []
        self.values: List[float] = []

    def store(
        self,
        state: np.ndarray,
        continuous_action: np.ndarray,
        discrete_action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        log_prob: float,
        value: float,
    ):
        """存储一步经验"""
        self.states.append(state)
        self.continuous_actions.append(continuous_action)
        self.discrete_actions.append(discrete_action)
        self.rewards.append(reward)
        self.next_states.append(next_state)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)

        # 限制容量
        if len(self.states) > self.capacity:
            self.states.pop(0)
            self.continuous_actions.pop(0)
            self.discrete_actions.pop(0)
            self.rewards.pop(0)
            self.next_states.pop(0)
            self.dones.pop(0)
            self.log_probs.pop(0)
            self.values.pop(0)

    def get_batch(self, device: torch.device) -> Dict[str, torch.Tensor]:
        """获取全部数据作为batch"""
        return {
            "states": torch.FloatTensor(np.array(self.states)).to(device),
            "continuous_actions": torch.FloatTensor(np.array(self.continuous_actions)).to(device),
            "discrete_actions": torch.LongTensor(self.discrete_actions).to(device),
            "rewards": torch.FloatTensor(self.rewards).to(device),
            "next_states": torch.FloatTensor(np.array(self.next_states)).to(device),
            "dones": torch.FloatTensor([float(d) for d in self.dones]).to(device),
            "old_log_probs": torch.FloatTensor(self.log_probs).to(device),
            "values": torch.FloatTensor(self.values).to(device),
        }

    def clear(self):
        """清空缓冲区"""
        self.states.clear()
        self.continuous_actions.clear()
        self.discrete_actions.clear()
        self.rewards.clear()
        self.next_states.clear()
        self.dones.clear()
        self.log_probs.clear()
        self.values.clear()

    def __len__(self) -> int:
        return len(self.states)


class PPOAgent:
    """
    PPO代理 (S5c)

    使用裁剪目标函数限制策略更新幅度:
    L^CLIP = E[min(r_t * A_t, clip(r_t, 1-eps, 1+eps) * A_t)]

    其中 r_t = pi_new / pi_old
    """

    def __init__(
        self,
        network: nn.Module,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        value_coeff: float = 0.5,
        entropy_coeff: float = 0.01,
        max_grad_norm: float = 0.5,
        update_epochs: int = 10,
        buffer_size: int = 10000,
    ):
        self.network = network
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.value_coeff = value_coeff
        self.entropy_coeff = entropy_coeff
        self.max_grad_norm = max_grad_norm
        self.update_epochs = update_epochs

        self.optimizer = torch.optim.Adam(network.parameters(), lr=lr)
        self.buffer = ExperienceBuffer(capacity=buffer_size)
        self.device = next(network.parameters()).device

    def compute_gae(
        self, rewards: torch.Tensor, values: torch.Tensor, next_values: torch.Tensor, dones: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        计算广义优势估计 GAE (S5c)

        A_t = sum_{l=0}^{T-t} (gamma * lambda)^l * delta_{t+l}
        delta_t = r_t + gamma * V(s_{t+1}) - V(s_t)
        """
        batch_size = len(rewards)
        advantages = torch.zeros(batch_size, device=self.device)
        returns = torch.zeros(batch_size, device=self.device)

        last_gae = 0
        last_return = 0

        for t in reversed(range(batch_size)):
            if t == batch_size - 1:
                next_value = next_values[t]
            else:
                next_value = values[t + 1]

            mask = 1.0 - dones[t]

            # TD误差
            delta = rewards[t] + self.gamma * next_value * mask - values[t]

            # GAE
            last_gae = delta + self.gamma * self.gae_lambda * mask * last_gae
            advantages[t] = last_gae

            # Returns
            last_return = rewards[t] + self.gamma * mask * last_return
            returns[t] = last_return

        return advantages, returns

    def update(self) -> Dict[str, float]:
        """
        PPO策略更新 (S5c)

        Returns:
            Dict包含各项损失值
        """
        if len(self.buffer) < 2:
            return {"policy_loss": 0, "value_loss": 0, "entropy": 0}

        batch = self.buffer.get_batch(self.device)

        # 计算next_state的value
        with torch.no_grad():
            next_values = self.network.get_value(batch["next_states"])

        # 计算GAE
        advantages, returns = self.compute_gae(batch["rewards"], batch["values"], next_values, batch["dones"])

        # 标准化优势
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        total_policy_loss = 0
        total_value_loss = 0
        total_entropy = 0

        # 多轮更新
        for _ in range(self.update_epochs):
            # 评估当前策略下的动作
            log_probs, entropy, values = self.network.evaluate_action(
                batch["states"], batch["continuous_actions"], batch["discrete_actions"]
            )

            # 概率比
            ratio = torch.exp(log_probs - batch["old_log_probs"])

            # 裁剪目标
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()

            # 价值函数损失
            value_loss = F.mse_loss(values, returns)

            # 总损失
            loss = policy_loss + self.value_coeff * value_loss - self.entropy_coeff * entropy.mean()

            self.optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.network.parameters(), self.max_grad_norm)
            self.optimizer.step()

            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
            total_entropy += entropy.mean().item()

        # 清空缓冲区
        self.buffer.clear()

        n = self.update_epochs
        return {"policy_loss": total_policy_loss / n, "value_loss": total_value_loss / n, "entropy": total_entropy / n}

    @torch.no_grad()
    def select_action(self, state: np.ndarray, explore: bool = True) -> Tuple[Dict[str, float], float, float]:
        """
        选择动作

        Args:
            state: 环境状态
            explore: 是否进行探索

        Returns:
            (actions_dict, log_prob, value)
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        actions, log_probs = self.network.get_action(state_tensor, deterministic=not explore)
        value = self.network.get_value(state_tensor)

        actions_dict = {
            "priority_weight": actions["priority_weight"].item(),
            "safety_coeff": actions["safety_coeff"].item(),
            "temperature": actions["temperature"].item(),
            "target_period": actions["target_period"].item(),
        }

        total_log_prob = log_probs["continuous"].item() + log_probs["discrete"].item()

        return actions_dict, total_log_prob, value.item()


# 需要import F
import torch.nn.functional as F
