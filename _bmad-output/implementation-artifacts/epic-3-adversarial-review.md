# Epic 3 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 3（数据采集调度器 + 实时数据推送）实施成果
**审查方法:** 代码审查 + 可靠性分析

---

## 审查结论

⚠️ **发现 15 个问题：1 个 P0 问题，6 个 P1 问题，8 个 P2 问题**

---

## 审查发现

### P0-1: 采集调度器停止后未等待任务完成

**问题描述:**
- 文件: `backend/gateway/scheduler.py:51-65`
- `stop()` 方法取消所有任务后使用 `return_exceptions=True`
- 这会吞掉 `CancelledError` 之外的异常，导致资源泄漏
- 如果适配器 `disconnect()` 抛出异常，会被静默忽略
- 可能导致连接未正确关闭，占用端口或文件描述符

**影响:** 严重 - 资源泄漏

**修复建议:**
```python
async def stop(self) -> None:
    """停止调度器，取消所有采集任务（保留 configs 以支持重启）"""
    self._running = False
    for ds_id, task in self._tasks.items():
        task.cancel()
        logger.info("取消采集任务: %s", ds_id)

    # 等待所有任务完成取消，记录异常但不抛出
    if self._tasks:
        results = await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        for ds_id, result in zip(self._tasks.keys(), results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                logger.error("任务 %s 停止时异常: %s", ds_id, result)

    self._tasks.clear()
    self._adapters.clear()
    self._dry_contact_monitor.clear_all()
    logger.info("采集调度器已停止，保留 %d 个数据源配置", len(self._configs))
```

**优先级:** P0 - 必须立即修复

---

### P1-1: 采集超时硬编码为 80%

**问题描述:**
- 文件: `backend/gateway/scheduler.py:201-202`
- 采集超时固定为 `collection_interval * 0.8`
- 未考虑不同协议的响应时间差异
- SNMP 可能需要更长超时，Modbus TCP 可能更短
- 无法通过配置调整

**影响:** 高 - 采集可靠性

**修复建议:**
在 `DataSourceConfig` 添加 `read_timeout` 字段：
```python
@dataclass
class DataSourceConfig:
    # ...
    read_timeout: float | None = None  # 读取超时（秒），None 则使用默认值
```

然后在调度器中使用：
```python
read_timeout = config.read_timeout or (config.collection_interval * 0.8)
```

**优先级:** P1 - 建议尽快修复

---

### P1-2: WebSocket 心跳检测未处理 pong 响应

**问题描述:**
- 文件: `backend/app/services/websocket.py:74-99`
- `_ping_all()` 方法发送 ping 消息但未等待 pong 响应
- 仅检查 `send_json()` 是否成功，不验证客户端是否真的活着
- 客户端可能接收 ping 但无法响应（如 CPU 100%）
- 会误判为正常连接

**影响:** 高 - 死连接检测不准确

**修复建议:**
使用 WebSocket 原生 ping/pong 机制：
```python
async def _ping_all(self):
    """向所有通道的所有连接发送 ping 帧，等待 pong 响应"""
    dead_connections: List[tuple] = []

    for channel, connections in self.active_connections.items():
        for ws in connections:
            try:
                if ws.client_state != WebSocketState.CONNECTED:
                    dead_connections.append((ws, channel))
                    continue
                # 使用原生 ping/pong
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=HEARTBEAT_TIMEOUT)
            except (asyncio.TimeoutError, Exception):
                dead_connections.append((ws, channel))
    # ... 清理逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: 历史数据批量写入未使用批量 INSERT

**问题描述:**
- 文件: `backend/app/services/ingest_pipeline.py:356-383`
- `_batch_insert_history()` 方法逐条 `session.add()`
- 未使用 `session.execute(PointHistory.__table__.insert(), rows)` 批量插入
- 大量数据时性能低下
- 与 `_batch_upsert_latest()` 的实现不一致

**影响:** 高 - 性能瓶颈

**修复建议:**
```python
async def _batch_insert_history(
    points: list[IngestPoint],
    session: AsyncSession,
    now: datetime,
) -> None:
    """批量插入 PointHistory（仅 AI 类型，按 store_interval 降采样）"""
    ai_points = [pt for pt in points if _point_meta_cache.get(pt.point_id, {}).get("point_type") == "AI"]
    if not ai_points:
        return

    rows_to_insert = []
    for pt in ai_points:
        point_id = pt.point_id
        timestamp = pt.timestamp or now

        # 获取点位的 store_interval 配置
        meta = _point_meta_cache.get(point_id, {})
        store_interval = meta.get("store_interval", 300)

        # 检查是否需要存储（降采样）
        last_stored = _last_store_time.get(point_id)
        if last_stored:
            elapsed = (timestamp - last_stored).total_seconds()
            if elapsed < store_interval:
                continue

        rows_to_insert.append({
            "point_id": point_id,
            "value": pt.value,
            "recorded_at": timestamp,
            "source": pt.source,
        })
        _last_store_time[point_id] = timestamp

    if rows_to_insert:
        await session.execute(PointHistory.__table__.insert(), rows_to_insert)
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: 点位元数据缓存未处理并发加载

