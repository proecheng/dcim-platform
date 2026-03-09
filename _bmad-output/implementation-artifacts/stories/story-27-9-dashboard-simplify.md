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

对抗性审查发现 P1-6 问题：Dashboard 的 `refreshData()` 函数同时调用 4 个不同的 API，并且有复杂的回退逻辑。

**当前问题：**
- 数据流向不清晰，难以追踪数据来源
- 容易出现竞态条件（多个 API 同时返回）
- 维护困难，回退逻辑复杂

**解决方案（保守方案）：**
- 保留 `getDashboardData()` 调用（用于 domainOverview 动态统计和回退数据）
- 简化 Promise 调用结构，使用 `Promise.allSettled` 并行调用
- 保留回退逻辑（当 RealtimeStore 为空时填充数据）
- 保留 `applyDashboardOverviewStat()` 函数（更新 domainOverview）

**注意:** 完全移除 `getDashboardData()` 需要更多工作（从各 Store 计算 domainOverview 的动态数据），风险较高，不在本 Story 范围内。

## Acceptance Criteria

### AC1: 简化 refreshData 函数结构

- Given Dashboard 页面加载或手动刷新
- When 调用 `refreshData()` 函数
- Then 使用 `Promise.allSettled` 并行调用所有数据源：
  - `getDashboardData()` - 获取 dashboard 概览数据
  - `realtimeStore.reload()` - 更新实时数据（仅 force 模式）
  - `alarmStore.fetchActiveAlarms()` - 更新告警数据
  - `energyStore.reload()` - 更新能源数据
- And 保留 `applyDashboardOverviewStat()` 函数（更新 domainOverview）
- And 保留回退逻辑（当 RealtimeStore 为空时填充数据）
- And 简化 Promise 调用结构，提高可读性

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
      // ... 回退逻辑
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
    // 并行调用所有数据源
    const [dashboardRes] = await Promise.allSettled([
      getDashboardData(),
      forceRefresh ? realtimeStore.reload() : Promise.resolve(),
      alarmStore.fetchActiveAlarms(),
      energyStore.reload()
    ])

    // 应用 dashboard 数据
    if (dashboardRes.status === 'fulfilled') {
      const dashData = unwrapApiData<DashboardRaw>(dashboardRes.value)
      applyDashboardOverviewStat(dashData)

      // 回退逻辑：如果 store 为空，用 dashboard 数据填充
      if (realtimeStore.totalPoints === 0 && Array.isArray(dashData?.realtime)) {
        realtimeStore.setAllData(dashData.realtime)
      }
      if (!realtimeStore.summary && dashData?.overview?.total_points) {
        realtimeStore.setSummary({
          total_points: dashData.overview.total_points || 0,
          online_points: dashData.overview.online_points || 0,
          alarm_points: dashData.overview.alarm_count || 0,
          offline_points: Math.max(0, (dashData.overview.total_points || 0) - (dashData.overview.online_points || 0)),
          by_type: {},
          by_area: {},
        })
      }
    }
  } catch (e) {
    console.error('刷新数据失败', e)
  } finally {
    isRefreshing.value = false
  }
}
```

**关键改进:**
1. 将 `energyStore.reload()` 移到 `Promise.allSettled` 中，真正并行执行
2. 保留 `getDashboardData()` 和回退逻辑（容错机制）
3. 保留 `applyDashboardOverviewStat()`（domainOverview 动态更新）
4. 代码结构更清晰，易于理解

### AC2: 保留 domainOverview 动态更新逻辑

- Given Dashboard 页面显示 6 大域概览
- When 数据刷新
- Then domainOverview 通过 `applyDashboardOverviewStat()` 更新动态数据
- And 保留 `applyDashboardOverviewStat()` 函数
- And 保留从 `getDashboardData()` 获取概览统计数据

**修改文件:** `frontend/src/views/dashboard/index.vue`

**说明:**
- domainOverview 的动态数据（功率、温度、告警数等）来自 `getDashboardData()` API
- 完全从 Store 计算这些数据需要更多工作，不在本 Story 范围内
- 保留现有逻辑，确保功能正常

### AC3: 移除不必要的导入（如果有）

- Given Dashboard 代码已简化
- When 检查导入语句
- Then 保留所有当前使用的导入
- And 不移除 `getDashboardData` 和 `type RealtimeData` 导入

**修改文件:** `frontend/src/views/dashboard/index.vue`

**说明:** 由于保留了 `getDashboardData()`，所有导入都需要保留。

### AC4: 保留辅助函数

- Given refreshData 已简化
- When 检查辅助函数
- Then 保留以下函数：
  - `unwrapApiData<T>(payload: unknown): T` - 用于解析 API 响应
  - `applyDashboardOverviewStat(dashRes: DashboardRaw)` - 用于更新 domainOverview
- And 保留 `type DashboardRaw = Awaited<ReturnType<typeof getDashboardData>>`

**修改文件:** `frontend/src/views/dashboard/index.vue`

**说明:** 这些函数仍然需要，因为保留了 `getDashboardData()` 调用。

## Technical Implementation

### 关键设计决策

**保守方案 - 保留 getDashboardData 和回退逻辑:**
- 保留 `getDashboardData()` 调用（用于 domainOverview 和回退数据）
- 保留 `applyDashboardOverviewStat()` 函数
- 保留回退逻辑（当 RealtimeStore 为空时填充数据）
- 只简化 Promise 调用结构，提高可读性

**为什么不完全移除 getDashboardData:**
1. domainOverview 的动态数据（功率、空调台数、温度等）来自 dashboard API
2. 回退逻辑是重要的容错机制，防止 Store 为空时页面空白
3. 完全从 Store 计算需要更多工作，风险较高

**改进点:**
1. 将 `energyStore.reload()` 移到 `Promise.allSettled` 中，真正并行执行
2. 代码结构更清晰，易于理解
3. 保留所有容错机制

### 修改清单

1. **frontend/src/views/dashboard/index.vue**
   - 修改 `refreshData()` 函数（lines 339-383）
   - 将 `energyStore.reload()` 移到 `Promise.allSettled` 中
   - 调整 Promise 解构顺序，将 `dashboardRes` 放在第一位
   - 保留所有现有函数和逻辑

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
Dashboard → getDashboardData() → 更新 domainOverview（功率、温度、告警数等）
         → realtimeStore.reload() → RealtimeStore 状态更新（仅 force 模式）
         → alarmStore.fetchActiveAlarms() → AlarmStore 状态更新
         → energyStore.reload() → EnergyStore 状态更新
         → 回退逻辑：如果 RealtimeStore 为空，用 dashboard 数据填充
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
- 修改后 Dashboard 的实时数据、告警数据、能源数据来自 Store，符合 SSOT 原则
- domainOverview 的动态统计数据仍从 `getDashboardData()` API 获取（保守方案）
- 未来可以考虑创建 computed 属性从 Store 计算 domainOverview 数据（激进方案）

## Related Issues

- Epic 27: 前端数据链路统一
- Story 27.7: 数据链路 P0 问题修复
- 对抗性审查报告: P1-6
