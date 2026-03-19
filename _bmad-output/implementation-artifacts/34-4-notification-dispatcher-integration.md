# Story 34.4: 通知分发器与告警引擎集成

Status: ready-for-dev

## Story

As a 运维工程师,
I want 告警触发后自动通过配置的渠道收到通知,
So that 不在监控室时也能第一时间知道告警。

## Acceptance Criteria

1. **Given** `_evaluate_alarms()` 创建新告警并 commit 后 **When** 告警事件循环处理 **Then** 异步调用通知分发器，不阻塞采集流水线
2. **Given** 通知策略配置为同时发送钉钉和短信 **When** 分发器执行 **Then** 为每个 channel+user 组合串行调用 send_notification（SQLite 写锁限制），每次调用创建 NotificationRecord
3. **Given** 某渠道适配器抛出异常 **When** 并行发送中 **Then** 不影响其他渠道和其他告警，异常渠道进入重试队列
4. **Given** 通知分发器内部发生未捕获异常 **When** create_task 执行 **Then** 异常被 done_callback 捕获并写入应用日志
5. **Given** 告警对应的策略 notify_user_ids 为空 **When** 分发器执行 **Then** 跳过发送，不创建 NotificationRecord
6. **Given** 告警对应的用户无该渠道的通知联系方式 **When** 分发器执行 **Then** 跳过该用户该渠道，记录日志

## Tasks / Subtasks

