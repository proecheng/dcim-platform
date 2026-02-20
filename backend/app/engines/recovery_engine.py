"""
恢复引擎 — 联动恢复流程
Story 9-4: 联动恢复流程
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select

from ..core.database import async_session
from ..models.linkage import (
    LinkageRecovery,
    LinkageRecoveryLog,
)
from .action_handlers import default_registry, ActionHandlerRegistry
from .event_bus import Event, EventPriority

logger = logging.getLogger(__name__)

# 不需要恢复的动作类型（通知类，不可逆）— 审查修复 H1
_SKIP_ACTION_TYPES = {"ALARM_NOTIFY", "VIDEO_POPUP"}

# 恢复命令映射: (action_type, command) -> recovery_command — 审查修复 C1
RECOVERY_COMMAND_MAP: Dict[Tuple[str, Optional[str]], str] = {
    ("MQTT_COMMAND", "shutdown"): "start",
    ("MQTT_COMMAND", "start"): "stop",
    ("MQTT_COMMAND", "cutoff"): "restore",
    ("MQTT_COMMAND", "unlock"): "lock",
    ("MQTT_COMMAND", "activate"): "deactivate",
    ("VIDEO_RECORD", None): "stop",
}

# 预设恢复顺序（越小越先执行）
RECOVERY_ORDER: Dict[str, int] = {
    "ACCESS_CONTROL": 1,
    "EMERGENCY_LIGHTING": 2,
    "NON_CRITICAL_POWER": 3,
    "HVAC": 4,
    "EXHAUST_FAN": 5,
}
# 未在映射中的 target_type 默认排在最后
_DEFAULT_ORDER = 99


class RecoveryEngine:
    """恢复引擎"""

    def __init__(self) -> None:
        self._handler_registry: ActionHandlerRegistry = default_registry()

    def generate_recovery_steps(self, logs: List[dict]) -> List[dict]:
        """从成功执行的 LinkageLog 生成恢复步骤列表

        Args:
            logs: LinkageLog 记录列表（dict 格式，含 action_type, action_config, status）

        Returns:
            恢复步骤列表，按 RECOVERY_ORDER 排序
        """
        steps: List[dict] = []

        for log_data in logs:
            # 仅从成功执行的动作生成恢复步骤 — 审查修复 M1
            if log_data.get("status") != "success":
                continue

            action_type = log_data.get("action_type", "")

            # 跳过不可逆动作 — 审查修复 H1
            if action_type in _SKIP_ACTION_TYPES:
                continue

            action_config = log_data.get("action_config") or {}
            command = action_config.get("command")
            target_type = action_config.get("target_type", "")

            # 查找恢复命令 — 审查修复 C1
            recovery_cmd = RECOVERY_COMMAND_MAP.get((action_type, command))
            if recovery_cmd is None:
                # VIDEO_RECORD 没有 command 字段
                recovery_cmd = RECOVERY_COMMAND_MAP.get((action_type, None))
            if recovery_cmd is None:
                # 无法映射的动作，跳过
                logger.warning("恢复引擎: 无法映射恢复命令 action_type=%s command=%s", action_type, command)
                continue

            # 构建恢复动作配置
            recovery_config = {
                "command": recovery_cmd,
                "target_type": target_type,
                "message": f"恢复: {action_config.get('message', '')}",
            }

            order = RECOVERY_ORDER.get(target_type, _DEFAULT_ORDER)

            steps.append(
                {
                    "step_order": order,
                    "action_type": action_type,
                    "target_type": target_type,
                    "recovery_command": recovery_cmd,
                    "action_config": recovery_config,
                }
            )

        # 按恢复顺序排序
        steps.sort(key=lambda s: s["step_order"])

        # 重新编号 step_order（从 1 开始连续）
        for i, step in enumerate(steps):
            step["step_order"] = i + 1

        return steps

    async def start_recovery(self, recovery_id: int) -> None:
        """后台串行执行所有恢复步骤 — 审查修复 H3"""
        try:
            await self._do_recovery(recovery_id)
        except Exception as e:
            logger.error("恢复引擎异常: recovery_id=%d, %s", recovery_id, e, exc_info=True)
            # 标记失败
            async with async_session() as session:
                result = await session.execute(select(LinkageRecovery).where(LinkageRecovery.id == recovery_id))
                recovery = result.scalar_one_or_none()
                if recovery is not None:
                    recovery.status = "failed"
                    recovery.completed_at = datetime.now()
                    await session.commit()

    async def _do_recovery(self, recovery_id: int) -> None:
        """执行恢复流程"""
        start_time = time.time()

        async with async_session() as session:
            result = await session.execute(select(LinkageRecovery).where(LinkageRecovery.id == recovery_id))
            recovery = result.scalar_one_or_none()
            if recovery is None:
                return

            # 获取所有 pending 步骤
            logs_result = await session.execute(
                select(LinkageRecoveryLog)
                .where(
                    LinkageRecoveryLog.recovery_id == recovery_id,
                    LinkageRecoveryLog.status == "pending",
                )
                .order_by(LinkageRecoveryLog.step_order)
            )
            pending_steps = logs_result.scalars().all()

        success_count = 0
        fail_count = 0

        for step in pending_steps:
            ok = await self._execute_step_internal(step.id)
            if ok:
                success_count += 1
            else:
                fail_count += 1
            # 步骤失败不中断后续步骤

        # 更新恢复记录状态
        elapsed_ms = int((time.time() - start_time) * 1000)
        if fail_count == 0:
            status = "completed"
        elif success_count == 0:
            status = "failed"
        else:
            status = "partial_recovery"

        async with async_session() as session:
            result = await session.execute(select(LinkageRecovery).where(LinkageRecovery.id == recovery_id))
            recovery = result.scalar_one_or_none()
            if recovery is not None:
                recovery.status = status
                recovery.completed_at = datetime.now()
                recovery.total_duration_ms = elapsed_ms
                await session.commit()

        # WebSocket 广播恢复完成
        try:
            from ..services.websocket import ws_manager

            await ws_manager.broadcast_linkage(
                {
                    "action": "recovery_completed",
                    "recovery_id": recovery_id,
                    "status": status,
                    "duration_ms": elapsed_ms,
                }
            )
        except Exception as e:
            logger.warning("恢复引擎: WebSocket 广播失败: %s", e)

    async def execute_single_step(self, recovery_id: int, step_order: int) -> bool:
        """手动执行单个恢复步骤"""
        async with async_session() as session:
            result = await session.execute(
                select(LinkageRecoveryLog).where(
                    LinkageRecoveryLog.recovery_id == recovery_id,
                    LinkageRecoveryLog.step_order == step_order,
                )
            )
            step = result.scalar_one_or_none()
            if step is None:
                return False
            step_id = step.id

        ok = await self._execute_step_internal(step_id)

        # 检查是否所有步骤都已完成，更新恢复记录状态
        await self._check_recovery_completion(recovery_id)
        return ok

    async def skip_step(self, recovery_id: int, step_order: int) -> bool:
        """跳过单个恢复步骤"""
        async with async_session() as session:
            result = await session.execute(
                select(LinkageRecoveryLog).where(
                    LinkageRecoveryLog.recovery_id == recovery_id,
                    LinkageRecoveryLog.step_order == step_order,
                )
            )
            step = result.scalar_one_or_none()
            if step is None:
                return False
            if step.status != "pending":
                return False

            step.status = "skipped"
            step.completed_at = datetime.now()
            await session.commit()

        # 检查是否所有步骤都已完成
        await self._check_recovery_completion(recovery_id)
        return True

    async def _execute_step_internal(self, step_id: int) -> bool:
        """执行单个恢复步骤（内部方法）"""
        step_start = time.time()

        async with async_session() as session:
            result = await session.execute(select(LinkageRecoveryLog).where(LinkageRecoveryLog.id == step_id))
            step = result.scalar_one_or_none()
            if step is None:
                return False
            if step.status not in ("pending",):
                return step.status == "success"

            step.status = "executing"
            step.started_at = datetime.now()
            await session.commit()

            action_type = step.action_type
            action_config = step.action_config or {}

        # 通过 ActionHandler 执行
        handler = self._handler_registry.get_handler(action_type)
        if handler is None:
            await self._update_step(step_id, "failed", "未找到动作处理器", step_start)
            return False

        # 构建模拟事件（恢复操作）
        event = Event(
            event_type="recovery.execute",
            source="recovery_engine",
            priority=EventPriority.normal,
            payload=action_config,
        )

        try:
            result = await asyncio.wait_for(
                handler.execute(action_config, event),
                timeout=5,
            )
            if result.success:
                await self._update_step(step_id, "success", None, step_start)
                return True
            else:
                await self._update_step(step_id, "failed", result.error_message, step_start)
                return False
        except asyncio.TimeoutError:
            await self._update_step(step_id, "failed", "恢复步骤执行超时", step_start)
            return False
        except Exception as e:
            await self._update_step(step_id, "failed", str(e), step_start)
            return False

    async def _update_step(self, step_id: int, status: str, error_message: Optional[str], start_time: float) -> None:
        """更新恢复步骤状态"""
        duration_ms = int((time.time() - start_time) * 1000)
        async with async_session() as session:
            result = await session.execute(select(LinkageRecoveryLog).where(LinkageRecoveryLog.id == step_id))
            step = result.scalar_one_or_none()
            if step is not None:
                step.status = status
                step.error_message = error_message
                step.completed_at = datetime.now()
                step.duration_ms = duration_ms
                await session.commit()

    async def _check_recovery_completion(self, recovery_id: int) -> None:
        """检查恢复是否全部完成，更新恢复记录状态"""
        async with async_session() as session:
            result = await session.execute(
                select(LinkageRecoveryLog).where(
                    LinkageRecoveryLog.recovery_id == recovery_id,
                )
            )
            all_steps = result.scalars().all()

            # 如果还有 pending/executing 步骤，不更新
            if any(s.status in ("pending", "executing") for s in all_steps):
                return

            recovery_result = await session.execute(select(LinkageRecovery).where(LinkageRecovery.id == recovery_id))
            recovery = recovery_result.scalar_one_or_none()
            if recovery is None or recovery.status not in ("executing",):
                return

            success_count = sum(1 for s in all_steps if s.status == "success")
            fail_count = sum(1 for s in all_steps if s.status == "failed")
            # skipped 不算失败

            if fail_count == 0:
                recovery.status = "completed"
            elif success_count == 0 and fail_count > 0:
                recovery.status = "failed"
            else:
                recovery.status = "partial_recovery"

            recovery.completed_at = datetime.now()
            if recovery.started_at:
                recovery.total_duration_ms = int((recovery.completed_at - recovery.started_at).total_seconds() * 1000)
            await session.commit()


# 全局单例
recovery_engine = RecoveryEngine()
