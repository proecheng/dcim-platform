# Story 27.1: 告警数据链路统一（方案 A）

Status: ready-for-dev

## Story

As a 用户,
I want 所有页面的告警数据来自同一个数据源,
So that 仪表盘、告警列表、大屏、告警铃铛显示的告警计数和列表始终一致。

## Acceptance Criteria (验收标准)

1. **AC-1: AlarmStore 成为唯一事实来源** — `AlarmStore` 新增 `fetchActiveAlarms()` action（带防重入锁），调用 `getActiveAlarms()` API 并更新自身 `activeAlarms` 和 `alarmCount`。所有页面通过 AlarmStore 读取告警数据。AlarmStore 不设置 200 条硬限制，完整保存后端返回的活动告警列表。
2. **AC-2: useAlarm composable 移除自有状态** — `useAlarm.ts` 的 `activeAlarms` ref（第33行）和 `alarmCount` ref（第34行）被移除，改为读取 `alarmStore.activeAlarms` 和 `alarmStore.alarmCount`。`addAlarm`/`updateAlarm` 操作直接调用 AlarmStore action。
3. **AC-3: BigscreenStore 派生告警** — `BigscreenStore.activeAlarms`（第37行）从独立状态改为 getter，通过完整字段映射函数将 `Alarm/AlarmInfo` 转换为 `BigscreenAlarm`（字段映射：`alarm_level`→`level`, `alarm_message`→`message`, `point_code`→`deviceId`, `point_name`→`deviceName`, `created_at`→`createdAt`, `trigger_value`→`value`, `threshold_value`→`threshold`）。`setAlarms()` action（第186-188行）移除。
4. **AC-4: Dashboard 移除局部告警状态** — `dashboard/index.vue` 的局部 `activeAlarms` ref（第247行）移除，改为直接读取 `alarmStore.activeAlarms`。`dcim_dashboard_cache`（第257行）中告警相关的 sessionStorage 缓存移除。告警区域在 `fetchActiveAlarms()` 加载期间显示 loading 状态（v-loading），避免白屏。
5. **AC-5: 温度页面保持 API 调用** — `temperature.vue:310` 的 `getActiveAlarms({ point_id })` API 调用**保留不变**（该调用按 point_id 精确查询后端，Store 只保存活动告警无法保证包含该点位的全部告警，改用 Store 可能丢数据）。告警计数/铃铛等全局展示从 AlarmStore 读取，但点位级别的精确查询保持 API 调用。
6. **AC-6: DemoDataLoader 触发全局 Store 刷新** — `DemoDataLoader.vue` 的 `@loaded`/`@unloaded` 事件处理中，调用 `alarmStore.fetchActiveAlarms()` 刷新全局 Store。同时为 `realtimeStore` 和 `energyStore` 新增 `reload()` 占位方法（空实现，Story 27.2/27.3 中填充），在 `refreshData()` 中一并调用。
7. **AC-7: 告警列表页保持分页 API** — `frontend/src/views/alarm/index.vue` 的分页查询（`loadAlarms()` 第895-927行调用 `getAlarmList(params)`）保持不变。告警列表页需要分页、筛选、排序功能，不适合从 Store 读取全量数据。但确认页面的告警计数（如有）从 AlarmStore 读取，WS 推送新告警后触发列表刷新走 AlarmStore 回调。
8. **AC-8: 5 个页面一致性验证** — 在仪表盘、大屏、Header 告警铃铛、环境监控温度页验证告警计数一致（均从 AlarmStore 读取）。告警列表页因使用独立分页 API，验证其计数与 AlarmStore 一致即可。

## Tasks / Subtasks (任务分解)

