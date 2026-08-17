"""
自适应优化服务测试

覆盖:
  - AdaptiveOptimizationService._build_state_from_proposal: 状态构建
  - AdaptiveOptimizationService._summarize_state: 状态摘要
  - AdaptiveOptimizationService._serialize_adjustments: 调整序列化
  - AdaptiveOptimizationService.optimize: RL优化（优化器不可用时）
  - AdaptiveOptimizationService.train_step: 训练步骤（优化器不可用时）
  - AdaptiveOptimizationService.get_model_info: 模型信息
  - AdaptiveOptimizationService.get_optimization_history: 优化历史
  - AdaptiveOptimizationService.apply_optimization: 应用优化
"""

import pytest
from unittest.mock import MagicMock
from decimal import Decimal

from app.services.adaptive_optimization_service import AdaptiveOptimizationService
from app.models.energy import EnergySavingProposal, RLModelState, RLTrainingLog


class TestBuildStateFromProposal:
    """状态构建测试"""

    def test_build_state(self):
        """从方案构建RL状态"""
        svc = AdaptiveOptimizationService.__new__(AdaptiveOptimizationService)

        # 创建模拟方案
        proposal = MagicMock(spec=EnergySavingProposal)
        proposal.total_benefit = Decimal("5.0")  # 5万元

        # 模拟措施
        measure1 = MagicMock()
        measure1.execution_status = "completed"
        measure2 = MagicMock()
        measure2.execution_status = "pending"
        proposal.measures = [measure1, measure2]

        state = svc._build_state_from_proposal(proposal)
        assert "load_data" in state
        assert len(state["load_data"]) == 16
        assert state["price_period"] == 2
        assert state["measure_states"] == [2, 0]  # completed=2, pending=0
        assert state["cumulative_saving"] == 50000  # 5万元 * 10000


class TestSummarizeState:
    """状态摘要测试"""

    def test_summarize(self):
        """生成状态摘要"""
        svc = AdaptiveOptimizationService.__new__(AdaptiveOptimizationService)
        state = {
            "price_period": 3,
            "measure_states": [0, 1, 2],
            "cumulative_saving": 30000,
            "achievement_rate": 0.85,
        }
        summary = svc._summarize_state(state)
        assert summary["price_period"] == 3
        assert summary["num_measures"] == 3
        assert summary["cumulative_saving"] == 30000
        assert summary["achievement_rate"] == 0.85

    def test_summarize_empty_state(self):
        """空状态摘要"""
        svc = AdaptiveOptimizationService.__new__(AdaptiveOptimizationService)
        summary = svc._summarize_state({})
        assert summary["price_period"] == 2  # 默认值
        assert summary["num_measures"] == 0


class TestSerializeAdjustments:
    """调整序列化测试"""

    def test_serialize_with_decimal(self):
        """Decimal值应转为float"""
        svc = AdaptiveOptimizationService.__new__(AdaptiveOptimizationService)
        adjustments = {
            "temperature": {"delta": Decimal("2.5"), "target": Decimal("26.0")},
            "mode": "eco",
        }
        result = svc._serialize_adjustments(adjustments)
        assert result["temperature"]["delta"] == 2.5
        assert isinstance(result["temperature"]["delta"], float)
        assert result["mode"] == "eco"

    def test_serialize_empty(self):
        """空调整"""
        svc = AdaptiveOptimizationService.__new__(AdaptiveOptimizationService)
        result = svc._serialize_adjustments({})
        assert result == {}


class TestOptimize:
    """RL优化测试"""

    @pytest.mark.asyncio
    async def test_optimizer_unavailable(self, async_db):
        """优化器不可用时返回错误"""
        svc = AdaptiveOptimizationService(async_db)
        # 强制模拟优化器不可用
        svc._get_optimizer = lambda: None
        result = await svc.optimize(proposal_id=1)
        assert result["success"] is False
        assert "不可用" in result["error"]

    @pytest.mark.asyncio
    async def test_proposal_not_found(self, async_db):
        """方案不存在时返回错误"""
        svc = AdaptiveOptimizationService(async_db)
        # Mock 优化器可用
        mock_optimizer = MagicMock()
        svc._optimizer = mock_optimizer
        svc._get_optimizer = lambda: mock_optimizer

        result = await svc.optimize(proposal_id=99999)
        assert result["success"] is False
        assert "不存在" in result["error"]


class TestTrainStep:
    """训练步骤测试"""

    @pytest.mark.asyncio
    async def test_optimizer_unavailable(self, async_db):
        """优化器不可用时返回错误"""
        svc = AdaptiveOptimizationService(async_db)
        svc._get_optimizer = lambda: None
        result = await svc.train_step(actual_saving=1000, expected_saving=2000)
        assert result["success"] is False
        assert "不可用" in result["error"]


