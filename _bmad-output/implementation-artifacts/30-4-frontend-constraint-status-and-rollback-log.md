# Story 30.4: 前端约束状态与回退记录展示

Status: done

## Story

As a 运维人员,
I want 在前端查看约束状态指示器和回退事件时间线,
So that 我能直观了解安全保护的运行情况。

## 依赖

- Story 30.3（回退保护 API）— done
  - 提供 `GET /api/v1/precool/zones/{zone_id}/rollback-status` — 实时回退状态
  - 提供 `GET /api/v1/precool/zones/{zone_id}/rollback-history` — 历史事件（分页 + status 筛选）
  - 提供 `GET /api/v1/precool/rollback-overview` — 全局回退概览
- Story 30.2（7 项自动回退保护机制）— done
  - WebSocket 已通过 `broadcast_alarm` 推送回退事件：
    - `action: "rollback"` — 触发回退（含 zone_id, trigger_type, trigger_value, threshold, rollback_action, timestamp）
    - `action: "rollback_recovery"` — 恢复（含 zone_id, trigger_type, timestamp）

## Acceptance Criteria

1. Given 回退保护 API 已就绪
   When 进入制冷联动监控页面（CoolingLinkageMonitor）
   Then 显示约束状态指示灯（绿/黄/红：正常/接近约束/回退中）
   - 绿色：无活跃回退，headroom > 3°C
   - 黄色：无活跃回退，headroom ≤ 3°C（接近约束边界）
   - 红色：有活跃回退（has_active_rollback = true）

2. Given 回退保护 API 已就绪
   When 进入制冷联动监控页面
   Then 显示回退事件时间线（最近事件列表）
   - 最新事件优先排列
   - 显示触发类型（中文映射）、触发值、阈值、动作、状态、时间
   - 支持状态筛选（active/resolved/全部）
   - 分页加载

3. Given WebSocket 已连接
   When 后端推送回退事件（action: rollback / rollback_recovery）
   Then 前端实时更新约束状态指示灯和事件列表（无需轮询）
   - 收到 `rollback` 消息后自动添加到事件列表并刷新状态
   - 收到 `rollback_recovery` 消息后更新对应事件状态并刷新

4. Given 制冷联动监控页面加载
   When API 调用
   Then 所有 API 函数在 `precool.ts` 中追加，遵循现有 request 封装模式

5. Given 组件和 API 已创建
   When 检查代码质量
   Then TypeScript 类型定义完整，无 any 类型泄露

## Tasks / Subtasks

