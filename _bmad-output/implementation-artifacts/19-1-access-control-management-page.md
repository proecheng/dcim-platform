# Story 19.1: 门禁管理页

## Story 描述

**As a** 运维工程师,
**I want to** 在门禁管理页面查看所有门禁设备状态，并通过时间线视图浏览出入记录和异常事件,
**So that** 我可以实时监控数据中心出入情况，快速发现未授权访问等安全异常。

## 状态: 就绪

## 验收标准 (AC)

### AC-1: 页面路由
- 页面路由: `/security/access-control`（已注册，当前为 PlaceholderView）
- 替换 PlaceholderView 为完整实现

### AC-2: 顶部统计卡片
- 显示 4 个统计卡片: 门禁设备总数、在线数、告警数(异常事件)、今日出入总次数
- 门禁设备筛选: `device_type === 'DOOR'`
- 使用 `stat-card` 模式（与 water-leak.vue / smoke-infrared.vue 一致）
- 2.5D 弧形倾斜效果

### AC-3: 左侧门禁设备列表
- 左侧面板宽度约 320px，可滚动
- 每个设备显示: 名称、位置(area_code)、当前状态(常闭/常开/异常/离线)、最后事件时间
- 状态映射:
  - `status === 'normal'` + `value === 0` → 常闭（绿色）
  - `status === 'normal'` + `value === 1` → 常开（蓝色）
  - `status === 'alarm'` → 异常（红色脉冲）
  - `status === 'offline'` → 离线（灰色）
- 选中设备高亮，默认选中第一个
- 告警设备排在列表顶部

### AC-4: 右侧时间线视图
- 核心区域: 使用 `el-timeline` 组件纵向展示选中门禁设备的出入记录
- 每条记录显示:
  - 时间（精确到秒）
  - 事件类型: 刷卡开门 / 远程开门 / 异常开门 / 消防联动开门
  - 人员信息（如有，从告警消息中提取）
  - 结果: 成功 / 失败
- 事件类型颜色编码:
  - 刷卡开门: 绿色（成功）/ 灰色（失败）
  - 远程开门: 蓝色
  - 异常开门（非授权时段进入、多次刷卡失败、强行闯入）: 红色高亮 + Warning 图标
  - 消防联动开门: 橙色标记，显示关联联动策略名称
- 数据来源: 告警记录 `getAlarmList({ point_id })` + 实时状态变化事件

### AC-5: 时间线筛选
- 日期范围筛选: `el-date-picker` type="daterange"
- 事件类型筛选: `el-select` 多选（刷卡开门/远程开门/异常开门/消防联动开门/全部）
- 筛选后时间线自动刷新

### AC-6: 设备切换联动
- 点击左侧不同门禁设备，右侧时间线自动切换到该设备的记录
- 切换时显示加载状态
- 保持筛选条件不变

### AC-7: DI 类型传感器特性
- 门禁设备: `device_type === 'DOOR'`，DI 类型（干接点信号）
- 状态只有正常/告警两种（加离线），不显示连续数值
- 显示 `value_text` 而非 `value`
- 状态变化触发告警

### AC-8: WebSocket 实时更新
- 通过 WebSocket 接收实时门禁事件
- 新事件自动插入时间线顶部（最新在上）
- 设备状态变化时左侧列表自动更新
- 告警时设备项立即切换为红色脉冲状态

### AC-9: 2.5D 视觉增强
- 使用 `@use '@/styles/mixins-25d' as *` 引入 2.5D mixin
- `page-dashboard` preset 应用于页面容器（4 个统计卡片用 `$card-count: 4`）
- 左右分栏布局的 2.5D 景深差效果
- 与安防模块其他页面视觉风格一致

## 技术任务

### Task 1: 创建 composable — `useAccessControlData.ts` [AC-2, AC-3, AC-7, AC-8]
- 路径: `frontend/src/composables/useAccessControlData.ts`
- 封装门禁设备数据获取、统计计算、事件记录获取
- 筛选逻辑: `device_type === 'DOOR'`
- 统计: totalCount, onlineCount, alarmCount, todayEventCount
- 设备列表: 按告警优先排序
- 事件记录获取: `getAlarmList({ point_id, start_time, end_time })`
- 消防联动策略: `getLinkagePolicies({ trigger_type: 'fire_alarm' })`
- WebSocket 实时更新 + 轮询降级
- 导出: 设备列表、统计数据、事件记录、筛选方法

### Task 2: 实现 access-control.vue 页面 [AC-1 ~ AC-9]
- 路径: `frontend/src/views/security/access-control.vue`
- 替换 PlaceholderView

#### Subtask 2.1: 顶部统计卡片 [AC-2]
- 4 个 stat-card: 设备总数、在线数、告警数、今日事件数
- 使用 `el-row :gutter="16"` + 4 列布局

#### Subtask 2.2: 左侧设备列表面板 [AC-3, AC-6]
- 固定宽度 320px 左侧面板
- 设备项: 名称、位置、状态标签、最后事件时间
- 选中高亮，默认选中第一个
- 告警设备排前面

#### Subtask 2.3: 右侧时间线视图 [AC-4, AC-5]
- `el-timeline` + `el-timeline-item` 纵向时间线
- 事件类型颜色编码和图标
- 异常事件红色高亮 + Warning 图标
- 消防联动事件橙色标记 + 策略名称
- 日期范围 + 事件类型筛选器

#### Subtask 2.4: WebSocket 实时更新 [AC-8]
- 复用 `realtimeWs` WebSocket 实例
- 新事件自动插入时间线
- 设备状态实时更新

#### Subtask 2.5: 2.5D 样式 [AC-9]
- `@use '@/styles/mixins-25d' as *`
- `.access-control-page { @include page-dashboard(4); }`
- 左右分栏景深差效果

## 开发备注

### 与其他安防页面的关键区别
| 维度 | overview.vue | access-control.vue |
|------|-------------|-------------------|
| 布局 | 统计卡片 + 表格 | 统计卡片 + 左右分栏(设备列表+时间线) |
| 核心交互 | 表格浏览 | 时间线视图 + 设备切换联动 |
| 设备类型 | DOOR+SMOKE+IR | 仅 DOOR |
| 事件展示 | 无 | 时间线（刷卡/远程/异常/消防联动） |
| 筛选 | 无 | 日期范围 + 事件类型 |

### 事件类型推导逻辑
门禁设备为 DI 类型，事件类型从告警记录推导:
- `alarm_type === 'threshold'` + `alarm_level === 'info'` → 刷卡开门
- `alarm_type === 'system'` → 远程开门
- `alarm_type === 'threshold'` + `alarm_level in ['major', 'critical']` → 异常开门
- 关联消防联动策略的事件 → 消防联动开门
- 无告警记录的状态变化 → 正常刷卡开门（从实时数据推导）

### 现有可复用资源
- `getAllRealtimeData` API — 获取所有点位实时数据
- `getAlarmList` API — 获取告警列表（支持 point_id + 时间范围筛选）
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

### 参考文件
- `frontend/src/views/environment/water-leak.vue` — DI 类型传感器页面模式
- `frontend/src/views/environment/smoke-infrared.vue` — 含联动策略关联的页面
- `frontend/src/views/security/overview.vue` — 安防总览页（同模块参考）
- `frontend/src/composables/useSmokeInfraredData.ts` — composable 模式参考
- `frontend/src/composables/useWaterLeakData.ts` — composable 模式参考
- `frontend/src/api/modules/linkage.ts` — 联动策略 API
- `frontend/src/api/websocket.ts` — WebSocket 客户端
- `frontend/src/styles/_mixins-25d.scss` — 2.5D mixin 系统
