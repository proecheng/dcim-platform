# Story 27.9 第一轮对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review Round 1)
**审查方法:** 对比 Story 假设与实际代码实现

---

## 审查结论

⚠️ **Story 存在 3 个严重问题，必须修改后才能实施**

---

## 发现的问题

### P0-1: Story 忽略了 getDashboardData 的回退逻辑作用

**问题描述:**
- Story 认为 `getDashboardData()` 和回退逻辑是"复杂且不必要的"
- 实际代码中，`getDashboardData()` 有两个重要作用：
  1. 更新 domainOverview 的动态统计（lines 357-359）
  2. 作为 RealtimeStore 的回退数据源（lines 361-376）

**证据:**
```typescript
// lines 361-376
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
```

**影响:**
- 如果移除 `getDashboardData()`，当 RealtimeStore 为空时，Dashboard 会显示空白
- 这是一个重要的容错机制

**修复方案:**
- AC1 需要保留回退逻辑，或者确保 RealtimeStore 在 Dashboard 加载前已有数据
- 或者将回退逻辑改为：如果 RealtimeStore 为空，先调用 `realtimeStore.reload()`

---

### P1-2: domainOverview 的动态数据来源不明确

**问题描述:**
- Story AC2 说"如果需要显示动态数据，直接从 Store 读取"
- 但没有说明如何从 Store 读取这些数据：
  - `ov.power` - 总功率（来自哪个 Store？）
  - `ov.ac_running` - 空调运行台数（来自哪个 Store？）
  - `ov.temperature` - 平均温度（来自哪个 Store？）
  - `ov.alarm_count` - 告警数（AlarmStore 有）
  - `ds.device_status` - 设备状态统计（来自哪个 Store？）

**证据:**
```typescript
// lines 319-336
function applyDashboardOverviewStat(dashRes: DashboardRaw) {
  const ov = dashRes?.overview
  if (!ov) return

  const alarmCount = ov.alarm_count || 0
  domainOverview.value[0].stat = ov.power != null ? `${ov.power}kW` : '运行中'
  domainOverview.value[1].stat = `${ov.ac_running || 0}台运行`
  domainOverview.value[2].stat = ov.temperature != null ? `${ov.temperature}°C` : '运行中'
  domainOverview.value[3].stat = alarmCount > 0 ? `${alarmCount}条告警` : '正常'

  const ds = dashRes.device_status || {}
  const totalDevices = Object.values(ds).reduce((sum: number, value) => sum + Number(value || 0), 0)
  domainOverview.value[4].stat = totalDevices > 0 ? `${totalDevices}台设备` : '运行中'

  const pue = energyStore.currentPUE
  domainOverview.value[5].stat = pue > 0 ? `PUE ${pue.toFixed(2)}` : '运行中'
}
```

**影响:**
- 如果移除 `applyDashboardOverviewStat()`，domainOverview 将永远显示 '运行中'
- 用户看不到动态统计数据

**修复方案:**
- 选项 A: 保留 `getDashboardData()` 和 `applyDashboardOverviewStat()`
- 选项 B: 创建 computed 属性从各 Store 计算这些统计数据
- 选项 C: domainOverview 保持静态，不显示动态数据（用户体验下降）

**推荐:** 选项 B，但需要明确数据来源

---

### P2-3: Story 没有考虑 MainLayout 的全局轮询

**问题描述:**
- 代码注释说"非 force 模式下跳过 realtimeStore.reload()，因为 MainLayout 的全局轮询已持续更新 store"（line 346）
- Story 的修改后代码没有保留这个优化

**证据:**
```typescript
// 当前代码 (line 347)
const realtimeReload = forceRefresh ? realtimeStore.reload() : Promise.resolve()

// Story 修改后
await Promise.all([
  forceRefresh ? realtimeStore.reload() : Promise.resolve(),  // 保留了
  alarmStore.fetchActiveAlarms(),
  energyStore.reload()
])
```

**影响:**
- 这个问题不严重，Story 的修改后代码实际上保留了这个优化
- 但 Story 没有说明为什么保留这个逻辑

**修复方案:**
- 在 Story 中添加说明：保留 `forceRefresh` 判断，避免重复调用 `realtimeStore.reload()`

---

## 修改建议

### 方案 A: 保守修改（推荐）

**保留 getDashboardData 和回退逻辑，只简化结构：**

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

**优点:**
- 保留了容错机制
- domainOverview 仍能显示动态数据
- 风险最小

**缺点:**
- 仍然调用 `getDashboardData()` API
- 没有完全实现 Story 的目标

---

### 方案 B: 激进修改（需要更多工作）

**完全移除 getDashboardData，从 Store 计算所有数据：**

1. 创建 computed 属性计算 domainOverview 的动态数据：
   ```typescript
   const domainOverviewStats = computed(() => ({
     power: energyStore.totalPower,
     acRunning: realtimeStore.realtimeData.filter(d => d.device_type === 'AC' && d.status === 'normal').length,
     temperature: realtimeStore.environment?.temperature?.avg || null,
     alarmCount: alarmStore.alarmCount.total,
     totalDevices: realtimeStore.totalPoints,
     pue: energyStore.currentPUE
   }))
   ```

2. 在模板中使用 computed 属性更新 domainOverview

3. 移除回退逻辑，确保 RealtimeStore 在 Dashboard 前加载

**优点:**
- 完全符合 SSOT 原则
- 数据流向清晰

**缺点:**
- 需要更多修改
- 需要确认数据来源（如 `ac_running` 如何计算）
- 风险较高

---

## 审查总结

Story 27.9 的目标是正确的（简化 refreshData），但实施方案过于激进，忽略了：
1. getDashboardData 的回退逻辑作用
2. domainOverview 的动态数据来源
3. 现有的性能优化（MainLayout 全局轮询）

**建议:** 采用方案 A（保守修改），或者修改 Story 采用方案 B（但需要更详细的实施计划）。

---

**审查完成时间:** 2026-03-10
**下一步:** 修改 Story 后进行第二轮审查
