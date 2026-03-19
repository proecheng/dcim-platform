# Story 34.6: 告警风暴抑制

Status: done

## Story

As a 运维工程师,
I want 短时间内大量告警时收到合并摘要通知而非逐条轰炸,
So that 我能快速了解整体情况而不被通知淹没。

## Acceptance Criteria

1. **Given** 60s内同站点触发≥20条告警 **When** 通知分发器检测到风暴 **Then** 合并为摘要通知（包含告警总数、各级别数量、关键设备列表）
2. **Given** 风暴期间有 critical 告警 **When** 合并通知 **Then** critical 也参与合并，摘要中突出 critical 数量和关键设备
3. **Given** Redis 不可用 **When** 风暴检测 **Then** 降级为内存计数器（asyncio.Lock 保护），功能不中断
4. **Given** 风暴结束（60s窗口内计数<阈值）**When** 新告警触发 **Then** 恢复逐条通知

## Tasks / Subtasks

- [x] Task 1: RedisService 扩展 `incr_with_ttl()` 和 `incrby_with_ttl()` (AC: #1, #3)
  - [x] 1.1 在 `app/core/redis.py` 的 RedisService 中新增 `async def incr_with_ttl(key, ttl=60) -> int`
  - [x] 1.2 新增 `async def incrby_with_ttl(key, amount, ttl=60) -> int`（批量递增）
  - [x] 1.3 使用 pipeline 原子执行 INCR/INCRBY + EXPIRE，Redis 不可用时返回 -1
  - [x] 1.4 仅提供异步版本（避免已知的同步/异步 delete 方法名冲突 bug）
- [x] Task 2: 风暴检测器 `StormDetector` (AC: #1, #3, #4)
  - [x] 2.1 在 `app/services/notification/storm.py` 新建 `StormDetector` 类
  - [x] 2.2 `check_storm(site_id, count=1) -> bool`：Redis 优先，内存降级；支持一次递增 count 条
  - [x] 2.3 Redis key: `notification:storm:{site_id}`，TTL=STORM_WINDOW
  - [x] 2.4 内存降级：`asyncio.Lock` + `defaultdict(list)` 滑动窗口计数；清理空列表防内存泄漏
  - [x] 2.5 阈值从 SystemConfig 读取，带默认值兜底
  - [x] 2.6 `get_config() -> tuple[int, int]` 公开方法，供 dispatcher 获取 window 值
- [x] Task 3: 摘要通知构建 (AC: #1, #2)
  - [x] 3.1 在 `app/schemas/notification.py` 新增 `STORM_SUMMARY_TEMPLATE` 模板
  - [x] 3.2 `build_storm_summary(site_name, alarm_data_list, window)` — window 参数必传，从 StormDetector 获取
  - [x] 3.3 摘要包含：告警总数、各级别数量、critical 设备列表、站点名称
- [x] Task 4: dispatcher.dispatch() 集成风暴检测 (AC: #1, #2, #4)
  - [x] 4.1 在 `dispatch()` 方法开头按 site_id 分组告警（site_id=None 的告警跳过风暴检测，直接逐条分发）
  - [x] 4.2 对每组一次性调用 `check_storm(site_id, count=len(group))` 判断风暴
  - [x] 4.3 风暴触发时：合并该站点所有告警为摘要通知发送
  - [x] 4.4 非风暴时：保持原有逐条分发逻辑
- [x] Task 5: 自动化测试 (AC: #1~#4)
  - [x] 5.1 创建 `backend/tests/services/test_storm_suppression.py`

## Dev Notes

### 关键设计决策

**critical 不豁免，全部合并：** 级联故障场景下可能同时触发数十条 critical 告警，如果 critical 豁免会导致通知 DDoS。摘要中突出 critical 数量和关键设备即可。

**Redis 优先 + 内存降级：** Redis INCRBY+TTL 用于批量递增计数。Redis 不可用时降级为内存计数器（asyncio.Lock 保护），单进程场景下功能等价。

**Redis 固定窗口 vs 内存滑动窗口：** Redis INCR+TTL 是固定窗口计数器（key 创建时设 TTL，到期清零），内存降级是真正的滑动窗口（保留每个时间戳，清理 >window 的）。两者行为在窗口边界有细微差异（Redis 会在 TTL 到期时突然重置），但对于风暴检测这种粗粒度场景，固定窗口近似完全可接受。

**阈值可配置：** 从 SystemConfig 表读取 `notification.storm_threshold`（默认20）和 `notification.storm_window`（默认60秒）。首次读取后缓存 300 秒，避免每次查库。

**风暴结束自动恢复：** Redis key 有 TTL 自动过期；内存计数器在滑动窗口内清理过期时间戳。无需显式"结束风暴"操作。

**site_id=None 的告警跳过风暴检测：** 无站点告警直接逐条分发，避免不同来源的无站点告警被错误地混合计数。

**批量计数，一次判断：** dispatch() 中对每组告警一次性调用 `check_storm(site_id, count=len(group))`，而非逐条递增。避免单批次内人为膨胀计数导致的不一致行为。

**摘要通知策略匹配：** 使用该组中最高级别告警来匹配策略，确保摘要通知发送给最相关的用户。风暴是站点级事件，单一策略匹配足够。

**StormDetector 独立模块：** 不在 dispatcher.py 中内联，而是独立为 `storm.py`，便于测试和维护。dispatcher 通过组合方式使用。

**内存计数器清理：** 滑动窗口清理后如果列表为空，删除该 key 防止长期运行的内存泄漏。

### 核心新增：StormDetector

```python
# backend/app/services/notification/storm.py

import asyncio
import logging
import time
from collections import defaultdict
from typing import Optional

from app.core.redis import redis_service

logger = logging.getLogger(__name__)

# 默认值（SystemConfig 未配置时使用）
DEFAULT_STORM_THRESHOLD = 20
DEFAULT_STORM_WINDOW = 60  # 秒


class StormDetector:
    """告警风暴检测器 — Redis 优先，内存降级"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._counter: dict[int, list[float]] = defaultdict(list)
        self._config_cache: Optional[dict] = None
        self._config_loaded_at: float = 0

    async def get_config(self) -> tuple[int, int]:
        """获取风暴阈值配置（threshold, window），缓存 300 秒"""
        now = time.time()
        if self._config_cache and now - self._config_loaded_at < 300:
            return (
                self._config_cache["threshold"],
                self._config_cache["window"],
            )
        try:
            from app.core.database import async_session
            from app.models.config import SystemConfig
            from sqlalchemy import select

            async with async_session() as session:
                result = await session.execute(
                    select(SystemConfig.config_key, SystemConfig.config_value)
                    .where(
                        SystemConfig.config_group == "notification",
                        SystemConfig.config_key.in_([
                            "storm_threshold", "storm_window"
                        ]),
                    )
                )
                rows = {r[0]: r[1] for r in result.all()}

            threshold = int(rows.get("storm_threshold", DEFAULT_STORM_THRESHOLD))
            window = int(rows.get("storm_window", DEFAULT_STORM_WINDOW))
        except Exception:
            threshold = DEFAULT_STORM_THRESHOLD
            window = DEFAULT_STORM_WINDOW

        self._config_cache = {"threshold": threshold, "window": window}
        self._config_loaded_at = now
        return threshold, window

    async def check_storm(self, site_id: int, count: int = 1) -> bool:
        """
        检测指定站点是否处于告警风暴状态。
        count: 本批次新增告警数量，先递增再判断。
        若递增后总数 >= 阈值则返回 True（本批告警应合并为摘要通知）。
        """
        threshold, window = await self.get_config()

        # Redis 优先
        if redis_service.is_available:
            try:
                if count == 1:
                    total = await redis_service.incr_with_ttl(
                        f"notification:storm:{site_id}", ttl=window
                    )
                else:
                    total = await redis_service.incrby_with_ttl(
                        f"notification:storm:{site_id}", count, ttl=window
                    )
                if total >= 0:
                    return total >= threshold
            except Exception as e:
                logger.warning("风暴检测 Redis 失败，降级内存: %s", e)

        # 内存降级
        return await self._check_storm_memory(site_id, count, threshold, window)

    async def _check_storm_memory(
        self, site_id: int, count: int, threshold: int, window: int
    ) -> bool:
        """内存滑动窗口计数（asyncio.Lock 保护）"""
        async with self._lock:
            now = time.time()
            # 清理过期时间戳
            timestamps = [
                t for t in self._counter[site_id] if now - t < window
            ]
            if not timestamps and count == 0:
                # 无活跃记录且无新增，清理 key 防内存泄漏
                self._counter.pop(site_id, None)
                return False
            # 添加 count 个时间戳
            timestamps.extend([now] * count)
            self._counter[site_id] = timestamps
            return len(timestamps) >= threshold


# 全局单例
storm_detector = StormDetector()
```

### RedisService 扩展

```python
# backend/app/core/redis.py — 在 sadd_with_ttl 之后新增

    async def incr_with_ttl(self, key: str, ttl: int = 60) -> int:
        """原子递增+TTL，Redis 不可用时返回 -1"""
        if not self.is_available:
            return -1
        try:
            pipe = self._pool.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning("Redis INCR 失败 key=%s: %s", key, e)
            return -1

    async def incrby_with_ttl(self, key: str, amount: int, ttl: int = 60) -> int:
        """原子批量递增+TTL，Redis 不可用时返回 -1"""
        if not self.is_available:
            return -1
        try:
            pipe = self._pool.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logger.warning("Redis INCRBY 失败 key=%s: %s", key, e)
            return -1
```

### 摘要通知模板

```python
# backend/app/schemas/notification.py — 新增

STORM_SUMMARY_TEMPLATE = (
    "[告警风暴] {site_name} 在 {window}s 内触发 {total_count} 条告警\n"
    "级别分布: {level_summary}\n"
    "{critical_detail}"
)

def build_storm_summary(
    site_name: str,
    alarm_data_list: list[dict],
    window: int,
) -> str:
    """构建风暴摘要通知内容。window 必传，从 StormDetector.get_config() 获取。"""
    from collections import Counter

    level_counter = Counter(d["alarm_level"] for d in alarm_data_list)
    level_summary = ", ".join(
        f"{ALARM_LEVEL_CN.get(k, k)} {v}条" for k, v in level_counter.most_common()
    )

    critical_detail = ""
    critical_alarms = [d for d in alarm_data_list if d["alarm_level"] == "critical"]
    if critical_alarms:
        devices = set(d.get("device_name") or "未知设备" for d in critical_alarms)
        critical_detail = f"⚠ 紧急告警 {len(critical_alarms)} 条，涉及设备: {', '.join(sorted(devices)[:5])}\n"

    return STORM_SUMMARY_TEMPLATE.format(
        site_name=site_name or "未知站点",
        window=window,
        total_count=len(alarm_data_list),
        level_summary=level_summary,
        critical_detail=critical_detail,
    )
```

### dispatcher.dispatch() 修改

```python
# backend/app/services/notification/dispatcher.py — 修改 dispatch 方法

    async def dispatch(self, alarm_data_list: list[dict]) -> dict[int, int]:
        """批量分发通知，返回 {alarm_id: sent_count} 映射。"""
        if not alarm_data_list:
            return {}

        from app.services.notification.storm import storm_detector

        result_map: dict[int, int] = {}

        # 按 site_id 分组（site_id=None 的归入 no_site 组，跳过风暴检测）
        site_groups: dict[int, list[dict]] = {}
        no_site_alarms: list[dict] = []
        for alarm_data in alarm_data_list:
            sid = alarm_data.get("site_id")
            if sid:
                site_groups.setdefault(sid, []).append(alarm_data)
            else:
                no_site_alarms.append(alarm_data)

        async with async_session() as db:
            # 有站点的告警：风暴检测
            for site_id, group in site_groups.items():
                # 一次性递增整组数量，判断是否风暴
                is_storm = await storm_detector.check_storm(site_id, count=len(group))

                if is_storm:
                    # 风暴模式：合并为摘要通知
                    sent = await self._dispatch_storm_summary(db, site_id, group)
                    for alarm_data in group:
                        result_map[alarm_data["alarm_id"]] = 1 if sent > 0 else 0
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
        policy = await self._match_policy(db, site_id, top_alarm["alarm_level"])
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
        summary_text = build_storm_summary(site_name, alarm_data_list, window)

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
                    logger.error("风暴摘要通知发送异常: %s", e, exc_info=True)

        if sent_count > 0:
            logger.info(
                "告警风暴摘要: 站点 %s, %d 条告警合并, 发送 %d 条通知",
                site_name, len(alarm_data_list), sent_count,
            )

        return sent_count
```

### 需要新增的 import

```python
# storm.py 无需额外 import（已在代码中列出）
# dispatcher.py 顶部已有 import json，方法内不重复 import
```

### 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `backend/app/services/notification/storm.py` — StormDetector 风暴检测器 |
| 修改 | `backend/app/core/redis.py` — 新增 `incr_with_ttl()`, `incrby_with_ttl()` |
| 修改 | `backend/app/schemas/notification.py` — 新增 `STORM_SUMMARY_TEMPLATE`, `build_storm_summary()` |
| 修改 | `backend/app/services/notification/dispatcher.py` — 修改 `dispatch()`, 新增 `_dispatch_storm_summary()` |
| 新建 | `backend/tests/services/test_storm_suppression.py` |

### 测试场景

1. StormDetector — Redis 可用时 INCR 计数正确，达到阈值返回 True
2. StormDetector — Redis 可用时未达阈值返回 False
3. StormDetector — Redis 不可用时降级内存计数，达到阈值返回 True
4. StormDetector — 内存计数滑动窗口过期后计数重置
5. StormDetector — get_config 从 SystemConfig 读取自定义阈值
6. StormDetector — get_config 缓存 300 秒内不重复查库
7. StormDetector — SystemConfig 查询异常时使用默认值
8. StormDetector — check_storm(site_id, count=N) 批量递增正确
9. StormDetector — 内存降级清理空列表防泄漏
10. RedisService.incr_with_ttl — Redis 可用时返回递增值
11. RedisService.incr_with_ttl — Redis 不可用时返回 -1
12. RedisService.incrby_with_ttl — 批量递增返回正确总数
13. dispatch — 同站点告警数<阈值时逐条分发（正常模式）
14. dispatch — 同站点告警数≥阈值时合并为摘要通知（风暴模式）
15. dispatch — site_id=None 的告警跳过风暴检测，直接逐条分发
16. dispatch — 不同站点独立计数，互不影响
17. dispatch — 风暴结束后（窗口过期）恢复逐条通知（AC#4）
18. build_storm_summary — 正确生成级别分布和 critical 详情
19. build_storm_summary — 无 critical 时不输出紧急告警行
20. build_storm_summary — window 参数正确传入显示
21. _dispatch_storm_summary — 使用最高级别告警匹配策略
22. _dispatch_storm_summary — 无匹配策略时返回 0
23. dispatch — 风暴摘要包含 critical 数量和设备列表（AC#2）
