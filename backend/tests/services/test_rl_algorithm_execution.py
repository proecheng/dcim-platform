import math

import numpy as np
import pytest
import torch

from app.ml_models.config import MLConfig
from app.ml_models.rl.agent import AdaptiveOptimizer


def build_state():
    return {
        "load_data": [100.0] * 16,
        "price_period": 2,
        "measure_states": [0, 1, 2],
        "device_params": [0.5] * 8,
        "cumulative_saving": 1000,
        "achievement_rate": 0.9,
        "achievement_history": [0.9] * 10,
    }


def build_optimizer(tmp_path, batch_size=64):
    np.random.seed(7)
    torch.manual_seed(7)
    config = MLConfig(checkpoint_dir=str(tmp_path))
    config.rl.actor_hidden_dims = [32]
    config.rl.batch_size = batch_size
    config.rl.update_epochs = 1
    return AdaptiveOptimizer(config)


def test_real_rl_optimization_returns_valid_business_actions(tmp_path):
    optimizer = build_optimizer(tmp_path)

    result = optimizer.optimize_scheme(build_state())

    actions = result["raw_actions"]
    assert 0.5 <= actions["priority_weight"] <= 2.0
    assert 1.0 <= actions["safety_coeff"] <= 1.2
    assert 24.0 <= actions["temperature"] <= 28.0
    assert 0 <= actions["target_period"] <= 4
    assert 0 <= result["confidence"] <= 1
    assert math.isfinite(result["state_value"])
    assert result["adjustments"]["priority_weight"]["value"] == pytest.approx(
        actions["priority_weight"], abs=0.001
    )


def test_rl_training_reward_and_ppo_update_are_finite(tmp_path):
    optimizer = build_optimizer(tmp_path, batch_size=2)

    first = optimizer.train_step(
        actual_saving=80,
        expected_saving=100,
        comfort_violation=0.5,
        safety_violation=0.25,
        current_state=build_state(),
    )
    second = optimizer.train_step(
        actual_saving=90,
        expected_saving=100,
        current_state=build_state(),
    )

    assert first["reward"] == pytest.approx(0.7)
    assert first["achievement_rate"] == pytest.approx(0.8)
    assert first["update_info"] == {}
    assert set(second["update_info"]) == {"policy_loss", "value_loss", "entropy"}
    assert all(math.isfinite(value) for value in second["update_info"].values())
    assert optimizer.is_trained is True


def test_manual_exploration_rate_survives_training(tmp_path):
    optimizer = build_optimizer(tmp_path)
    optimizer._exploration_rate = 0.27
    optimizer._exploration_phase = "manual"

    result = optimizer.train_step(
        actual_saving=80,
        expected_saving=100,
        comfort_violation=0.1,
        safety_violation=0.1,
        current_state=build_state(),
    )

    assert result["exploration_rate"] == pytest.approx(0.27)
    assert optimizer._exploration_phase == "manual"
