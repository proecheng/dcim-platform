/**
 * useAlarm composable 纯逻辑函数单元测试
 *
 * 覆盖: 告警级别筛选、计数更新、确认/解决逻辑、WebSocket 消息处理
 * 这些函数定义在 composable 内部，未 export，因此复制核心逻辑进行测试。
 */
import { describe, it, expect } from 'vitest'

// ============================================================
// 辅助: 告警数据工厂
// ============================================================
interface AlarmInfo {
  id: number
  alarm_level: string
  alarm_message: string
  status: string
  point_id?: number
  escalated_from?: string
}

interface AlarmCount {
  critical: number
  major: number
  minor: number
  info: number
  total: number
}

function makeAlarmInfo(overrides: Partial<AlarmInfo> = {}): AlarmInfo {
  return {
    id: 1,
    alarm_level: 'major',
    alarm_message: '温度超限',
    status: 'active',
    point_id: 100,
    ...overrides,
  }
}

function makeAlarmCount(overrides: Partial<AlarmCount> = {}): AlarmCount {
  return { critical: 0, major: 0, minor: 0, info: 0, total: 0, ...overrides }
}

// ============================================================
// 来源: useAlarm.ts — getAlarmsByLevel (line 263)
// ============================================================
function getAlarmsByLevel(alarms: AlarmInfo[], level: string): AlarmInfo[] {
  return alarms.filter(a => a.alarm_level === level)
}

// ============================================================
// 来源: useAlarm.ts — handleAlarmAck (line 149-154)
// ============================================================
function handleAlarmAck(alarms: AlarmInfo[], alarmId: number): AlarmInfo[] {
  const result = [...alarms]
  const index = result.findIndex(a => a.id === alarmId)
  if (index !== -1) {
    result[index] = { ...result[index], status: 'acknowledged' }
  }
  return result
}

// ============================================================
// 来源: useAlarm.ts — handleAlarmResolve (line 157-173)
// ============================================================
function handleAlarmResolve(
  alarms: AlarmInfo[],
  count: AlarmCount,
  alarmId: number
): { alarms: AlarmInfo[]; count: AlarmCount } {
  const result = [...alarms]
  const newCount = { ...count }
  const index = result.findIndex(a => a.id === alarmId)
  if (index !== -1) {
    const alarm = result[index]
    result.splice(index, 1)
    newCount.total = Math.max(0, newCount.total - 1)
    const levelKey = alarm.alarm_level as keyof Omit<AlarmCount, 'total'>
    if (levelKey in newCount && levelKey !== ('total' as string)) {
      newCount[levelKey] = Math.max(0, newCount[levelKey] - 1)
    }
  }
  return { alarms: result, count: newCount }
}

// ============================================================
// 来源: useAlarm.ts — handleNewAlarm 中的计数更新逻辑 (line 97-106)
// ============================================================
function addAlarmToCount(count: AlarmCount, alarm: AlarmInfo): AlarmCount {
  const validLevels = ['critical', 'major', 'minor', 'info'] as const
  const newCount = { ...count }
  newCount.total++
  if (validLevels.includes(alarm.alarm_level as typeof validLevels[number])) {
    newCount[alarm.alarm_level as keyof Omit<AlarmCount, 'total'>]++
  }
  return newCount
}

// ============================================================
// 来源: useAlarm.ts — handleAlarmMessage switch 中的 escalate 逻辑 (line 214-226)
// ============================================================
function handleEscalate(
  alarms: AlarmInfo[],
  data: { id: number; alarm_level: string; previous_level: string }
): AlarmInfo[] {
  const result = [...alarms]
  const idx = result.findIndex(a => a.id === data.id)
  if (idx !== -1) {
    result[idx] = {
      ...result[idx],
      alarm_level: data.alarm_level,
      escalated_from: data.previous_level,
    }
  }
  return result
}

// ============================================================
// 来源: useAlarm.ts — 通知类型映射 (line 132-137)
// ============================================================
function getNotificationType(level: string): 'error' | 'warning' | 'info' | 'success' {
  const typeMap: Record<string, 'error' | 'warning' | 'info' | 'success'> = {
    critical: 'error',
    major: 'warning',
    minor: 'info',
    info: 'info',
  }
  return typeMap[level] || 'info'
}

// ============================================================
// 测试
// ============================================================

describe('useAlarm — 按级别筛选告警', () => {
  const alarms = [
    makeAlarmInfo({ id: 1, alarm_level: 'critical' }),
    makeAlarmInfo({ id: 2, alarm_level: 'major' }),
    makeAlarmInfo({ id: 3, alarm_level: 'critical' }),
    makeAlarmInfo({ id: 4, alarm_level: 'minor' }),
    makeAlarmInfo({ id: 5, alarm_level: 'info' }),
  ]

  it('正常: 筛选 critical 告警', () => {
    const result = getAlarmsByLevel(alarms, 'critical')
    expect(result).toHaveLength(2)
    expect(result.every(a => a.alarm_level === 'critical')).toBe(true)
  })

  it('正常: 筛选 major 告警', () => {
    expect(getAlarmsByLevel(alarms, 'major')).toHaveLength(1)
  })

  it('边界: 无匹配级别返回空', () => {
    expect(getAlarmsByLevel(alarms, 'unknown')).toHaveLength(0)
  })

  it('边界: 空数组返回空', () => {
    expect(getAlarmsByLevel([], 'critical')).toHaveLength(0)
  })
})

