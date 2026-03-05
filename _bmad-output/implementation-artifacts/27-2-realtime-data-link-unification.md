# Story 27.2: 实时数据链路统一

Status: done

## Story

As a 用户,
I want 所有页面的实时点位数据来自同一个数据源 (RealtimeStore),
So that 仪表盘、环境监控、安防、大屏等页面的实时数据始终一致，不会出现数据割裂。

## Acceptance Criteria (验收标准)

1. **AC-1: RealtimeStore 成为唯一事实来源** — `RealtimeStore` 新增 `fetchAllData()`（带防重入锁）、`fetchSummary()`、`reload()`、`updatePoint()`、`updatePoints()`、`setAllData()`、`setSummary()` 等方法。`dataMap: Map<number, RealtimeData>` 为全局唯一数据容器。新增 `simpleSummary` computed 供 dashboard 使用。
   - **验证**: Vue DevTools Pinia 面板检查 realtime store 的 dataMap.size > 0；多个页面的传感器数值来源均为同一 store 实例。
2. **AC-2: useRealtime composable 委托给 Store** — `useRealtime.ts` 使用 `storeToRefs(store)` 获取响应式状态，WS 消息通过 `store.updatePoint()` 写入，轮询在 WS 断开时回退到 `store.fetchAllData()`。
   - **验证**: 在 useRealtime.ts 中搜索不到任何 `ref<Map>` 或 `ref<RealtimeData[]>` 的自有状态声明。
3. **AC-3: Dashboard 读取 Store** — `dashboard/index.vue` 的 `summary` 改为 `computed(() => realtimeStore.simpleSummary)`，`realtimeData` 改为 `computed(() => realtimeStore.realtimeData.slice(0, MAX_REALTIME_ROWS))`。`refreshData()` 调用 `realtimeStore.reload()`。sessionStorage 缓存通过 `realtimeStore.setSummary()` / `realtimeStore.setAllData()` 写入 Store（而非局部 ref），读取也从 Store computed 派生。
   - **验证**: dashboard 代码中无 `getAllRealtimeData` / `getRealtimeSummary` 的直接 import。
4. **AC-4: 环境/安防 Composables 迁移** — `useTemperatureData`、`useWaterLeakData`、`useSmokeInfraredData`、`useAccessControlData` 全部移除自有 `allData` Map、自有 WS 处理（`handleWsMessage`）、自有轮询（`startPolling`/`stopPolling`）、自有 `onUnmounted` 清理。改为 `computed(() => realtimeStore.dataMap)` 读取，`loading`/`wsConnected` 为 store computed。条件 fetch（`if store.totalPoints === 0`）仅在 store 未初始化时触发。
   - **验证**: 4 个 composable 文件中搜索不到 `setInterval`、`clearInterval`、`onUnmounted`、`realtimeWs`。
5. **AC-5: 环境/安防 Overview 页面迁移** — `environment/overview.vue`、`security/overview.vue` 移除直接 `getAllRealtimeData()` 调用和自有 `setInterval` 轮询。改为从 `realtimeStore.realtimeData` computed 读取，条件 fetch 同 AC-4。
   - **验证**: 两个文件中搜索不到 `getAllRealtimeData`、`setInterval`、`onUnmounted`。
6. **AC-6: BigscreenData 读取 Store** — `useBigscreenData.ts` 的 `fetchEnvironmentData()` 和 `fetchDeviceData()` 从 `realtimeStore.realtimeData` 读取，仅在 `realtimeStore.totalPoints === 0` 时触发 `reload()`。
   - **验证**: 文件中搜索不到 `getAllRealtimeData` 的直接 import。
7. **AC-7: MainLayout 激活 useRealtime** — 在 `MainLayout.vue` 调用 `useRealtime()`，确保全局 WS 订阅和轮询在应用启动（登录后）即生效，直到用户注销（组件 unmount）时清理。
   - **验证**: MainLayout.vue 的 `<script setup>` 中包含 `useRealtime()` 调用。
