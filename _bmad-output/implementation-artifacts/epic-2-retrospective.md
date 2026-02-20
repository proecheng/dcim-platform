# Epic 2 回顾：网关管理 + MQTT 通信链路

## 完成情况

全部 6 个 Story 完成，建立了网关自动注册、状态监控、远程配置下发、离线缓存、MQTT 数据上报和 Redis 缓存的完整通信链路。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 2-1 | 网关自动注册 | ✅ | N/A |
| 2-2 | 网关状态监控 | ✅ | N/A |
| 2-3 | 远程配置下发 | ✅ | N/A |
| 2-4 | 离线缓存与断点续传 | ✅ | N/A |
| 2-5 | MQTT 数据上报链路 | ✅ | N/A |
| 2-6 | Redis 缓存策略 | ✅ | N/A |

## 关键经验教训

### 架构决策

1. **MQTT 优雅降级**：MqttService 连接失败时不阻塞后端启动，MQTT 功能降级运行。这个模式后续在 Redis 降级中复用
2. **Redis Write-through + Read-through**：数据写入 DB 同时写入 Redis，读取优先 Redis、miss 时查 DB 回填。Redis 断开时静默降级为直接查库
3. **离线缓存使用 aiosqlite**：网关侧用独立 SQLite 做离线缓存（upload_queue 表），与后端 SQLite 无关。flush_batch 保证顺序性，单条失败停止当前批次

### 反复出现的模式

1. **aiomqtt 连接管理**：aiomqtt 的 Client 是 async context manager，需要在 `async with` 内保持连接。断线重连使用指数退避
2. **MQTT topic 设计**：`dcim/{site_id}/gw/{gw_id}/status|config|data` 三级 topic，通配符订阅 `dcim/+/gw/+/status`
3. **心跳超时检测**：90 秒未心跳标记 offline，定时任务每 30 秒检查。last_heartbeat=NULL 的 online 网关也需标记 offline
4. **资源告警冷却期**：同网关 5 分钟内不重复告警，避免心跳频繁触发资源告警

### 技术模式沉淀

- **GatewayEvent 事件记录**：网关上线/离线/资源告警统一记录到 gateway_events 表，支持事件溯源
- **ConfigPushRecord 下发记录**：每次配置下发创建记录（pending→delivered/failed），支持下发历史查询
- **PointDataLatest UPSERT**：点位数据使用 upsert 语义，point_id 存在则更新，不存在则插入
- **psutil 条件依赖**：StatusReporter 使用 psutil 获取系统指标，不可用时返回 None

## 下一步

Epic 3: 数据源管理 UI + 设备模板 — 5 个 Stories
