# Story 18.2: 水浸检测页

## Story 描述

**As a** 运维工程师,
**I want to** 在水浸检测页面查看所有水浸传感器的实时状态和区域分布,
**So that** 当漏水发生时我可以立即定位漏水位置。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/environment/water-leak`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现

### AC-2: 顶部统计卡片
- 显示 4 个统计卡片: 传感器总数、在线数、告警数(当前漏水)、最近24小时告警数
- 使用 `stat-card` 模式（与 temperature.vue 一致）
- 2.5D 弧形倾斜效果

### AC-3: 区域/房间分组状态卡片
- 核心区域: 按区域/房间分组的卡片布局
- 每个区域卡片显示: 区域名、传感器数、当前状态汇总(全部正常/有漏水告警)
- 漏水告警区域卡片红色脉冲动画（`@keyframes pulse-alarm`）
- 使用 `el-row` + `el-col :span="6"` 网格布局

### AC-4: 传感器详情面板
- 点击区域卡片展开该区域传感器列表（el-drawer）
- 点击传感器显示详情面板: 设备名、当前状态(正常/漏水/离线)、最近告警记录列表、安装位置描述
- 告警记录使用 `getAlarmList` API（按 point_id 筛选）
- 不需要趋势图（DI 类型无连续数值）

### AC-5: 底部数据表格
- 传感器数据表格
- 支持按区域、按状态(正常/告警/离线)筛选
- 支持按名称搜索

### AC-6: DI 类型传感器特性
- 水浸传感器为 DI 类型（干接点），筛选条件: `device_type === 'WL'`
- 状态只有正常/告警两种（加离线），不显示连续数值
- 显示 `value_text` 而非 `value`（如 "正常" / "漏水"）
- 状态变化触发告警而非阈值判断

### AC-7: WebSocket 实时更新
- 通过 WebSocket 接收实时状态变化
- 卡片和表格自动刷新
- 漏水告警时区域卡片立即切换为红色脉冲状态

### AC-8: 2.5D 视觉增强
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard` preset 应用于页面容器
- 与 temperature.vue 视觉风格一致

## 技术任务

### Task 1: 创建 composable — `useWaterLeakData.ts` [AC-3, AC-6, AC-7]
- 路径: `frontend/src/composables/useWaterLeakData.ts`
- 封装水浸传感器数据获取、区域分组、统计计算
- 筛选逻辑: `device_type === 'WL'`（水浸传感器）
- 调用 `getAllRealtimeData` 获取实时数据
- 调用 `getAlarmList` 获取最近 24 小时告警数
- WebSocket 实时更新 + 轮询降级
- 导出: 分组数据、统计数据、筛选方法

### Task 2: 实现 water-leak.vue 页面 [AC-1 ~ AC-8]
- 路径: `frontend/src/views/environment/water-leak.vue`
- 替换 PlaceholderView

#### Subtask 2.1: 顶部统计卡片 [AC-2]
- 4 个 stat-card: 传感器总数、在线数、告警数(当前漏水)、最近24小时告警数
- 使用 `el-row :gutter="16"` + `el-col :span="6"` 布局

#### Subtask 2.2: 区域分组卡片 [AC-3, AC-6]
- 按 `area_code` 分组
- 每个卡片: 区域名、传感器数、正常数、告警数、状态汇总
- 漏水告警区域红色脉冲动画
- 使用 `el-row` + `el-col :span="6"` 网格布局

#### Subtask 2.3: 传感器详情面板 [AC-4]
- 点击区域卡片展开传感器列表（el-drawer）
- 点击传感器显示详情: 设备名、当前状态、安装位置、告警记录列表
- 告警记录使用 `getAlarmList` API（按 point_id + 时间范围筛选）

#### Subtask 2.4: 底部数据表格 [AC-5]
- `el-table` 显示所有水浸传感器
- 筛选: 区域下拉、状态下拉（正常/告警/离线）
- 搜索: 名称关键字

#### Subtask 2.5: WebSocket 实时更新 [AC-7]
- 复用 `realtimeWs` WebSocket 实例
- 数据更新时自动刷新统计、卡片、表格

#### Subtask 2.6: 2.5D 样式 [AC-8]
- `@use '@/styles/mixins-25d' as *`
- `.water-leak-monitor { @include page-dashboard(4); }`

## 开发备注

### 与 Story 18.1 的关键区别
| 维度 | 18.1 温湿度 | 18.2 水浸检测 |
|------|------------|-------------|
| 传感器类型 | AI（模拟量） | DI（干接点） |
| device_type | `TH` | `WL` |
| 数据特征 | 连续数值（温度、湿度） | 二值状态（正常/漏水） |
| 统计卡片 | 6 个（含平均温湿度、漂移数） | 4 个（含 24h 告警数） |
| 详情面板 | 24h 趋势图 + 告警列表 | 告警记录列表（无趋势图） |
| 区域卡片指标 | 平均温湿度、最大/最小值 | 正常数/告警数、状态汇总 |
| 告警视觉 | 红色边框 | 红色脉冲动画 |
| 漂移检测 | 有 | 无（DI 类型不适用） |

### 现有可复用资源
- `getAllRealtimeData` API — 获取所有点位实时数据
- `getAlarmList` API — 获取告警列表（支持 point_id 筛选）
- `getActiveAlarms` API — 获取活动告警
- `realtimeWs` WebSocket 实例 — 实时数据推送
- `_mixins-25d.scss` — 2.5D 视觉增强 mixin
- `DataQualityTag` 组件 — 数据质量标签

### API 端点
| 用途 | API | 文件 |
|------|-----|------|
| 实时数据 | `GET /v1/realtime` | `api/modules/realtime.ts` |
| DI 类型数据 | `GET /v1/realtime/by-type/DI` | `api/modules/realtime.ts` |
| 告警列表 | `GET /v1/alarms` | `api/modules/alarm.ts` |
| 活动告警 | `GET /v1/alarms/active` | `api/modules/alarm.ts` |
| 变化记录 | `GET /v1/history/changes/:id` | `api/modules/history.ts` |

### 参考文件
- `frontend/src/views/environment/temperature.vue` — 同 Epic 页面模式
- `frontend/src/composables/useTemperatureData.ts` — composable 模式参考
- `frontend/src/api/websocket.ts` — WebSocket 客户端
- `frontend/src/styles/_mixins-25d.scss` — 2.5D mixin 系统
