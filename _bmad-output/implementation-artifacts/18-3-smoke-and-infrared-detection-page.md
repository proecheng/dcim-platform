# Story 18.3: 烟雾/红外检测页

## Story 描述

**As a** 运维工程师,
**I want to** 在烟雾/红外检测页面查看所有烟雾和红外传感器的实时状态和区域分布,
**So that** 当烟雾或入侵事件发生时我可以快速定位并响应。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/environment/smoke-infrared`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现

### AC-2: 顶部统计卡片
- 显示 5 个统计卡片: 烟雾传感器总数/告警数、红外传感器总数/告警数、最近24小时事件数
- 按传感器类型分别统计（烟雾 `device_type === 'SMOKE'`，红外 `device_type === 'IR'`）
- 使用 `stat-card` 模式（与 water-leak.vue 一致）
- 2.5D 弧形倾斜效果

### AC-3: 区域/房间分组状态卡片
- 核心区域: 按区域/房间分组的卡片布局
- 每个区域卡片显示: 区域名、烟雾传感器数、红外传感器数、当前状态汇总
- 告警区域卡片红色脉冲动画（`@keyframes pulseAlarm`）
- 使用 `el-row` + `el-col :span="6"` 网格布局

### AC-4: 传感器详情面板
- 点击区域卡片展开该区域传感器列表（el-drawer）
- 传感器列表按类型分组显示（烟雾/红外）
- 点击传感器显示详情面板: 设备名、类型(烟雾/红外)、当前状态、最近事件记录、关联联动策略
- 告警记录使用 `getAlarmList` API（按 point_id 筛选）

### AC-5: 消防联动策略关联
- 烟雾传感器告警时，详情面板显示关联消防联动策略状态
- 通过 `getLinkagePolicies({ trigger_type: 'fire_alarm' })` 查询消防联动策略
- 显示策略配置状态: 已配置(策略名+启用状态) / 未配置

### AC-6: 底部数据表格
- 传感器数据表格
- 支持按类型(烟雾/红外)筛选
- 支持按区域、按状态(正常/告警/离线)筛选
- 支持按名称搜索

### AC-7: DI 类型传感器特性
- 烟雾传感器: `device_type === 'SMOKE'`，DI 类型
- 红外传感器: `device_type === 'IR'`，DI 类型
- 状态只有正常/告警两种（加离线），不显示连续数值
- 显示 `value_text` 而非 `value`
- 状态变化触发告警

### AC-8: WebSocket 实时更新
- 通过 WebSocket 接收实时状态变化
- 卡片和表格自动刷新
- 告警时区域卡片立即切换为红色脉冲状态

### AC-9: 2.5D 视觉增强
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard` preset 应用于页面容器（5 个统计卡片用 `$card-count: 5`）
- 与 water-leak.vue 视觉风格一致

## 技术任务

### Task 1: 创建 composable — `useSmokeInfraredData.ts` [AC-2, AC-3, AC-7, AC-8]
- 路径: `frontend/src/composables/useSmokeInfraredData.ts`
- 封装烟雾+红外传感器数据获取、区域分组、统计计算
- 筛选逻辑: `device_type === 'SMOKE' || device_type === 'IR'`
- 按类型分别统计: smokeTotal, smokeAlarm, irTotal, irAlarm
- 区域分组: 每个区域包含 smokeCount, irCount, smokeAlarmCount, irAlarmCount
- 调用 `getAllRealtimeData` 获取实时数据
- 调用 `getAlarmList` 获取最近 24 小时告警数
- WebSocket 实时更新 + 轮询降级
- 导出: 分组数据、统计数据、筛选方法

### Task 2: 实现 smoke-infrared.vue 页面 [AC-1 ~ AC-9]
- 路径: `frontend/src/views/environment/smoke-infrared.vue`
- 替换 PlaceholderView

#### Subtask 2.1: 顶部统计卡片 [AC-2]
- 5 个 stat-card: 烟雾总数、烟雾告警、红外总数、红外告警、24h事件数
- 使用 `el-row :gutter="16"` + 5 列布局

#### Subtask 2.2: 区域分组卡片 [AC-3, AC-7]
- 按 `area_code` 分组
- 每个卡片: 区域名、烟雾传感器数/告警数、红外传感器数/告警数、状态汇总
- 告警区域红色脉冲动画

#### Subtask 2.3: 传感器详情面板 [AC-4, AC-5]
- 点击区域卡片展开传感器列表（el-drawer）
- 传感器按类型分组显示
- 点击传感器显示详情: 设备名、类型、当前状态、告警记录
- 烟雾传感器告警时显示消防联动策略状态

#### Subtask 2.4: 底部数据表格 [AC-6]
- `el-table` 显示所有烟雾+红外传感器
- 筛选: 类型下拉(烟雾/红外)、区域下拉、状态下拉
- 搜索: 名称关键字

#### Subtask 2.5: WebSocket 实时更新 [AC-8]
- 复用 `realtimeWs` WebSocket 实例
- 数据更新时自动刷新统计、卡片、表格

#### Subtask 2.6: 2.5D 样式 [AC-9]
- `@use '@/styles/mixins-25d' as *`
- `.smoke-infrared-monitor { @include page-dashboard(5); }`

## 开发备注

### 与 Story 18.2 的关键区别
| 维度 | 18.2 水浸检测 | 18.3 烟雾/红外检测 |
|------|-------------|-------------------|
| 传感器类型 | 单一 (WL) | 双类型 (SMOKE + IR) |
| device_type | `WL` | `SMOKE` / `IR` |
| 统计卡片 | 4 个 | 5 个（按类型分别统计） |
| 区域卡片指标 | 正常数/告警数 | 烟雾数/告警+红外数/告警 |
| 详情面板 | 告警记录 | 告警记录 + 消防联动策略状态 |
| 表格筛选 | 区域+状态 | 类型+区域+状态 |
| 联动策略 | 无 | 烟雾告警关联消防联动策略 |

### 现有可复用资源
- `getAllRealtimeData` API — 获取所有点位实时数据
- `getAlarmList` API — 获取告警列表（支持 point_id 筛选）
- `getLinkagePolicies` API — 获取联动策略列表（支持 trigger_type 筛选）
- `realtimeWs` WebSocket 实例 — 实时数据推送
- `_mixins-25d.scss` — 2.5D 视觉增强 mixin
- `DataQualityTag` 组件 — 数据质量标签

### API 端点
| 用途 | API | 文件 |
|------|-----|------|
| 实时数据 | `GET /v1/realtime` | `api/modules/realtime.ts` |
| 告警列表 | `GET /v1/alarms` | `api/modules/alarm.ts` |
| 联动策略 | `GET /v1/linkage/policies` | `api/modules/linkage.ts` |
| 消防策略状态 | `GET /v1/linkage/fire-protection/status` | `api/modules/linkage.ts` |

### 参考文件
- `frontend/src/views/environment/water-leak.vue` — 同 Epic DI 类型页面模式
- `frontend/src/composables/useWaterLeakData.ts` — composable 模式参考
- `frontend/src/api/modules/linkage.ts` — 联动策略 API
- `frontend/src/api/websocket.ts` — WebSocket 客户端
- `frontend/src/styles/_mixins-25d.scss` — 2.5D mixin 系统
