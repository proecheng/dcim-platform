// Source: frontend/src/views/alarm/compound.vue
// - evaluateGroup and evaluateCondition are defined in the <script setup> block
// - We reproduce pure-function versions here for unit testing
// Source: frontend/src/views/alarm/shield.vue
// - computeStatus is defined in the <script setup> block
// - We reproduce pure-function version here for unit testing

import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'

// Type definitions (local, for test-only pure copies)
type ConditionItem = {
  type: 'condition'
  pointId: number | null
  threshold: number | null
  operator: '>' | '<' | '=' | '>=' | '<='
}
type ConditionGroup = {
  type: 'group'
  logic: 'AND' | 'OR'
  children: Array<ConditionItem | ConditionGroup>
}
type AlarmShieldInfo = { start_time: string | Date; end_time: string | Date }
type ShieldStatus = 'active' | 'scheduled' | 'expired'

// Pure function copies (复制自 Vue 组件中的实现)
function evaluateCondition(cond: ConditionItem, values: Record<number, number>): boolean {
  if (cond.pointId == null || cond.threshold == null) return false
  const val = values[cond.pointId]
  if (val == null) return false
  switch (cond.operator) {
    case '>': return val > cond.threshold
    case '<': return val < cond.threshold
    case '=': return Math.abs(val - cond.threshold) < 0.001
    case '>=': return val >= cond.threshold
    case '<=': return val <= cond.threshold
    default: return false
  }
}

function evaluateGroup(group: ConditionGroup, values: Record<number, number>): boolean {
  if (!group.children.length) return false
  const results = group.children.map(child => {
    if (child.type === 'condition') return evaluateCondition(child, values)
    return evaluateGroup(child, values)
  })
  return group.logic === 'AND'
    ? results.every(Boolean)
    : results.some(Boolean)
}

function computeStatus(shield: AlarmShieldInfo): ShieldStatus {
  const now = new Date()
  const start = new Date(shield.start_time)
  const end = new Date(shield.end_time)
  if (now > end) return 'expired'
  if (now < start) return 'scheduled'
  return 'active'
}

describe('evaluateGroup', () => {
  it('空的子项 -> false', () => {
    const group: ConditionGroup = { type: 'group', logic: 'AND', children: [] }
    expect(evaluateGroup(group, {})).toBe(false)
  })

  it('AND 逻辑：全部满足 -> true', () => {
    const c1: ConditionItem = { type: 'condition', pointId: 1, threshold: 5, operator: '>' }
    const c2: ConditionItem = { type: 'condition', pointId: 2, threshold: 3, operator: '<' }
    const group: ConditionGroup = { type: 'group', logic: 'AND', children: [c1, c2] }
    const values = { 1: 6, 2: 2 }
    expect(evaluateGroup(group, values)).toBe(true)
  })

  it('AND 逻辑：任一不满足 -> false', () => {
    const c1: ConditionItem = { type: 'condition', pointId: 1, threshold: 5, operator: '>' }
    const c2: ConditionItem = { type: 'condition', pointId: 2, threshold: 5, operator: '<' }
    const group: ConditionGroup = { type: 'group', logic: 'AND', children: [c1, c2] }
    const values = { 1: 6, 2: 8 }
    expect(evaluateGroup(group, values)).toBe(false)
  })

  it('OR 逻辑：任一满足 -> true', () => {
    const c1: ConditionItem = { type: 'condition', pointId: 1, threshold: 5, operator: '>' }
    const c2: ConditionItem = { type: 'condition', pointId: 2, threshold: 5, operator: '<' }
    const group: ConditionGroup = { type: 'group', logic: 'OR', children: [c1, c2] }
    const values = { 1: 6, 2: 9 }
    expect(evaluateGroup(group, values)).toBe(true)
  })

  it('OR 逻辑：全部不满足 -> false', () => {
    const c1: ConditionItem = { type: 'condition', pointId: 1, threshold: 10, operator: '>' }
    const c2: ConditionItem = { type: 'condition', pointId: 2, threshold: 1, operator: '<' }
    const group: ConditionGroup = { type: 'group', logic: 'OR', children: [c1, c2] }
    const values = { 1: 5, 2: 5 }
    expect(evaluateGroup(group, values)).toBe(false)
  })

  it('多层嵌套：两层条件', () => {
    const cA: ConditionItem = { type: 'condition', pointId: 1, threshold: 5, operator: '>' }
    const cB: ConditionItem = { type: 'condition', pointId: 3, threshold: 7, operator: '>' }
    const cC: ConditionItem = { type: 'condition', pointId: 4, threshold: 10, operator: '<' }
    const inner: ConditionGroup = { type: 'group', logic: 'OR', children: [cB, cC] }
    const outer: ConditionGroup = { type: 'group', logic: 'AND', children: [cA, inner] }
    const values = { 1: 6, 3: 8, 4: 9 }
    expect(evaluateGroup(outer, values)).toBe(true)
  })

  it('未提供值的条件返回 false', () => {
    const missing: ConditionItem = { type: 'condition', pointId: 99, threshold: 1, operator: '>' }
    const group: ConditionGroup = { type: 'group', logic: 'AND', children: [missing] }
    expect(evaluateGroup(group, {})).toBe(false)
  })
})

