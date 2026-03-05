# Story 27.2: 实时数据链路统一

Status: done

## Story

As a 用户,
I want 所有页面的实时点位数据来自同一个数据源 (RealtimeStore),
So that 仪表盘、环境监控、安防、大屏等页面的实时数据始终一致，不会出现数据割裂。

## Acceptance Criteria (验收标准)

1. **AC-1: RealtimeStore 成为唯一事实来源** — `RealtimeStore` 新增 `fetchAllData()`（带防重入锁）、`fetchSummary()`、`reload()`、`updatePoint()`、`updatePoints()`、`setAllData()`、`setSummary()` 等方法。`dataMap: Map<number, RealtimeData>` 为全局唯一数据容器。新增 `simpleSummary` computed 供 dashboard 使用。
2. **AC-2: useRealtime composable 委托给 Store** — `useRealtime.ts` 使用 `storeToRefs(store)` 获取响应式状态，WS 消息通过 `store.updatePoint()` 写入，轮询在 WS 断开时回退到 `store.fetchAllData()`。
3. **AC-3: Dashboard 读取 Store** — `dashboard/index.vue` 的 `summary` 改为 `computed(() => realtimeStore.simpleSummary)`，`realtimeData` 改为 `computed(() => realtimeStore.realtimeData.slice(0, MAX_REALTIME_ROWS))`。`refreshData()` 调用 `realtimeStore.reload()`。sessionStorage 缓存写入/读取 Store。
4. **AC-4: 环境/安防 Composables 迁移** — `useTemperatureData`、`useWaterLeakData`、`useSmokeInfraredData`、`useAccessControlData` 全部移除自有 `allData` Map、自有 WS 处理、自有轮询，改为从 `realtimeStore.dataMap` computed 读取。
5. **AC-5: 环境/安防 Overview 页面迁移** — `environment/overview.vue`、`security/overview.vue` 移除直接 `getAllRealtimeData()` 调用和自有轮询，改为从 `realtimeStore.realtimeData` computed 读取。
6. **AC-6: BigscreenData 读取 Store** — `useBigscreenData.ts` 的 `fetchEnvironmentData()` 和 `fetchDeviceData()` 从 `realtimeStore.realtimeData` 读取。
7. **AC-7: MainLayout 激活 useRealtime** — 在 `MainLayout.vue` 调用 `useRealtime()`，确保全局 WS 订阅和轮询在应用启动时即生效。
8. **AC-8: 批量更新性能优化** — `updatePoints()` 使用单次 Map 替换而非 N 次响应式 set，减少渲染触发。

## Implementation Summary

### 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `frontend/src/stores/realtime.ts` | 重写 | SSOT store，新增全量 API |
| `frontend/src/composables/useRealtime.ts` | 重写 | 委托给 store，管理 WS/轮询 |
| `frontend/src/views/dashboard/index.vue` | 重构 | 读取 store computed |
| `frontend/src/composables/useTemperatureData.ts` | 迁移 | 移除自有 Map/WS/轮询 |
| `frontend/src/composables/useWaterLeakData.ts` | 迁移 | 移除自有 Map/WS/轮询 |
| `frontend/src/composables/useSmokeInfraredData.ts` | 迁移 | 移除自有 Map/WS/轮询，修复 computed 写入 bug |
| `frontend/src/composables/useAccessControlData.ts` | 迁移 | 移除自有 Map/WS/轮询 |
| `frontend/src/composables/bigscreen/useBigscreenData.ts` | 迁移 | 读取 store |
| `frontend/src/views/environment/overview.vue` | 迁移 | 移除直接 API/轮询 |
| `frontend/src/views/security/overview.vue` | 迁移 | 移除直接 API/轮询 |
| `frontend/src/layouts/MainLayout.vue` | 新增 | 调用 useRealtime() 激活全局订阅 |

### 验证结果

- 前端构建: 通过 (0 errors)
- Store 单测: 13/13 通过
- Composable 单测: 136/136 通过
- 后端测试: 315 通过 (1 个预存在的无关失败)
