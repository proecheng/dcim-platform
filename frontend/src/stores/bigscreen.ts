// frontend/src/stores/bigscreen.ts
import { defineStore } from 'pinia'
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

interface BigscreenState {
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

  // Story 27.7 AC3 & AC4: environment 和 energy 移到 getters，不再是 state

  // 相机预设
  cameraPresets: Record<string, CameraPreset>

  // 是否正在加载
  loading: boolean

  // 面板状态
  panelStates: Record<string, PanelState>
}

export const useBigscreenStore = defineStore('bigscreen', {
  state: (): BigscreenState => ({
    mode: 'command',
    layout: null,
    deviceData: {},
    layers: {
      heatmap: true,
      status: true,
      power: true,
      airflow: false
    },
    selectedDeviceId: null,
    cameraPresets: {
      overview: { position: [0, 50, 50], target: [0, 0, 0] },
      topDown: { position: [0, 80, 0], target: [0, 0, 0] },
      moduleA: { position: [20, 15, 20], target: [20, 0, 0] }
    },
    loading: false,
    panelStates: {
      leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
      rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
      deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
      floorSelector: { x: 20, y: 120, collapsed: false, visible: true },
      bottomBar: { x: 0, y: 0, collapsed: false, visible: true }
    }
  }),

  getters: {
    // 获取设备数据
    getDeviceData: (state) => (deviceId: string) => {
      return state.deviceData[deviceId] || null
    },

    // 活动告警（从 AlarmStore 派生，统一数据源）
    activeAlarms(): BigscreenAlarm[] {
      const alarmStore = useAlarmStore()
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
    },

    // 获取告警数量（从 AlarmStore 派生）
    alarmCount(): number {
      return useAlarmStore().alarmCount.total
    },

    // 获取严重告警数量（从 AlarmStore 派生）
    criticalAlarmCount(): number {
      return useAlarmStore().alarmCount.critical
    },

    // 是否有选中设备
    hasSelectedDevice: (state) => state.selectedDeviceId !== null,

    // 获取当前模式配置
    modeConfig: (state) => {
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
      return configs[state.mode]
    },

    // 最近告警列表（从 activeAlarms getter 派生）
    recentAlarms(): BigscreenAlarm[] {
      return this.activeAlarms.slice(0, 10)
    },

    // Story 27.7 AC3: energy 从 EnergyStore 派生
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
    },

    // Story 27.7 AC4: environment 从 RealtimeStore 派生
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
  },

  actions: {
    // 设置场景模式
    setMode(mode: SceneMode) {
      this.mode = mode
    },

    // 设置布局
    setLayout(layout: DataCenterLayout) {
      this.layout = layout
    },

    // 更新设备数据
    updateDeviceData(deviceId: string, data: Partial<DeviceRealtimeData>) {
      this.deviceData[deviceId] = {
        ...this.deviceData[deviceId],
        id: deviceId,
        ...data
      } as DeviceRealtimeData
    },

    // 批量更新设备数据
    updateAllDeviceData(dataList: DeviceRealtimeData[]) {
      dataList.forEach(data => {
        this.deviceData[data.id] = data
      })
    },

    // 切换图层
    toggleLayer(layer: keyof DataLayers) {
      this.layers[layer] = !this.layers[layer]
    },

    // 设置选中设备
    selectDevice(deviceId: string | null) {
      this.selectedDeviceId = deviceId
    },

    // Story 27.7 AC3 & AC4: 移除 updateEnvironment 和 updateEnergy actions
    // environment 和 energy 现在是 getters，从对应 Store 派生

    // 设置加载状态
    setLoading(loading: boolean) {
      this.loading = loading
    },

    // 更新面板位置
    updatePanelPosition(panelId: string, x: number, y: number) {
      if (this.panelStates[panelId]) {
        this.panelStates[panelId].x = x
        this.panelStates[panelId].y = y
        this.savePanelStates()
      }
    },

    // 更新面板折叠状态
    updatePanelCollapsed(panelId: string, collapsed: boolean) {
      if (this.panelStates[panelId]) {
        this.panelStates[panelId].collapsed = collapsed
        this.savePanelStates()
      }
    },

    // 切换面板可见性
    togglePanelVisible(panelId: string) {
      if (this.panelStates[panelId]) {
        this.panelStates[panelId].visible = !this.panelStates[panelId].visible
        this.savePanelStates()
      }
    },

    // 保存面板状态到 localStorage
    savePanelStates() {
      try {
        localStorage.setItem('bigscreen-panel-states', JSON.stringify(this.panelStates))
      } catch (e) {
        console.warn('Failed to save panel states:', e)
      }
    },

    // 从 localStorage 加载面板状态
    loadPanelStates() {
      try {
        const saved = localStorage.getItem('bigscreen-panel-states')
        if (saved) {
          const parsed = JSON.parse(saved)
          Object.keys(parsed).forEach(key => {
            if (this.panelStates[key]) {
              this.panelStates[key] = { ...this.panelStates[key], ...parsed[key] }
            }
          })
        }
      } catch (e) {
        console.warn('Failed to load panel states:', e)
      }
    },

    // 重置面板状态
    resetPanelStates() {
      this.panelStates = {
        leftPanel: { x: 20, y: 60, collapsed: false, visible: true },
        rightPanel: { x: -300, y: 60, collapsed: false, visible: true },
        deviceDetail: { x: -320, y: 60, collapsed: false, visible: true },
        floorSelector: { x: 20, y: 120, collapsed: false, visible: true },
        bottomBar: { x: 0, y: 0, collapsed: false, visible: true }
      }
      this.savePanelStates()
    }
  }
})