**问题描述:**
- 文件: `backend/app/services/ingest_pipeline.py:69-101`
- `_ensure_point_cache()` 使用全局变量 `_cache_loaded` 标记
- 多个并发请求可能同时触发缓存加载
- 未使用锁保护，可能导致重复查询数据库
- 虽然不会导致数据错误，但浪费资源

**影响:** 高 - 并发性能

**修复建议:**
使用 `asyncio.Lock` 保护缓存加载：
```python
_cache_lock = asyncio.Lock()

async def _ensure_point_cache(session: AsyncSession) -> None:
    """加载点位元数据缓存（首次调用时加载，后续跳过）"""
    global _cache_loaded
    if _cache_loaded:
        return

    async with _cache_lock:
        # 双重检查
        if _cache_loaded:
            return

        result = await session.execute(...)
        # ... 加载逻辑
        _cache_loaded = True
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: 采集循环异常后未重置重试策略

**问题描述:**
- 文件: `backend/gateway/scheduler.py:246-269`
- 采集异常后使用 `retry.record_failure()` 累计失败次数
- 但在通信中断后 `await asyncio.sleep(config.retry_max_delay)` 等待
- 未调用 `retry.reset()` 重置重试策略
- 导致后续采集仍然使用长延迟

**影响:** 高 - 恢复速度慢

**修复建议:**
```python
# 通信中断处理
if retry.is_interrupted:
    error_msg = f"数据源 '{ds_id}' 通信中断，连续失败 {retry.failure_count} 次"
    logger.error(error_msg)
    if self._on_alarm:
        try:
            result = self._on_alarm(ds_id, error_msg)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("告警回调执行失败")
    await asyncio.sleep(config.retry_max_delay)
    retry.reset()  # 重置重试策略，避免长期使用最大延迟
else:
    await asyncio.sleep(delay)
```

**优先级:** P1 - 建议尽快修复

---

### P1-6: WebSocket 广播未限制消息大小

**问题描述:**
- 文件: `backend/app/services/websocket.py:110-122`
- `broadcast()` 方法直接发送任意大小的消息
- 未检查消息大小，可能导致内存溢出或网络拥塞
- 大量实时数据推送时可能阻塞事件循环
- 未实现消息队列或背压机制

**影响:** 高 - 系统稳定性

**修复建议:**
添加消息大小限制和队列：
```python
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB

async def broadcast(self, message: dict, channel: str = "realtime"):
    """广播消息 — 发送失败的连接自动清理"""
    if channel not in self.active_connections:
        return

    # 检查消息大小
    message_json = json.dumps(message)
    if len(message_json) > MAX_MESSAGE_SIZE:
        logger.warning("消息过大，跳过广播: %d bytes", len(message_json))
        return

    dead: List[WebSocket] = []
    for connection in self.active_connections[channel]:
        try:
            await connection.send_json(message)
        except Exception as e:
            logger.warning("WebSocket 广播失败，标记清理: %s", e)
            dead.append(connection)
    for ws in dead:
        self.disconnect(ws, channel)
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: 采集调度器未记录任务启动失败

