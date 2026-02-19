# Story 16-3: 多站点网关接入 — 设计方案

## 验收标准（来自 epics.md）

1. 各机房网关通过 VPN/专线连接中心 EMQX Broker
2. 网关上报数据按 site_id 路由到对应站点的数据空间
3. 网关离线时本地 SQLite 缓存，恢复后断点续传
4. 支持从单站点平滑扩展到 200 台设备

## 现状分析

### MQTT Topic 格式（已有）
```
dcim/{site_id}/gw/{gw_id}/status   — 网关心跳
dcim/{site_id}/gw/{gw_id}/data     — 点位数据上报
dcim/{site_id}/gw/{gw_id}/ota/status — OTA 状态
```

### 关键缺口
1. **`_handle_message()` 不传递 site_id** — topic 中已有 site_id（`parts[1]`），但 `handle_gateway_status(payload, db)` 和 `handle_point_data(payload, db)` 只接收 payload，不接收 site_id
2. **网关自动注册不设置 site_id** — `gateway_registration.py` 创建 Gateway 时未设置 `site_id`
3. **缓存无 site_id 维度** — Redis key `point:{point_id}:latest` 和 `gateway:{gateway_id}:status` 无 site 隔离
4. **无离线缓存/断点续传机制** — 网关侧功能，需要提供配置文档和协议规范
5. **无 200 设备扩展性保障** — 需要连接池、批量写入等优化

## 设计方案

### 变更 1: MQTT 消息处理传递 site_id

**文件**: `backend/app/mqtt/client.py`

在 `_handle_message()` 中，从 topic 解析 site_id 并传递给下游处理函数：

```python
# 现有代码 (line 158-165):
elif len(parts) == 5 and parts[0] == "dcim":
    msg_type = parts[4]
    if msg_type == "status":
        async with async_session() as db:
            await handle_gateway_status(payload, db)
    elif msg_type == "data":
        async with async_session() as db:
            await handle_point_data(payload, db)

# 改为:
elif len(parts) == 5 and parts[0] == "dcim":
    site_id_str = parts[1]  # 从 topic 提取 site_id
    msg_type = parts[4]
    if msg_type == "status":
        async with async_session() as db:
            await handle_gateway_status(payload, db, site_id=site_id_str)
    elif msg_type == "data":
        async with async_session() as db:
            await handle_point_data(payload, db, site_id=site_id_str)
```

同样处理 OTA 消息（6段 topic）中的 site_id。

### 变更 2: 网关注册/心跳绑定 site_id

**文件**: `backend/app/services/gateway_registration.py`

修改 `handle_gateway_status` 签名，增加 `site_id: str | None = None` 参数：

- **自动注册时**: 将 site_id 转为 int 并设置 `Gateway.site_id`（需验证 site 存在）
- **心跳更新时**: 如果网关已有 site_id 且与 topic 中的不一致，记录警告日志（不覆盖，防止误操作）
- **site_id 验证**: 查询 Site 表确认 site_id 存在，不存在则记录警告但仍注册网关（site_id 留空）

```python
async def handle_gateway_status(
    payload: dict, db: AsyncSession, *, site_id: str | None = None
) -> None:
    # ... 解析 gw_id ...
    
    # 解析并验证 site_id
    resolved_site_id: int | None = None
    if site_id is not None:
        try:
            resolved_site_id = int(site_id)
            # 验证 site 存在
            site_exists = await db.execute(
                select(Site.id).where(Site.id == resolved_site_id)
            )
            if site_exists.scalar_one_or_none() is None:
                logger.warning("topic 中 site_id=%s 对应站点不存在", site_id)
                resolved_site_id = None
        except (ValueError, TypeError):
            logger.warning("topic 中 site_id=%s 无法解析为整数", site_id)
    
    if existing is None:
        # 自动注册 — 设置 site_id
        gateway = Gateway(
            ...,
            site_id=resolved_site_id,
        )
    else:
        # 心跳更新 — 如果网关无 site_id 且 topic 有，则补充设置
        update_values = { ... }
        if resolved_site_id is not None and existing.site_id is None:
            update_values["site_id"] = resolved_site_id
        elif resolved_site_id is not None and existing.site_id != resolved_site_id:
            logger.warning(
                "网关 %s site_id 不一致: DB=%s, topic=%s",
                gw_id, existing.site_id, resolved_site_id
            )
```

### 变更 3: 点位数据处理传递 site_id（日志增强）

**文件**: `backend/app/services/point_data.py`

修改 `handle_point_data` 签名，增加 `site_id: str | None = None`：

- 当前 PointDataLatest 通过 gateway_id 间接关联 site，无需在点位表增加 site_id 列
- 但在日志中记录 site_id 以便排查跨站数据问题
- 缓存 key 保持不变（point_id 全局唯一，不需要 site 隔离）

