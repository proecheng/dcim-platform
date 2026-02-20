/**
 * Realtime Store 单元测试
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRealtimeStore } from '@/stores/realtime'

const makePoint = (overrides: Record<string, unknown> = {}) => ({
  point_id: 1,
  point_code: 'T001',
  point_name: '温度传感器1',
  point_type: 'AI' as const,
  device_type: 'sensor',
  area_code: 'A01',
  raw_value: 25.5,
  value: 25.5,
  value_text: '25.5',
  unit: '℃',
  quality: 100,
  status: 'normal' as const,
  alarm_level: null,
  change_count: 0,
  last_change_at: '2026-01-01',
  updated_at: '2026-01-01',
  ...overrides
})

describe('useRealtimeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态为空', () => {
    const store = useRealtimeStore()
    expect(store.realtimeData).toEqual([])
    expect(store.totalPoints).toBe(0)
    expect(store.summary).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
    expect(store.wsConnected).toBe(false)
    expect(store.alarmCount).toBe(0)
    expect(store.offlineCount).toBe(0)
  })

  it('updatePoint 更新单个点位', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint() as any)
    expect(store.totalPoints).toBe(1)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('updatePoints 批量更新', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1 }) as any,
      makePoint({ point_id: 2 }) as any
    ])
    expect(store.totalPoints).toBe(2)
  })

  it('setAllData 替换全部数据', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint({ point_id: 99 }) as any)
    store.setAllData([makePoint({ point_id: 1 }) as any])
    expect(store.totalPoints).toBe(1)
    expect(store.getPointData(99)).toBeUndefined()
  })

  it('setSummary 设置汇总数据', () => {
    const store = useRealtimeStore()
    const summary = { total_points: 50, online_points: 48, offline_points: 2, alarm_points: 3, by_type: {}, by_area: {} }
    store.setSummary(summary as any)
    expect(store.summary).toEqual(summary)
  })

  it('getPointData 获取点位数据', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint({ point_id: 42 }) as any)
    expect(store.getPointData(42)).toBeDefined()
    expect(store.getPointData(999)).toBeUndefined()
  })

  it('getDataByType 按类型过滤', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, point_type: 'AI' }) as any,
      makePoint({ point_id: 2, point_type: 'DI' }) as any,
      makePoint({ point_id: 3, point_type: 'AI' }) as any
    ])
    expect(store.getDataByType('AI')).toHaveLength(2)
    expect(store.getDataByType('DI')).toHaveLength(1)
    expect(store.getDataByType('AO')).toHaveLength(0)
  })

  it('getDataByArea 按区域过滤', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, area_code: 'A01' }) as any,
      makePoint({ point_id: 2, area_code: 'A02' }) as any,
      makePoint({ point_id: 3, area_code: 'A01' }) as any
    ])
    expect(store.getDataByArea('A01')).toHaveLength(2)
    expect(store.getDataByArea('A02')).toHaveLength(1)
    expect(store.getDataByArea('A99')).toHaveLength(0)
  })

  it('alarmPoints / alarmCount 过滤告警点位', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, status: 'normal' }) as any,
      makePoint({ point_id: 2, status: 'alarm' }) as any,
      makePoint({ point_id: 3, status: 'alarm' }) as any
    ])
    expect(store.alarmPoints).toHaveLength(2)
    expect(store.alarmCount).toBe(2)
  })

  it('offlinePoints / offlineCount 过滤离线点位', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, status: 'normal' }) as any,
      makePoint({ point_id: 2, status: 'offline' }) as any
    ])
    expect(store.offlinePoints).toHaveLength(1)
    expect(store.offlineCount).toBe(1)
  })

  it('setWsConnected 设置连接状态', () => {
    const store = useRealtimeStore()
    store.setWsConnected(true)
    expect(store.wsConnected).toBe(true)
  })

  it('clearData 清空所有数据', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint() as any)
    store.setSummary({ total_points: 1 } as any)
    store.clearData()
    expect(store.totalPoints).toBe(0)
    expect(store.summary).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
  })

  it('updatePoint 覆盖已有点位数据', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint({ point_id: 1, value: 25.5 }) as any)
    store.updatePoint(makePoint({ point_id: 1, value: 30.0 }) as any)
    expect(store.totalPoints).toBe(1)
    expect(store.getPointData(1)?.value).toBe(30.0)
  })
})
