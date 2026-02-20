# Epic 4 回顾：实时监控适配

## 完成情况

全部 5 个 Story 完成，将仪表盘从模拟数据切换为真实数据展示，新增设备详情页、设备状态看板、通信中断检测和优雅降级机制。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 4-1 | 六大子系统仪表盘适配 | ✅ | ✅ |
| 4-2 | 设备详情与历史曲线 | ✅ | ✅ |
| 4-3 | 设备状态看板 | ✅ | ✅ |
| 4-4 | 通信中断检测与展示 | ✅ | ✅ |
| 4-5 | 优雅降级 | ✅ | ✅ |

## 关键经验教训

### 架构决策

1. **DataSourceBridge 桥接服务**：将 DataSource/DataSourcePoint 采集的真实数据同步到 Point/PointRealtime 表，使现有仪表盘无需修改即可展示真实数据。这是棕地项目中"新旧系统共存"的关键桥接模式
2. **Redis 优先读取 + 数据库降级**：实时数据 API 优先从 Redis 读取，Redis 不可用时降级为数据库查询。降级时在响应 header 附加 `X-Degraded: true`，前端通过 axios 拦截器检测
3. **设备在线状态 Redis 缓存**：模拟器更新点位数据时同步写入 `device:{device_id}:online`（TTL 60s），设备状态看板优先从 Redis 判断在线状态

### 反复出现的模式

1. **FastAPI 路由顺序**：`/status-board`、`/communication-status`、`/detail` 等静态路由必须在 `/{device_id}` 之前定义。这是 Epic 1 以来持续遵循的规则
2. **无数据占位显示**：SIMULATION_ENABLED=false 且无真实数据时，仪表盘数值显示"--"而非 0 或空白
3. **通信中断级联影响**：数据源 interrupted 时，关联的 PointRealtime.quality 更新为 2（坏），告警引擎跳过这些点位

### 技术模式沉淀

- **WebSocket 指数退避重连**：初始 1s，最大 30s，每次翻倍。重连期间显示"连接中断，正在重连..."提示条
- **Pinia degradation store**：全局管理 redis/websocket/mqtt 三种降级状态，DegradationBanner 组件根据状态显示对应警告条
- **设备详情聚合 API**：一次请求返回设备信息 + 关联点位实时数据 + 当前活动告警，减少前端请求次数
- **ECharts 历史曲线**：支持 5 种时间范围快捷选择（1h/6h/24h/7d/30d），复用现有 history trend API

## 下一步

Epic 5: 告警管理增强 — 5 个 Stories
