// frontend/src/stores/bigscreen.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAlarmStore } from '@/stores/alarm'
import { useEnergyStore } from '@/stores/energy'
import { useRealtimeStore } from '@/stores/realtime'
import type {
  SceneMode,
  DataCenterLayout,
  DeviceRealtimeData,
  DataLayers,
  BigscreenAlarm,
  CameraPreset
} from '@/types/bigscreen'

// 面板状态类型
interface PanelState {
  x: number
  y: number
  collapsed: boolean
  visible: boolean
}

interface _BigscreenState {
  // 场景模式
  mode: SceneMode

  // 布局配置
  layout: DataCenterLayout | null

  // 设备实时数据 (按设备ID索引)
  deviceData: Record<string, DeviceRealtimeData>

  // 数据图层开关
  layers: DataLayers

  // 选中的设备
  selectedDeviceId: string | null

  // 相机预设
  cameraPresets: Record<string, CameraPreset>

  // 是否正在加载
  loading: boolean

  // 面板状态
  panelStates: Record<string, PanelState>
}

// Story 27.10: 改为 setup API，使用 computed 缓存所有 getters
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

  // getDeviceData 改为函数（原来是 getter）
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