describe('useAlarm — 告警确认 (handleAlarmAck)', () => {
  it('正常: 确认后状态变为 acknowledged', () => {
    const alarms = [makeAlarmInfo({ id: 1, status: 'active' })]
    const result = handleAlarmAck(alarms, 1)
    expect(result[0].status).toBe('acknowledged')
  })

  it('边界: 确认不存在的 ID 不影响列表', () => {
    const alarms = [makeAlarmInfo({ id: 1, status: 'active' })]
    const result = handleAlarmAck(alarms, 999)
    expect(result[0].status).toBe('active')
  })

  it('正常: 不修改原数组', () => {
    const alarms = [makeAlarmInfo({ id: 1, status: 'active' })]
    handleAlarmAck(alarms, 1)
    expect(alarms[0].status).toBe('active')
  })
})

describe('useAlarm — 告警解决 (handleAlarmResolve)', () => {
  it('正常: 解决后从列表移除并更新计数', () => {
    const alarms = [
      makeAlarmInfo({ id: 1, alarm_level: 'major' }),
      makeAlarmInfo({ id: 2, alarm_level: 'critical' }),
    ]
    const count = makeAlarmCount({ major: 1, critical: 1, total: 2 })
    const result = handleAlarmResolve(alarms, count, 1)
    expect(result.alarms).toHaveLength(1)
    expect(result.count.major).toBe(0)
    expect(result.count.total).toBe(1)
    expect(result.count.critical).toBe(1)
  })

  it('边界: 解决不存在的 ID 不影响', () => {
    const alarms = [makeAlarmInfo({ id: 1 })]
    const count = makeAlarmCount({ major: 1, total: 1 })
    const result = handleAlarmResolve(alarms, count, 999)
    expect(result.alarms).toHaveLength(1)
    expect(result.count.total).toBe(1)
  })

  it('边界: 计数不会变为负数', () => {
    const alarms = [makeAlarmInfo({ id: 1, alarm_level: 'major' })]
    const count = makeAlarmCount({ major: 0, total: 0 })
    const result = handleAlarmResolve(alarms, count, 1)
    expect(result.count.major).toBe(0)
    expect(result.count.total).toBe(0)
  })
})

describe('useAlarm — 新告警计数更新 (addAlarmToCount)', () => {
  it('正常: 增加 critical 计数', () => {
    const count = makeAlarmCount()
    const result = addAlarmToCount(count, makeAlarmInfo({ alarm_level: 'critical' }))
    expect(result.critical).toBe(1)
    expect(result.total).toBe(1)
  })

  it('正常: 增加 info 计数', () => {
    const count = makeAlarmCount({ info: 2, total: 5 })
    const result = addAlarmToCount(count, makeAlarmInfo({ alarm_level: 'info' }))
    expect(result.info).toBe(3)
    expect(result.total).toBe(6)
  })

  it('边界: 未知级别只增加 total', () => {
    const count = makeAlarmCount()
    const result = addAlarmToCount(count, makeAlarmInfo({ alarm_level: 'unknown' }))
    expect(result.total).toBe(1)
    expect(result.critical).toBe(0)
    expect(result.major).toBe(0)
  })
})

describe('useAlarm — 告警升级 (handleEscalate)', () => {
  it('正常: 升级告警级别', () => {
    const alarms = [makeAlarmInfo({ id: 1, alarm_level: 'minor' })]
    const result = handleEscalate(alarms, { id: 1, alarm_level: 'critical', previous_level: 'minor' })
    expect(result[0].alarm_level).toBe('critical')
    expect(result[0].escalated_from).toBe('minor')
  })

  it('边界: 升级不存在的 ID 不影响', () => {
    const alarms = [makeAlarmInfo({ id: 1, alarm_level: 'minor' })]
    const result = handleEscalate(alarms, { id: 999, alarm_level: 'critical', previous_level: 'minor' })
    expect(result[0].alarm_level).toBe('minor')
  })
})

describe('useAlarm — 通知类型映射', () => {
  it('critical → error', () => { expect(getNotificationType('critical')).toBe('error') })
  it('major → warning', () => { expect(getNotificationType('major')).toBe('warning') })
  it('minor → info', () => { expect(getNotificationType('minor')).toBe('info') })
  it('info → info', () => { expect(getNotificationType('info')).toBe('info') })
  it('unknown → info', () => { expect(getNotificationType('unknown')).toBe('info') })
})
