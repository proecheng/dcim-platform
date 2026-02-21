# Story 21.1: 网关列表与状态监控

## Story 描述

**As a** 运维工程师,
**I want to** 在网关管理页面查看所有网关设备的在线/离线状态、连接质量和数据吞吐量,
**So that** 我可以快速识别网关通信问题，确保数据采集链路稳定。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/gateway`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现

### AC-2: 顶部统计卡片
- 显示 5 个统计卡片: 网关总数、在线数、离线数、告警数、平均数据吞吐量
- 使用 `stat-card` 模式（参考 `temperature.vue`）
- 2.5D 弧形倾斜效果

### AC-3: 网关列表表格
- 列: 网关名称、IP地址、协议类型(capabilities)、在线状态(在线/离线/告警)、连接质量(CPU/内存使用率)、数据吞吐量(关联数据源数)、最后心跳时间、关联设备数(datasource_count)
- 支持按状态筛选、按名称/IP搜索
- 分页（使用后端分页 API `GET /api/v1/gateways`）

### AC-4: 展开详情面板
- 点击网关行展开详情面板
- 基本信息: 网关ID、固件版本、IP、创建时间
- 实时状态指标: CPU/内存/磁盘使用率进度条
- 关联数据源列表（通过 `GET /api/v1/gateways/{id}` 获取 datasource_count/point_count）
- 最近24小时连接质量趋势图(ECharts) — 使用网关事件历史 `GET /api/v1/gateways/{id}/events`

### AC-5: WebSocket 实时更新
- 通过 `/ws/system` WebSocket 通道接收网关状态变化
- 网关状态变化时自动更新表格行状态
- 降级: WebSocket 断开时回退到轮询

### AC-6: 离线告警标识
- 网关离线时行标红 + 告警图标
- 离线超过阈值（5分钟无心跳）自动标红

### AC-7: 2.5D 视觉增强
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard(5)` preset 应用于页面容器

## 技术任务

### Task 1: 创建网关 API 模块 [AC-3, AC-4]
- 路径: `frontend/src/api/modules/gateway.ts`
- 封装: `getGatewayList`, `getGatewaySummary`, `getGatewayDetail`, `getGatewayEvents`
- 类型定义: `GatewayInfo`, `GatewaySummary`, `GatewayDetail`, `GatewayEvent`

### Task 2: 实现 gateway/index.vue 页面 [AC-1 ~ AC-7]
- 路径: `frontend/src/views/gateway/index.vue`
- 替换 PlaceholderView

#### Subtask 2.1: 顶部统计卡片 [AC-2]
- 5 个 stat-card: 网关总数、在线数、离线数、告警数、平均吞吐量
- 使用 `el-row :gutter="16"` + `el-col` 布局
- 调用 `GET /api/v1/gateways/summary`

#### Subtask 2.2: 网关列表表格 [AC-3, AC-6]
- 使用 `el-table` + 后端分页
- 状态列: 在线(绿)、离线(红)、告警(橙)
- 离线行标红 + 告警图标
- 筛选: 状态下拉、名称搜索

#### Subtask 2.3: 展开详情面板 [AC-4]
- 使用 `el-table` 的 `expand` 行展开
- 基本信息 + 资源使用率进度条
- 24h 事件趋势图(ECharts)

#### Subtask 2.4: WebSocket 实时更新 [AC-5]
- 使用 `useWebSocket` composable 连接 `/ws/system`
- 监听 `gateway_status` 类型消息
- 更新对应网关行状态

## 数据来源

| 数据 | API | 说明 |
|------|-----|------|
| 网关列表 | `GET /api/v1/gateways` | 分页、筛选、搜索 |
| 状态汇总 | `GET /api/v1/gateways/summary` | total/online/offline |
| 网关详情 | `GET /api/v1/gateways/{id}` | datasource_count/point_count |
| 事件历史 | `GET /api/v1/gateways/{id}/events` | 状态变更事件 |
| 实时状态 | WebSocket `/ws/system` | gateway_status 消息 |

## 对抗性审查

### 审查结论: 通过（附修正）

1. **数据吞吐量**: 后端 Gateway 模型无直接吞吐量字段 → 使用 `datasource_count` 作为关联数据源数代替，详情面板展示 `point_count` 作为点位吞吐量指标
2. **协议类型**: Gateway 模型无 `protocol_type` 字段 → 使用 `capabilities` JSON 字段展示能力标签
3. **连接质量**: 无信号强度/延迟字段 → 使用 `cpu_usage`/`memory_usage` 作为连接质量指标
4. **告警数**: `GatewayStatusSummary` 只有 total/online/offline → 前端计算: 告警数 = 有 resource_warning 事件的网关数，或简化为离线数
5. **24h趋势图**: 使用事件历史 API 绘制状态变更时间线，而非连续数据曲线

## Dev Notes

### 文件位置
```
frontend/src/api/modules/gateway.ts        # 新建 — 网关 API 模块
frontend/src/views/gateway/index.vue       # 修改 — 替换 PlaceholderView
```

### 关键模式
- 参考 `temperature.vue` 的统计卡片 + 表格 + WebSocket 模式
- 参考 `device-manage/index.vue` 的列表 + 分页 + 筛选模式
- 使用 `@use '@/styles/mixins-25d' as *` + `page-dashboard(5)` 2.5D 增强
- WebSocket 使用 `useWebSocket` composable 连接 `/ws/system`
