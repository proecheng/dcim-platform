"""
自适应优化器

整合环境、Actor-Critic网络和PPO算法，实现节能方案的自适应优化

参考专利:
- S5e: 将Agent输出的动作转换为方案参数的增量调整
- S5f: 自适应探索率调整机制
"""

import logging
import torch
import numpy as np
from typing import Dict, Optional, Any

from .environment import EnergySavingEnv
from .actor_critic import ActorCriticNetwork
from .ppo import PPOAgent
from ..config import MLConfig

logger = logging.getLogger(__name__)


class AdaptiveOptimizer:
    """
    深度强化学习自适应优化器 (S5)

    功能:
    1. 构建MDP环境并与节能系统交互
    2. 使用PPO算法在线学习优化策略
    3. 输出方案参数调整建议
    4. 自适应探索率调整
    """

    def __init__(self, config: Optional[MLConfig] = None):
        if config is None:
            config = MLConfig()
        self.config = config
        self.rl_config = config.rl
        self.device = torch.device(config.device)

        # 创建环境
        self.env = EnergySavingEnv(
            lambda_comfort=self.rl_config.lambda_comfort, lambda_safety=self.rl_config.lambda_safety
        )

        state_dim = self.env.get_state_dim()

        # 创建网络
        self.network = ActorCriticNetwork(
            state_dim=state_dim, hidden_dim=self.rl_config.actor_hidden_dims[0], num_periods=5
        ).to(self.device)

        # 创建PPO代理
        self.ppo = PPOAgent(
            network=self.network,
            lr=self.rl_config.learning_rate,
            gamma=self.rl_config.gamma,
            gae_lambda=self.rl_config.gae_lambda,
            clip_epsilon=self.rl_config.clip_epsilon,
            buffer_size=self.rl_config.buffer_size,
            update_epochs=self.rl_config.update_epochs,
        )

        # 探索率调度 (S5f)
        self._exploration_rate = self.rl_config.initial_exploration_rate
        self._step_count = 0
        self._recent_achievements = []
        self._is_trained = False

        # 加载检查点
        self._load_checkpoint()

    def optimize_scheme(self, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        基于当前状态输出方案参数调整建议 (S5e)

        Args:
            current_state: 当前系统状态字典，包含
                - load_data: 负荷数据
                - price_period: 当前时段
                - measure_states: 措施状态
                - device_params: 设备参数等

        Returns:
            参数调整建议字典
        """
        # 构建状态向量
        if current_state is not None:
            state = self._build_state_vector(current_state)
        else:
            state = self.env.reset()

        # 是否探索
        explore = np.random.random() < self._exploration_rate

        # 选择动作
        actions, log_prob, value = self.ppo.select_action(state, explore=explore)

        # 转换为调整建议 (S5e)
        adjustments = self._translate_action(actions)

        return {
            "adjustments": adjustments,
            "raw_actions": actions,
            "exploration": explore,
            "exploration_rate": self._exploration_rate,
            "confidence": 1 - self._exploration_rate,
            "state_value": value,
        }

    def _translate_action(self, actions: Dict[str, float]) -> Dict[str, Any]:
        """
        将动作转换为参数调整指令 (S5e)

        - 优先级权重 -> 措施排序调整
        - 目标时段 -> 负荷转移目标
        - 安全系数 -> 需量控制参数
        - 温度设定 -> 空调控制指令
        """
        period_names = ["sharp_peak", "peak", "normal", "valley", "deep_valley"]
        target_period_idx = int(actions.get("target_period", 3))

        return {
            "priority_weight": {
                "value": round(actions.get("priority_weight", 1.0), 3),
                "description": "措施优先级权重调整",
            },
            "target_period": {
                "value": period_names[target_period_idx],
                "index": target_period_idx,
                "description": "建议转移至该时段",
            },
            "safety_coefficient": {"value": round(actions.get("safety_coeff", 1.05), 3), "description": "需量安全系数"},
            "temperature_setpoint": {
                "value": round(actions.get("temperature", 26.0), 1),
                "unit": "celsius",
                "description": "建议空调温度设定值",
            },
        }

    def train_step(
        self,
        actual_saving: float,
        expected_saving: float,
        comfort_violation: float = 0.0,
        safety_violation: float = 0.0,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行一步在线训练

        Args:
            actual_saving: 实际节能收益
            expected_saving: 预期节能收益
            comfort_violation: 舒适度违反程度
            safety_violation: 安全约束违反

        Returns:
            训练信息
        """
        self._step_count += 1

        # 构建状态
        state = self.env.reset() if current_state is None else self._build_state_vector(current_state)

        # 选择动作
        explore = np.random.random() < self._exploration_rate
        actions, log_prob, value = self.ppo.select_action(state, explore=explore)

        # 计算奖励
        achievement_rate = actual_saving / expected_saving if expected_saving > 0 else 1.0
        reward = (
            achievement_rate
            - self.rl_config.lambda_comfort * comfort_violation
            - self.rl_config.lambda_safety * safety_violation
        )

        # 获取下一状态
        next_state, _, _, _ = self.env.step(actions)

        # 存储经验
        continuous_actions = np.array([actions["priority_weight"], actions["safety_coeff"], actions["temperature"]])
        self.ppo.buffer.store(
            state, continuous_actions, int(actions["target_period"]), reward, next_state, False, log_prob, value
        )

        # 记录达成率
        self._recent_achievements.append(achievement_rate)
        if len(self._recent_achievements) > 100:
            self._recent_achievements.pop(0)

        # 更新探索率 (S5f)
        self._update_exploration_rate()

        # 定期更新网络
        update_info = {}
        if len(self.ppo.buffer) >= self.rl_config.batch_size:
            update_info = self.ppo.update()
            self._is_trained = True

        return {
            "reward": reward,
            "achievement_rate": achievement_rate,
            "exploration_rate": self._exploration_rate,
            "step": self._step_count,
            "update_info": update_info,
        }

    def _update_exploration_rate(self):
        """
        自适应探索率调整 (S5f)

        - 初始阶段（前1000步）: epsilon = 0.3
        - 稳定阶段（连续100步达成率 > 90%）: epsilon = 0.1
        - 波动阶段（连续3次 < 80%）: epsilon = 0.2
        """
        if self._step_count < 1000:
            self._exploration_rate = 0.3
            return

        recent = (
            self._recent_achievements[-100:] if len(self._recent_achievements) >= 100 else self._recent_achievements
        )

        if len(recent) >= 100 and all(r > 0.9 for r in recent):
            # 稳定阶段
            self._exploration_rate = 0.1
        elif len(recent) >= 3 and all(r < 0.8 for r in recent[-3:]):
            # 波动阶段
            self._exploration_rate = 0.2
        else:
            # 默认逐步衰减
            self._exploration_rate = max(0.1, 0.3 * (0.999 ** (self._step_count - 1000)))

    def _build_state_vector(self, state_dict: Dict[str, Any]) -> np.ndarray:
        """将状态字典转换为向量"""
        parts = []

        # 负荷数据 (填充到16维)
        load_data = np.array(state_dict.get("load_data", [100.0] * 16), dtype=np.float32)[:16]
        if len(load_data) < 16:
            load_data = np.pad(load_data, (0, 16 - len(load_data)))
        parts.append(load_data)

        # 电价时段 (one-hot, 5维)
        period = state_dict.get("price_period", 2)
        period_onehot = np.zeros(5, dtype=np.float32)
        period_onehot[min(period, 4)] = 1.0
        parts.append(period_onehot)

        # 措施状态 (10维)
        measures = np.array(state_dict.get("measure_states", [0] * 10), dtype=np.float32)[:10]
        if len(measures) < 10:
            measures = np.pad(measures, (0, 10 - len(measures)))
        parts.append(measures / 2.0)  # 归一化

        # 设备参数 (8维)
        device_params = np.array(state_dict.get("device_params", [0.5] * 8), dtype=np.float32)[:8]
        if len(device_params) < 8:
            device_params = np.pad(device_params, (0, 8 - len(device_params)), constant_values=0.5)
        parts.append(device_params)

        # 累计收益和达成率 (2维)
        saving = state_dict.get("cumulative_saving", 0) / 1000.0
        rate = state_dict.get("achievement_rate", 0.9)
        parts.append(np.array([saving, rate], dtype=np.float32))

        # 达成率历史 (10维)
        history = np.array(state_dict.get("achievement_history", [0.9] * 10), dtype=np.float32)[-10:]
        if len(history) < 10:
            history = np.pad(history, (0, 10 - len(history)), constant_values=0.9)
        parts.append(history)

        return np.concatenate(parts)

    def _load_checkpoint(self) -> bool:
        """加载模型检查点"""
        ckpt_path = self.config.get_checkpoint_path("rl")
        if ckpt_path.exists():
            try:
                checkpoint = torch.load(ckpt_path, map_location=self.device, weights_only=True)
                self.network.load_state_dict(checkpoint)
                self._is_trained = True
                logger.info(f"RL模型检查点已加载: {ckpt_path}")
                return True
            except Exception as e:
                logger.warning(f"加载RL检查点失败: {e}")
        return False

    def _save_checkpoint(self):
        """保存模型检查点"""
        ckpt_path = self.config.get_checkpoint_path("rl")
        ckpt_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.network.state_dict(), ckpt_path)
        logger.info(f"RL模型已保存: {ckpt_path}")

    @property
    def is_trained(self) -> bool:
        return self._is_trained
