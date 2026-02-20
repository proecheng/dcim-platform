/**
 * Energy Store 单元测试
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useEnergyStore } from '@/stores/energy'

const makePowerData = (overrides: Record<string, unknown> = {}) => ({
  device_id: 1,
  device_code: 'D001',
  device_name: 'UPS-1',
  device_type: 'UPS',
  active_power: 100,
  status: 'normal' as const,
  update_time: '2026-01-01 00:00:00',
  ...overrides
})

const makeSuggestion = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  rule_id: 'R001',
  suggestion: '建议降低空调温度',
  priority: 'high' as const,
  status: 'pending' as const,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
  ...overrides
})

describe('useEnergyStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态为空', () => {
    const store = useEnergyStore()
    expect(store.powerDataList).toEqual([])
    expect(store.powerSummary).toBeNull()
    expect(store.pueData).toBeNull()
    expect(store.suggestions).toEqual([])
    expect(store.distributionDiagram).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
    expect(store.wsConnected).toBe(false)
  })

  it('计算属性默认值', () => {
    const store = useEnergyStore()
    expect(store.currentPUE).toBe(0)
    expect(store.totalPower).toBe(0)
    expect(store.itPower).toBe(0)
    expect(store.coolingPower).toBe(0)
    expect(store.todayEnergy).toBe(0)
    expect(store.todayCost).toBe(0)
    expect(store.monthEnergy).toBe(0)
    expect(store.monthCost).toBe(0)
    expect(store.pendingCount).toBe(0)
    expect(store.highPrioritySuggestions).toEqual([])
  })

  it('updatePowerData 更新单个设备数据', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData() as any)
    expect(store.powerDataList).toHaveLength(1)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('updatePowerDataBatch 批量更新', () => {
    const store = useEnergyStore()
    store.updatePowerDataBatch([
      makePowerData({ device_id: 1 }) as any,
      makePowerData({ device_id: 2 }) as any
    ])
    expect(store.powerDataList).toHaveLength(2)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('setAllPowerData 替换全部数据', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData({ device_id: 99 }) as any)
    store.setAllPowerData([makePowerData({ device_id: 1 }) as any])
    expect(store.powerDataList).toHaveLength(1)
    expect(store.getDevicePower(99)).toBeUndefined()
  })

  it('setPowerSummary 设置电力汇总', () => {
    const store = useEnergyStore()
    const summary = {
      total_power: 500, it_power: 300, cooling_power: 150,
      ups_power: 30, other_power: 20, current_pue: 1.67,
      today_energy: 1200, today_cost: 960,
      month_energy: 36000, month_cost: 28800
    }
    store.setPowerSummary(summary as any)
    expect(store.totalPower).toBe(500)
    expect(store.itPower).toBe(300)
    expect(store.coolingPower).toBe(150)
    expect(store.todayEnergy).toBe(1200)
    expect(store.todayCost).toBe(960)
    expect(store.monthEnergy).toBe(36000)
    expect(store.monthCost).toBe(28800)
  })

  it('setPUEData 设置 PUE 数据', () => {
    const store = useEnergyStore()
    store.setPUEData({ current_pue: 1.45, total_power: 500, it_power: 345, cooling_power: 100, ups_loss: 10, lighting_power: 5, other_power: 40, update_time: '2026-01-01' } as any)
    expect(store.currentPUE).toBe(1.45)
  })

  it('setSuggestions 设置节能建议列表', () => {
    const store = useEnergyStore()
    store.setSuggestions([makeSuggestion() as any, makeSuggestion({ id: 2, status: 'accepted' }) as any])
    expect(store.suggestions).toHaveLength(2)
    expect(store.pendingCount).toBe(1)
  })

  it('addSuggestion 新建议插入头部', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1 }) as any)
    store.addSuggestion(makeSuggestion({ id: 2 }) as any)
    expect(store.suggestions).toHaveLength(2)
    expect(store.suggestions[0].id).toBe(2)
  })

  it('addSuggestion 去重 — 相同 id 更新', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1, suggestion: '旧建议' }) as any)
    store.addSuggestion(makeSuggestion({ id: 1, suggestion: '新建议' }) as any)
    expect(store.suggestions).toHaveLength(1)
    expect(store.suggestions[0].suggestion).toBe('新建议')
  })

  it('updateSuggestionStatus 更新建议状态', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1, status: 'pending' }) as any)
    store.updateSuggestionStatus(1, 'accepted', { accepted_at: '2026-01-02' })
    expect(store.suggestions[0].status).toBe('accepted')
    expect(store.suggestions[0].accepted_at).toBe('2026-01-02')
  })

  it('updateSuggestionStatus 不存在的 id 无副作用', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1 }) as any)
    store.updateSuggestionStatus(999, 'accepted')
    expect(store.suggestions[0].status).toBe('pending')
  })

  it('setDistributionDiagram 设置配电图', () => {
    const store = useEnergyStore()
    const diagram = { root: { device_id: 1, device_code: 'D001', device_name: 'Main', device_type: 'MAIN', status: 'normal', children: [] }, total_power: 500, timestamp: '2026-01-01' }
    store.setDistributionDiagram(diagram as any)
    expect(store.distributionDiagram).not.toBeNull()
  })

  it('getDevicePower 获取设备电力数据', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData({ device_id: 42 }) as any)
    expect(store.getDevicePower(42)).toBeDefined()
    expect(store.getDevicePower(999)).toBeUndefined()
  })

  it('getPowerByType 按类型过滤', () => {
    const store = useEnergyStore()
    store.updatePowerDataBatch([
      makePowerData({ device_id: 1, device_type: 'UPS' }) as any,
      makePowerData({ device_id: 2, device_type: 'PDU' }) as any,
      makePowerData({ device_id: 3, device_type: 'UPS' }) as any
    ])
    expect(store.getPowerByType('UPS')).toHaveLength(2)
    expect(store.getPowerByType('PDU')).toHaveLength(1)
    expect(store.getPowerByType('AC')).toHaveLength(0)
  })

  it('setWsConnected 设置 WebSocket 状态', () => {
    const store = useEnergyStore()
    store.setWsConnected(true)
    expect(store.wsConnected).toBe(true)
    store.setWsConnected(false)
    expect(store.wsConnected).toBe(false)
  })

  it('clearData 清空所有数据', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData() as any)
    store.setPowerSummary({ total_power: 100 } as any)
    store.setPUEData({ current_pue: 1.5 } as any)
    store.setSuggestions([makeSuggestion() as any])
    store.setDistributionDiagram({ root: {} } as any)
    store.clearData()
    expect(store.powerDataList).toEqual([])
    expect(store.powerSummary).toBeNull()
    expect(store.pueData).toBeNull()
    expect(store.suggestions).toEqual([])
    expect(store.distributionDiagram).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
  })

  it('highPrioritySuggestions 过滤高优先级待处理建议', () => {
    const store = useEnergyStore()
    store.setSuggestions([
      makeSuggestion({ id: 1, priority: 'high', status: 'pending' }) as any,
      makeSuggestion({ id: 2, priority: 'low', status: 'pending' }) as any,
      makeSuggestion({ id: 3, priority: 'high', status: 'accepted' }) as any
    ])
    expect(store.highPrioritySuggestions).toHaveLength(1)
    expect(store.highPrioritySuggestions[0].id).toBe(1)
  })

  it('pendingSuggestions 过滤待处理建议', () => {
    const store = useEnergyStore()
    store.setSuggestions([
      makeSuggestion({ id: 1, status: 'pending' }) as any,
      makeSuggestion({ id: 2, status: 'accepted' }) as any,
      makeSuggestion({ id: 3, status: 'pending' }) as any
    ])
    expect(store.pendingSuggestions).toHaveLength(2)
    expect(store.pendingCount).toBe(2)
  })
})
