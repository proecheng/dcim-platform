"""
自适应优化服务 (专利 S5)

封装 AdaptiveOptimizer 与业务系统的集成:
- S5a: MDP 环境交互
- S5e: 动作转换为方案参数调整
- S5f: 自适应探索率调整
- 在线学习接口
- 优化历史记录
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.energy import (
    EnergySavingProposal, RLOptimizationHistory,
    RLTrainingLog, RLModelState
)

logger = logging.getLogger(__name__)


class AdaptiveOptimizationService:
    """
    自适应优化服务

    连接 RL Agent 与数据库，提供完整的优化闭环:
    1. 接收系统状态 → RL 输出调整建议
    2. 记录优化历史
    3. 接收效果反馈 → 在线训练
    4. 管理模型状态和探索率
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._optimizer = None
        self._ml_service = None

    def _get_optimizer(self):
        """延迟加载 AdaptiveOptimizer"""
        if self._optimizer is None:
            try:
                from app.ml_models.rl.agent import AdaptiveOptimizer
                from app.ml_models.config import MLConfig
                self._optimizer = AdaptiveOptimizer(MLConfig())
                logger.info("AdaptiveOptimizer 初始化成功")
            except Exception as e:
                logger.warning(f"AdaptiveOptimizer 初始化失败: {e}")
        return self._optimizer

    def _get_ml_service(self):
        """延迟加载 MLEnergySavingService"""
        if self._ml_service is None:
            try:
                from app.services.ml_service import MLEnergySavingService
                from app.ml_models.config import MLConfig
                self._ml_service = MLEnergySavingService(MLConfig())
            except Exception as e:
                logger.warning(f"MLEnergySavingService 初始化失败: {e}")
        return self._ml_service

    # ==================== 优化接口 ====================

    async def optimize(
        self,
        proposal_id: int,
        current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        为方案执行 RL 优化 (S5e)

        参数:
            proposal_id: 方案ID
            current_state: 当前系统状态字典

        返回:
            优化结果，包含调整建议
        """
        optimizer = self._get_optimizer()
        if optimizer is None:
            return {"success": False, "error": "RL 优化器不可用"}

        # 验证方案存在
        stmt = select(EnergySavingProposal).where(
            EnergySavingProposal.id == proposal_id
        )
        result = await self.db.execute(stmt)
        proposal = result.scalar_one_or_none()
        if not proposal:
            return {"success": False, "error": f"方案不存在: {proposal_id}"}

        try:
            # 如果未提供状态，从方案构建
            if current_state is None:
                current_state = self._build_state_from_proposal(proposal)

            # 执行优化
            result = optimizer.optimize_scheme(current_state)

            # 记录优化历史
            history = RLOptimizationHistory(
                proposal_id=proposal_id,
                state_vector=current_state,
                state_summary=self._summarize_state(current_state),
                actions=result.get("raw_actions"),
                adjustments=self._serialize_adjustments(result.get("adjustments", {})),
                exploration=result.get("exploration", False),
                exploration_rate=Decimal(str(round(result.get("exploration_rate", 0), 4))),
                confidence=Decimal(str(round(result.get("confidence", 0), 4))),
                state_value=Decimal(str(round(result.get("state_value", 0), 4))),
            )
            self.db.add(history)
            await self.db.commit()
            await self.db.refresh(history)

            return {
                "success": True,
                "proposal_id": proposal_id,
                "optimization_id": history.id,
                "adjustments": result.get("adjustments", {}),
                "raw_actions": result.get("raw_actions"),
                "exploration": result.get("exploration", False),
                "exploration_rate": result.get("exploration_rate", 0),
                "confidence": result.get("confidence", 0),
                "state_value": result.get("state_value", 0),
            }

        except Exception as e:
            logger.error(f"RL 优化失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 在线训练接口 ====================

    async def train_step(
        self,
        actual_saving: float,
        expected_saving: float,
        comfort_violation: float = 0.0,
        safety_violation: float = 0.0,
        current_state: Optional[Dict[str, Any]] = None,
        proposal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行一步在线训练

        接收效果反馈并更新 RL 模型

        参数:
            actual_saving: 实际节能收益
            expected_saving: 预期节能收益
            comfort_violation: 舒适度违反程度 (0-1)
            safety_violation: 安全约束违反 (0-1)
            current_state: 当前状态
            proposal_id: 关联方案ID

        返回:
            训练结果
        """
        optimizer = self._get_optimizer()
        if optimizer is None:
            return {"success": False, "error": "RL 优化器不可用"}

        try:
            result = optimizer.train_step(
                actual_saving=actual_saving,
                expected_saving=expected_saving,
                comfort_violation=comfort_violation,
                safety_violation=safety_violation,
                current_state=current_state
            )

            # 记录训练日志
            update_info = result.get("update_info", {})
            network_updated = bool(update_info)

            log = RLTrainingLog(
                proposal_id=proposal_id,
                actual_saving=Decimal(str(actual_saving)),
                expected_saving=Decimal(str(expected_saving)),
                comfort_violation=Decimal(str(comfort_violation)),
                safety_violation=Decimal(str(safety_violation)),
                reward=Decimal(str(round(result.get("reward", 0), 4))),
                achievement_rate=Decimal(str(round(result.get("achievement_rate", 0), 4))),
                exploration_rate=Decimal(str(round(result.get("exploration_rate", 0), 4))),
                step_count=result.get("step", 0),
                policy_loss=Decimal(str(round(update_info.get("policy_loss", 0), 6))) if network_updated else None,
                value_loss=Decimal(str(round(update_info.get("value_loss", 0), 6))) if network_updated else None,
                entropy=Decimal(str(round(update_info.get("entropy", 0), 6))) if network_updated else None,
                network_updated=network_updated,
            )
            self.db.add(log)

            # 更新模型状态
            await self._update_model_state(optimizer, result)

            await self.db.commit()
            await self.db.refresh(log)

            return {
                "success": True,
                "training_log_id": log.id,
                "reward": result.get("reward", 0),
                "achievement_rate": result.get("achievement_rate", 0),
                "exploration_rate": result.get("exploration_rate", 0),
                "step": result.get("step", 0),
                "network_updated": network_updated,
                "update_info": update_info if network_updated else None,
            }

        except Exception as e:
            logger.error(f"RL 训练失败: {e}")
            return {"success": False, "error": str(e)}

    async def train_from_monitoring(self, proposal_id: int) -> Dict[str, Any]:
        """
        从监测数据自动训练 (S4e → S5 闭环)

        从 EffectMonitoringService 获取最新效果报告并触发训练
        """
        try:
            from app.services.effect_monitoring_service import EffectMonitoringService
            monitoring = EffectMonitoringService(self.db)

            # 获取效果汇总
            summary = await monitoring.get_effect_summary(proposal_id)
            if summary.get("total_reports", 0) == 0:
                return {"success": False, "error": "无监测数据"}

            latest = summary.get("latest_report", {})
            achievement = latest.get("achievement_rate", 0)

            # 获取方案预期收益
            stmt = select(EnergySavingProposal).where(
                EnergySavingProposal.id == proposal_id
            )
            result = await self.db.execute(stmt)
            proposal = result.scalar_one_or_none()
            if not proposal:
                return {"success": False, "error": f"方案不存在: {proposal_id}"}

            expected = float(proposal.total_benefit or 0) * 10000  # 万元→元
            actual = expected * achievement / 100 if achievement > 0 else 0

            # 执行训练
            return await self.train_step(
                actual_saving=actual,
                expected_saving=expected,
                proposal_id=proposal_id
            )

        except Exception as e:
            logger.error(f"从监测数据训练失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 模型信息 ====================

    async def get_model_info(self) -> Dict[str, Any]:
        """获取 RL 模型信息"""
        optimizer = self._get_optimizer()
        is_available = optimizer is not None

        # 从数据库获取持久化状态
        stmt = select(RLModelState).where(
            RLModelState.model_name == "adaptive_optimizer"
        ).order_by(desc(RLModelState.updated_at))
        result = await self.db.execute(stmt)
        model_state = result.scalar_one_or_none()

        info = {
            "model_name": "adaptive_optimizer",
            "is_available": is_available,
            "is_trained": False,
            "total_steps": 0,
            "total_episodes": 0,
            "exploration_rate": 0.3,
            "exploration_phase": "initial",
            "avg_reward": None,
            "avg_achievement_rate": None,
            "best_reward": None,
            "checkpoint_saved_at": None,
            "state_dim": None,
            "action_spec": None,
        }

        if is_available:
            info["is_trained"] = optimizer.is_trained
            info["exploration_rate"] = optimizer._exploration_rate
            info["total_steps"] = optimizer._step_count
            info["state_dim"] = optimizer.env.get_state_dim()
            info["action_spec"] = optimizer.env.get_action_spec()

            # 确定探索阶段
            if optimizer._step_count < 1000:
                info["exploration_phase"] = "initial"
            elif optimizer._exploration_rate <= 0.1:
                info["exploration_phase"] = "stable"
            elif optimizer._exploration_rate >= 0.2:
                info["exploration_phase"] = "fluctuating"
            else:
                info["exploration_phase"] = "decaying"

        if model_state:
            info["avg_reward"] = float(model_state.avg_reward) if model_state.avg_reward else None
            info["avg_achievement_rate"] = float(model_state.avg_achievement_rate) if model_state.avg_achievement_rate else None
            info["best_reward"] = float(model_state.best_reward) if model_state.best_reward else None
            info["checkpoint_saved_at"] = model_state.checkpoint_saved_at

        # 从训练日志统计
        stats_stmt = select(
            func.count(RLTrainingLog.id).label("total_steps"),
            func.avg(RLTrainingLog.reward).label("avg_reward"),
            func.avg(RLTrainingLog.achievement_rate).label("avg_achievement"),
            func.max(RLTrainingLog.reward).label("best_reward"),
        )
        stats_result = await self.db.execute(stats_stmt)
        stats = stats_result.first()
        if stats and stats.total_steps > 0:
            info["total_steps"] = max(info["total_steps"], stats.total_steps)
            info["avg_reward"] = info["avg_reward"] or (float(stats.avg_reward) if stats.avg_reward else None)
            info["avg_achievement_rate"] = info["avg_achievement_rate"] or (
                float(stats.avg_achievement) * 100 if stats.avg_achievement else None
            )
            info["best_reward"] = info["best_reward"] or (float(stats.best_reward) if stats.best_reward else None)

        return info

    # ==================== 优化历史 ====================

    async def get_optimization_history(
        self,
        proposal_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """获取方案的 RL 优化历史"""
        count_stmt = select(func.count(RLOptimizationHistory.id)).where(
            RLOptimizationHistory.proposal_id == proposal_id
        )
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        items_stmt = select(RLOptimizationHistory).where(
            RLOptimizationHistory.proposal_id == proposal_id
        ).order_by(desc(RLOptimizationHistory.created_at)).offset(offset).limit(limit)
        items_result = await self.db.execute(items_stmt)
        items = items_result.scalars().all()

        return {
            "total": total,
            "items": items,
        }

    async def apply_optimization(self, optimization_id: int) -> Dict[str, Any]:
        """标记优化建议为已应用"""
        stmt = select(RLOptimizationHistory).where(
            RLOptimizationHistory.id == optimization_id
        )
        result = await self.db.execute(stmt)
        history = result.scalar_one_or_none()

        if not history:
            return {"success": False, "error": f"优化记录不存在: {optimization_id}"}

        history.applied = True
        history.applied_at = datetime.now()
        await self.db.commit()

        return {"success": True, "optimization_id": optimization_id}

    # ==================== 探索率管理 ====================

    async def update_exploration_rate(
        self,
        exploration_rate: float,
        phase: Optional[str] = None
    ) -> Dict[str, Any]:
        """手动更新探索率"""
        optimizer = self._get_optimizer()
        if optimizer is None:
            return {"success": False, "error": "RL 优化器不可用"}

        old_rate = optimizer._exploration_rate
        optimizer._exploration_rate = exploration_rate

        # 更新数据库
        await self._update_model_state(optimizer, {
            "exploration_rate": exploration_rate,
            "step": optimizer._step_count,
        })
        await self.db.commit()

        return {
            "success": True,
            "old_rate": old_rate,
            "new_rate": exploration_rate,
            "phase": phase or "manual",
        }

    async def save_checkpoint(self) -> Dict[str, Any]:
        """保存模型检查点"""
        optimizer = self._get_optimizer()
        if optimizer is None:
            return {"success": False, "error": "RL 优化器不可用"}

        try:
            optimizer._save_checkpoint()

            # 更新数据库中的检查点时间
            model_state = await self._get_or_create_model_state()
            model_state.checkpoint_saved_at = datetime.now()
            model_state.checkpoint_path = str(optimizer.config.get_checkpoint_path("rl"))
            await self.db.commit()

            return {"success": True, "checkpoint_path": model_state.checkpoint_path}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 辅助方法 ====================

    def _build_state_from_proposal(self, proposal: EnergySavingProposal) -> Dict[str, Any]:
        """从方案构建 RL 状态"""
        measure_states = []
        for m in proposal.measures:
            if m.execution_status == "completed":
                measure_states.append(2)
            elif m.execution_status in ("executing", "in_progress"):
                measure_states.append(1)
            else:
                measure_states.append(0)

        return {
            "load_data": [100.0] * 16,
            "price_period": 2,
            "measure_states": measure_states[:10],
            "device_params": [0.5] * 8,
            "cumulative_saving": float(proposal.total_benefit or 0) * 10000,
            "achievement_rate": 0.9,
            "achievement_history": [0.9] * 10,
        }

    def _summarize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """生成状态摘要"""
        return {
            "price_period": state.get("price_period", 2),
            "num_measures": len(state.get("measure_states", [])),
            "cumulative_saving": state.get("cumulative_saving", 0),
            "achievement_rate": state.get("achievement_rate", 0),
        }

    def _serialize_adjustments(self, adjustments: Dict[str, Any]) -> Dict[str, Any]:
        """序列化调整建议 (确保 JSON 兼容)"""
        result = {}
        for key, val in adjustments.items():
            if isinstance(val, dict):
                result[key] = {k: (float(v) if isinstance(v, (Decimal,)) else v) for k, v in val.items()}
            else:
                result[key] = val
        return result

    async def _update_model_state(self, optimizer, result: Dict[str, Any]):
        """更新数据库中的模型状态"""
        model_state = await self._get_or_create_model_state()

        model_state.is_trained = optimizer.is_trained
        model_state.total_steps = optimizer._step_count
        model_state.exploration_rate = Decimal(str(round(result.get("exploration_rate", optimizer._exploration_rate), 4)))

        # 确定探索阶段
        if optimizer._step_count < 1000:
            model_state.exploration_phase = "initial"
        elif optimizer._exploration_rate <= 0.1:
            model_state.exploration_phase = "stable"
        elif optimizer._exploration_rate >= 0.2:
            model_state.exploration_phase = "fluctuating"
        else:
            model_state.exploration_phase = "decaying"

        # 更新统计
        achievements = optimizer._recent_achievements
        if achievements:
            model_state.avg_achievement_rate = Decimal(str(round(
                sum(achievements) / len(achievements) * 100, 2
            )))
            model_state.recent_achievements = achievements[-100:]

        reward = result.get("reward")
        if reward is not None:
            model_state.avg_reward = Decimal(str(round(reward, 4)))
            if model_state.best_reward is None or reward > float(model_state.best_reward):
                model_state.best_reward = Decimal(str(round(reward, 4)))

    async def _get_or_create_model_state(self) -> RLModelState:
        """获取或创建模型状态记录"""
        stmt = select(RLModelState).where(
            RLModelState.model_name == "adaptive_optimizer"
        )
        result = await self.db.execute(stmt)
        model_state = result.scalar_one_or_none()

        if model_state is None:
            model_state = RLModelState(model_name="adaptive_optimizer")
            self.db.add(model_state)
            await self.db.flush()

        return model_state
