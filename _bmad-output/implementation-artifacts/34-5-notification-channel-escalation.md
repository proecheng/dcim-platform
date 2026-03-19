# Story 34.5: 通知渠道升级

Status: done

## Story

As a 运维工程师,
I want 如果我没有及时确认告警，系统自动通过更紧急的渠道再次通知我,
So that 重要告警不会被遗漏。

## Acceptance Criteria

1. **Given** 通知策略启用渠道升级（`channel_escalation_enabled=True`）**When** 告警最近一次通知发出后超过 `escalation_timeout_minutes` 分钟且 `Alarm.status` 仍为 `active` **Then** 自动通过 `escalation_channel_order` 中的下一渠道重新通知所有目标用户
2. **Given** 渠道升级进行中 **When** 运维人员确认告警（`Alarm.status` 变为 `acknowledged`/`resolved`）**Then** 立即停止升级（下次扫描时跳过该告警）
3. **Given** `escalation_channel_order` 中所有渠道已用尽 **When** 告警仍未确认 **Then** 停止升级，记录 debug 级别日志（避免每 60 秒重复 info 输出）

## Tasks / Subtasks

- [x] Task 1: 新增 `check_channel_escalations()` 函数 (AC: #1, #2, #3)
  - [x] 1.1 在 `dispatcher.py` 中新增 `check_channel_escalations(session)` — 扫描需要渠道升级的告警
  - [x] 1.2 查询条件：`Alarm.status='active' AND Alarm.is_notified=True`，关联 NotificationRecord 取 `MAX(sent_at)` 作为超时基准
  - [x] 1.3 查询匹配策略（复用 `_match_policy`），检查 `channel_escalation_enabled=True`
  - [x] 1.4 确定当前已发送渠道（从 NotificationRecord 查 DISTINCT channel_type），计算下一渠道
  - [x] 1.5 调用 `send_notification` 发送下一渠道通知
  - [x] 1.6 所有渠道用尽时记录 debug 日志并跳过（避免日志洪泛）
- [x] Task 2: 注册定时任务 (AC: #1)
  - [x] 2.1 在 `main.py` 中注册 `_channel_escalation_loop()`，每 60 秒执行一次
- [x] Task 3: 自动化测试 (AC: #1~#3)
  - [x] 3.1 创建 `backend/tests/services/test_channel_escalation.py`

## Dev Notes

### 关键设计决策

**与告警级别升级（AlarmEscalation）完全独立：** 告警级别升级（`escalation_engine.py`）改变 `Alarm.alarm_level`（如 minor→major→critical）。渠道升级改变通知渠道（如 im→sms→voice），不改变告警级别。两者并行运行，互不干扰。

**超时基准时间：** 使用 `MAX(sent_at)` 而非 `MIN(sent_at)`。原因：每次升级发送新渠道通知后，`MAX(sent_at)` 会更新为最新发送时间，下次扫描时从该时间重新计算超时。这确保每步升级之间都有完整的 `escalation_timeout_minutes` 等待窗口，而非从首次发送开始一次性触发所有升级。

**已发送渠道判断：** 从 `NotificationRecord` 查询 `SELECT DISTINCT channel_type FROM notification_records WHERE alarm_id=X AND status='sent'`，与 `escalation_channel_order` 对比，找到第一个未发送的渠道。

**策略匹配复用：** 复用 `_match_policy(db, site_id, alarm_level)` 获取策略，检查 `channel_escalation_enabled` 和 `escalation_channel_order`。

**幂等性：** 每次扫描都重新计算"下一渠道"，如果该渠道已有 sent 记录则跳过。`send_notification` 成功后会创建 NotificationRecord(status='sent')，下次扫描时该渠道进入 sent_channels 集合，自动推进到下一渠道。即使定时任务重复执行也不会重复发送。

**escalation_channel_order 与 policy.channels 的关系：** `escalation_channel_order` 定义升级路径（如 `["im","sms","voice"]`），`policy.channels` 定义初始发送渠道（如 `["im"]`）。初始发送的渠道已在 sent_channels 中，升级时会自动跳过，直接推进到下一个未发送渠道。

**日志洪泛防护：** "所有渠道已用尽" 使用 `logger.debug` 级别，避免每 60 秒重复输出 info 日志。

**_point_meta_cache 依赖：** 缓存可能在系统启动初期未加载（首次数据入库前）。此时 `meta = {}`，`site_id = None`，策略匹配退化为全局策略。这是可接受的降级行为，因为渠道升级只在告警已通知后才触发，而告警通知必然在数据入库之后。

**Session 策略：** `check_channel_escalations` 接收外部 session 用于读操作，`send_notification` 内部创建独立 session 用于写操作。与 Story 34.4 的 dispatch 模式一致。

### 核心新增：check_channel_escalations

```python
# backend/app/services/notification/dispatcher.py — 新增模块级函数

async def check_channel_escalations(session: AsyncSession) -> int:
    """
    扫描需要渠道升级的告警，返回本次升级发送数量。
    由 main.py 定时任务每 60 秒调用。
    """
    from app.models.alarm import Alarm
    from app.models.notification_record import NotificationRecord

    now = datetime.now()
    escalated_count = 0

    # 1. 查询所有已通知但未确认的活动告警
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

    dispatcher = notification_dispatcher  # 模块级单例

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

    # 1. 查询该告警最近一次 sent_at（MAX 而非 MIN，确保每步升级间有完整超时窗口）
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

    # 2. 获取 site_id 和点位元数据（从 point_meta_cache）
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
        # 所有渠道已用尽 — 使用 debug 避免每 60 秒重复 info 日志
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

    # 9. 构建 context 并发送（补充 device_name/point_name 等字段）
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
```

### main.py 注册定时任务

```python
# backend/app/main.py — 在 _escalation_engine_loop 之后新增

async def _channel_escalation_loop():
    """渠道升级定时扫描 — 每 60 秒"""
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as session:
                from app.services.notification.dispatcher import check_channel_escalations
                await check_channel_escalations(session)
        except Exception as e:
            logger.warning("渠道升级检查失败: %s", e)

channel_escalation_task = asyncio.create_task(_channel_escalation_loop())
```

### 需要新增的 import

```python
# dispatcher.py 顶部新增
from sqlalchemy import func
```

### 文件清单

| 操作 | 文件 |
|------|------|
| 修改 | `backend/app/services/notification/dispatcher.py` — 新增 `check_channel_escalations()`, `_escalate_single_alarm()`, import `func` |
| 修改 | `backend/app/main.py` — 注册 `_channel_escalation_loop()` 定时任务 |
| 新建 | `backend/tests/services/test_channel_escalation.py` |

### 测试场景

1. check_channel_escalations — 无活动告警返回 0
2. check_channel_escalations — 告警未超时不升级（elapsed < timeout_minutes）
3. check_channel_escalations — 告警超时且有下一渠道，发送成功
4. check_channel_escalations — 告警已确认（status=acknowledged）不在查询结果中
5. check_channel_escalations — 告警已恢复（status=resolved）不在查询结果中
6. check_channel_escalations — 策略未启用渠道升级（channel_escalation_enabled=False），跳过
7. check_channel_escalations — 所有渠道已用尽，返回 0（debug 日志）
8. check_channel_escalations — 无 sent 记录（max_sent_at=None）跳过
9. _escalate_single_alarm — 正确识别下一未发送渠道（跳过已发送的）
10. _escalate_single_alarm — JSON 字符串 escalation_channel_order 正确反序列化
11. _escalate_single_alarm — 单个告警异常不影响其他告警（per-alarm try/except）
12. _escalate_single_alarm — 无联系方式时跳过
13. _escalate_single_alarm — 幂等性：已发送渠道不重复发送
14. _escalate_single_alarm — 多步升级链路：im→sms→voice 逐步推进
15. _escalate_single_alarm — MAX(sent_at) 确保每步升级间有完整超时窗口
16. _escalate_single_alarm — context 包含 device_name/point_name 字段
