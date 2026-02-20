/**
 * Bigscreen Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useBigscreenStore } from '@/stores/bigscreen'

// Mock bigscreen types
vi.mock('@/types/bigscreen', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/types/bigscreen')
  return { ...actual }
})

describe('useBigscreenStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态正确', () => {
    const store = useBigscreenStore()
    expect(store.mode).toBe('command')
    expect(store.layout).toBeNull()
    expect(store.deviceData).toEqual({})
    expect(store.layers.heatmap).toBe(true)
    expect(store.layers.status).toBe(true)
    expect(store.layers.power).toBe(true)
    expect(store.layers.airflow).toBe(false)
    expect(store.selectedDeviceId).toBeNull()
    expect(store.activeAlarms).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('初始能耗数据', () => {
    const store = useBigscreenStore()
    expect(store.energy.totalPower).toBe(0)
    expect(store.energy.itPower).toBe(0)
    expect(store.energy.coolingPower).toBe(0)
    expect(store.energy.pue).toBe(1.5)
    expect(store.energy.todayEnergy).toBe(0)
    expect(store.energy.todayCost).toBe(0)
  })

  it('setMode 设置场景模式', () => {
    const store = useBigscreenStore()
    store.setMode('operation')
    expect(store.mode).toBe('operation')
    store.setMode('showcase')
    expect(store.mode).toBe('showcase')
  })

  it('setLayout 设置布局', () => {
    const store = useBigscreenStore()
    const layout = { name: '测试机房', dimensions: { width: 100, length: 200, height: 10 }, modules: [], infrastructure: {} }
    store.setLayout(layout as any)
    expect(store.layout).not.toBeNull()
    expect(store.layout?.name).toBe('测试机房')
  })

  it('updateDeviceData 更新设备数据', () => {
    const store = useBigscreenStore()
    store.updateDeviceData('dev-1', { status: 'normal', temperature: 25 } as any)
    expect(store.deviceData['dev-1']).toBeDefined()
    expect(store.deviceData['dev-1'].status).toBe('normal')
  })

  it('updateAllDeviceData 批量更新设备数据', () => {
    const store = useBigscreenStore()
    store.updateAllDeviceData([
      { id: 'dev-1', status: 'normal', temperature: 25 } as any,
      { id: 'dev-2', status: 'alarm', temperature: 40 } as any
    ])
    expect(Object.keys(store.deviceData)).toHaveLength(2)
  })

  it('toggleLayer 切换图层', () => {
    const store = useBigscreenStore()
    expect(store.layers.airflow).toBe(false)
    store.toggleLayer('airflow')
    expect(store.layers.airflow).toBe(true)
    store.toggleLayer('airflow')
    expect(store.layers.airflow).toBe(false)
  })

  it('selectDevice 设置选中设备', () => {
    const store = useBigscreenStore()
    store.selectDevice('dev-1')
    expect(store.selectedDeviceId).toBe('dev-1')
    expect(store.hasSelectedDevice).toBe(true)
    store.selectDevice(null)
    expect(store.selectedDeviceId).toBeNull()
    expect(store.hasSelectedDevice).toBe(false)
  })

  it('setAlarms 更新告警列表', () => {
    const store = useBigscreenStore()
    const alarms = [
      { id: '1', level: 'critical', message: '温度过高', deviceId: 'dev-1', timestamp: '2026-01-01' },
      { id: '2', level: 'major', message: '湿度异常', deviceId: 'dev-2', timestamp: '2026-01-01' }
    ]
    store.setAlarms(alarms as any)
    expect(store.activeAlarms).toHaveLength(2)
    expect(store.alarmCount).toBe(2)
    expect(store.criticalAlarmCount).toBe(1)
  })

  it('updateEnvironment 更新环境数据', () => {
    const store = useBigscreenStore()
    const env = {
      temperature: { max: 30, avg: 25, min: 20 },
      humidity: { max: 60, avg: 50, min: 40 }
    }
    store.updateEnvironment(env)
    expect(store.environment.temperature.avg).toBe(25)
    expect(store.environment.humidity.avg).toBe(50)
  })

  it('updateEnergy 更新能耗数据', () => {
    const store = useBigscreenStore()
    const energy = { totalPower: 500, itPower: 300, coolingPower: 150, pue: 1.67, todayEnergy: 1200, todayCost: 960 }
    store.updateEnergy(energy)
    expect(store.energy.totalPower).toBe(500)
    expect(store.energy.pue).toBe(1.67)
  })

  it('setLoading 设置加载状态', () => {
    const store = useBigscreenStore()
    store.setLoading(true)
    expect(store.loading).toBe(true)
    store.setLoading(false)
    expect(store.loading).toBe(false)
  })

  it('getDeviceData getter 获取设备数据', () => {
    const store = useBigscreenStore()
    store.updateDeviceData('dev-1', { status: 'normal' } as any)
    expect(store.getDeviceData('dev-1')).not.toBeNull()
    expect(store.getDeviceData('nonexistent')).toBeNull()
  })

  it('modeConfig getter 返回模式配置', () => {
    const store = useBigscreenStore()
    expect(store.modeConfig.refreshInterval).toBe(5000)
    store.setMode('operation')
    expect(store.modeConfig.refreshInterval).toBe(3000)
    store.setMode('showcase')
    expect(store.modeConfig.refreshInterval).toBe(10000)
  })

  it('recentAlarms getter 返回最近10条告警', () => {
    const store = useBigscreenStore()
    const alarms = Array.from({ length: 15 }, (_, i) => ({
      id: String(i), level: 'minor', message: `告警${i}`, deviceId: 'dev-1', timestamp: '2026-01-01'
    }))
    store.setAlarms(alarms as any)
    expect(store.recentAlarms).toHaveLength(10)
  })

  it('updatePanelPosition 更新面板位置', () => {
    const store = useBigscreenStore()
    store.updatePanelPosition('leftPanel', 100, 200)
    expect(store.panelStates.leftPanel.x).toBe(100)
    expect(store.panelStates.leftPanel.y).toBe(200)
    expect(localStorage.setItem).toHaveBeenCalled()
  })

  it('updatePanelPosition 不存在的面板无副作用', () => {
    const store = useBigscreenStore()
    store.updatePanelPosition('nonexistent', 100, 200)
    expect(store.panelStates['nonexistent']).toBeUndefined()
  })

  it('updatePanelCollapsed 更新面板折叠状态', () => {
    const store = useBigscreenStore()
    store.updatePanelCollapsed('leftPanel', true)
    expect(store.panelStates.leftPanel.collapsed).toBe(true)
  })

  it('togglePanelVisible 切换面板可见性', () => {
    const store = useBigscreenStore()
    expect(store.panelStates.leftPanel.visible).toBe(true)
    store.togglePanelVisible('leftPanel')
    expect(store.panelStates.leftPanel.visible).toBe(false)
  })

  it('loadPanelStates 从 localStorage 加载面板状态', () => {
    const saved = { leftPanel: { x: 50, y: 80, collapsed: true, visible: false } }
    localStorage.setItem('bigscreen-panel-states', JSON.stringify(saved))
    const store = useBigscreenStore()
    store.loadPanelStates()
    expect(store.panelStates.leftPanel.x).toBe(50)
    expect(store.panelStates.leftPanel.collapsed).toBe(true)
  })

  it('loadPanelStates 无存储时不报错', () => {
    const store = useBigscreenStore()
    expect(() => store.loadPanelStates()).not.toThrow()
  })

  it('resetPanelStates 重置面板状态', () => {
    const store = useBigscreenStore()
    store.updatePanelPosition('leftPanel', 999, 999)
    store.resetPanelStates()
    expect(store.panelStates.leftPanel.x).toBe(20)
    expect(store.panelStates.leftPanel.y).toBe(60)
  })
})
