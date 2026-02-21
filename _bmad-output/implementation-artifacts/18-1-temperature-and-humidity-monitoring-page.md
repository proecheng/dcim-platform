# Story 18.1: 温湿度监测页

## Story 描述

**As a** 运维工程师,
**I want to** 通过温度监测页面上按区域分组的卡片快速发现温湿度异常，并查看每个传感器的实时数据和趋势,
**So that** 我可以在温湿度超限之前采取行动。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/environment/temperature`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现

### AC-2: 顶部统计卡片
- 显示 6 个统计卡片: 传感器总数、在线数、告警数、平均温度、平均湿度、疑似漂移数
- 使用 `stat-card` 模式（参考 `cooling/overview.vue`）
- 2.5D 弧形倾斜效果

### AC-3: 区域分组卡片布局
- 核心区域: 按区域/房间分组的卡片布局
- 每个区域卡片显示: 区域名、传感器数、平均温湿度、最大/最小值、告警数
- 异常区域红色边框，疑似漂移黄色边框
- 组件架构预留热力图升级接口（数据层通过 composable 封装）

### AC-4: 传感器详情面板
- 点击区域卡片展开该区域传感器列表
- 点击传感器显示详情面板: 设备名、当前温湿度值、最近 24 小时趋势图(ECharts)、关联告警列表

### AC-5: 底部数据表格
- 传感器数据表格
- 支持按区域、按状态(正常/告警/离线/疑似漂移)筛选
- 支持按名称搜索

### AC-6: 疑似漂移标识
- 疑似漂移传感器在卡片和表格中有明确标识
- 黄色图标 + tooltip "数据可靠性: 低"

### AC-7: WebSocket 实时更新
- 通过 WebSocket 接收实时数据更新
- 卡片和表格自动刷新

### AC-8: 2.5D 视觉增强
- 遵循 `cooling/overview.vue` "一览无余" 设计模式
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard` preset 应用于页面容器

## 技术任务

### Task 1: 创建 composable — `useTemperatureData.ts` [AC-3, AC-7]
- 路径: `frontend/src/composables/useTemperatureData.ts`
- 封装温湿度数据获取、区域分组、统计计算
- 复用 `useRealtime` composable 获取实时数据和 WebSocket
- 调用 `getDriftResults` 获取漂移检测数据
- 导出: 分组数据、统计数据、筛选方法
- 预留热力图数据接口

### Task 2: 实现 temperature.vue 页面 [AC-1 ~ AC-8]
- 路径: `frontend/src/views/environment/temperature.vue`
- 替换 PlaceholderView

#### Subtask 2.1: 顶部统计卡片 [AC-2]
- 6 个 stat-card: 传感器总数、在线数、告警数、平均温度、平均湿度、疑似漂移数
- 使用 `el-row :gutter="16"` + `el-col :span="4"` 布局

#### Subtask 2.2: 区域分组卡片 [AC-3, AC-6]
- 按 `area_code` 分组
- 每个卡片: 区域名、传感器数、平均温湿度、最大/最小温度、告警数
- 异常区域 `border-color: #f5222d`，漂移区域 `border-color: #faad14`
- 使用 `el-row` + `el-col :span="6"` 网格布局

#### Subtask 2.3: 传感器详情面板 [AC-4]
- 点击区域卡片展开传感器列表（el-drawer 或内联展开）
- 点击传感器显示详情: 设备名、当前值、24h 趋势图、关联告警
- 趋势图使用 ECharts（`getPointTrend` API）
- 告警列表使用 `getActiveAlarms` API

#### Subtask 2.4: 底部数据表格 [AC-5, AC-6]
- `el-table` 显示所有温湿度传感器
- 筛选: 区域下拉、状态下拉（正常/告警/离线/疑似漂移）
- 搜索: 名称关键字
- 漂移传感器黄色标识 + tooltip

#### Subtask 2.5: WebSocket 实时更新 [AC-7]
- 复用 `useRealtime` composable 的 WebSocket 连接
- 数据更新时自动刷新统计、卡片、表格

#### Subtask 2.6: 2.5D 样式 [AC-8]
- `@use '@/styles/mixins-25d' as *`
- `.temperature-monitor { @include page-dashboard(6); }`
- stat-card、detail-card 样式参考 `cooling/overview.vue`

## 开发备注

### 现有可复用资源
- `useRealtime` composable — 实时数据 + WebSocket + 轮询
- `getAllRealtimeData` API — 获取所有点位实时数据
- `getRealtimeByArea` API — 按区域获取实时数据
- `getPointTrend` API — 获取点位趋势数据（24h 图表）
- `getActiveAlarms` API — 获取活动告警
- `getDriftResults` / `getDriftSummary` API — 漂移检测数据
- `DataQualityTag` 组件 — 数据质量标签
- `realtimeWs` WebSocket 实例 — 实时数据推送
- `_mixins-25d.scss` — 2.5D 视觉增强 mixin

### 数据筛选逻辑
- 温湿度传感器: `device_type === 'TH'`
- 温度点位: `unit === '°C'`
- 湿度点位: `unit === '%'`
- 区域分组: 按 `area_code` 字段分组
- 漂移判断: 关联 drift API 的 `status === 'suspected'` 或 `status === 'confirmed'`

### API 端点
| 用途 | API | 文件 |
|------|-----|------|
| 实时数据 | `GET /v1/realtime` | `api/modules/realtime.ts` |
| 按区域数据 | `GET /v1/realtime/by-area/:code` | `api/modules/realtime.ts` |
| 趋势数据 | `GET /v1/history/:id/trend` | `api/modules/history.ts` |
| 活动告警 | `GET /v1/alarms/active` | `api/modules/alarm.ts` |
| 漂移结果 | `GET /v1/drift/results` | `api/modules/drift.ts` |
| 漂移概览 | `GET /v1/drift/summary` | `api/modules/drift.ts` |

### 参考文件
- `frontend/src/views/cooling/overview.vue` — stat-card 模式、2.5D 样式
- `frontend/src/views/environment/overview.vue` — 环境监控模式、数据筛选
- `frontend/src/composables/useRealtime.ts` — 实时数据 composable
- `frontend/src/composables/useWebSocket.ts` — WebSocket composable
- `frontend/src/api/modules/drift.ts` — 漂移检测 API
- `frontend/src/styles/_mixins-25d.scss` — 2.5D mixin 系统
- `frontend/src/components/common/DataQualityTag.vue` — 数据质量标签
