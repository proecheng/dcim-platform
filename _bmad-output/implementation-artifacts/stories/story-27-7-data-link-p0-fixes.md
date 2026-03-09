---
epic: 27
story_id: 27.7
title: 数据链路 P0 问题修复
status: ready-for-dev
priority: P0
created: 2026-03-10
assigned_to: dev
estimated_effort: 8h
sprint: current
---

# Story 27.7: 数据链路 P0 问题修复

## User Story

As a 用户,
I want 所有页面的数据完全来自统一的 Store,
So that 不同页面显示的数据始终保持一致，不会出现数据不同步的问题。

## Context

对抗性审查发现 Epic 27 实施不完整，存在 3 个 P0 级别的严重问题：

1. **P0-1**: 温度监控页面仍直接调用 `getActiveAlarms` API，绕过 AlarmStore
2. **P0-2**: Dashboard 仍维护独立的 `energyData` ref，与 EnergyStore 状态脱节
3. **P0-3**: BigscreenStore 的 `energy` 和 `environment` 仍是独立状态，未改为从对应 Store 派生的 getter

这些问题导致用户在不同页面看到不同的数据，违反了"单一事实来源"原则。

## Acceptance Criteria

### AC1: 温度监控页面告警数据统一

- Given 用户在温度监控页面点击传感器
- When 加载传感器关联告警
- Then 从 `alarmStore.activeAlarms` 中过滤 `point_id` 匹配的告警
- And 移除 `getActiveAlarms({ point_id: sensor.point_id })` 直接 API 调用
- And 告警数据与全局告警状态完全同步

**修改文件:**
- `frontend/src/views/environment/temperature.vue:310`

**修改前:**
```typescript
const alarms = await getActiveAlarms({ point_id: sensor.point_id })
sensorAlarms.value = Array.isArray(alarms) ? alarms : []
```

**修改后:**
```typescript
const alarmStore = useAlarmStore()
sensorAlarms.value = alarmStore.activeAlarms.filter(a => a.point_id === sensor.point_id)
```

### AC2: Dashboard 能源数据完全依赖 EnergyStore

- Given Dashboard 页面加载
- When 显示能源卡片数据
- Then 完全从 `useEnergyStore()` 的 computed 属性读取
- And 移除局部 `energyData` ref
- And 移除 `getEnergyDashboard()` 直接 API 调用
- And 能源数据与能源管理页面完全一致

**修改文件:**
- `frontend/src/views/dashboard/index.vue`

**修改内容:**
1. 移除 `const energyData = ref<EnergyDashboardData | null>(null)`
2. 改用 `const energyStore = useEnergyStore()`
3. 模板中的 `energyData.value?.realtime?.total_power` 改为 `energyStore.totalPower`
4. 模板中的 `energyData.value?.efficiency?.pue` 改为 `energyStore.currentPUE`
5. 移除 `refreshData()` 中的 `getEnergyDashboard()` 调用和回退逻辑
6. 保留 `energyStore.reload()` 调用

### AC3: BigscreenStore 的 energy 改为 getter

- Given BigscreenStore 初始化
- When 大屏页面访问 `bigscreenStore.energy`
- Then 返回从 EnergyStore 派生的数据
- And `energy` 从 `state` 移到 `getters`
- And 移除 `updateEnergyData` action

**修改文件:**
- `frontend/src/stores/bigscreen.ts:44-51`

**修改前 (state):**
```typescript
energy: {
  totalPower: 0,
  itPower: 0,
  coolingPower: 0,
  pue: 1.5,
  todayEnergy: 0,
  todayCost: 0
}
```

**修改后 (getter):**
```typescript
// 在 getters 中添加
energy(): {
  totalPower: number
  itPower: number
  coolingPower: number
  pue: number
  todayEnergy: number
  todayCost: number
} {
  const energyStore = useEnergyStore()
  return {
    totalPower: energyStore.totalPower,
    itPower: energyStore.itPower,
    coolingPower: energyStore.coolingPower,
    pue: energyStore.currentPUE,
    todayEnergy: energyStore.todayEnergy,
    todayCost: energyStore.todayCost
  }
}
```

### AC4: BigscreenStore 的 environment 改为 getter

- Given BigscreenStore 初始化
- When 大屏页面访问 `bigscreenStore.environment`
- Then 返回从 RealtimeStore 派生的温湿度统计
- And `environment` 从 `state` 移到 `getters`
- And 移除 `updateEnvironmentData` action

**修改文件:**
- `frontend/src/stores/bigscreen.ts:38-41`