- [x] Task 1: 在 `precool.ts` 追加回退 API 函数和类型 (AC: #4, #5)
  - [x] 1.1 追加 `RollbackTriggerInfo`、`RollbackStatusResponse`、`RollbackEventItem`、`RollbackOverviewResponse` 接口
  - [x] 1.2 追加 `getRollbackStatus(zoneId)` API 函数
  - [x] 1.3 追加 `getRollbackHistory(zoneId, params)` API 函数（支持 skip/limit/status）
  - [x] 1.4 追加 `getRollbackOverview()` API 函数

- [x] Task 2: 创建 `RollbackStatusCard.vue` 约束状态卡片组件 (AC: #1)
  - [x] 2.1 状态指示灯：绿/黄/红三色，根据 has_active_rollback 和 headroom 判断
  - [x] 2.2 展示活跃触发条件列表（trigger_type 中文映射、since 时间、recovering 状态）
  - [x] 2.3 触发类型中文映射（7 种 RollbackTriggerType）
  - [x] 2.4 接收 `zoneId` 和 `headroom` 两个 props — zoneId 用于 API 调用，headroom 用于指示灯颜色判断（来自父页面 `zoneList` 中的 `DashboardZone.headroom`）

- [x] Task 3: 创建 `RollbackTimeline.vue` 回退事件时间线组件 (AC: #2)
  - [x] 3.1 使用 el-timeline 展示最近回退事件
  - [x] 3.2 状态筛选（el-radio-group: 全部/active/resolved）
  - [x] 3.3 分页加载（limit=10，el-pagination）
  - [x] 3.4 每个事件显示：trigger_type（中文）、trigger_value vs threshold、action、status tag、时间

- [x] Task 4: 集成到 CoolingLinkageMonitor.vue (AC: #1, #2)
  - [x] 4.1 在监控页面顶部统计卡片行后追加 RollbackStatusCard，传入 `selectedZoneId` 和当前 zone 的 `headroom`（从 `zoneList` 中查找）
  - [x] 4.2 在页面底部追加 RollbackTimeline，传入 `selectedZoneId`

- [x] Task 5: WebSocket 实时推送处理 (AC: #3)
  - [x] 5.1 在 RollbackStatusCard 和 RollbackTimeline 中监听 `alarms` 通道的 `rollback` / `rollback_recovery` action
  - [x] 5.2 收到 rollback 消息后自动刷新状态 + 在时间线头部插入新事件
  - [x] 5.3 收到 rollback_recovery 消息后刷新状态

## Dev Notes

### 架构约束

- **修改文件**: `frontend/src/api/modules/precool.ts` — 追加 4 个 API 函数 + 4 个接口
- **新建文件**: `frontend/src/components/energy/RollbackStatusCard.vue` — 约束状态卡片
- **新建文件**: `frontend/src/components/energy/RollbackTimeline.vue` — 回退事件时间线
- **修改文件**: `frontend/src/views/energy/shift/CoolingLinkageMonitor.vue` — 集成新组件

### API 函数设计

```typescript
// 追加到 frontend/src/api/modules/precool.ts

// ========== 回退保护类型 ==========

export interface RollbackTriggerInfo {
  trigger_type: string
  since: string | null
  event_id: number | null
  recovering: boolean
}

export interface RollbackStatusResponse {
  zone_id: number
  has_active_rollback: boolean
  active_triggers: RollbackTriggerInfo[]
}

export interface RollbackEventItem {
  id: number
  zone_id: number
  trigger_type: string
  trigger_value: number | null
  threshold: number | null
  action: string
  status: string  // "active" | "resolved"
  context_json: string | null
  created_at: string | null
  resolved_at: string | null
}

export interface RollbackOverviewResponse {
  total_zones: number
  zones_with_active_rollback: number
  total_active_triggers: number
  trigger_type_counts: Record<string, number>
  recent_events_24h: number
  zone_statuses: RollbackStatusResponse[]
}

// ========== 回退保护 API ==========

/** 查询 zone 回退状态 */
export function getRollbackStatus(zoneId: number) {
  return request.get<{ code: number; message: string; data: RollbackStatusResponse }>(
    `/v1/precool/zones/${zoneId}/rollback-status`
  )
}

/** 查询回退历史事件 */
export function getRollbackHistory(
  zoneId: number,
  params?: { skip?: number; limit?: number; status?: 'active' | 'resolved' }
) {
  return request.get<{ code: number; message: string; data: { items: RollbackEventItem[]; total: number } }>(
    `/v1/precool/zones/${zoneId}/rollback-history`,
    { params }
  )
}

/** 全局回退概览 */
export function getRollbackOverview() {
  return request.get<{ code: number; message: string; data: RollbackOverviewResponse }>(
    '/v1/precool/rollback-overview'
  )
}
```

### 组件设计

#### RollbackStatusCard.vue

```vue
<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>回退保护状态</span>
        <!-- 状态指示灯 -->
        <el-tag :type="statusTagType" effect="dark" size="large">
          {{ statusText }}
        </el-tag>
      </div>
    </template>

    <!-- 活跃触发条件列表 -->
    <div v-if="status?.active_triggers?.length">
      <el-descriptions :column="1" border size="small" v-for="trigger in status.active_triggers">
        <el-descriptions-item :label="triggerTypeMap[trigger.trigger_type] || trigger.trigger_type">
          <el-tag :type="trigger.recovering ? 'warning' : 'danger'" size="small">
            {{ trigger.recovering ? '恢复中' : '触发中' }}
          </el-tag>
          <span v-if="trigger.since" style="margin-left: 8px; color: #909399; font-size: 12px">
            {{ formatTime(trigger.since) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </div>
    <div v-else style="color: #67c23a; text-align: center; padding: 10px">
      所有约束检查通过，系统运行正常
    </div>
  </el-card>
</template>
```

**Props 定义**：
```typescript
const props = defineProps<{
  zoneId: number
  headroom: number | null  // 来自父页面 DashboardZone.headroom
}>()

// statusTagType 计算逻辑：
// - has_active_rollback === true → 'danger'（红色）
// - headroom !== null && headroom <= 3 → 'warning'（黄色）
// - 其他 → 'success'（绿色）

#### RollbackTimeline.vue

```vue
<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>回退事件记录</span>
        <el-radio-group v-model="statusFilter" size="small" @change="refresh">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="active">进行中</el-radio-button>
          <el-radio-button value="resolved">已恢复</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-timeline>
      <el-timeline-item v-for="event in events" :key="event.id"
        :type="event.status === 'active' ? 'danger' : 'success'"
        :timestamp="formatTime(event.created_at)" placement="top">
        <el-card shadow="never" class="timeline-event-card">
          <div>
            <el-tag :type="event.status === 'active' ? 'danger' : 'success'" size="small">
              {{ event.status === 'active' ? '进行中' : '已恢复' }}
            </el-tag>
            <span style="margin-left: 8px; font-weight: bold">
              {{ triggerTypeMap[event.trigger_type] || event.trigger_type }}
            </span>
          </div>
          <div style="margin-top: 4px; font-size: 13px; color: #606266">
            {{ event.action }}
          </div>
          <div v-if="event.trigger_value != null" style="margin-top: 4px; font-size: 12px; color: #909399">
            触发值: {{ event.trigger_value }} / 阈值: {{ event.threshold }}
          </div>
          <div v-if="event.resolved_at" style="margin-top: 4px; font-size: 12px; color: #67c23a">
            恢复时间: {{ formatTime(event.resolved_at) }}
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <el-pagination v-if="total > pageSize" layout="prev, pager, next"
      :total="total" :page-size="pageSize" :current-page="currentPage"
      @current-change="handlePageChange" style="margin-top: 16px; justify-content: center" />
  </el-card>
</template>
```

### 触发类型中文映射

```typescript
const triggerTypeMap: Record<string, string> = {
  temp_over_limit: '温度超限',
  rate_over_predicted: '温升超预测',
  rate_over_limit: '温变速率超限',
  ac_fault: '空调故障',
  sensor_offline: '传感器离线',
  ups_active: 'UPS 切换',
  humidity_dew_point: '湿度露点风险',
}
```

### WebSocket 集成

后端 `rollback_manager.py` 已通过 `broadcast_alarm` 推送两种消息：

1. **触发回退** — `action: "rollback"`
```json
{
  "action": "rollback",
  "id": 42,
  "zone_id": 1,
  "trigger_type": "temp_over_limit",
  "trigger_value": 27.5,
  "threshold": 26.0,
  "rollback_action": "恢复正常制冷",
  "timestamp": "2026-03-11T10:30:00"
}
```

2. **恢复** — `action: "rollback_recovery"`
```json
{
  "action": "rollback_recovery",
  "id": 42,
  "zone_id": 1,
  "trigger_type": "temp_over_limit",
  "timestamp": "2026-03-11T10:45:00"
}
```

**前端处理模式**（参照 `useAlarm.ts`）：

组件内使用 `useWebSocketManager()` 注册 `alarms` 通道的 `alarm` 类型消息处理器，在 handler 中判断 `action === 'rollback'` 或 `action === 'rollback_recovery'`，分别刷新状态和事件列表。

```typescript
// 在组件 onMounted 中
const wsManager = useWebSocketManager()

const handleRollbackMessage = (message: any) => {
  const { action, data } = message
  if (action === 'rollback' && data?.zone_id === props.zoneId) {
    // 刷新状态 + 刷新事件列表
    fetchStatus()
    fetchEvents()
  }
  if (action === 'rollback_recovery' && data?.zone_id === props.zoneId) {
    fetchStatus()
    fetchEvents()
  }
}

wsManager.on('alarms', 'alarm', handleRollbackMessage)

onUnmounted(() => {
  wsManager.off('alarms', 'alarm', handleRollbackMessage)
})
```

**注意**：`useAlarm.ts` 的 handler 用 `switch(action)` 处理 `new/ack/update/resolve/batch_ack/escalate`，不会拦截 `rollback` / `rollback_recovery`。但 handler 注册在同一个 type `'alarm'` 上，WebSocketClient 会分发给所有注册的 handler。所以新组件的 handler 能正常接收到这些消息，不会冲突。

### CoolingLinkageMonitor.vue 集成

在现有页面中追加两个组件，位置在统计卡片行之后：

```vue
<!-- 在 el-row（4 个统计卡片）之后追加 -->
<el-row :gutter="20" style="margin-top: 20px">
  <el-col :span="8">
    <RollbackStatusCard :zone-id="selectedZoneId" :headroom="currentZoneHeadroom" />
  </el-col>
  <el-col :span="16">
    <RollbackTimeline :zone-id="selectedZoneId" />
  </el-col>
</el-row>
```

**数据来源**：CoolingLinkageMonitor 已有 `selectedZoneId` 和 `zoneList`（`DashboardZone[]`），`headroom` 通过 computed 从 `zoneList` 中查找：

```typescript
const currentZoneHeadroom = computed(() => {
  const zone = zoneList.value.find(z => z.zone_id === selectedZoneId.value)
  return zone?.headroom ?? null
})

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story30.4] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 预冷 TCL 架构
- [Source: frontend/src/api/modules/precool.ts] — 现有 API 函数（追加模式）
- [Source: frontend/src/views/energy/shift/CoolingLinkageMonitor.vue] — 集成目标页面
- [Source: frontend/src/composables/useAlarm.ts] — WebSocket alarm 消息处理模式
- [Source: frontend/src/composables/useWebSocketManager.ts] — WebSocket 管理器
- [Source: backend/app/services/precool/rollback_manager.py:327-341,408-419] — 已有的 WebSocket 推送代码

### Previous Story Intelligence

**从 Story 30.3 学到的关键经验：**
1. **API 响应格式**: `{"code": 200, "message": "success", "data": ...}` — 前端需匹配
2. **rollback-history 分页**: 支持 skip/limit/status 参数
3. **rollback-status 结构**: `{zone_id, has_active_rollback, active_triggers: [{trigger_type, since, event_id, recovering}]}`
4. **权限**: 回退 API 使用 viewer+ 权限（前端不需要特殊权限处理）
5. **Dev Agent Record**: 实施完必须更新 tasks [x]、File List、Change Log

## NFR 追溯

- **NFR-TCL-6**: 回退响应时间 ≤ 30 秒（WebSocket 推送实时更新，远低于限制）

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Completion Notes List
- 5 个 Task 全部完成，前端构建通过 (32.30s)
- precool.ts 追加 4 个接口 + 3 个 API 函数，遵循现有 request 封装模式
- RollbackStatusCard.vue 实现三色状态指示灯（绿/黄/红），支持 WebSocket 实时更新
- RollbackTimeline.vue 实现 el-timeline + 状态筛选 + 分页，支持 WebSocket 实时更新
- CoolingLinkageMonitor.vue 集成两个新组件，通过 computed 从 zoneList 获取 headroom
- WebSocket 使用 useWebSocketManager 监听 alarms 通道的 rollback/rollback_recovery action
- 经过两轮对抗性审查，修复 6 个问题（WebSocket 消息格式、headroom 数据源、el-radio-button 属性等）

### Change Log
- `frontend/src/api/modules/precool.ts` — 追加回退保护类型定义和 API 函数
- `frontend/src/components/energy/RollbackStatusCard.vue` — 新建约束状态卡片组件
- `frontend/src/components/energy/RollbackTimeline.vue` — 新建回退事件时间线组件
- `frontend/src/views/energy/shift/CoolingLinkageMonitor.vue` — 集成新组件、添加 computed headroom

### File List
- `frontend/src/api/modules/precool.ts` (modified)
- `frontend/src/components/energy/RollbackStatusCard.vue` (new)
- `frontend/src/components/energy/RollbackTimeline.vue` (new)
- `frontend/src/views/energy/shift/CoolingLinkageMonitor.vue` (modified)
