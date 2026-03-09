---
epic: 27
story_id: 27.9
title: 数据链路 P1 问题修复 - Dashboard refreshData 简化
status: ready-for-dev
priority: P1
created: 2026-03-10
assigned_to: dev
estimated_effort: 4h
sprint: next
---

# Story 27.9: 简化 Dashboard refreshData 逻辑

## User Story

As a 开发者,
I want Dashboard 的 refreshData 逻辑简化为只调用 Store 的 reload 方法,
So that 数据流向清晰，避免复杂的回退逻辑和潜在的竞态条件。

## Context

对抗性审查发现 P1-6 问题：Dashboard 的 `refreshData()` 函数同时调用 4 个不同的 API（`getDashboardData`、`getActiveAlarms`、`getEnergyDashboard`、`realtimeStore.reload`），并且有复杂的回退逻辑。

**当前问题：**
- 数据流向不清晰，难以追踪数据来源
- 容易出现竞态条件（多个 API 同时返回）
- 维护困难，回退逻辑复杂

**解决方案：**
- Dashboard 只调用各 Store 的 `reload()` 方法
- 由 Store 负责数据获取和状态管理
- 移除 `getDashboardData()` 直接 API 调用
- 移除复杂的回退逻辑

## Acceptance Criteria

### AC1: 简化 refreshData 函数

- Given Dashboard 页面加载或手动刷新
- When 调用 `refreshData()` 函数
- Then 只调用以下 Store 方法：
  - `realtimeStore.reload()`
  - `alarmStore.fetchActiveAlarms()`
  - `energyStore.reload()`
- And 移除 `getDashboardData()` API 调用
- And 移除 `applyDashboardOverviewStat()` 函数
- And 移除 `unwrapApiData()` 函数

**修改文件:** `frontend/src/views/dashboard/index.vue`

**修改前（约 line 339-383）:**
```typescript
async function refreshData(options: { force?: boolean } = {}) {
  const forceRefresh = options.force === true
  if (isRefreshing.value) return
  if (!forceRefresh && !isPageVisible) return

  isRefreshing.value = true
  try {
    const realtimeReload = forceRefresh ? realtimeStore.reload() : Promise.resolve()
    const [_realtimeRes, _alarmsRes, dashboardRes] = await Promise.allSettled([
      realtimeReload,
      alarmStore.fetchActiveAlarms(),
      getDashboardData()
    ])

    await energyStore.reload()

    if (dashboardRes.status === 'fulfilled') {
      const dashData = unwrapApiData<DashboardRaw>(dashboardRes.value)
      applyDashboardOverviewStat(dashData)
      // ... 复杂的回退逻辑
    }
  } catch (e) {
    console.error('刷新数据失败', e)
  } finally {
    isRefreshing.value = false
  }
}
```

**修改后:**
```typescript
async function refreshData(options: { force?: boolean } = {}) {
  const forceRefresh = options.force === true
  if (isRefreshing.value) return
  if (!forceRefresh && !isPageVisible) return

  isRefreshing.value = true
  try {
    // 只调用 Store 的 reload 方法
    await Promise.all([
      forceRefresh ? realtimeStore.reload() : Promise.resolve(),
      alarmStore.fetchActiveAlarms(),
      energyStore.reload()
    ])
  } catch (e) {
    console.error('刷新数据失败', e)
  } finally {
    isRefreshing.value = false
  }
}
```

### AC2: 移除 domainOverview 动态更新逻辑

- Given Dashboard 页面显示 6 大域概览
- When 数据刷新
- Then domainOverview 保持静态配置，不再动态更新 `stat` 字段
- And 移除 `applyDashboardOverviewStat()` 函数
- And 如果需要显示动态数据，直接从 Store 读取

**修改文件:** `frontend/src/views/dashboard/index.vue`

**说明:** 6 大域概览卡片的动态数据（如功率、温度、告警数）应该直接从对应的 Store 读取，而非通过 `getDashboardData()` API 获取后再更新。

### AC3: 移除 getDashboardData 导入

- Given Dashboard 不再直接调用 API
- When 编译代码
- Then 移除 `import { getDashboardData, type RealtimeData } from '@/api/modules/realtime'`
- And 保留 `type RealtimeData` 导入（如果仍需要）

**修改文件:** `frontend/src/views/dashboard/index.vue`

### AC4: 移除辅助函数

- Given refreshData 已简化
- When 清理代码
- Then 移除以下函数：
  - `unwrapApiData<T>(payload: unknown): T`
  - `applyDashboardOverviewStat(dashRes: DashboardRaw)`
- And 移除 `type DashboardRaw = Awaited<ReturnType<typeof getDashboardData>>`

**修改文件:** `frontend/src/views/dashboard/index.vue`

## Technical Implementation

### 修改清单

1. **frontend/src/views/dashboard/index.vue**
   - 简化 `refreshData()` 函数，只调用 Store 的 reload 方法
   - 移除 `getDashboardData()` 导入和调用
   - 移除 `applyDashboardOverviewStat()` 函数
   - 移除 `unwrapApiData()` 函数
   - 移除 `type DashboardRaw` 类型定义
   - 如果 domainOverview 需要动态数据，改为从 Store 的 computed 属性读取

### 数据流向

**修改前:**
```
Dashboard → getDashboardData() API → 解析数据 → 更新 domainOverview
         → realtimeStore.reload()
         → alarmStore.fetchActiveAlarms()
         → energyStore.reload()
```

**修改后:**
```
Dashboard → realtimeStore.reload() → RealtimeStore 状态更新
         → alarmStore.fetchActiveAlarms() → AlarmStore 状态更新
         → energyStore.reload() → EnergyStore 状态更新
         → 模板直接从 Store 读取数据
```

### 测试验证

**手动测试步骤:**

1. **验证 Dashboard 数据加载:**
   - 打开 Dashboard 页面
   - 检查统计卡片、能源卡片、实时数据表格是否正常显示
   - 检查告警列表是否正常显示

2. **验证手动刷新:**
   - 点击刷新按钮
   - 验证所有数据正常更新
   - 检查控制台无错误

3. **验证自动刷新:**
   - 等待 15 秒（自动刷新间隔）
   - 验证数据自动更新
   - 检查控制台无错误

4. **验证页面切换:**
   - 切换到其他页面
   - 切换回 Dashboard
   - 验证数据正常显示

## Definition of Done

- [ ] AC1-AC4 全部通过验证
- [ ] 手动测试步骤全部通过
- [ ] 代码审查通过
- [ ] 无 TypeScript 类型错误
- [ ] 无控制台错误或警告
- [ ] 提交代码并创建 commit

## Notes

- 本 Story 是对 Epic 27 的持续改进，属于代码重构
- 修改后 Dashboard 的数据完全来自 Store，符合 SSOT 原则
- 如果 domainOverview 需要动态数据，建议创建 computed 属性从 Store 读取

## Related Issues

- Epic 27: 前端数据链路统一
- Story 27.7: 数据链路 P0 问题修复
- 对抗性审查报告: P1-6
