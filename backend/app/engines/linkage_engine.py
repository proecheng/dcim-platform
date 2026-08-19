"""
联动引擎 — 策略匹配与动作执行
Story 9-1: 联动引擎核心框架
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.database import async_session
from ..models.linkage import LinkagePolicy, LinkageExecution, LinkageLog
from .event_bus import Event, get_event_bus
from .action_handlers import default_registry, ActionHandlerRegistry

logger = logging.getLogger(__name__)


class LinkageEngine:
    """联动引擎 — 核心类"""

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        self._policy_cache: Dict[int, dict] = {}
        self._handler_registry: ActionHandlerRegistry = default_registry()

    async def load_policies(self, session: Optional[AsyncSession] = None) -> int:
        """从数据库加载所有启用的策略到内存缓存"""
        if session is None:
            async with async_session() as managed_session:
                return await self._load_policies(managed_session)
        return await self._load_policies(session)

    async def _load_policies(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(LinkagePolicy)
            .where(LinkagePolicy.is_enabled == True)  # noqa: E712
            .options(selectinload(LinkagePolicy.actions))
        )
        policies = result.scalars().all()

        # 构建新缓存（copy-on-write）— 存储纯 dict，避免 detached ORM 对象
        new_cache: Dict[int, dict] = {}
        for p in policies:
            actions_data = []
            if hasattr(p, "actions") and p.actions is not None:
                sorted_actions = sorted(p.actions, key=lambda a: a.sort_order if a.sort_order is not None else 0)
                actions_data = [
                    {
                        "id": a.id,
                        "action_type": a.action_type,
                        "action_config": a.action_config,
                        "sort_order": a.sort_order,
                        "timeout_seconds": a.timeout_seconds,
                        "retry_count": a.retry_count,
                    }
                    for a in sorted_actions
                ]
            new_cache[p.id] = {
                "id": p.id,
                "name": p.name,
                "trigger_type": p.trigger_type,
                "trigger_condition": p.trigger_condition,
                "priority": p.priority,
                "is_system": p.is_system,
                "actions": actions_data,
            }

        # 原子替换
        self._policy_cache = new_cache
        logger.info("联动引擎: 已加载 %d 条策略", len(new_cache))
        return len(new_cache)

    async def reload_policies(self, session: Optional[AsyncSession] = None) -> int:
        """重新加载策略缓存（公开接口）"""
        try:
            return await self.load_policies(session)
        except Exception as e:
            logger.warning("联动引擎: 重新加载策略失败: %s", e)
            return len(self._policy_cache)

    async def on_event(self, event: Event) -> None:
        """事件处理入口 — 评估并执行匹配的策略"""
        matched = self._evaluate(event)
        if not matched:
            logger.debug("联动引擎: 事件 %s 无匹配策略", event.event_type)
            return

        logger.info(
            "联动引擎: 事件 %s 匹配 %d 条策略, is_test=%s",
            event.event_type,
            len(matched),
            event.is_test,
        )

        # 按优先级排序执行
        priority_order = {"fire_signal": 0, "critical": 1, "normal": 2}
        matched.sort(key=lambda p: priority_order.get(p.get("priority", "normal"), 2))

        for policy_data in matched:
            try:
                await self._execute_policy(policy_data, event)
            except Exception as e:
                logger.error("联动引擎: 策略 %s 执行异常: %s", policy_data["name"], e)

    def _evaluate(self, event: Event) -> List[dict]:
        """评估事件，返回匹配的策略列表"""
        matched = []
        for policy_data in self._policy_cache.values():
            # 匹配 trigger_type
            if policy_data["trigger_type"] != event.event_type:
                continue

            # 匹配 trigger_condition
            condition = policy_data.get("trigger_condition")
            if condition is not None:
                if not self._match_condition(condition, event.payload):
                    continue

            matched.append(policy_data)
        return matched

    # 策略元数据字段 — 不参与事件匹配（仅用于前端展示和策略管理）
    _CONDITION_META_KEYS = {"fire_level"}

    def _match_condition(self, condition: dict, payload: dict) -> bool:
        """简单条件匹配 — 检查 payload 是否包含 condition 中的所有键值"""
        if not condition:
            return True
        for key, expected in condition.items():
            # 跳过策略元数据字段（如 fire_level），不参与事件匹配
            if key in self._CONDITION_META_KEYS:
                continue
            actual = payload.get(key)
            if actual is None:
                return False
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    async def _execute_policy(self, policy_data: dict, event: Event) -> None:
        """执行单条策略的所有动作"""
        start_time = time.time()
        event_id = str(uuid.uuid4())

        # 创建执行记录
        async with async_session() as session:
            execution = LinkageExecution(
                policy_id=policy_data["id"],
                event_id=event_id,
                trigger_source=event.source,
                trigger_event={
                    "event_type": event.event_type,
                    "priority": event.priority.value,
                    "payload": event.payload,
                    "is_test": event.is_test,
                },
                status="executing",
            )
            session.add(execution)
            await session.commit()
            await session.refresh(execution)
            execution_id = execution.id

        actions = policy_data.get("actions", [])
        if not actions:
            # 无动作，直接标记完成
            await self._update_execution_status(execution_id, "completed", start_time)
            return

        # 并行执行所有动作
        results = await asyncio.gather(
            *[self._execute_action(execution_id, action, event) for action in actions],
            return_exceptions=True,
        )

        # 统计结果
        success_count = 0
        fail_count = 0
        for r in results:
            if isinstance(r, Exception):
                fail_count += 1
            elif r is True:
                success_count += 1
            else:
                fail_count += 1

        if fail_count == 0:
            status = "completed"
        elif success_count == 0:
            status = "failed"
        else:
            status = "partial_failure"

        await self._update_execution_status(execution_id, status, start_time)

        # 广播联动执行结果到 WebSocket
        try:
            from ..services.websocket import ws_manager

            await ws_manager.broadcast_linkage(
                {
                    "execution_id": execution_id,
                    "policy_name": policy_data["name"],
                    "status": status,
                    "event_type": event.event_type,
                    "is_test": event.is_test,
                },
                site_id=event.payload.get("site_id"),
            )
        except Exception as e:
            logger.warning("联动引擎: WebSocket 广播失败: %s", e)

        # 失败告警通知 — partial_failure 或 failed 时通知运维工程师（Story 9-2）
        if status in ("partial_failure", "failed"):
            try:
                from ..services.websocket import ws_manager

                await ws_manager.broadcast_alarm(
                    {
                        "action": "linkage_failure",
                        "alarm_level": "critical",
                        "alarm_message": f"联动策略执行{'部分失败' if status == 'partial_failure' else '失败'}: "
                        f"{policy_data['name']}（失败 {fail_count} 个动作）",
                        "execution_id": execution_id,
                        "policy_name": policy_data["name"],
                        "event_id": event_id,
                    },
                    site_id=event.payload.get("site_id"),
                )
            except Exception as e:
                logger.warning("联动引擎: 失败告警通知发送失败: %s", e)

    async def _execute_action(self, execution_id: int, action: dict, event: Event) -> bool:
        """执行单个动作并记录日志（含重试机制）"""
        action_start = time.time()
        action_id = action.get("id")
        action_type = action.get("action_type", "")
        action_config = action.get("action_config")
        timeout_seconds = action.get("timeout_seconds")

        # 读取重试次数（审查修复 C1/M4）
        retry_count = action.get("retry_count")
        if retry_count is None:
            retry_count = 0

        # 创建日志记录
        async with async_session() as session:
            log_entry = LinkageLog(
                execution_id=execution_id,
                action_id=action_id,
                action_type=action_type,
                action_config=action_config,
                status="executing",
                started_at=datetime.now(),
            )
            session.add(log_entry)
            await session.commit()
            await session.refresh(log_entry)
            log_id = log_entry.id

        handler = self._handler_registry.get_handler(action_type)

        if handler is None:
            await self._update_log(log_id, "skipped", "未找到动作处理器", action_start)
            return False

        config = action_config if action_config is not None else {}

        timeout = timeout_seconds if timeout_seconds is not None else 3

        # 执行（含重试）— 每次尝试有独立的 wait_for 超时（审查修复 C3）
        max_attempts = 1 + retry_count
        last_error = None
        for attempt in range(max_attempts):
            try:
                result = await asyncio.wait_for(
                    handler.execute(config, event),
                    timeout=timeout,
                )
                if result.success:
                    await self._update_log(log_id, result.status, result.error_message, action_start)
                    return True
                else:
                    last_error = result.error_message
                    if attempt < max_attempts - 1:
                        logger.info(
                            "联动引擎: 动作 %s 第 %d 次执行失败，%0.1fs 后重试: %s",
                            action_type,
                            attempt + 1,
                            0.5,
                            last_error,
                        )
                        await asyncio.sleep(0.5)
                    else:
                        await self._update_log(log_id, result.status, result.error_message, action_start)
                        return False
            except asyncio.TimeoutError:
                last_error = f"动作执行超时（{timeout}秒）"
                if attempt < max_attempts - 1:
                    logger.info(
                        "联动引擎: 动作 %s 第 %d 次超时，%0.1fs 后重试",
                        action_type,
                        attempt + 1,
                        0.5,
                    )
                    await asyncio.sleep(0.5)
                else:
                    await self._update_log(log_id, "timeout", last_error, action_start)
                    return False
            except Exception as e:
                last_error = str(e)
                if attempt < max_attempts - 1:
                    logger.info(
                        "联动引擎: 动作 %s 第 %d 次异常，%0.1fs 后重试: %s",
                        action_type,
                        attempt + 1,
                        0.5,
                        last_error,
                    )
                    await asyncio.sleep(0.5)
                else:
                    await self._update_log(log_id, "failed", last_error, action_start)
                    return False

        # 不应到达此处
        await self._update_log(log_id, "failed", last_error, action_start)
        return False

    async def _update_execution_status(self, execution_id: int, status: str, start_time: float) -> None:
        """更新执行记录状态"""
        duration_ms = int((time.time() - start_time) * 1000)
        async with async_session() as session:
            result = await session.execute(select(LinkageExecution).where(LinkageExecution.id == execution_id))
            execution = result.scalar_one_or_none()
            if execution is not None:
                execution.status = status
                execution.completed_at = datetime.now()
                execution.total_duration_ms = duration_ms
                await session.commit()

    async def _update_log(self, log_id: int, status: str, error_message: str | None, start_time: float) -> None:
        """更新日志记录"""
        duration_ms = int((time.time() - start_time) * 1000)
        async with async_session() as session:
            result = await session.execute(select(LinkageLog).where(LinkageLog.id == log_id))
            log_entry = result.scalar_one_or_none()
            if log_entry is not None:
                log_entry.status = status
                log_entry.error_message = error_message
                log_entry.completed_at = datetime.now()
                log_entry.duration_ms = duration_ms
                await session.commit()


# 全局单例
linkage_engine = LinkageEngine()
