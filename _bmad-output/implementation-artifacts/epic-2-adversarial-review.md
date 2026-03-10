# Epic 2 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 2（网关管理 + MQTT 通信链路）实施成果
**审查方法:** 代码审查 + 安全漏洞分析

---

## 审查结论

⚠️ **发现 15 个问题：2 个 P0 问题，6 个 P1 问题，7 个 P2 问题**

---

## 审查发现

### P0-1: 网关自动注册无认证机制

**问题描述:**
- 文件: `backend/app/services/gateway_registration.py:34-73`
- `handle_gateway_status` 函数接收任何 MQTT 消息就自动注册网关，无需认证
- 恶意设备可以伪造 gateway_id 注册，占用系统资源或冒充合法网关
- 严重安全漏洞

**影响:** 严重 - 安全漏洞

**修复建议:**
1. 在网关注册时验证预共享密钥（PSK）或证书
2. 使用 MQTT 用户名/密码认证
3. 维护网关白名单，只允许预注册的 gateway_id

**优先级:** P0 - 必须立即修复

---

### P0-2: MQTT 消息未验证签名

**问题描述:**
- 所有 MQTT 消息（心跳、配置、数据）未进行签名验证
- 攻击者可以伪造消息注入恶意数据或配置
- 严重安全漏洞

**影响:** 严重 - 数据完整性

**修复建议:**
使用 HMAC 签名验证消息：
```python
import hmac
import hashlib

def verify_message(payload: dict, signature: str, secret_key: str) -> bool:
    message = json.dumps(payload, sort_keys=True)
    expected = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**优先级:** P0 - 必须立即修复

---

### P1-1: 离线缓存数据未加密

**问题描述:**
- 文件: `backend/gateway/cache.py:24-55`
- SQLite 数据库以明文存储敏感数据（topic、payload）
- 如果网关设备被物理访问，数据会泄露

**影响:** 高 - 数据安全

**修复建议:**
使用 SQLCipher 或应用层加密：
```python
from cryptography.fernet import Fernet

cipher = Fernet(encryption_key)
encrypted_payload = cipher.encrypt(payload.encode())
```

**优先级:** P1 - 建议尽快修复

---

### P1-2: 网关 site_id 绑定可被覆盖

**问题描述:**
- 文件: `backend/app/services/gateway_registration.py:89-99`
- 允许通过 topic 中的 site_id 覆盖已有网关的站点绑定
- 仅记录警告不阻止
- 攻击者可以通过伪造 topic 将网关重新绑定到其他站点

**影响:** 高 - 权限绕过

**修复建议:**
禁止覆盖已有 site_id：
```python
elif resolved_site_id is not None and existing.site_id != resolved_site_id:
    logger.error(
        "网关 %s site_id 冲突: DB=%s, topic=%s（拒绝）",
        gw_id,
        existing.site_id,
        resolved_site_id,
    )
    return  # 拒绝处理
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: 离线缓存无容量限制

**问题描述:**
- 文件: `backend/gateway/cache.py:57-65`
- `enqueue` 方法无限制写入数据
- 长时间离线会导致 SQLite 文件无限增长，耗尽磁盘空间
- 虽然有 `check_storage` 方法，但未自动调用

**影响:** 高 - 资源耗尽

**修复建议:**
在 `enqueue` 前检查队列大小：
```python
async def enqueue(self, topic: str, payload: str) -> None:
    # 检查队列大小
    stats = await self.get_stats()
    if stats["pending_count"] >= MAX_QUEUE_SIZE:
        logger.error("离线缓存队列已满，丢弃数据")
        return
    # ... 原有逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: 配置下发未验证配置合法性

**问题描述:**
- 未看到配置下发前的验证逻辑
- 错误配置可能导致网关崩溃或采集失败

**影响:** 高 - 系统稳定性

**修复建议:**
在配置下发前验证：
```python
def validate_datasource_config(config: dict) -> bool:
    # 验证协议类型
    if config.get("protocol_type") not in ADAPTER_REGISTRY:
        return False
    # 验证点位地址格式
    for point in config.get("points", []):
        # ... 验证逻辑
    return True
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: 离线缓存批量上传单条失败停止

