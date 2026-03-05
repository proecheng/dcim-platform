# Story 27.3: 能源数据链路统一

Status: in-progress

## Story

As a 用户,
I want 仪表盘、用电监控、大屏等页面的能源数据（PUE、总功率、今日用电等）来自同一个数据源 (EnergyStore),
So that 各页面显示的能源指标始终一致，不会出现数据割裂。

## 背景分析

与 Story 27.2（实时数据链路）不同，能源数据链路已有较好的基础架构：
- `useEnergy` composable 已正确委托 `EnergyStore` 进行状态管理
- Store 已有完整的 setter/getter 方法体系
- 主要问题集中在 3 点：`reload()` 空实现、Dashboard/大屏绕过 Store、Store 方法安全性

**不在范围内的页面**: `energy/statistics.vue`、`energy/analysis.vue`、`energy/config.vue` 等页面使用带参数的查询（日期范围、设备筛选），这些是"按需查询"场景，不适合放入全局 Store。本 Story 只统一"全局概览级"能源数据（PUE、总功率、汇总等）。

## Acceptance Criteria (验收标准)

1. **AC-1: EnergyStore.reload() 填充实现** — `reload()` 直接导入并调用 `getRealtimePower()` + `getPowerSummary()` + `getCurrentPUE()` 三个 API，使用 `Promise.allSettled` 并行加载，对每个成功的结果解包 `ResponseModel`（检查 `res.code === 0 && res.data`）后写入 Store。带防重入锁（`loading` ref）。返回 `Promise<boolean>`：`false` 仅表示防重入跳过，`true` 表示实际执行（即使部分 API 失败仍返回 `true`）。
   - **验证**: `stores/energy.ts` 的 `reload()` 非空实现，包含 `await Promise.allSettled`，有 `if (loading.value) return false` 守卫，包含 `ResponseModel` 解包逻辑。
   - **错误处理**: 3 个并行请求使用 `Promise.allSettled`，每个独立处理。一个失败不影响其他两个写入。

2. **AC-2: Dashboard 能源数据写入 Store** — `dashboard/index.vue` 的 `refreshData()` 中，`getEnergyDashboard()` API 返回的核心指标同步写入 `EnergyStore` 作为**回退**数据源（仅在 Store 对应字段为空时写入，避免覆盖 `reload()` 返回的更精确数据）。Dashboard 的能源卡片组件**保留原有 `energyData` ref** 读取（`EnergyDashboardData` 含 trends/demand/cost 等 dashboard 专用聚合数据，不放入全局 Store）。
   - **验证**: `refreshData()` 的 `energyRes` 处理块中，有条件写入 Store（`if (!energyStore.powerSummary)` 守卫）。
   - **竞态保护**: Dashboard line 419 的 `reload()` (fire-and-forget) 写入权威数据，`energyRes` 块的写入为回退。使用 "write-if-empty" 模式避免覆盖。
   - **注意**: `EnergyDashboardData` 的类型字段与 `RealtimePowerSummary`/`PUEData` 不完全对齐（缺少 `ups_power`、`ups_loss`、`lighting_power`、`update_time` 等），回退写入需填充默认值（0 / `new Date().toISOString()`）。

3. **AC-3: BigscreenData 能源数据写入 Store** — `useBigscreenData.ts` 的 `fetchEnergyData()` 在调用 `getEnergyDashboard()` 获取数据后，将核心指标写入 `EnergyStore`（使用 `setPowerSummary()` + `setPUEData()`），而非触发 `reload()`（避免额外 3 个 API 请求）。
   - **验证**: `useBigscreenData.ts` 的 `fetchEnergyData()` 中包含 `energyStore.setPowerSummary()` 和 `energyStore.setPUEData()` 调用。