8. **AC-8: 批量更新性能优化** — `updatePoints()` 使用 `new Map(dataMap.value)` 复制后批量写入再一次性替换引用，减少 N 次响应式触发为 1 次。
   - **验证**: updatePoints 方法体中包含 `new Map(dataMap.value)` 和 `dataMap.value = newMap`。
9. **AC-9: 27.1 AC-6 交叉验证** — 27.1 为 `realtimeStore.reload()` 创建的占位方法已被填充为 `Promise.all([fetchAllData(), fetchSummary()])`。DemoDataLoader 的 `refreshData()` 调用链 → `realtimeStore.reload()` 现在能正确刷新数据。
   - **验证**: `stores/realtime.ts` 的 `reload()` 非空实现；`dashboard/index.vue` 的 `refreshData()` 中调用 `realtimeStore.reload()`。

## Tasks / Subtasks (任务分解)

- [x] Task 1: RealtimeStore 重写为 SSOT (AC: #1, #8, #9)
  - [x] 1.1 在 `frontend/src/stores/realtime.ts` 保留 `dataMap: ref<Map<number, RealtimeData>>(new Map())` 作为唯一数据容器
  - [x] 1.2 新增 `fetchAllData(pointIds?)` async action：带 `if (loading.value) return` 防重入锁，调用 `getAllRealtimeData()` API 成功后用 `new Map` 一次性替换（API 失败时保留旧数据）
  - [x] 1.3 新增 `fetchSummary()` 调用 `getRealtimeSummary()` API
  - [x] 1.4 填充 `reload()` 为 `Promise.all([fetchAllData(), fetchSummary()])`（兑现 27.1 AC-6 占位）
  - [x] 1.5 新增 `updatePoint(data)` — 单条 WS 推送写入
  - [x] 1.6 新增 `updatePoints(data[])` — 批量 WS 推送预留接口（当前 WS handler 使用 `updatePoint` 单条写入，`updatePoints` 为 Story 27.5 WebSocketManager 批量推送预留），使用 `new Map` 复制+替换模式
  - [x] 1.7 新增 `setAllData(data[])`、`setSummary(data)` — 供 dashboard 缓存恢复使用
  - [x] 1.8 新增 `simpleSummary` computed — 优先使用 summary API 数据，降级为 dataMap 计算
  - [x] 1.9 re-export `RealtimeData` / `RealtimeSummary` 类型

- [x] Task 2: useRealtime composable 重写 (AC: #2)
  - [x] 2.1 使用 `storeToRefs(store)` 获取响应式引用，移除所有自有 `ref`
  - [x] 2.2 WS 消息 handler 改为调用 `store.updatePoint()`
  - [x] 2.3 轮询仅在 `!isConnected.value` 时触发 `store.fetchAllData()`
  - [x] 2.4 `watch(isConnected)` 同步 `store.setWsConnected()`，WS 连接时停轮询/断开时启轮询
  - [x] 2.5 `onMounted`: autoFetch → fetchRealtimeData + fetchSummary；autoSubscribe → subscribeRealtime；startPolling
  - [x] 2.6 `onUnmounted`: stopPolling + off WS handler + disconnect

- [x] Task 3: Dashboard 迁移 (AC: #3)
  - [x] 3.1 `summary` 改为 `computed(() => realtimeStore.simpleSummary)`
  - [x] 3.2 `realtimeData` 改为 `computed(() => realtimeStore.realtimeData.slice(0, MAX_REALTIME_ROWS))`
  - [x] 3.3 `refreshData()` 中调用 `realtimeStore.reload()` 替代直接 API
  - [x] 3.4 `saveDashboardCache()` 从 `realtimeStore.simpleSummary` / `realtimeStore.realtimeData` 读取
  - [x] 3.5 `applyCachedDashboardData()` 通过 `realtimeStore.setSummary()` / `realtimeStore.setAllData()` 写入 Store
  - [x] 3.6 移除 `getAllRealtimeData` / `getRealtimeSummary` 直接 import

- [x] Task 4: 环境/安防 Composables 迁移 (AC: #4)
  - [x] 4.1 `useTemperatureData.ts`: `allData` → `computed(() => realtimeStore.dataMap)`，移除自有 WS/轮询/onUnmounted
  - [x] 4.2 `useWaterLeakData.ts`: 同 4.1 模式
  - [x] 4.3 `useSmokeInfraredData.ts`: 同 4.1 模式 + 修复 `wsConnected.value = false` 对 computed 的非法写入（根因：迁移前 wsConnected 是 `ref(false)` 可写，迁移后变为 `computed(() => store.wsConnected)` 只读，但 onMounted 中遗留的 `wsConnected.value = false` 赋值未同步清理。其他 3 个 composable 无此问题：useTemperatureData/useWaterLeakData 的 onMounted 中没有写 wsConnected，useAccessControlData 的 onMounted 重写时已移除相关代码）
  - [x] 4.4 `useAccessControlData.ts`: 同 4.1 模式，保留门禁特有的 fetchTodayEventCount/fetchDeviceEvents/fetchFirePolicies

- [x] Task 5: Overview 页面迁移 (AC: #5)
  - [x] 5.1 `environment/overview.vue`: 移除 `ref<RealtimeData[]>` + `getAllRealtimeData()` + `setInterval`，改为从 store computed 读取
  - [x] 5.2 `security/overview.vue`: 同 5.1 模式

- [x] Task 6: BigscreenData 迁移 (AC: #6)
  - [x] 6.1 `fetchEnvironmentData()` 读取 `realtimeStore.realtimeData`，仅 store 为空时触发 `realtimeStore.reload()`
  - [x] 6.2 `fetchDeviceData()` 读取 `realtimeStore.realtimeData`，仅 store 为空时触发 `realtimeStore.fetchAllData()`

- [x] Task 7: MainLayout 激活全局订阅 (AC: #7)
  - [x] 7.1 在 `MainLayout.vue` 的 `<script setup>` 中 import 并调用 `useRealtime()`

- [x] Task 8: 构建与验证 (AC: #1-#9)
  - [x] 8.1 `npm run build` — 通过 (0 errors)
  - [x] 8.2 `vitest run stores/realtime` — 13/13 通过
  - [x] 8.3 `vitest run composables/` — 136/136 通过
  - [x] 8.4 后端 pytest — 315 通过

## Dev Notes (开发指南)

### 迁移前状态

**以下文件在迁移前各自维护独立的数据副本:**

| 文件 | 迁移前的自有状态 | 迁移后 |
|------|-----------------|--------|
| `stores/realtime.ts` | 基础 store（无 fetchAllData） | SSOT，新增全量 API |
| `composables/useRealtime.ts` | 自有 `ref<Map>` + WS + 轮询 | 委托 store，仅管 WS/轮询生命周期 |
| `views/dashboard/index.vue` | 自有 `summary` ref + 自有 `realtimeData` ref | computed 从 store 派生 |
| `composables/useTemperatureData.ts` | 自有 `allData` Map + WS handler + 10s 轮询 | `computed(() => store.dataMap)` |
| `composables/useWaterLeakData.ts` | 同上 | 同上 |
| `composables/useSmokeInfraredData.ts` | 同上 + `wsConnected.value=false` bug | 同上 + 修复 bug |
| `composables/useAccessControlData.ts` | 同上 + `pollingTimer` + `onUnmounted` | 同上，保留门禁特有逻辑 |
| `views/environment/overview.vue` | 自有 `allData` ref + `getAllRealtimeData()` + 10s 轮询 | store computed |
| `views/security/overview.vue` | 同上 | 同上 |
| `composables/bigscreen/useBigscreenData.ts` | 直接调用 `getAllRealtimeData()` | 读取 store |

### 数据加载双路径设计

存在两条路径触发数据加载，这是有意的设计：

1. **全局路径**: MainLayout → `useRealtime()` → onMounted → `store.fetchAllData()` + WS 订阅 + 轮询回退
2. **按需路径**: 各 composable/页面 → `if (store.totalPoints === 0) store.fetchAllData()`

**优先级关系**: 全局路径在登录后立即生效。按需路径仅在 store 为空时（如直接 URL 访问、热更新后 store 重置）作为安全网触发。由于 `fetchAllData` 有防重入锁，两条路径不会产生重复请求。

**防重入锁的已知妥协**: `if (loading.value) return` 意味着并发调用被静默丢弃。如果用户在轮询正在进行时点击"刷新"，该次刷新请求会被忽略。这是可接受的，因为轮询会在几秒内完成并更新数据。

**轮询的实际行为**: `useRealtime` 在 `onMounted` 中无条件 `startPolling()`。timer 始终运行（每 5s 检查一次），但 interval handler 内检查 `!isConnected.value`，WS 连接正常时跳过实际 fetch。当 `watch(isConnected)` 检测到 WS 连接成功时调用 `stopPolling()` 彻底清除 timer。由于 WS 连接是异步的，实际时序为：`startPolling()` → WS 连接中 → 轮询先执行一两次 → WS 连接成功 → `stopPolling()` → 此后仅 WS 增量更新。WS 断开时 watch 重新 `startPolling()`。

**Dashboard 自有 15s 刷新的叠加**: Dashboard 有 `DASHBOARD_REFRESH_INTERVAL_MS = 15000` 的自有定时器调用 `refreshData()` → `realtimeStore.reload()`。这与 useRealtime 的 5s 轮询存在重叠，但由于防重入锁，不会产生重复请求。Dashboard 的 15s 刷新同时还刷新能源数据和 dashboard API 等，这些超出了 RealtimeStore 的职责范围。

**缓存恢复防覆盖**: `applyCachedDashboardData()` 仅在 `realtimeStore.totalPoints === 0` 时将 sessionStorage 缓存写入 store。如果 MainLayout 的 `useRealtime()` 已先一步加载了数据（store 非空），缓存恢复会被跳过，避免过期数据覆盖新鲜数据。

### fetchAllData 的错误处理策略

`fetchAllData` 使用"先 await 再替换"模式：API 成功后构建新 `Map`，一次性替换 `dataMap.value` 引用。
- **API 失败时**: dataMap 保留旧数据不清空，页面继续显示上一次成功的数据，避免空白闪烁
- **API 成功时**: 使用 `new Map` + 单次赋值替换，旧的已删除点位自然被移除
- **降级行为**: API 失败后 `loading` 重置为 false，下一轮轮询（5s）会重试

### 增量更新 vs 全量替换的一致性窗口

- `updatePoint()` (WS) 是增量写入，不删除旧点位
- `fetchAllData()` (API) 是全量替换（clear + fill），会移除已删除的点位
- 如果后端删除了某个点位，WS 不推送删除消息，该点位会在 dataMap 中残留，直到下一次 `fetchAllData()` 才会被清理
- 轮询间隔 5s（WS 连接正常时不轮询），所以最长一致性窗口约为 5s

### 与其他 Story 的关系

| Story | 关系 |
|-------|------|
| 27.1 | 27.1 AC-6 为 `realtimeStore.reload()` 创建占位，本 Story 填充实现 |
| 27.3 | 能源数据链路统一，模式相同，需为 `energyStore.reload()` 填充实现 |
| 27.5 | WebSocket 单连接管理，将接管 useRealtime 中的 WS 连接管理 |
| 28.1 | 数据源追踪，RealtimeData 类型可能新增 `source` 字段，当前代码透传不受影响 |

### 验证结果

- 前端构建: 通过 (0 errors)
- Store 单测: 13/13 通过（含 updatePoint、updatePoints、setAllData、setSummary、clearData 等）
- Composable 单测: 136/136 通过
- 后端测试: 315 通过 (1 个预存在的无关失败 test_delete_device)
