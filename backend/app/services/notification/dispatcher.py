"""
通知分发器 + 重试队列
Story 34.2 — 通知渠道适配器框架
Story 34.4 — 通知分发器与告警引擎集成
Story 34.5 — 通知渠道升级
Story 34.6 — 告警风暴抑制
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update, func

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
        self._pending_tasks: set[asyncio.Task] = set()  # 防止 dispatch task 被 GC

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
        # 等待所有 pending dispatch tasks
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)
        await self._drain_queue()
        logger.info("通知分发器已关闭")

    # ==================== Story 34.4: 批量分发 ====================

    async def dispatch(self, alarm_data_list: list[dict]) -> dict[int, int]:
        """
        批量分发通知，返回 {alarm_id: sent_count} 映射。
        Story 34.6: 集成风暴检测 — 同站点告警超阈值时合并为摘要通知。

        alarm_data_list 结构（纯数据 dict，非 ORM 对象）:
        [{"alarm_id", "alarm_level", "alarm_message", "trigger_value",
          "threshold_value", "created_at", "site_id", "site_name",
          "device_name", "point_name"}, ...]
        """
        if not alarm_data_list:
            return {}

        from app.services.notification.storm import storm_detector

        result_map: dict[int, int] = {}

        # 按 site_id 分组（site_id=None 的跳过风暴检测，直接逐条分发）
        site_groups: dict[int, list[dict]] = {}
        no_site_alarms: list[dict] = []
        for alarm_data in alarm_data_list:
            sid = alarm_data.get("site_id")
            if sid is not None:
                site_groups.setdefault(sid, []).append(alarm_data)
            else:
                no_site_alarms.append(alarm_data)

        async with async_session() as db:
            # 有站点的告警：风暴检测
            for site_id, group in site_groups.items():
                # 一次性递增整组数量，判断是否风暴
                is_storm = await storm_detector.check_storm(
                    site_id, count=len(group)
                )

                if is_storm:
                    # 风暴模式：合并为摘要通知
                    sent = await self._dispatch_storm_summary(
                        db, site_id, group
                    )
                    for alarm_data in group:
                        result_map[alarm_data["alarm_id"]] = (
                            1 if sent > 0 else 0
                        )
                else:
                    # 正常模式：逐条分发
                    for alarm_data in group:
                        try:
                            sent = await self._dispatch_single(db, alarm_data)
                            result_map[alarm_data["alarm_id"]] = sent
                        except Exception as e:
                            logger.error(
                                "分发告警 %s 通知失败: %s",
                                alarm_data.get("alarm_id"),
                                e,
                                exc_info=True,
                            )
                            result_map[alarm_data["alarm_id"]] = 0

            # 无站点告警：直接逐条分发，不做风暴检测
            for alarm_data in no_site_alarms:
                try:
                    sent = await self._dispatch_single(db, alarm_data)
                    result_map[alarm_data["alarm_id"]] = sent
                except Exception as e:
                    logger.error(
                        "分发告警 %s 通知失败: %s",
                        alarm_data.get("alarm_id"),
                        e,
                        exc_info=True,
                    )
                    result_map[alarm_data["alarm_id"]] = 0

        return result_map

    async def _dispatch_storm_summary(
        self, db, site_id: int, alarm_data_list: list[dict]
    ) -> int:
        """风暴模式：合并告警为摘要通知发送"""
        from app.schemas.notification import build_storm_summary
        from app.services.notification.storm import storm_detector

        if not alarm_data_list:
            return 0

        # 使用最高级别告警来匹配策略
        level_priority = {"critical": 0, "major": 1, "minor": 2, "info": 3}
        sorted_alarms = sorted(
            alarm_data_list,
            key=lambda d: level_priority.get(d["alarm_level"], 99),
        )
        top_alarm = sorted_alarms[0]
        site_name = top_alarm.get("site_name") or "未知站点"

        # 匹配策略
        policy = await self._match_policy(
            db, site_id, top_alarm["alarm_level"]
        )
        if not policy:
            return 0

        user_ids = policy.notify_user_ids
        if isinstance(user_ids, str):
            user_ids = json.loads(user_ids)
        if not user_ids:
            return 0

        channels = policy.channels
        if isinstance(channels, str):
            channels = json.loads(channels)

        # 构建摘要（从 StormDetector 获取实际 window 值）
        _, window = await storm_detector.get_config()
        summary_text = build_storm_summary(
            site_name, alarm_data_list, window
        )

        # 构建 context（使用最高级别告警的信息）
        context = AlarmNotificationContext(
            alarm_id=top_alarm["alarm_id"],
            alarm_level=top_alarm["alarm_level"],
            alarm_message=summary_text,
            device_name=top_alarm.get("device_name"),
            point_name=top_alarm.get("point_name"),
            current_value=None,
            threshold_value=None,
            site_id=site_id,
            site_name=site_name,
            created_at=top_alarm.get("created_at") or datetime.now(),
        )

        sent_count = 0
        for channel in channels:
            contacts = await self._get_user_contacts(db, user_ids, channel)
            if not contacts:
                continue
            for user_id, contact_value, platform in contacts:
                try:
                    await self.send_notification(
                        context, channel, contact_value, user_id,
                        policy_id=policy.id, platform=platform,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        "风暴摘要通知发送异常: %s", e, exc_info=True
                    )

        if sent_count > 0:
            logger.info(
                "告警风暴摘要: 站点 %s, %d 条告警合并, 发送 %d 条通知",
                site_name, len(alarm_data_list), sent_count,
            )

        return sent_count

    async def _dispatch_single(self, db, alarm_data: dict) -> int:
        """处理单个告警的通知分发，返回发送数量"""
        site_id = alarm_data.get("site_id")
        alarm_level = alarm_data["alarm_level"]

        # 1. 匹配策略
        policy = await self._match_policy(db, site_id, alarm_level)
        if not policy:
            return 0

        # 2. 检查 notify_user_ids（JSON 列安全处理）
        user_ids = policy.notify_user_ids
        if isinstance(user_ids, str):
            user_ids = json.loads(user_ids)
        if not user_ids:
            return 0

        # 3. 获取渠道列表（JSON 列安全处理）
        channels = policy.channels
        if isinstance(channels, str):
            channels = json.loads(channels)

        # 4. 构建 context
        context = AlarmNotificationContext(
            alarm_id=alarm_data["alarm_id"],
            alarm_level=alarm_level,
            alarm_message=alarm_data.get("alarm_message") or "告警触发",
            device_name=alarm_data.get("device_name"),
            point_name=alarm_data.get("point_name"),
            current_value=alarm_data.get("trigger_value"),
            threshold_value=alarm_data.get("threshold_value"),
            site_id=site_id,
            site_name=alarm_data.get("site_name") or "未知站点",
            created_at=alarm_data.get("created_at") or datetime.now(),
        )

        # 5. 收集并串行发送（SQLite 写锁限制）
        sent_count = 0
        for channel in channels:
            contacts = await self._get_user_contacts(db, user_ids, channel)
            if not contacts:
                logger.debug(
                    "告警 %s 渠道 %s 无可用联系方式",
                    alarm_data["alarm_id"],
                    channel,
                )
                continue
            for user_id, contact_value, platform in contacts:
                try:
                    await self.send_notification(
                        context,
                        channel,
                        contact_value,
                        user_id,
                        policy_id=policy.id,
                        platform=platform,
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error("通知发送异常: %s", e, exc_info=True)
        return sent_count

    async def _match_policy(self, db, site_id: Optional[int], alarm_level: str):
        """匹配最具体的启用策略：站点策略优先于全局策略，按 id ASC"""
        from app.models.notification_policy import NotificationPolicy

        now = datetime.now().strftime("%H:%M")

        query = (
            select(NotificationPolicy)
            .where(
                NotificationPolicy.alarm_level == alarm_level,
                NotificationPolicy.is_enabled == True,
            )
            .order_by(NotificationPolicy.id)
        )
        result = await db.execute(query)
        candidates = result.scalars().all()

        # 站点策略优先
        if site_id is not None:
            for p in candidates:
                if p.site_id == site_id and self._is_time_in_range(
                    now, p.time_range_start, p.time_range_end
                ):
                    return p

        # 全局策略兜底
        for p in candidates:
            if p.site_id is None and self._is_time_in_range(
                now, p.time_range_start, p.time_range_end
            ):
                return p

        return None

    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        """将 'HH:MM' 转为分钟数 0~1439"""
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    def _is_time_in_range(
        self, current_time: str, start: Optional[str], end: Optional[str]
    ) -> bool:
        """判断当前时间是否在策略时段内"""
        if start is None or end is None:
            return True
        now_min = self._to_minutes(current_time)
        s_min = self._to_minutes(start)
        e_min = self._to_minutes(end)
        if s_min < e_min:
            return s_min <= now_min < e_min
        else:  # 跨午夜
            return now_min >= s_min or now_min < e_min

    async def _get_user_contacts(
        self, db, user_ids: list[int], channel: str
    ) -> list[tuple]:
        """查询用户的通知联系方式，返回 [(user_id, contact_value, platform), ...]"""
        from app.models.user_notification_contact import UserNotificationContact

        result = await db.execute(
            select(
                UserNotificationContact.user_id,
                UserNotificationContact.contact_value,
                UserNotificationContact.platform,
            ).where(
                UserNotificationContact.user_id.in_(user_ids),
                UserNotificationContact.channel_type == channel,
                UserNotificationContact.is_enabled == True,
            )
        )
        return result.all()

    # ==================== Story 34.2: 单条发送 ====================

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


# ==================== Story 34.5: 渠道升级 ====================


async def check_channel_escalations(session) -> int:
    """
    扫描需要渠道升级的告警，返回本次升级发送数量。
    由 main.py 定时任务每 60 秒调用。
    """
    from app.models.alarm import Alarm

    now = datetime.now()
    escalated_count = 0

    # 查询所有已通知但未确认的活动告警
    result = await session.execute(
        select(Alarm.id, Alarm.alarm_level, Alarm.point_id)
        .where(
            Alarm.status == "active",
            Alarm.is_notified == True,
        )
    )
    active_alarms = result.all()

    if not active_alarms:
        return 0

    dispatcher = notification_dispatcher

    for alarm_id, alarm_level, point_id in active_alarms:
        try:
            sent = await _escalate_single_alarm(
                session, dispatcher, alarm_id, alarm_level, point_id, now
            )
            escalated_count += sent
        except Exception as e:
            logger.error("渠道升级告警 %s 失败: %s", alarm_id, e, exc_info=True)

    return escalated_count


async def _escalate_single_alarm(
    session, dispatcher, alarm_id: int, alarm_level: str,
    point_id: int, now: datetime
) -> int:
    """处理单个告警的渠道升级，返回发送数量"""
    from app.models.notification_record import NotificationRecord

    # 1. 查询该告警最近一次 sent_at（MAX，确保每步升级间有完整超时窗口）
    max_sent_result = await session.execute(
        select(func.max(NotificationRecord.sent_at))
        .where(
            NotificationRecord.alarm_id == alarm_id,
            NotificationRecord.status == "sent",
        )
    )
    max_sent_at = max_sent_result.scalar()
    if max_sent_at is None:
        return 0  # 无成功发送记录，跳过

    # 2. 获取 site_id 和点位元数据
    from app.services.ingest_pipeline import _point_meta_cache
    meta = _point_meta_cache.get(point_id, {})
    site_id = meta.get("site_id")

    # 3. 匹配策略
    policy = await dispatcher._match_policy(session, site_id, alarm_level)
    if not policy or not policy.channel_escalation_enabled:
        return 0

    # 4. 检查超时（基于最近一次发送时间）
    timeout_minutes = policy.escalation_timeout_minutes or 5
    elapsed = (now - max_sent_at).total_seconds() / 60
    if elapsed < timeout_minutes:
        return 0  # 未超时

    # 5. 获取升级渠道顺序（JSON 列安全处理）
    escalation_order = policy.escalation_channel_order
    if isinstance(escalation_order, str):
        escalation_order = json.loads(escalation_order)
    if not escalation_order:
        return 0

    # 6. 查询已发送的渠道
    sent_channels_result = await session.execute(
        select(NotificationRecord.channel_type)
        .where(
            NotificationRecord.alarm_id == alarm_id,
            NotificationRecord.status == "sent",
        )
        .distinct()
    )
    sent_channels = {row[0] for row in sent_channels_result.all()}

    # 7. 找到下一个未发送的渠道
    next_channel = None
    for ch in escalation_order:
        if ch not in sent_channels:
            next_channel = ch
            break

    if next_channel is None:
        logger.debug(
            "告警 %d 所有升级渠道已用尽: %s", alarm_id, escalation_order
        )
        return 0

    # 8. 获取用户列表（JSON 列安全处理）
    user_ids = policy.notify_user_ids
    if isinstance(user_ids, str):
        user_ids = json.loads(user_ids)
    if not user_ids:
        return 0

    contacts = await dispatcher._get_user_contacts(session, user_ids, next_channel)
    if not contacts:
        logger.debug("告警 %d 渠道 %s 无可用联系方式", alarm_id, next_channel)
        return 0

    # 9. 构建 context 并发送
    context = AlarmNotificationContext(
        alarm_id=alarm_id,
        alarm_level=alarm_level,
        alarm_message=f"[渠道升级] 告警未确认，升级至 {next_channel}",
        device_name=meta.get("device_name"),
        point_name=meta.get("point_name"),
        current_value=None,
        threshold_value=None,
        site_id=site_id,
        site_name=meta.get("site_name") or "未知站点",
        created_at=max_sent_at,
    )

    sent_count = 0
    for user_id, contact_value, platform in contacts:
        try:
            await dispatcher.send_notification(
                context, next_channel, contact_value, user_id,
                policy_id=policy.id, platform=platform,
            )
            sent_count += 1
        except Exception as e:
            logger.error("渠道升级发送异常: %s", e, exc_info=True)

    if sent_count > 0:
        logger.info(
            "告警 %d 渠道升级: %s → %s, 发送 %d 条",
            alarm_id, sent_channels, next_channel, sent_count,
        )

    return sent_count