- [ ] Task 1: AlarmStore 增强 — 新增 fetchActiveAlarms action (AC: #1)
  - [ ] 1.1 在 `frontend/src/stores/alarm.ts` 新增 `fetchActiveAlarms()` async action：
    - 调用 `getActiveAlarms()` API（从 `@/api/modules/alarm` 导入）
    - 清空 `activeAlarms` 后用返回数据重新填充（不设 200 条限制）
    - 调用 `updateCount()` 刷新计数
    - 新增 `loading: ref(false)` 状态，fetch 前设 true，完成后设 false
    - **防重入锁**：若 `loading` 已为 true，直接 return 不重复请求
  - [ ] 1.2 新增 `handleWsMessage(data: any)` action 供未来 WebSocketManager（Story 27.5）回调：
    - 根据 `data.type`（new/ack/resolve/update/batch_ack/escalate）分发处理
    - 复用现有 `addAlarm`/`updateAlarm`/`removeAlarm` 方法
  - [ ] 1.3 新增 `getAlarmsByPointId(pointId: number): Alarm[]` getter，从 activeAlarms 按 point_id 过滤
  - [ ] 1.4 移除 `addAlarm` 中的 200 条限制（当前第46行 `if (this.activeAlarms.length > 200)`），改为不限制或提高上限至 1000
  - [ ] 1.5 确保 `addAlarm` 调用后自动 `updateCount()`（当前第39-48行已有此逻辑，确认无遗漏）

- [ ] Task 2: useAlarm composable 重构 — 移除自有状态 (AC: #2)
  - [ ] 2.1 移除 `useAlarm.ts` 中的自有 `activeAlarms` ref（第33行）和 `alarmCount` ref（第34行）
  - [ ] 2.2 用 `storeToRefs` 从 AlarmStore 获取响应式引用：
    ```typescript
    const alarmStore = useAlarmStore()
    const { activeAlarms, alarmCount } = storeToRefs(alarmStore)
    ```
  - [ ] 2.3 重构 `fetchActiveAlarms()`（第75-85行）：改为调用 `alarmStore.fetchActiveAlarms()`
  - [ ] 2.4 重构 `handleNewAlarm()`（第97-146行）：
    - 移除本地 `activeAlarms.value.unshift(alarm)` 操作
    - 改为调用 `alarmStore.addAlarm(alarm)`
    - 保留声音播放和 ElNotification 通知逻辑（这些是 composable 的职责）
  - [ ] 2.5 重构 `handleAlarmMessage()`（第176-228行）：
    - `case 'new'`: 调用 `alarmStore.addAlarm()` 替代本地操作
    - `case 'ack'`/`case 'update'`: 调用 `alarmStore.updateAlarm()` 替代本地操作
    - `case 'resolve'`: 调用 `alarmStore.removeAlarm()` 替代本地操作
    - `case 'batch_ack'`: 遍历调用 `alarmStore.updateAlarm()`
    - `case 'escalate'`: 调用 `alarmStore.updateAlarm()`
  - [ ] 2.6 保留 WebSocket 订阅逻辑（`subscribeAlarms`，第231-241行）暂不改动，等 Story 27.5 统一
  - [ ] 2.7 **onUnmounted 清理注意**：当前第285-287行有 `onUnmounted()` 清理 WS 连接。由于 useAlarm 可能在多个组件中实例化（MainLayout + 告警页面），需确保一个组件卸载时不影响其他组件的 WS。暂保持现有逻辑，在 Story 27.5 统一解决。添加 `// TODO: Story 27.5 - 迁移到 WebSocketManager 后移除此清理逻辑` 注释标记。
  - [ ] 2.8 保留 computed 属性（`criticalAlarms`、`majorAlarms` 等，第268-272行），改为从 `alarmStore.activeAlarms` 派生
  - [ ] 2.9 返回值中的 `activeAlarms` 和 `alarmCount` 改为 store 引用

- [ ] Task 3: BigscreenStore 告警派生 (AC: #3)
  - [ ] 3.1 在 `frontend/src/stores/bigscreen.ts` 中导入 `useAlarmStore`
  - [ ] 3.2 从 state 中移除 `activeAlarms: BigscreenAlarm[]`（第37行）
  - [ ] 3.3 新增 `activeAlarms` getter，包含**完整字段映射**（`BigscreenAlarm` 定义在 `types/bigscreen.ts:65-76`）：
    ```typescript
    activeAlarms: (): BigscreenAlarm[] => {
      return useAlarmStore().activeAlarms.map(alarm => ({
        id: alarm.id,
        deviceId: alarm.point_code || String(alarm.point_id),  // 必需字段
        deviceName: alarm.point_name || '',
        level: alarm.alarm_level as BigscreenAlarm['level'],   // alarm_level → level
        message: alarm.alarm_message || '',                     // alarm_message → message
        value: alarm.trigger_value,
        threshold: alarm.threshold_value,
        createdAt: alarm.created_at,                            // created_at → createdAt
      }))
    }
    ```
  - [ ] 3.4 将 `alarmCount` getter（第112行）改为从 AlarmStore 派生：
    ```typescript
    alarmCount: () => useAlarmStore().alarmCount.total
    ```
  - [ ] 3.5 将 `criticalAlarmCount` getter（第115-117行）改为从 AlarmStore 派生：
    ```typescript
    criticalAlarmCount: () => useAlarmStore().alarmCount.critical
    ```
  - [ ] 3.6 将 `recentAlarms` getter（第145行）改为从新 `activeAlarms` getter 派生：
    ```typescript
    recentAlarms(): BigscreenAlarm[] { return this.activeAlarms.slice(0, 10) }
    ```
  - [ ] 3.7 移除 `setAlarms()` action（第186-188行）
  - [ ] 3.8 检查 `useBigscreenData.ts` 中所有调用 `bigscreenStore.setAlarms()` 的地方，改为调用 `alarmStore.fetchActiveAlarms()`

- [ ] Task 4: Dashboard 移除局部告警状态 (AC: #4)
  - [ ] 4.1 在 `frontend/src/views/dashboard/index.vue` 中导入 `useAlarmStore`
  - [ ] 4.2 移除局部 `activeAlarms` ref（第247行）
  - [ ] 4.3 用 `const alarmStore = useAlarmStore()` 替代，模板中用 `alarmStore.activeAlarms`
  - [ ] 4.4 在 `refreshData()`（第412行）中移除 `getActiveAlarms()` 直接调用，改为 `await alarmStore.fetchActiveAlarms()`
  - [ ] 4.5 从 `DashboardCachePayload` 接口（第259行）中移除 `activeAlarms` 字段
  - [ ] 4.6 从 `saveDashboardCache()`（第381行）和 `applyCachedDashboardData()`（第397行）中移除告警相关缓存逻辑
  - [ ] 4.7 更新模板中所有 `activeAlarms` 引用为 `alarmStore.activeAlarms`
  - [ ] 4.8 在告警展示区域添加 loading 状态：使用 `v-loading="alarmStore.loading"` 包裹告警卡片区域

- [ ] Task 5: DemoDataLoader 触发全局刷新 (AC: #6)
  - [ ] 5.1 确认 `DemoDataLoader.vue` 的 `emit('loaded')` 和 `emit('unloaded')` 事件（第197、252行）
  - [ ] 5.2 在 `frontend/src/stores/realtime.ts` 新增 `reload()` 空方法占位：
    ```typescript
    async reload() { /* Story 27.2 实现 */ }
    ```
  - [ ] 5.3 在 `frontend/src/stores/energy.ts` 新增 `reload()` 空方法占位：
    ```typescript
    async reload() { /* Story 27.3 实现 */ }
    ```
  - [ ] 5.4 在 `dashboard/index.vue` 的 `refreshData()` 函数中，新增全局 Store 刷新：
    ```typescript
    await Promise.all([
      alarmStore.fetchActiveAlarms(),
      useRealtimeStore().reload(),
      useEnergyStore().reload(),
    ])
    ```

- [ ] Task 6: 告警列表页确认 (AC: #7)
  - [ ] 6.1 检查 `frontend/src/views/alarm/index.vue` 的 `loadAlarms()` 函数（第895-927行）
  - [ ] 6.2 确认该页面使用 `getAlarmList(params)` 分页 API — **保持不变**，这是合理的
  - [ ] 6.3 检查页面是否有独立的告警计数统计（如 badge、标签页计数），如有则改为从 AlarmStore 读取
  - [ ] 6.4 检查 WS 推送新告警后是否触发列表自动刷新（如有，确认经由 AlarmStore 回调）

- [ ] Task 7: 类型兼容预留 (跨 Story 28.1)
  - [ ] 7.1 在 `frontend/src/stores/alarm.ts` 的 Alarm 接口（第4-25行）预留 `data_source?: string` 可选字段
  - [ ] 7.2 在 `frontend/src/api/modules/alarm.ts` 的 AlarmInfo 接口（第7-34行）预留 `data_source?: string` 可选字段
  - [ ] 7.3 **说明**：这些字段在 Story 28.1 后端实现前为 undefined，不影响现有逻辑，但避免 28.1 合入时的类型冲突

- [ ] Task 8: 构建与验证 (AC: #8)
  - [ ] 8.1 `cd frontend && npm run build` 确认无编译错误
  - [ ] 8.2 `cd frontend && npm run typecheck` 确认无类型错误
  - [ ] 8.3 启动服务后验证页面告警计数一致性：
    - 仪表盘（Dashboard）— 告警区域从 AlarmStore 读取
    - 大屏（Bigscreen）— getter 从 AlarmStore 派生
    - Header 告警铃铛 — 从 AlarmStore 读取
  - [ ] 8.4 验证方法：使用 Vue DevTools 的 Pinia 面板查看 alarm store 状态，确认各页面引用同一份数据

## Dev Notes (开发指南)

### 现有代码结构

**AlarmStore** (`stores/alarm.ts`, 91行)：
- 状态：`activeAlarms: ref<Alarm[]>([])`, `alarmCount: ref({...})`, `soundEnabled: ref`
- 方法：`addAlarm()`, `removeAlarm()`, `updateAlarm()`, `updateCount()`, `toggleSound()`
- `addAlarm` 中有 200 条硬限制（第46行）— **本次需移除或提高**
- Alarm 接口（第4-25行）字段：id, alarm_no, point_id, point_code, point_name, threshold_id, alarm_level, alarm_type, alarm_message, trigger_value, threshold_value, status, acknowledged_by, acknowledged_at, ack_remark, resolved_by, resolved_at, resolve_remark, duration_seconds, escalation_count, escalated_from, created_at

**useAlarm composable** (`composables/useAlarm.ts`, 312行)：
- 维护独立的 `activeAlarms` 和 `alarmCount` ref — **这是本次要消除的割裂**
- WebSocket 连接在第69-72行创建，第231-241行订阅
- `handleAlarmMessage()` 是 WS 消息处理枢纽（第176-228行）
- 声音播放逻辑在第42-66行（Web Audio API 兜底）和第121-127行
- **onUnmounted** 清理 WS 在第285-287行 — 多实例时有相互影响风险

**BigscreenStore** (`stores/bigscreen.ts`, 269行)：
- `activeAlarms: BigscreenAlarm[]` 在第37行 — 独立状态，与 AlarmStore 完全割裂
- `setAlarms()` 在第186-188行 — 由 `useBigscreenData` 调用填充
- **BigscreenAlarm 类型**（`types/bigscreen.ts:65-76`）：字段为 id, deviceId(必需), deviceName, level(必需), message(必需), value, threshold, duration, time, createdAt。与 Alarm 类型字段名完全不同，需逐字段映射。

**Dashboard** (`views/dashboard/index.vue`, 939行)：
- 局部 `activeAlarms` ref 在第247行
- `dcim_dashboard_cache` 在第257行（sessionStorage 缓存含告警数据）
- `refreshData()` 在第412行直接调用 `getActiveAlarms()` API
- DemoDataLoader 在第216行：`<DemoDataLoader @loaded="refreshData" @unloaded="refreshData" />`

**告警列表页** (`views/alarm/index.vue`)：
- 第895-927行 `loadAlarms()` 直接调用 `getAlarmList(params)` 分页 API — **保持不变**
- 分页列表不适合从 Store 读取全量数据

**温度页面** (`views/environment/temperature.vue`, 693行)：
- 第310行直接调用 `getActiveAlarms({ point_id })` — **保持不变**
- 该调用按 point_id 精确查询后端，Store 只保存活动告警，改用 Store 可能丢数据

### 注意事项

1. **声音/通知逻辑保留在 useAlarm**：composable 仍负责播放告警声音和 ElNotification 弹窗，这些是 UI 副作用，不属于 Store
2. **WebSocket 暂不改动**：当前 WS 连接仍在 useAlarm 中管理，等 Story 27.5 统一迁移到 WebSocketManager
3. **告警列表页和温度页面保持 API 调用**：这两个页面有特殊的数据需求（分页筛选/点位精确查询），不适合从全量 Store 读取
4. **跨 Story 类型预留**：Story 28.1 将在 API 返回和 WS 消息中增加 `data_source`/`source` 字段，Task 7 预留了类型定义

### 执行顺序说明

本 Story 与 Story 28.1 可并行开发。两者修改文件无直接冲突：
- 27.1 修改前端 Store/Composable/Views
- 28.1 修改后端 Models/Pipeline/API + 前端 `views/alarm/index.vue`（仅新增列）

唯一交叉点是 `views/alarm/index.vue`：27.1 的 Task 6 仅检查不修改，28.1 的 Task 10 新增来源列。无合并冲突风险。

### 参考文档

- `docs/data-flow-audit.md` — P0-1 告警三源割裂问题定义
- `architecture.md` Section 19 — 前端数据链路规范
