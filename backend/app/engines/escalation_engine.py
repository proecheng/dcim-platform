"""告警升级引擎"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from ..models.alarm import Alarm, AlarmEscalation
from ..services.websocket import ws_manager

logger = logging.getLogger(__name__)


async def check_escalations(session: AsyncSession):
    """检查超时未处理的告警并执行升级"""
    # 1. 查询所有启用的升级规则
    rules_result = await session.execute(select(AlarmEscalation).where(AlarmEscalation.is_enabled == True))
    rules = rules_result.scalars().all()

    pending_broadcasts = []
    now = datetime.now()

    for rule in rules:
        # 2. 查询匹配的 active 告警
        # 使用 COALESCE(last_escalated_at, created_at) 作为时间基准
        # 这样多步升级链中，每一步都从上次升级时间开始计算超时
        cutoff_time = now - timedelta(minutes=rule.timeout_minutes)
        time_ref = func.coalesce(Alarm.last_escalated_at, Alarm.created_at)
        alarms_result = await session.execute(
            select(Alarm).where(
                Alarm.status == "active", Alarm.alarm_level == rule.source_level, time_ref <= cutoff_time
            )
        )
        alarms = alarms_result.scalars().all()

        for alarm in alarms:
            # 3. Build broadcast message from local vars BEFORE modifying ORM
            alarm_id = alarm.id
            source_level = rule.source_level
            target_level = rule.target_level
            remark = f"[自动升级] 从 {source_level} 升级为 {target_level}，超时 {rule.timeout_minutes} 分钟未处理"

            # 4. Update alarm
            await session.execute(
                update(Alarm)
                .where(Alarm.id == alarm_id)
                .values(
                    alarm_level=target_level,
                    escalated_from=source_level,
                    escalation_count=Alarm.escalation_count + 1,
                    escalation_remark=remark,
                    last_escalated_at=now,
                )
            )

            pending_broadcasts.append(
                {
                    "action": "escalate",
                    "id": alarm_id,
                    "alarm_level": target_level,
                    "previous_level": source_level,
                    "escalation_remark": remark,
                }
            )

    # 5. Commit FIRST, then broadcast
    if pending_broadcasts:
        await session.commit()
        for payload in pending_broadcasts:
            try:
                await ws_manager.broadcast_alarm(payload)
            except Exception as e:
                logger.warning("升级广播失败: %s", e)