describe('evaluateCondition', () => {
  it('各运算符正常工作', () => {
    const v = { 1: 6, 2: 4, 3: 5 }
    expect(evaluateCondition({ type: 'condition', pointId: 1, threshold: 5, operator: '>' }, v)).toBe(true)
    expect(evaluateCondition({ type: 'condition', pointId: 2, threshold: 5, operator: '<' }, v)).toBe(true)
    expect(evaluateCondition({ type: 'condition', pointId: 3, threshold: 5, operator: '=' }, v)).toBe(true)
    expect(evaluateCondition({ type: 'condition', pointId: 1, threshold: 5, operator: '>=' }, v)).toBe(true)
    expect(evaluateCondition({ type: 'condition', pointId: 3, threshold: 5, operator: '<=' }, v)).toBe(true)
  })

  it('= 运算符 0.001 精度边界', () => {
    expect(evaluateCondition({ type: 'condition', pointId: 1, threshold: 5, operator: '=' }, { 1: 5.0004 })).toBe(true)
    expect(evaluateCondition({ type: 'condition', pointId: 1, threshold: 5, operator: '=' }, { 1: 5.001 })).toBe(false)
  })

  it('pointId/threshold 为 null 或值缺失时返回 false', () => {
    expect(evaluateCondition({ type: 'condition', pointId: null, threshold: 1, operator: '>' }, {})).toBe(false)
    expect(evaluateCondition({ type: 'condition', pointId: 1, threshold: null, operator: '>' }, { 1: 2 })).toBe(false)
    expect(evaluateCondition({ type: 'condition', pointId: 2, threshold: 3, operator: '>' }, { 1: 10 })).toBe(false)
  })
})

describe('computeStatus', () => {
  beforeAll(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-21T12:00:00Z'))
  })
  afterAll(() => {
    vi.useRealTimers()
  })

  it('active: 当前时间在 start-end 之间', () => {
    expect(computeStatus({
      start_time: '2026-02-21T11:00:00Z',
      end_time: '2026-02-21T13:00:00Z'
    })).toBe('active')
  })

  it('scheduled: 当前时间在 start 之前', () => {
    expect(computeStatus({
      start_time: '2026-02-22T00:00:00Z',
      end_time: '2026-02-22T01:00:00Z'
    })).toBe('scheduled')
  })

  it('expired: 当前时间在 end 之后', () => {
    expect(computeStatus({
      start_time: '2026-02-21T08:00:00Z',
      end_time: '2026-02-21T11:00:00Z'
    })).toBe('expired')
  })
})