**问题描述:**
- 文件: `backend/gateway/scheduler.py:82-89`
- `add_datasource()` 创建任务后未检查任务是否启动成功
- 如果 `_collection_loop()` 立即抛出异常，任务会静默失败
- 用户无法知道数据源未正常工作

**影响:** 中等 - 可观测性

**修复建议:**
添加任务启动检查：
```python
task = asyncio.create_task(
    self._collection_loop(config),
    name=f"collect-{ds_id}",
)
self._tasks[ds_id] = task

# 添加任务失败回调
def task_done_callback(t: asyncio.Task):
    if not t.cancelled() and t.exception():
        logger.error("采集任务 %s 异常退出: %s", ds_id, t.exception())

task.add_done_callback(task_done_callback)
```

**优先级:** P2 - 可以接受现状

---

### P2-2: 降采样缓存未持久化

**问题描述:**
- 文件: `backend/app/services/ingest_pipeline.py:66`
- `_last_store_time` 使用内存字典存储最后存储时间
- 进程重启后丢失，导致重复存储历史数据
- 可能导致历史数据重复或缺失

**影响:** 中等 - 数据一致性

**修复建议:**
使用 Redis 存储降采样状态：
```python
async def _should_store_history(point_id: int, timestamp: datetime, store_interval: int) -> bool:
    """检查是否应该存储历史数据"""
    if not redis_service.is_available:
        # Redis 不可用，回退到内存缓存
        last_stored = _last_store_time.get(point_id)
        if last_stored:
            elapsed = (timestamp - last_stored).total_seconds()
            if elapsed < store_interval:
                return False
        _last_store_time[point_id] = timestamp
        return True

    # 使用 Redis 存储
    key = f"history:last_store:{point_id}"
    last_stored_str = await redis_service.get(key)
    if last_stored_str:
        last_stored = datetime.fromisoformat(last_stored_str)
        elapsed = (timestamp - last_stored).total_seconds()
        if elapsed < store_interval:
            return False

    await redis_service.set(key, timestamp.isoformat(), ttl=store_interval * 2)
    return True
```

**优先级:** P2 - 可以接受现状

---

### P2-3: WebSocket 心跳任务未处理启动失败

**问题描述:**
- 文件: `backend/app/services/websocket.py:50-54`
- `start_heartbeat()` 创建后台任务但未检查是否启动成功
- 如果 `_heartbeat_loop()` 立即抛出异常，心跳检测会静默失败
- 死连接不会被清理

**影响:** 中等 - 可靠性

**修复建议:**
添加任务启动检查和重启逻辑

**优先级:** P2 - 可以接受现状

---

### P2-4: 历史数据生成器未验证时间范围

**问题描述:**
- 文件: `backend/app/services/history_generator.py:86-111`
- `generate_point_history()` 生成历史数据时未验证时间范围
- 如果 `base_time` 设置错误，可能生成未来时间的数据
- 未检查是否与现有历史数据重叠

**影响:** 中等 - 数据质量

**修复建议:**
添加时间范围验证

**优先级:** P2 - 可以接受现状

---

### P2-5: 实时数据 API 未限制返回数量

**问题描述:**
- 文件: `backend/app/api/v1/realtime.py:22-139`
- `get_all_realtime()` 返回所有启用点位的实时数据
- 未分页，可能返回数千条记录
- 大量数据时响应慢，占用内存

**影响:** 中等 - 性能

**修复建议:**
添加分页参数或限制返回数量

**优先级:** P2 - 可以接受现状

---

### P2-6: 采集调度器未限制并发任务数

**问题描述:**
- 文件: `backend/gateway/scheduler.py:67-89`
- `add_datasource()` 无限制创建采集任务
- 如果有数百个数据源，会创建数百个并发任务
- 可能导致资源耗尽或性能下降

**影响:** 中等 - 资源管理

**修复建议:**
添加并发任务数限制或使用任务池

**优先级:** P2 - 可以接受现状

---

### P2-7: 告警评估未处理数据库死锁

**问题描述:**
- 文件: `backend/app/services/ingest_pipeline.py:388-589`
- `_evaluate_alarms()` 批量查询和更新告警
- 未处理数据库死锁或锁超时
- 高并发时可能导致告警评估失败

