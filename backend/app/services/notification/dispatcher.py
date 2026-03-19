"""
通知分发器 + 重试队列
Story 34.2 — 通知渠道适配器框架
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import update

from app.core.database import async_session
from app.models.notification_record import NotificationRecord
from app.schemas.notification import (
    AlarmNotificationContext,
    get_subject_for_channel,
    get_template_for_channel,
    render_notification,
)
from .adapters import ADAPTER_REGISTRY, NotificationResult

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """异步通知分发器 + 重试队列"""

    def __init__(self):
        self._retry_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动重试 worker — 在 lifespan startup 调用"""
        self._worker_task = asyncio.create_task(self._retry_worker())
        logger.info("通知重试 worker 已启动")

    async def shutdown(self):
        """优雅关闭 — 在 lifespan shutdown 调用"""
        self._shutdown_event.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=30)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        await self._drain_queue()
        logger.info("通知分发器已关闭")

    async def send_notification(
        self,
        context: AlarmNotificationContext,
        channel_type: str,
        contact_value: str,
        user_id: Optional[int],
        policy_id: Optional[int] = None,
        platform: Optional[str] = None,
    ):
        """发送单条通知 — 创建 NotificationRecord + 调用适配器"""
        subject = render_notification(get_subject_for_channel(channel_type), context)
        content = render_notification(get_template_for_channel(channel_type), context)

        # 1. 创建 NotificationRecord(status=pending)
        async with async_session() as session:
            record = NotificationRecord(
                alarm_id=context.alarm_id,
                user_id=user_id,
                policy_id=policy_id,
                channel_type=channel_type,
                platform=platform,
                contact_value=contact_value,
                content_summary=subject[:500],
                status="pending",
                max_retries=3,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            record_id = record.id

        # 2. 调用 adapter
        adapter = ADAPTER_REGISTRY.get(channel_type)
        if not adapter or not adapter.is_enabled():
            async with async_session() as session:
                rec = await session.get(NotificationRecord, record_id)
                if rec:
                    rec.status = "failed"
                    rec.error_message = f"渠道 {channel_type} 未启用"
                    await session.commit()
            return

        result = await adapter.send(contact_value, subject, content, context)

        # 3. 更新记录
        async with async_session() as session:
            rec = await session.get(NotificationRecord, record_id)
            if not rec:
                return
            if result.success:
                rec.status = "sent"
                rec.sent_at = datetime.now()
            else:
                rec.status = "failed"
                rec.error_message = result.error_message
                await session.commit()
                if rec.retry_count < rec.max_retries:
                    try:
                        self._retry_queue.put_nowait(record_id)
                    except asyncio.QueueFull:
                        logger.error("重试队列已满，丢弃: record_id=%d", record_id)
                return
            await session.commit()

    async def _retry_worker(self):
        """后台重试协程 — 指数退避"""
        while not self._shutdown_event.is_set():
            try:
                record_id = await asyncio.wait_for(
                    self._retry_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # 从 DB 加载 record
            async with async_session() as session:
                record = await session.get(NotificationRecord, record_id)
                if not record or record.retry_count >= record.max_retries:
                    continue
                delay = min(30 * (2 ** record.retry_count), 300)
                channel_type = record.channel_type
                contact_value = record.contact_value
                content_summary = record.content_summary

            await asyncio.sleep(delay)
            await self._retry_send(record_id, channel_type, contact_value, content_summary)

    async def _retry_send(
        self,
        record_id: int,
        channel_type: str,
        contact_value: str,
        content_summary: Optional[str],
    ):
        """重试发送单条通知"""
        # 更新状态为 retrying
        async with async_session() as session:
            record = await session.get(NotificationRecord, record_id)
            if not record or record.status == "sent":
                return
            record.retry_count += 1
            record.status = "retrying"
            await session.commit()

        adapter = ADAPTER_REGISTRY.get(channel_type)
        if not adapter or not adapter.is_enabled():
            async with async_session() as session:
                record = await session.get(NotificationRecord, record_id)
                if record:
                    record.status = "failed"
                    record.error_message = f"渠道 {channel_type} 未启用"
                    await session.commit()
            return

        subject = content_summary or "DCIM告警通知"
        result = await adapter.send(contact_value, subject, subject, None)

        async with async_session() as session:
            record = await session.get(NotificationRecord, record_id)
            if not record:
                return
            if result.success:
                record.status = "sent"
                record.sent_at = datetime.now()
            else:
                record.status = "failed"
                record.error_message = result.error_message
                if record.retry_count < record.max_retries:
                    try:
                        self._retry_queue.put_nowait(record_id)
                    except asyncio.QueueFull:
                        logger.error("重试队列已满，丢弃: record_id=%d", record_id)
            await session.commit()

    async def _drain_queue(self):
        """优雅关闭时清空队列 — 批量更新为 failed"""
        record_ids = []
        while not self._retry_queue.empty():
            try:
                record_ids.append(self._retry_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if record_ids:
            async with async_session() as session:
                await session.execute(
                    update(NotificationRecord)
                    .where(NotificationRecord.id.in_(record_ids))
                    .values(status="failed", error_message="进程关闭，重试中断")
                )
                await session.commit()
            logger.info("关闭时清空重试队列: %d 条记录标记为 failed", len(record_ids))


# 全局单例
notification_dispatcher = NotificationDispatcher()