class TestGetModelInfo:
    """模型信息测试"""

    @pytest.mark.asyncio
    async def test_model_info_without_optimizer(self, async_db):
        """无优化器时返回基本信息"""
        svc = AdaptiveOptimizationService(async_db)
        svc._get_optimizer = lambda: None
        info = await svc.get_model_info()
        assert info["model_name"] == "adaptive_optimizer"
        assert info["is_available"] is False
        assert info["is_trained"] is False
        assert info["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_model_info_restores_persisted_shared_state(self, async_db, monkeypatch):
        state = RLModelState(
            model_name="adaptive_optimizer",
            is_trained=True,
            total_steps=12,
            exploration_rate=Decimal("0.18"),
            exploration_phase="manual",
            recent_achievements=[0.81, 0.92],
        )
        async_db.add(state)
        async_db.add(
            RLTrainingLog(
                actual_saving=Decimal("80"),
                expected_saving=Decimal("100"),
                reward=Decimal("0.8"),
                achievement_rate=Decimal("0.8"),
                exploration_rate=Decimal("0.18"),
                step_count=20,
            )
        )
        await async_db.commit()

        fake_env = MagicMock()
        fake_env.get_state_dim.return_value = 51
        fake_env.get_action_spec.return_value = {"continuous": {}, "discrete": {}}
        fake_optimizer = MagicMock()
        fake_optimizer._exploration_rate = 0.3
        fake_optimizer._step_count = 0
        fake_optimizer._is_trained = False
        fake_optimizer.is_trained = False
        fake_optimizer.env = fake_env
        del fake_optimizer._persistent_state_loaded
        monkeypatch.setattr(AdaptiveOptimizationService, "_shared_optimizer", fake_optimizer)

        svc = AdaptiveOptimizationService(async_db)
        info = await svc.get_model_info()

        assert svc._get_optimizer() is fake_optimizer
        assert fake_optimizer._exploration_rate == pytest.approx(0.18)
        assert fake_optimizer._step_count == 20
        assert fake_optimizer._is_trained is True
        assert fake_optimizer._exploration_phase == "manual"
        assert fake_optimizer._recent_achievements == [0.81, 0.92]
        assert info["exploration_rate"] == pytest.approx(0.18)
        assert info["exploration_phase"] == "manual"
        assert info["total_steps"] == 20


class TestGetOptimizationHistory:
    """优化历史测试"""

    @pytest.mark.asyncio
    async def test_empty_history(self, async_db):
        """无优化历史"""
        svc = AdaptiveOptimizationService(async_db)
        result = await svc.get_optimization_history(proposal_id=1)
        assert result["total"] == 0
        assert len(result["items"]) == 0


class TestApplyOptimization:
    """应用优化测试"""

    @pytest.mark.asyncio
    async def test_optimization_not_found(self, async_db):
        """优化记录不存在"""
        svc = AdaptiveOptimizationService(async_db)
        result = await svc.apply_optimization(optimization_id=99999)
        assert result["success"] is False
        assert "不存在" in result["error"]


class TestUpdateExplorationRate:
    """探索率更新测试"""

    @pytest.mark.asyncio
    async def test_optimizer_unavailable(self, async_db):
        """优化器不可用时返回错误"""
        svc = AdaptiveOptimizationService(async_db)
        svc._get_optimizer = lambda: None
        result = await svc.update_exploration_rate(0.1)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_manual_rate_and_phase_are_persisted(self, async_db):
        svc = AdaptiveOptimizationService(async_db)
        optimizer = MagicMock()
        optimizer._persistent_state_loaded = True
        optimizer._exploration_rate = 0.3
        optimizer._exploration_phase = "initial"
        optimizer._step_count = 4
        optimizer._recent_achievements = [0.8]
        optimizer.is_trained = False
        svc._get_optimizer = lambda: optimizer

        result = await svc.update_exploration_rate(0.27, phase="manual")

        assert result["new_rate"] == pytest.approx(0.27)
        assert optimizer._exploration_phase == "manual"
        state = await svc._get_or_create_model_state()
        assert float(state.exploration_rate) == pytest.approx(0.27)
        assert state.exploration_phase == "manual"


class TestSaveCheckpoint:
    """保存检查点测试"""

    @pytest.mark.asyncio
    async def test_optimizer_unavailable(self, async_db):
        """优化器不可用时返回错误"""
        svc = AdaptiveOptimizationService(async_db)
        svc._get_optimizer = lambda: None
        result = await svc.save_checkpoint()
        assert result["success"] is False