4. **AC-4: Store 方法安全性修复** — 以下方法改为安全模式：
   - `setAllPowerData()`: 改为 `new Map` + 单次赋值模式（不用 `.clear()` + fill）
   - `updatePowerDataBatch()`: 改为 `new Map(existing)` + fill + 单次赋值（避免 N 次 `.set()` 触发 N 次响应更新）
   - `clearData()`: `realtimePowerData.value = new Map()` 替换 `.clear()`（其他 ref 的 `= null` / `= []` 赋值本身安全，保留不变）
   - **验证**: `setAllPowerData`、`updatePowerDataBatch`、`clearData` 方法体中不包含 `.clear()` 或多次 `.set()`。

5. **AC-5: useEnergy composable 增加防重入** — `loadRealtimePower()` 增加 `if (loading.value) return` 守卫。注意：`loading` 是 per-composable-instance 的 ref，跨组件实例无共享（这是有意设计，因为不同组件可能传不同 params 参数）。
   - **验证**: `loadRealtimePower` 方法开头有 `if (loading.value) return` 守卫。

6. **AC-6: 27.1 AC-6 兑现验证** — DemoDataLoader → `refreshData()` → `energyStore.reload()` 调用链完整可用。Dashboard line 419 的 `useEnergyStore().reload()` 为 fire-and-forget 调用，不阻塞 `refreshData` 主流程（有意设计，dashboard 有自己的 `getEnergyDashboard()` 数据源）。
   - **验证**: `reload()` 已填充实现，调用链可追溯。

## Tasks / Subtasks (任务分解)