**问题描述:**
- 文件: `backend/gateway/cache.py:88-96`
- `flush_batch` 方法在单条上传失败时停止整个批次
- 未标记失败原因
- 如果某条数据格式错误，会阻塞后续所有数据上传

**影响:** 高 - 数据上传阻塞

**修复建议:**
跳过失败的单条数据，继续上传后续数据：
```python
for row_id, topic, payload in rows:
    try:
        await publish_fn(topic, payload)
        await self._db.execute("UPDATE upload_queue SET uploaded = 1 WHERE id = ?", (row_id,))
        uploaded_count += 1
    except Exception as e:
        logger.warning("缓存上传失败 (id=%s): %s，跳过继续", row_id, e)
        # 标记为失败但不停止
        await self._db.execute("UPDATE upload_queue SET uploaded = -1 WHERE id = ?", (row_id,))
```

**优先级:** P1 - 建议尽快修复

---

### P1-6: 站点权限过滤未验证 site_id 存在

**问题描述:**
- 文件: `backend/app/api/v1/gateways.py:42-43`
- 使用 `user_site_ids` 过滤网关列表
- 未验证 `site_id` 查询参数是否在用户权限范围内
- 可能导致权限绕过

**影响:** 高 - 权限控制

**修复建议:**
验证 site_id 参数：
```python
if site_id is not None:
    if user_site_ids is not None and site_id not in user_site_ids:
        raise HTTPException(status_code=403, detail="无权访问该站点")
    query = query.where(Gateway.site_id == site_id)
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: Redis 缓存降级未记录日志

**问题描述:**
- `cache_service.py` 中 Redis 操作失败时静默降级到数据库
- 未记录降级事件
- 运维人员无法及时发现 Redis 故障

**影响:** 中等 - 可观测性

**修复建议:**
记录降级事件到日志和监控系统

**优先级:** P2 - 可以接受现状

---

### P2-2: MQTT 发布失败未重试

**问题描述:**
- 文件: `backend/gateway/mqtt_client.py:60-74`
- `publish` 方法在 MQTT 发布失败时直接降级到离线缓存
- 未尝试重试
- 网络抖动可能导致大量数据进入缓存队列

**影响:** 中等 - 性能

**修复建议:**
添加重试逻辑（指数退避）

**优先级:** P2 - 可以接受现状

---

### P2-3: 心跳超时检测未考虑时钟偏移

**问题描述:**
- `gateway_registration.py:15` 硬编码 90 秒超时
- 未考虑网关和服务器时钟不同步的情况
- 如果网关时钟快于服务器，可能导致误判离线

**影响:** 中等 - 监控准确性

**修复建议:**
使用 NTP 同步时钟或增加容错时间

**优先级:** P2 - 可以接受现状

---

### P2-4: 资源告警冷却期使用数据库查询

**问题描述:**
- 文件: `backend/app/services/gateway_monitor.py:52-63`
- 每次心跳都查询数据库检查冷却期
- 高频心跳会增加数据库负载

**影响:** 中等 - 性能

**修复建议:**
使用 Redis 或内存缓存存储冷却期状态

**优先级:** P2 - 可以接受现状

---

### P2-5: 网关状态缓存未设置过期时间

**问题描述:**
- `cache_service.py:97-100` 的 `cache_gateway_status` 方法代码被截断
- 可能未设置 TTL，导致过期网关状态长期驻留缓存

**影响:** 中等 - 缓存一致性

**修复建议:**
验证是否设置了 TTL

**优先级:** P2 - 需要验证

---

### P2-6: MQTT 连接状态管理不完整

**问题描述:**
- 文件: `backend/gateway/mqtt_client.py:83-91`
- `set_connected/set_disconnected` 方法由外部调用
- 未看到自动检测连接状态的机制
- 如果外部忘记调用，状态会不准确

**影响:** 中等 - 状态准确性

**修复建议:**
添加连接状态自动检测机制

**优先级:** P2 - 可以接受现状

---

### P2-7: 网关事件表无分区或归档策略

**问题描述:**
- `gateway_monitor.py:24-33` 的 `GatewayEvent` 表会无限增长
- 每次心跳、状态变化、资源告警都记录
- 长期运行会导致性能下降

**影响:** 中等 - 长期性能

**修复建议:**
添加定时归档任务，将旧事件移到历史表

**优先级:** P2 - 可以接受现状

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------|
| P0-1 | 网关自动注册无认证机制 | P0 | ✅ 已修复 | 安全性 |
| P0-2 | MQTT 消息未验证签名 | P0 | ✅ 已修复 | 数据完整性 |
| P1-1 | 离线缓存数据未加密 | P1 | ⚠️ 待修复 | 数据安全 |
| P1-2 | 网关 site_id 绑定可被覆盖 | P1 | ✅ 已修复 | 权限控制 |
| P1-3 | 离线缓存无容量限制 | P1 | ⚠️ 待修复 | 资源管理 |
| P1-4 | 配置下发未验证配置合法性 | P1 | ⚠️ 待修复 | 系统稳定性 |
| P1-5 | 离线缓存批量上传单条失败停止 | P1 | ⚠️ 待修复 | 数据上传 |
| P1-6 | 站点权限过滤未验证 site_id 存在 | P1 | ✅ 已修复 | 权限控制 |
| P2-1 | Redis 缓存降级未记录日志 | P2 | ⚠️ 待修复 | 可观测性 |
| P2-2 | MQTT 发布失败未重试 | P2 | ⚠️ 待修复 | 性能 |
| P2-3 | 心跳超时检测未考虑时钟偏移 | P2 | ⚠️ 待修复 | 监控准确性 |
| P2-4 | 资源告警冷却期使用数据库查询 | P2 | ⚠️ 待修复 | 性能 |
| P2-5 | 网关状态缓存未设置过期时间 | P2 | ⚠️ 需要验证 | 缓存一致性 |
| P2-6 | MQTT 连接状态管理不完整 | P2 | ⚠️ 待修复 | 状态准确性 |
| P2-7 | 网关事件表无分区或归档策略 | P2 | ⚠️ 待修复 | 长期性能 |

---

## Epic 2 实施质量评估

### 优点

1. **MQTT 通信链路完整** - 心跳、配置、数据上报三条链路完整实现
2. **离线缓存机制完善** - SQLite 断点续传、批量上传、存储检查
3. **Redis 缓存策略合理** - Write-through + Read-through，降级处理
4. **网关状态监控完整** - 心跳超时检测、资源告警、事件记录
5. **站点权限过滤** - 支持多站点数据隔离

### 缺点

1. **2 个 P0 安全漏洞** - 网关注册无认证、MQTT 消息无签名验证
2. **6 个 P1 功能缺陷** - 数据加密、权限控制、配置验证、容量限制
3. **7 个 P2 改进点** - 日志记录、性能优化、状态管理
4. **安全机制缺失** - 缺少认证、签名、加密等基本安全措施

### 总体评价

Epic 2 的功能实现完整，但存在严重的安全漏洞。网关自动注册无认证和 MQTT 消息无签名验证是两个关键安全问题，必须修复才能投入生产使用。

**建议:**
1. **立即修复 P0 问题** - 添加网关认证机制和消息签名验证
2. **尽快修复 P1 问题** - 特别是数据加密和权限控制
3. **评估 P2 问题** - 根据实际使用情况决定是否修复

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0 安全漏洞，继续审查 Epic 3
