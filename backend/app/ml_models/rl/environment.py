"""
节能优化强化学习环境

实现马尔可夫决策过程 (MDP) 环境 (S5a)

状态空间 S:
- 当前负荷数据向量
- 电价时段标识
- 已执行措施状态向量
- 设备运行参数
- 累计节能收益
- 效果达成率历史

动作空间 A:
- 调整措施优先级权重 (连续, 0.5-2.0)
- 修改转移负荷目标时段 (离散, 0-4)
- 调整需量安全系数 (连续, 1.0-1.2)
- 变更温度设定目标值 (连续, 24-28)

奖励函数 R:
R_t = ActualSaving_t / ExpectedSaving_t - lambda1 * ComfortViolation - lambda2 * SafetyViolation
"""

import numpy as np
from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class ActionSpace:
    """动作空间定义"""

    # 连续动作边界
    priority_weight_range: Tuple[float, float] = (0.5, 2.0)
    safety_coeff_range: Tuple[float, float] = (1.0, 1.2)
    temperature_range: Tuple[float, float] = (24.0, 28.0)
    # 离散动作数量
    num_target_periods: int = 5  # 尖峰/高峰/平段/低谷/深谷


@dataclass
class StateSpace:
    """状态空间定义"""

    load_data_dim: int = 16  # 最近16个时间步的负荷
    price_period_dim: int = 5  # 时段类型one-hot
    measure_state_dim: int = 10  # 最多10个措施的状态
    device_param_dim: int = 8  # 关键设备参数
    history_dim: int = 10  # 达成率历史序列长度

    @property
    def total_dim(self) -> int:
        return (
            self.load_data_dim
            + self.price_period_dim
            + self.measure_state_dim
            + self.device_param_dim
            + 2
            + self.history_dim
        )  # +2 for cumulative_saving and current_rate


class EnergySavingEnv:
    """
    节能优化强化学习环境

    实现专利 S5a 中的MDP模型
    """

    def __init__(
        self,
        state_space: Optional[StateSpace] = None,
        action_space: Optional[ActionSpace] = None,
        lambda_comfort: float = 0.1,
        lambda_safety: float = 0.2,
        max_steps: int = 100,
    ):
        self.state_space = state_space or StateSpace()
        self.action_space = action_space or ActionSpace()
        self.lambda_comfort = lambda_comfort
        self.lambda_safety = lambda_safety
        self.max_steps = max_steps

        # 状态变量
        self._step_count = 0
        self._state = None
        self._cumulative_saving = 0.0
        self._achievement_history = []

        # 模拟参数
        self._expected_saving = 100.0  # 预期节能收益
        self._comfort_threshold = 26.0  # 舒适度阈值
        self._safety_threshold = 0.95  # 安全阈值

    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        """重置环境"""
        if seed is not None:
            np.random.seed(seed)

        self._step_count = 0
        self._cumulative_saving = 0.0
        self._achievement_history = [0.9] * self.state_space.history_dim

        self._state = self._build_state()
        return self._state

    def sync_context(self, state: Dict[str, Any]) -> None:
        """Synchronize internal transition context with an externally supplied state."""
        self._step_count = 0
        self._cumulative_saving = float(state.get("cumulative_saving", 0))

        current_rate = float(state.get("achievement_rate", 0.9))
        history = [float(value) for value in state.get("achievement_history", [])]
        if len(history) < self.state_space.history_dim:
            history = [current_rate] * (self.state_space.history_dim - len(history)) + history
        self._achievement_history = history[-self.state_space.history_dim :]

    def _build_state(self) -> np.ndarray:
        """构建状态向量"""
        # 负荷数据 (模拟)
        load_data = np.random.uniform(50, 200, self.state_space.load_data_dim)

        # 电价时段 (one-hot)
        current_period = np.random.randint(0, 5)
        price_period = np.zeros(self.state_space.price_period_dim)
        price_period[current_period] = 1.0

        # 措施状态 (模拟: 0=未执行, 1=执行中, 2=完成)
        measure_states = np.random.randint(0, 3, self.state_space.measure_state_dim).astype(float) / 2

        # 设备参数 (归一化)
        device_params = np.random.uniform(0, 1, self.state_space.device_param_dim)

        # 累计收益和当前达成率
        cumulative = np.array([self._cumulative_saving / 1000])  # 归一化
        current_rate = np.array([np.mean(self._achievement_history[-5:])])

        # 达成率历史
        history = np.array(self._achievement_history[-self.state_space.history_dim :])

        state = np.concatenate(
            [load_data, price_period, measure_states, device_params, cumulative, current_rate, history]
        )

        return state.astype(np.float32)

    def step(self, action: Dict[str, Any]) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        执行动作

        Args:
            action: 包含以下键的字典
                - priority_weight: float
                - target_period: int
                - safety_coeff: float
                - temperature: float

        Returns:
            next_state, reward, done, info
        """
        self._step_count += 1

        # 解析动作
        priority = action.get("priority_weight", 1.0)
        target_period = action.get("target_period", 2)
        safety_coeff = action.get("safety_coeff", 1.05)
        temperature = action.get("temperature", 26.0)

        # 模拟实际节能效果 (基于动作计算)
        base_saving = self._expected_saving * priority * 0.5
        period_bonus = (4 - target_period) * 5  # 转到低谷时段奖励更高
        actual_saving = base_saving + period_bonus + np.random.normal(0, 10)
        actual_saving = max(0, actual_saving)

        # 计算达成率
        achievement_rate = actual_saving / self._expected_saving if self._expected_saving > 0 else 1.0
        achievement_rate = np.clip(achievement_rate, 0, 2)

        # 计算舒适度违反程度
        comfort_violation = max(0, temperature - self._comfort_threshold) / 4.0

        # 计算安全约束违反
        safety_violation = 1.0 if safety_coeff < self._safety_threshold else 0.0

        # 计算奖励 (S5a奖励函数)
        reward = achievement_rate - self.lambda_comfort * comfort_violation - self.lambda_safety * safety_violation

        # 更新状态
        self._cumulative_saving += actual_saving
        self._achievement_history.append(achievement_rate)

        # 构建下一状态
        next_state = self._build_state()

        # 检查终止条件
        done = self._step_count >= self.max_steps

        info = {
            "actual_saving": actual_saving,
            "expected_saving": self._expected_saving,
            "achievement_rate": achievement_rate,
            "comfort_violation": comfort_violation,
            "safety_violation": safety_violation,
            "cumulative_saving": self._cumulative_saving,
            "step": self._step_count,
        }

        self._state = next_state
        return next_state, reward, done, info

    def get_state_dim(self) -> int:
        """获取状态维度"""
        return self.state_space.total_dim

    def get_action_spec(self) -> Dict[str, Any]:
        """获取动作规格"""
        return {
            "continuous": {
                "priority_weight": self.action_space.priority_weight_range,
                "safety_coeff": self.action_space.safety_coeff_range,
                "temperature": self.action_space.temperature_range,
            },
            "discrete": {"target_period": self.action_space.num_target_periods},
        }

    def set_expected_saving(self, value: float):
        """设置预期节能收益"""
        self._expected_saving = value