```python
async def handle_point_data(
    payload: dict, db: AsyncSession, *, site_id: str | None = None
) -> int:
    # ... 现有逻辑不变 ...
    logger.debug("点位数据处理: site=%s, gw=%s, %d 条", site_id, gw_id, count)
```

### 变更 4: 网关站点分配 API

**文件**: `backend/app/api/v1/gateways.py`

新增端点：

```
PUT /api/v1/gateways/{gateway_id}/site
Body: { "site_id": 1 }
```

- 允许管理员手动将网关分配到指定站点
- 验证 site_id 对应的站点存在
- 验证当前用户有目标站点的访问权限
- 返回更新后的网关信息

### 变更 5: 网关离线缓存与断点续传（协议规范）

**说明**: 离线缓存是网关侧（edge）功能，不在后端平台实现。平台需要：

1. **定义断点续传协议**:
   - 网关在 payload 中携带 `seq`（序列号）和 `cached: true` 标记
   - 平台收到 `cached: true` 的数据时，按 `seq` 去重
   - 网关恢复连接后，先发送缓存数据（按时间顺序），再切换到实时模式

2. **平台侧去重逻辑**:
   - 在 `handle_point_data` 中，如果 payload 包含 `seq` 字段，检查是否已处理过
   - 使用 Redis SET `gw:{gw_id}:processed_seqs` 存储最近处理的序列号（TTL 1小时）
   - 重复 seq 直接跳过

3. **配置文档**: 在 `docs/` 下新增网关离线缓存配置指南

**新增文件**: `backend/app/services/dedup_service.py`

```python
async def is_duplicate(gw_id: str, seq: int) -> bool:
    """检查消息序列号是否重复（断点续传去重）"""
    key = f"gw:{gw_id}:seq"
    # 使用 Redis SISMEMBER + SADD，TTL 1小时
    ...

async def mark_processed(gw_id: str, seq: int) -> None:
    """标记序列号已处理"""
    ...
```

### 变更 6: 200 设备扩展性优化

1. **批量点位写入**: 在 `handle_point_data` 中，将逐条 UPSERT 改为批量操作
   - 使用 `insert().on_conflict_do_update()` (SQLAlchemy) 批量 upsert
   - 减少数据库往返次数

2. **连接池配置文档**: 在 Settings 中增加 MQTT 连接池相关配置项
   - `MQTT_MAX_INFLIGHT`: 最大并发消息数（默认 200）
   - `DB_POOL_SIZE`: 数据库连接池大小（默认 20）

3. **消息处理并发控制**: 在 `_handle_message` 中使用 asyncio.Semaphore 限制并发数据库写入

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/mqtt/client.py` | 修改 | `_handle_message` 传递 site_id |
| `backend/app/services/gateway_registration.py` | 修改 | 接收 site_id，自动注册时绑定站点 |
| `backend/app/services/point_data.py` | 修改 | 接收 site_id，日志增强，批量 upsert |
| `backend/app/services/dedup_service.py` | 新增 | 断点续传消息去重 |
| `backend/app/api/v1/gateways.py` | 修改 | 新增 PUT /{gateway_id}/site 端点 |
| `backend/app/schemas/gateway.py` | 修改 | 新增 GatewayAssignSite schema |
| `backend/tests/test_multi_site_gateway.py` | 新增 | 多站点网关接入测试 |

## 测试计划

1. **网关自动注册绑定 site_id** — topic 中 site_id 有效时，新注册网关自动绑定
2. **网关自动注册 site_id 无效** — topic 中 site_id 对应站点不存在，网关仍注册但 site_id 为 None
3. **心跳更新补充 site_id** — 已有网关无 site_id，心跳 topic 带 site_id 时自动补充
4. **心跳 site_id 不一致告警** — 已有网关 site_id 与 topic 不一致，记录警告不覆盖
5. **点位数据处理传递 site_id** — 验证日志中包含 site_id
6. **断点续传去重** — 相同 gw_id + seq 的消息只处理一次
7. **断点续传无 seq** — 无 seq 字段的消息正常处理（向后兼容）
8. **网关站点分配 API** — PUT 端点正确更新 site_id
9. **网关站点分配权限** — 非管理员无法分配
10. **批量点位 upsert** — 大批量点位数据正确写入
11. **并发消息处理** — Semaphore 限制下多消息并发不死锁

## 不做的事情

- 不修改 PointDataLatest 表结构（通过 gateway_id 间接关联 site）
- 不实现网关侧 SQLite 缓存（网关侧功能，仅定义协议）
- 不修改 Redis 缓存 key 结构（point_id 全局唯一）
- 不修改前端（本 Story 纯后端）
