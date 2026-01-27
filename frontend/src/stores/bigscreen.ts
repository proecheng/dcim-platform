// frontend/src/stores/bigscreen.ts
import { defineStore } from 'pinia'
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

  // 活动告警
  activeAlarms: BigscreenAlarm[]

  // 环境数据
  environment: {
    temperature: { max: number; avg: number; min: number }
    humidity: { max: number; avg: number; min: number }
  }

  // 能耗数据
  energy: {
    totalPower: number
    itPower: number
    coolingPower: number
    pue: number
    todayEnergy: number
    todayCost: number
  }

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
    activeAlarms: [],
    environment: {
      temperature: { max: 0, avg: 0, min: 0 },
      humidity: { max: 0, avg: 0, min: 0 }
    },
    energy: {
      totalPower: 0,
      itPower: 0,
      coolingPower: 0,
      pue: 1.5,
      todayEnergy: 0,
      todayCost: 0
    },
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

    // 获取告警数量
    alarmCount: (state) => state.activeAlarms.length,

    // 获取严重告警数量
    criticalAlarmCount: (state) => {
      return state.activeAlarms.filter(a => a.level === 'critical').length
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

    // 最近告警列表
    recentAlarms: (state) => state.activeAlarms.slice(0, 10)
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

    // 更新告警列表
    setAlarms(alarms: BigscreenAlarm[]) {
      this.activeAlarms = alarms
    },

    // 更新环境数据
    updateEnvironment(env: BigscreenState['environment']) {
      this.environment = env
    },

    // 更新能耗数据
    updateEnergy(energy: BigscreenState['energy']) {
      this.energy = energy
    },

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
