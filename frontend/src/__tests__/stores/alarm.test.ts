/**
 * Alarm Store 单元测试
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAlarmStore, type Alarm } from '@/stores/alarm'

function makeAlarm(overrides: Partial<Alarm> = {}): Alarm {
  return {
    id: 1,
    point_code: 'T001',
    point_name: '温度传感器1',
    alarm_level: 'critical',
    alarm_message: '温度过高',
    status: 'active',
    created_at: '2026-01-01 00:00:00',
    ...overrides
  }
}

describe('useAlarmStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('初始状态为空', () => {
    const store = useAlarmStore()
    expect(store.activeAlarms).toEqual([])
    expect(store.alarmCount.total).toBe(0)
  })

  it('addAlarm 添加告警并更新计数', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1, alarm_level: 'critical' }))
    store.addAlarm(makeAlarm({ id: 2, alarm_level: 'major' }))
    store.addAlarm(makeAlarm({ id: 3, alarm_level: 'minor' }))
    store.addAlarm(makeAlarm({ id: 4, alarm_level: 'info' }))

    expect(store.activeAlarms).toHaveLength(4)
    expect(store.alarmCount.critical).toBe(1)
    expect(store.alarmCount.major).toBe(1)
    expect(store.alarmCount.minor).toBe(1)
    expect(store.alarmCount.info).toBe(1)
    expect(store.alarmCount.total).toBe(4)
  })

  it('addAlarm 去重 — 相同 id 不重复添加', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1 }))
    store.addAlarm(makeAlarm({ id: 1 }))
    expect(store.activeAlarms).toHaveLength(1)
  })

  it('addAlarm 新告警插入到头部', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1, point_name: '第一条' }))
    store.addAlarm(makeAlarm({ id: 2, point_name: '第二条' }))
    expect(store.activeAlarms[0].point_name).toBe('第二条')
  })

  it('addAlarm 超过 1000 条时截断', () => {
    const store = useAlarmStore()
    for (let i = 1; i <= 1010; i++) {
      store.addAlarm(makeAlarm({ id: i }))
    }
    expect(store.activeAlarms.length).toBeLessThanOrEqual(1000)
  })

  it('removeAlarm 移除告警并更新计数', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1, alarm_level: 'critical' }))
    store.addAlarm(makeAlarm({ id: 2, alarm_level: 'major' }))
    store.removeAlarm(1)

    expect(store.activeAlarms).toHaveLength(1)
    expect(store.alarmCount.critical).toBe(0)
    expect(store.alarmCount.total).toBe(1)
  })

  it('updateAlarm 更新字段', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1, status: 'active' }))
    store.updateAlarm(1, { status: 'acknowledged', acknowledged_at: '2026-01-01 01:00:00' })

    expect(store.activeAlarms[0].status).toBe('acknowledged')
    expect(store.activeAlarms[0].acknowledged_at).toBe('2026-01-01 01:00:00')
  })

  it('updateAlarm 状态为 resolved 时自动移除', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1 }))
    store.updateAlarm(1, { status: 'resolved' })

    expect(store.activeAlarms).toHaveLength(0)
    expect(store.alarmCount.total).toBe(0)
  })

  it('updateAlarm 不存在的 id 无副作用', () => {
    const store = useAlarmStore()
    store.addAlarm(makeAlarm({ id: 1 }))
    store.updateAlarm(999, { status: 'resolved' })
    expect(store.activeAlarms).toHaveLength(1)
  })
})