**修改后 (getter):**
```typescript
// 在 getters 中添加
environment(): {
  temperature: { max: number; avg: number; min: number }
  humidity: { max: number; avg: number; min: number }
} {
  const realtimeStore = useRealtimeStore()
  const thSensors = Array.from(realtimeStore.dataMap.values())
    .filter(d => d.device_type === 'TH' && d.status !== 'offline')

  const tempSensors = thSensors.filter(d => d.unit === '°C' || d.unit === '℃')
  const humiditySensors = thSensors.filter(d => d.unit === '%' || d.unit === '%RH')

  const tempValues = tempSensors.map(s => s.value ?? 0).filter(v => v > 0)
  const humidityValues = humiditySensors.map(s => s.value ?? 0).filter(v => v > 0)

  return {
    temperature: {
      max: tempValues.length ? Math.max(...tempValues) : 0,
      avg: tempValues.length ? tempValues.reduce((a, b) => a + b, 0) / tempValues.length : 0,
      min: tempValues.length ? Math.min(...tempValues) : 0
    },
    humidity: {
      max: humidityValues.length ? Math.max(...humidityValues) : 0,
      avg: humidityValues.length ? humidityValues.reduce((a, b) => a + b, 0) / humidityValues.length : 0,
      min: humidityValues.length ? Math.min(...humidityValues) : 0
    }
  }
}
```

### AC5: 移除 Dashboard 的 sessionStorage 缓存

- Given Dashboard 页面刷新
- When 加载数据
- Then 完全依赖 Store 的状态，不使用 sessionStorage 缓存
- And 移除 `saveDashboardCache()` 和 `loadDashboardCache()` 函数
- And 移除 `dcim_dashboard_cache` 相关代码

**修改文件:**
- `frontend/src/views/dashboard/index.vue`

## Technical Implementation

### 修改清单

1. **frontend/src/views/environment/temperature.vue**
   - 导入 `useAlarmStore`
   - 修改 `handleSensorClick` 函数中的告警加载逻辑

2. **frontend/src/views/dashboard/index.vue**
   - 移除 `energyData` ref
   - 移除 `getEnergyDashboard()` 调用
   - 简化 `refreshData()` 逻辑
   - 移除 sessionStorage 缓存相关代码
   - 模板中所有 `energyData.value` 改为 `energyStore`

3. **frontend/src/stores/bigscreen.ts**
   - 从 `state` 中移除 `energy` 和 `environment`
   - 在 `getters` 中添加 `energy` 和 `environment` getter
   - 移除 `updateEnergyData` 和 `updateEnvironmentData` actions

### 测试验证

**手动测试步骤:**

1. **验证告警数据统一:**
   - 打开温度监控页面
   - 点击任意传感器
   - 检查抽屉中显示的告警
   - 打开告警列表页面，验证相同 point_id 的告警数据一致
   - 通过 WebSocket 推送新告警，验证两个页面同步更新

2. **验证能源数据统一:**
   - 打开 Dashboard 页面，记录 PUE 值和总功率
   - 打开能源管理页面，验证数值完全一致
   - 刷新页面，验证数据不会回退到旧缓存

3. **验证大屏数据统一:**
   - 打开大屏页面
   - 检查左侧面板的能源数据（PUE、功率）
   - 检查环境数据（温湿度统计）
   - 与 Dashboard 和能源页面对比，验证数值一致

**自动化测试（可选）:**

```typescript
// frontend/src/views/environment/__tests__/temperature.test.ts
describe('Temperature View - Alarm Data', () => {
  it('should load alarms from AlarmStore instead of API', async () => {
    const alarmStore = useAlarmStore()
    alarmStore.activeAlarms = [
      { id: 1, point_id: 100, alarm_level: 'critical', alarm_message: 'Test' }
    ]

    const wrapper = mount(TemperatureView)
    await wrapper.vm.handleSensorClick({ point_id: 100 })

    expect(wrapper.vm.sensorAlarms).toHaveLength(1)
    expect(wrapper.vm.sensorAlarms[0].id).toBe(1)
  })
})
```

## Definition of Done

- [ ] AC1-AC5 全部通过验证
- [ ] 手动测试步骤全部通过
- [ ] 代码审查通过
- [ ] 无 TypeScript 类型错误
- [ ] 无 console 错误或警告
- [ ] 提交代码并创建 commit

## Notes

- 本 Story 是对 Epic 27 的修复补充，不是新功能开发
- 修改后应立即进行回归测试，确保不影响现有功能
- 如果发现其他类似问题，应在代码审查时一并指出

## Related Issues

- Epic 27: 前端数据链路统一
- 对抗性审查报告: 2026-03-10
- 参考文档: `docs/data-flow-audit.md`