- [ ] Task 1: 新增 dispatch 方法 — 策略匹配 + 并行分发 (AC: #1~#6)
  - [ ] 1.1 在 `dispatcher.py` 中新增 `dispatch(alarm_data_list)` 方法（接收纯数据 dict，非 ORM 对象）
  - [ ] 1.2 新增 `_match_policy(db, site_id, alarm_level)` — 完整 SQL 查询 + 时间匹配
  - [ ] 1.3 新增 `_is_time_in_range(current_time, start, end)` — 内联分钟转换
  - [ ] 1.4 新增 `_get_user_contacts(db, user_ids, channel)` — 查询 UserNotificationContact
  - [ ] 1.5 新增 `_pending_tasks` 集合 — 防止 create_task 被 GC
- [ ] Task 2: 集成到 ingest_pipeline (AC: #1, #4)
  - [ ] 2.1 在 `_evaluate_alarms()` commit 成功后，构建纯数据 alarm_data_list
  - [ ] 2.2 调用 `asyncio.create_task` + done_callback，存储 task 引用
  - [ ] 2.3 扩展 `_ensure_point_cache` 预加载 site_id/device_name/site_name（LEFT JOIN）
- [ ] Task 3: dispatch 完成后回写 Alarm (AC: #1)
  - [ ] 3.1 dispatch 返回实际发送数量，回写 `is_notified` 和 `notify_count`
- [ ] Task 4: 自动化测试 (AC: #1~#6)
  - [ ] 4.1 创建 `backend/tests/services/test_notification_dispatch.py`

## Dev Notes

### 关键设计决策

**传递纯数据而非 ORM 对象：** `_evaluate_alarms` commit 后，Alarm ORM 对象仍绑定到 pipeline 的 session。dispatch 使用独立 session，直接访问 ORM 属性可能触发 DetachedInstanceError。因此在 commit 成功后，提取纯数据 dict 传给 dispatch。

**并行发送：** 使用 `asyncio.gather(*tasks, return_exceptions=True)` 实现 AC #2 的并行要求。每个 send_notification 调用包装为独立 coroutine，异常不影响其他。

**Task 引用保持：** dispatcher 实例维护 `_pending_tasks: set[asyncio.Task]` 集合，create_task 后 add，done_callback 中 discard，防止 GC 回收。

**Session 策略：** dispatch 使用独立 `async_session()`。由于 SQLite 单写者限制，dispatch 在 pipeline commit 完成后才被 create_task 调度（下一个事件循环 tick），不会与 pipeline 的写操作并发。send_notification 内部的 session 操作是串行的（gather 并行的是适配器调用，不是 DB 写入）。

**时区约定：** 使用服务器本地时间 `datetime.now().strftime("%H:%M")`，与策略配置时的时区一致（项目为单机房部署，无跨时区需求）。

### 核心新增：dispatch 方法

```python
# backend/app/services/notification/dispatcher.py — 新增方法

def __init__(self):
    # ... 现有初始化 ...
    self._pending_tasks: set[asyncio.Task] = set()  # 防止 task 被 GC

async def dispatch(self, alarm_data_list: list[dict]) -> dict[int, int]:
    """
    批量分发通知，返回 {alarm_id: sent_count} 映射。

    alarm_data_list 结构（纯数据 dict，非 ORM 对象）:
    [{
        "alarm_id": int,
        "alarm_level": str,
        "alarm_message": str,
        "trigger_value": float,
        "threshold_value": float,
        "created_at": datetime,
        "site_id": int | None,
        "site_name": str | None,
        "device_name": str | None,
        "point_name": str | None,
    }, ...]
    """
    if not alarm_data_list:
        return {}

    from app.core.database import async_session

    result_map: dict[int, int] = {}
    async with async_session() as db:
        for alarm_data in alarm_data_list:
            try:
                sent = await self._dispatch_single(db, alarm_data)
                result_map[alarm_data["alarm_id"]] = sent
            except Exception as e:
                logger.error(
                    f"分发告警 {alarm_data.get('alarm_id')} 通知失败: {e}",
                    exc_info=True,
                )
                result_map[alarm_data["alarm_id"]] = 0
    return result_map


async def _dispatch_single(self, db: AsyncSession, alarm_data: dict) -> int:
    """处理单个告警的通知分发，返回发送数量"""
    site_id = alarm_data.get("site_id")
    alarm_level = alarm_data["alarm_level"]

    # 1. 匹配策略
    policy = await self._match_policy(db, site_id, alarm_level)
    if not policy:
        return 0

    # 2. 检查 notify_user_ids
    user_ids = policy.notify_user_ids
    if isinstance(user_ids, str):
        import json
        user_ids = json.loads(user_ids)
    if not user_ids:
        return 0

    # 3. 获取渠道列表
    channels = policy.channels
    if isinstance(channels, str):
        import json
        channels = json.loads(channels)

    # 4. 构建 context（确保非 Optional 字段有安全默认值）
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

    # 5. 收集所有 send 任务
    send_coros = []
    for channel in channels:
        contacts = await self._get_user_contacts(db, user_ids, channel)
        if not contacts:
            logger.debug(f"告警 {alarm_data['alarm_id']} 渠道 {channel} 无可用联系方式")
            continue
        for user_id, contact_value, platform in contacts:
            send_coros.append(
                self.send_notification(
                    context, channel, contact_value, user_id,
                    policy_id=policy.id, platform=platform,
                )
            )

    if not send_coros:
        return 0

    # 6. 串行发送（send_notification 内部有 DB 写操作，SQLite 不支持并发写）
    # 注意：每个 send_notification 内部的适配器 HTTP 调用是 async 的，
    # 但 DB record 创建/更新必须串行以避免 SQLite "database is locked"
    sent_count = 0
    for coro in send_coros:
        try:
            await coro
            sent_count += 1
        except Exception as e:
            logger.error(f"通知发送异常: {e}", exc_info=True)
    return sent_count
```

### 策略匹配逻辑（完整实现）

```python
async def _match_policy(
    self, db: AsyncSession, site_id: Optional[int], alarm_level: str
) -> Optional["NotificationPolicy"]:
    """匹配最具体的启用策略：站点策略优先于全局策略，按 id ASC 取第一个"""
    from app.models.notification_policy import NotificationPolicy

    now = datetime.now().strftime("%H:%M")

    # 查询所有匹配 alarm_level 且 is_enabled=True 的策略
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
            if p.site_id == site_id and self._is_time_in_range(now, p.time_range_start, p.time_range_end):
                return p

    # 全局策略兜底
    for p in candidates:
        if p.site_id is None and self._is_time_in_range(now, p.time_range_start, p.time_range_end):
            return p

    return None
```

### 时间匹配辅助（内联分钟转换，不依赖私有方法）

```python
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
        return True  # 全天策略
    now_min = self._to_minutes(current_time)
    s_min = self._to_minutes(start)
    e_min = self._to_minutes(end)
    if s_min < e_min:
        return s_min <= now_min < e_min
    else:  # 跨午夜
        return now_min >= s_min or now_min < e_min
```

### 用户联系方式查询

```python
async def _get_user_contacts(
    self, db: AsyncSession, user_ids: list[int], channel: str
) -> list[tuple[int, str, Optional[str]]]:
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
```

### ingest_pipeline 集成点

```python
# ingest_pipeline.py — _evaluate_alarms() 内部
# 注意：文件顶部已有 import asyncio（现有代码使用 asyncio.create_task 做 WS 广播）

# 在 session.commit() 成功后（约 line 584），构建纯数据列表
if alarm_events:
    alarm_data_list = []
    for evt in alarm_events:
        alarm = evt["alarm"]
        meta = evt["point_meta"]
        alarm_data_list.append({
            "alarm_id": alarm.id,
            "alarm_level": alarm.alarm_level,
            "alarm_message": alarm.alarm_message,
            "trigger_value": alarm.trigger_value,
            "threshold_value": alarm.threshold_value,
            "created_at": alarm.created_at,
            "site_id": meta.get("site_id"),
            "site_name": meta.get("site_name"),
            "device_name": meta.get("device_name"),
            "point_name": meta.get("point_name"),
        })

    from app.services.notification import notification_dispatcher

    async def _dispatch_and_update(data_list):
        """分发通知并按告警回写 is_notified + notify_count"""
        try:
            result_map = await notification_dispatcher.dispatch(data_list)
            # result_map: {alarm_id: sent_count}
            notified_alarms = {aid: cnt for aid, cnt in result_map.items() if cnt > 0}
            if notified_alarms:
                from app.core.database import async_session as _async_session
                from app.models.alarm import Alarm
                async with _async_session() as db:
                    for aid, cnt in notified_alarms.items():
                        result = await db.execute(
                            select(Alarm).where(Alarm.id == aid)
                        )
                        a = result.scalar_one_or_none()
                        if a:
                            a.is_notified = True
                            a.notify_count = cnt
                    await db.commit()
        except Exception as e:
            logger.error(f"通知分发异常: {e}", exc_info=True)

    task = asyncio.create_task(_dispatch_and_update(alarm_data_list))
    notification_dispatcher._pending_tasks.add(task)
    task.add_done_callback(notification_dispatcher._pending_tasks.discard)
```

### 扩展 _ensure_point_cache

```python
# 在 _ensure_point_cache 的 SELECT 中增加 LEFT JOIN Device + Site 获取 site_id
# 原始查询: select(Point.id, Point.point_code, ...)
# 扩展为:
from app.models.device import Device
from app.models.spatial import Site

query = (
    select(
        Point.id, Point.point_code, Point.point_name, Point.point_type,
        Point.device_id, Point.area_code, Point.unit,
        Point.is_enabled, Point.store_interval,
        Device.device_type,
        Device.site_id,
        Device.device_name,
        Site.site_name,
    )
    .outerjoin(Device, Point.device_id == Device.id)
    .outerjoin(Site, Device.site_id == Site.id)
)

# _point_meta_cache 新增字段:
#   "site_id": int or None
#   "device_name": str or None
#   "site_name": str or None
```

### 不再使用乐观标记

**移除 Alarm 创建时的 `is_notified=True` 硬编码。** 改为 dispatch 完成后通过独立 session 回写实际发送结果。这样：
- 如果 dispatch 跳过（无策略/无用户），`is_notified` 保持 False（正确）
- 如果 dispatch 成功发送 N 条，`is_notified=True, notify_count=N`（正确）
- 如果 dispatch 全部失败，`is_notified` 保持 False（正确）

### 文件清单

| 操作 | 文件 |
|------|------|
| 修改 | `backend/app/services/notification/dispatcher.py` — 新增 dispatch, _dispatch_single, _match_policy, _is_time_in_range, _to_minutes, _get_user_contacts, _pending_tasks |
| 修改 | `backend/app/services/ingest_pipeline.py` — 扩展 _ensure_point_cache, 集成通知分发到 _evaluate_alarms（commit 后） |
| 新建 | `backend/tests/services/test_notification_dispatch.py` |

### 测试场景

1. dispatch — 正常分发，匹配策略后为每个 channel+user 调用 send_notification
2. dispatch — 空 alarm_data_list 返回空 dict
3. dispatch — 无匹配策略时跳过，返回 sent_count=0
4. dispatch — 策略 notify_user_ids 为空时跳过
5. dispatch — 用户无该渠道联系方式时跳过该用户
6. dispatch — 多渠道串行发送（im + sms），每个都创建 NotificationRecord
7. dispatch — 单个告警异常不影响其他告警（per-alarm try/except）
8. dispatch — 单个 send_notification 异常不影响其他（per-send try/except）
9. dispatch — JSON 字符串 channels/notify_user_ids 正确反序列化
10. dispatch — 返回 per-alarm {alarm_id: sent_count} 映射
11. _match_policy — 站点策略优先于全局策略
12. _match_policy — 当前时间在时段内匹配
13. _match_policy — 当前时间不在时段内不匹配
14. _match_policy — 跨午夜时段正确匹配
15. _match_policy — 全天策略始终匹配
16. _match_policy — 无启用策略返回 None
17. _is_time_in_range — 普通时段内返回 True
18. _is_time_in_range — 普通时段外返回 False
19. _is_time_in_range — 跨午夜时段内返回 True
20. _is_time_in_range — 全天返回 True
21. _get_user_contacts — 返回启用的联系方式
22. _get_user_contacts — 禁用的联系方式不返回
23. _pending_tasks — task 完成后从集合中移除
24. 回写逻辑 — dispatch 成功后按告警 is_notified=True, notify_count=per-alarm count
25. 回写逻辑 — dispatch 返回全部 0 时不回写
26. AlarmNotificationContext — alarm_message 为 None 时使用默认值
27. AlarmNotificationContext — created_at 为 None 时使用 datetime.now()