**影响:** 中等 - 并发可靠性

**修复建议:**
添加重试逻辑或使用乐观锁

**优先级:** P2 - 可以接受现状

---

### P2-8: Redis 缓存更新失败未记录日志

**问题描述:**
- 文件: `backend/app/services/ingest_pipeline.py:613-646`
- `_update_redis_cache()` 捕获所有异常但不记录
- Redis 故障时无法及时发现
- 影响可观测性

**影响:** 中等 - 可观测性

**修复建议:**
记录 Redis 更新失败：
```python
try:
    await redis_service.set(f"point:{pt.point_id}:latest", cache_data, ttl=60)
except Exception as e:
    logger.warning("Redis 缓存更新失败 (point_id=%d): %s", pt.point_id, e)
```

**优先级:** P2 - 可以接受现状

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------| | P0-1 | 采集调度器停止后未等待任务完成 | P0 | ✅ 已修复 | 资源泄漏 |
| P1-1 | 采集超时硬编码为 80% | P1 | ⚠️ 待修复 | 采集可靠性 |
| P1-2 | WebSocket 心跳检测未处理 pong 响应 | P1 | ⚠️ 待修复 | 死连接检测 |
| P1-3 | 历史数据批量写入未使用批量 INSERT | P1 | ⚠️ 待修复 | 性能瓶颈 |
| P1-4 | 点位元数据缓存未处理并发加载 | P1 | ⚠️ 待修复 | 并发性能 |
| P1-5 | 采集循环异常后未重置重试策略 | P1 | ⚠️ 待修复 | 恢复速度 |
| P1-6 | WebSocket 广播未限制消息大小 | P1 | ⚠️ 待修复 | 系统稳定性 |
| P2-1 | 采集调度器未记录任务启动失败 | P2 | ⚠️ 待修复 | 可观测性 |
| P2-2 | 降采样缓存未持久化 | P2 | ⚠️ 待修复 | 数据一致性 |
| P2-3 | WebSocket 心跳任务未处理启动失败 | P2 | ⚠️ 待修复 | 可靠性 |
| P2-4 | 历史数据生成器未验证时间范围 | P2 | ⚠️ 待修复 | 数据质量 |
| P2-5 | 实时数据 API 未限制返回数量 | P2 | ⚠️ 待修复 | 性能 |
| P2-6 | 采集调度器未限制并发任务数 | P2 | ⚠️ 待修复 | 资源管理 |
| P2-7 | 告警评估未处理数据库死锁 | P2 | ⚠️ 待修复 | 并发可靠性 |
| P2-8 | Redis 缓存更新失败未记录日志 | P2 | ⚠️ 待修复 | 可观测性 |

---

## Epic 3 实施质量评估

### 优点

1. **采集调度器设计合理** - 独立任务、指数退避、错误恢复机制完善
2. **数据入库管道统一** - 单一入口 `process_payload()`，链路清晰
3. **批量操作优化** - 使用 CASE WHEN 批量更新，性能优秀
4. **WebSocket 心跳检测** - 自动清理死连接，防止资源泄漏
5. **降采样机制** - 按 `store_interval` 存储历史数据，节省空间

### 缺点

1. **1 个 P0 资源泄漏问题** - 调度器停止时未正确处理异常
2. **6 个 P1 功能缺陷** - 超时配置、心跳检测、批量写入、并发控制、重试策略、消息大小
3. **8 个 P2 改进点** - 可观测性、数据一致性、性能优化
4. **缺少背压机制** - WebSocket 广播和数据入库未实现背压控制

### 总体评价

Epic 3 的核心功能实现正确，采集调度器和数据入库管道设计合理。发现的问题主要集中在资源管理、并发控制、性能优化等方面。P0 问题必须修复，P1 问题建议尽快修复。

**建议:**
1. **立即修复 P0 问题** - 调度器停止时正确处理异常
2. **尽快修复 P1 问题** - 特别是 P1-2（心跳检测）和 P1-3（批量写入）
3. **评估 P2 问题** - 根据实际使用情况决定是否修复

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0 问题，继续审查其他 Epic