- [ ] Task 1: EnergyStore 增强 (AC: #1, #4)
  - [ ] 1.1 新增 `import { getRealtimePower, getPowerSummary, getCurrentPUE } from '@/api/modules/energy'`
  - [ ] 1.2 新增 `loading: ref(false)` 状态并导出
  - [ ] 1.3 填充 `reload()`: `if (loading.value) return false` 守卫 → `Promise.allSettled` 并行调用 3 个 API → 对每个 fulfilled 结果解包 `ResponseModel`（检查 `res.code === 0 && res.data`）→ 分别调用 `setAllPowerData`/`setPowerSummary`/`setPUEData` → `finally` 释放锁 → 返回 `true`
  - [ ] 1.4 `setAllPowerData()` 改为 `const newMap = new Map(); dataList.forEach(...); realtimePowerData.value = newMap`
  - [ ] 1.5 `updatePowerDataBatch()` 改为 `const newMap = new Map(realtimePowerData.value); dataList.forEach(...); realtimePowerData.value = newMap`
  - [ ] 1.6 `clearData()` 的 `realtimePowerData.value.clear()` 改为 `realtimePowerData.value = new Map()`

- [ ] Task 2: useEnergy composable 防重入 (AC: #5)
  - [ ] 2.1 `loadRealtimePower()` 开头增加 `if (loading.value) return` 守卫

- [ ] Task 3: Dashboard 能源数据写入 Store (AC: #2)
  - [ ] 3.1 确认 `useEnergyStore().reload()` 调用（line 419）在 reload 填充后自动生效
  - [ ] 3.2 在 `refreshData()` 的 `energyRes` 处理块中，条件写入 Store（write-if-empty 模式）：
    ```typescript
    // 回退：仅在 reload() 尚未写入时，用 dashboard 聚合数据填充 Store
    const energyStoreRef = useEnergyStore()
    if (!energyStoreRef.powerSummary && energyPayload?.realtime) {
      energyStoreRef.setPowerSummary({
        total_power: energyPayload.realtime.total_power || 0,
        it_power: energyPayload.realtime.it_power || 0,
        cooling_power: energyPayload.realtime.cooling_power || 0,
        ups_power: 0,  // dashboard 聚合 API 不含此字段
        other_power: energyPayload.realtime.other_power || 0,
        current_pue: energyPayload.efficiency?.pue ?? null,
        today_energy: energyPayload.realtime.today_energy || 0,
        today_cost: energyPayload.cost?.today_cost || 0,
        month_energy: energyPayload.realtime.month_energy || 0,
        month_cost: energyPayload.cost?.month_cost || 0,
      })
    }
    if (!energyStoreRef.pueData && energyPayload?.efficiency?.pue != null) {
      energyStoreRef.setPUEData({
        current_pue: energyPayload.efficiency.pue,
        total_power: energyPayload.realtime?.total_power || 0,
        it_power: energyPayload.realtime?.it_power || 0,
        cooling_power: energyPayload.realtime?.cooling_power || 0,
        ups_loss: 0,
        lighting_power: 0,
        other_power: energyPayload.realtime?.other_power || 0,
        update_time: new Date().toISOString(),
      })
    }
    ```

- [ ] Task 4: BigscreenData 能源数据写入 Store (AC: #3)
  - [ ] 4.1 在 `useBigscreenData.ts` 顶部新增 `import { useEnergyStore } from '@/stores/energy'`
  - [ ] 4.2 在 `fetchEnergyData()` 函数开头新增 `const energyStore = useEnergyStore()`
  - [ ] 4.3 在 `store.updateEnergy(data)` 之后，用 write-if-empty 模式写入 EnergyStore（与 Task 3.2 同模式，字段映射相同）

- [ ] Task 5: 构建与验证 (AC: #1-#6)
  - [ ] 5.1 `npm run build` 无编译错误
  - [ ] 5.2 相关单测通过
  - [ ] 5.3 确认 DemoDataLoader → reload 调用链

## Dev Notes (开发指南)

### 范围限定

能源数据分两类：
1. **全局概览数据** — PUE、总功率、IT 功率、制冷功率、今日用电/电费 → **本 Story 统一到 Store**
2. **按需查询数据** — 能耗趋势（按日期范围）、同环比（按周期）、设备级电力详情 → **保持 API 直接调用**（带参数的精确查询不适合全局缓存）

### Store 与 Composable 的架构边界

**关键约束**: Store 不能依赖 Composable（否则会产生循环依赖：Composable → Store → Composable）。

因此 `EnergyStore.reload()` 必须直接导入并调用 API 函数（`getRealtimePower` 等），不能调用 `useEnergy` composable 的方法。这会导致 `reload()` 与 `useEnergy` 的加载逻辑有少量重复（ResponseModel 解包），这是架构约束的必要代价。

### ResponseModel 解包

所有 API 返回 `ResponseModel<T>` 格式：`{ code: number, message: string, data: T }`。Store 的 `reload()` 需要对每个 API 结果检查 `res.code === 0 && res.data` 才能写入。

### Dashboard 能源数据策略

Dashboard 的能源卡片使用 `EnergyDashboardData`，它是一个**聚合 API**，一次返回 realtime/efficiency/demand/cost/trends/suggestions 等完整数据。这些数据中：
- **核心指标**（total_power, it_power, cooling_power, pue, today_energy, today_cost）→ **回退写入** Store（仅在 Store 为空时）
- **Dashboard 专用数据**（trends, demand, cost breakdown, suggestions count）→ 保留在 dashboard 本地 `energyData` ref

### 类型映射注意事项

`EnergyDashboardData` 与 Store 类型的字段差异：

| Store 类型 | 缺少的必需字段 | 默认值 |
|-----------|--------------|--------|
| `RealtimePowerSummary` | `ups_power` | `0` |
| `PUEData` | `ups_loss`, `lighting_power`, `update_time` | `0`, `0`, `new Date().toISOString()` |

### 竞态处理

Dashboard 的 `refreshData()` 中有两个向 EnergyStore 写数据的路径：
1. **`reload()`** (line 419, fire-and-forget) — 调用权威 API，数据最精确
2. **`energyRes` 处理块** — 从聚合 API 回退写入

为避免路径 2 覆盖路径 1 的精确数据，路径 2 使用 "write-if-empty" 守卫：`if (!energyStore.powerSummary)`。

### 与其他 Story 的关系

| Story | 关系 |
|-------|------|
| 27.1 | 27.1 AC-6 为 `energyStore.reload()` 创建占位，本 Story 填充 |
| 27.2 | 模式参考：防重入锁、new Map 替换、Promise.allSettled 独立错误处理 |
| 27.5 | WebSocket 将来可能接管能源数据推送，当前 useEnergy 的轮询保留 |
