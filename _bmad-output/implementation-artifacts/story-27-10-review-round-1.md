# Story 27.10 第一轮对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review Round 1)
**审查方法:** 对比 Story 假设与实际代码实现

---

## 审查结论

⚠️ **Story 存在 2 个问题，需要修改**

---

## 发现的问题

### P1-1: Story 假设的实现方案不适用于 Options API

**问题描述:**
- Story AC1 的修改后代码假设可以在 options API 中使用 `computed`
- 实际代码使用 Pinia options API（`defineStore('bigscreen', { state, getters, actions })`）
- Options API 的 getters 本身就是 computed 属性，但每次访问都会执行函数体

**证据:**
```typescript
// 当前代码 (lines 51-76)
export const useBigscreenStore = defineStore('bigscreen', {
  state: (): BigscreenState => ({ ... }),
  getters: {
    activeAlarms(): BigscreenAlarm[] {
      const alarmStore = useAlarmStore()
      return alarmStore.activeAlarms.map(alarm => ({ ... }))
    }
  },
  actions: { ... }
})
```

**影响:**
- Story 提供的修改后代码无法直接应用
- 需要将 store 从 options API 改为 setup API，或者使用其他方案

**修复方案:**

**方案 A: 改为 setup API（推荐）**
```typescript
export const useBigscreenStore = defineStore('bigscreen', () => {
  // state
  const mode = ref<SceneMode>('command')
  const layout = ref<DataCenterLayout | null>(null)
  // ... 其他 state

  // computed
  const alarmStore = useAlarmStore()
  const activeAlarms = computed(() => {
    return alarmStore.activeAlarms.map(alarm => ({
      id: alarm.id,
      deviceId: alarm.point_code || String(alarm.point_id || ''),
      deviceName: alarm.point_name || '',
      level: alarm.alarm_level as BigscreenAlarm['level'],
      message: alarm.alarm_message || '',
      value: alarm.trigger_value,
      threshold: alarm.threshold_value,
      createdAt: alarm.created_at,
    }))
  })

  // actions
  function setMode(newMode: SceneMode) {
    mode.value = newMode
  }
  // ... 其他 actions

  return {
    mode,
    layout,
    // ... 其他 state
    activeAlarms,
    // ... 其他 getters
    setMode,
    // ... 其他 actions
  }
})
```

**方案 B: 在 options API 中使用缓存变量（不推荐）**
- 在 state 中添加 `_cachedActiveAlarms` 和 `_lastAlarmVersion`
- 在 getter 中检查版本号，如果未变化则返回缓存
- 这种方案复杂且容易出错

**推荐:** 方案 A（改为 setup API）

---

### P2-2: Story 没有说明如何处理其他 getters

**问题描述:**
- BigscreenStore 有多个 getters：
  - `activeAlarms` (line 85) - 需要优化
  - `alarmCount` (line 100) - 已经很简单
  - `criticalAlarmCount` (line 105) - 已经很简单
  - `recentAlarms` (line 135) - 依赖 `activeAlarms`
  - `energy` (line 140) - 已经很简单
  - `environment` (line 160) - 可能也需要优化（复杂计算）
- Story 只提到优化 `activeAlarms`，但没有说明其他 getters 如何处理

**证据:**
```typescript
// lines 160-186
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

**影响:**
- `environment` getter 也有复杂计算（多次 filter、map、reduce）
- 如果改为 setup API，需要明确说明如何处理所有 getters

**修复方案:**
- 在 Story 中添加说明：改为 setup API 后，所有 getters 都会自动变成 computed 属性
- 或者明确说明只优化 `activeAlarms`，其他 getters 保持不变

---

## 修改建议

### 方案 A: 改为 setup API（推荐）

**修改 Story AC1:**

**修改前（约 line 51-76）:**
```typescript
export const useBigscreenStore = defineStore('bigscreen', {
  state: (): BigscreenState => ({ ... }),
  getters: {
    activeAlarms(): BigscreenAlarm[] {
      const alarmStore = useAlarmStore()
      return alarmStore.activeAlarms.map(alarm => ({ ... }))
    }
  },
  actions: { ... }
})
```

**修改后:**
```typescript
export const useBigscreenStore = defineStore('bigscreen', () => {
  // state
  const mode = ref<SceneMode>('command')
  const layout = ref<DataCenterLayout | null>(null)
  const deviceData = ref<Record<string, DeviceRealtimeData>>({})
  const layers = ref<DataLayers>({
    heatmap: true,
    status: true,
    power: true,
    airflow: false
  })
  const selectedDeviceId = ref<string | null>(null)
  const cameraPresets = ref<Record<string, CameraPreset>>({
    overview: { position: [0, 50, 50], target: [0, 0, 0] },
    topDown: { position: [0, 80, 0], target: [0, 0, 0] },
    moduleA: { position: [20, 15, 20], target: [20, 0, 0] }
  })
  const loading = ref(false)
  const panelStates = ref<Record<string, PanelState>>({
    leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
    rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
    deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
    floorSelector: { x: 20, y: 120, collapsed: false, visible: true },
    bottomBar: { x: 0, y: 0, collapsed: false, visible: true }
  })

  // computed (getters)
  const alarmStore = useAlarmStore()
  const energyStore = useEnergyStore()
  const realtimeStore = useRealtimeStore()

  const activeAlarms = computed(() => {
    return alarmStore.activeAlarms.map(alarm => ({
      id: alarm.id,
      deviceId: alarm.point_code || String(alarm.point_id || ''),
      deviceName: alarm.point_name || '',
      level: alarm.alarm_level as BigscreenAlarm['level'],
      message: alarm.alarm_message || '',
      value: alarm.trigger_value,
      threshold: alarm.threshold_value,
      createdAt: alarm.created_at,
    }))
  })

  const alarmCount = computed(() => alarmStore.alarmCount.total)
  const criticalAlarmCount = computed(() => alarmStore.alarmCount.critical)
  const hasSelectedDevice = computed(() => selectedDeviceId.value !== null)
  const recentAlarms = computed(() => activeAlarms.value.slice(0, 10))

  const energy = computed(() => ({
    totalPower: energyStore.totalPower,
    itPower: energyStore.itPower,
    coolingPower: energyStore.coolingPower,
    pue: energyStore.currentPUE,
    todayEnergy: energyStore.todayEnergy,
    todayCost: energyStore.todayCost
  }))

  const environment = computed(() => {
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
  })

  const modeConfig = computed(() => {
    const configs = {
      command: {
        cameraLocked: true,
        refreshInterval: 5000,
        showAllPanels: true
      },
      operation: {
        cameraLocked: false,
        refreshInterval: 3000,
        showAllPanels: true
      },
      showcase: {
        cameraLocked: true,
        refreshInterval: 10000,
        showAllPanels: false
      }
    }
    return configs[mode.value]
  })

  // actions
  function setMode(newMode: SceneMode) {
    mode.value = newMode
  }

  function setLayout(newLayout: DataCenterLayout) {
    layout.value = newLayout
  }

  function updateDeviceData(deviceId: string, data: Partial<DeviceRealtimeData>) {
    deviceData.value[deviceId] = {
      ...deviceData.value[deviceId],
      id: deviceId,
      ...data
    } as DeviceRealtimeData
  }

  function updateAllDeviceData(dataList: DeviceRealtimeData[]) {
    dataList.forEach(data => {
      deviceData.value[data.id] = data
    })
  }

  function toggleLayer(layer: keyof DataLayers) {
    layers.value[layer] = !layers.value[layer]
  }

  function selectDevice(deviceId: string | null) {
    selectedDeviceId.value = deviceId
  }

  function setLoading(isLoading: boolean) {
    loading.value = isLoading
  }

  function updatePanelPosition(panelId: string, x: number, y: number) {
    if (panelStates.value[panelId]) {
      panelStates.value[panelId].x = x
      panelStates.value[panelId].y = y
      savePanelStates()
    }
  }

  function updatePanelCollapsed(panelId: string, collapsed: boolean) {
    if (panelStates.value[panelId]) {
      panelStates.value[panelId].collapsed = collapsed
      savePanelStates()
    }
  }

  function togglePanelVisible(panelId: string) {
    if (panelStates.value[panelId]) {
      panelStates.value[panelId].visible = !panelStates.value[panelId].visible
      savePanelStates()
    }
  }

  function savePanelStates() {
    try {
      localStorage.setItem('bigscreen-panel-states', JSON.stringify(panelStates.value))
    } catch (e) {
      console.warn('Failed to save panel states:', e)
    }
  }

  function loadPanelStates() {
    try {
      const saved = localStorage.getItem('bigscreen-panel-states')
      if (saved) {
        const parsed = JSON.parse(saved)
        Object.keys(parsed).forEach(key => {
          if (panelStates.value[key]) {
            panelStates.value[key] = { ...panelStates.value[key], ...parsed[key] }
          }
        })
      }
    } catch (e) {
      console.warn('Failed to load panel states:', e)
    }
  }

  function resetPanelStates() {
    panelStates.value = {
      leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
      rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
      deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
      floorSelector: { x: 20, y: 120, collapsed: false, visible: true },
      bottomBar: { x: 0, y: 0, collapsed: false, visible: true }
    }
    savePanelStates()
  }

  // 添加 getDeviceData 函数（原来是 getter）
  function getDeviceData(deviceId: string) {
    return deviceData.value[deviceId] || null
  }

  return {
    // state
    mode,
    layout,
    deviceData,
    layers,
    selectedDeviceId,
    cameraPresets,
    loading,
    panelStates,
    // computed
    activeAlarms,
    alarmCount,
    criticalAlarmCount,
    hasSelectedDevice,
    recentAlarms,
    energy,
    environment,
    modeConfig,
    // actions
    setMode,
    setLayout,
    updateDeviceData,
    updateAllDeviceData,
    toggleLayer,
    selectDevice,
    setLoading,
    updatePanelPosition,
    updatePanelCollapsed,
    togglePanelVisible,
    savePanelStates,
    loadPanelStates,
    resetPanelStates,
    getDeviceData
  }
})
```

**关键改进:**
1. 所有 state 改为 `ref`
2. 所有 getters 改为 `computed`
3. 所有 actions 改为普通函数
4. `getDeviceData` 从 getter 改为函数（因为它接受参数）
5. 所有 computed 自动缓存，只在依赖变化时重新计算

---

## 审查总结

Story 27.10 的目标是正确的（优化 activeAlarms 性能），但实施方案需要调整：

1. **P1-1:** 需要将 store 从 options API 改为 setup API
2. **P2-2:** 需要说明如何处理其他 getters

**建议:** 修改 Story 采用方案 A（改为 setup API），这样所有 getters 都会自动获得 computed 缓存。

---

**审查完成时间:** 2026-03-10
**下一步:** 修改 Story 后进行第二轮审查
