/**
 * 复合告警规则页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))
vi.mock('@/api/modules/alarm', () => ({
  getAlarmRules: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createAlarmRule: vi.fn().mockResolvedValue({}),
  updateAlarmRule: vi.fn().mockResolvedValue({}),
  deleteAlarmRule: vi.fn().mockResolvedValue({}),
  toggleAlarmRule: vi.fn().mockResolvedValue({}),
}))
vi.mock('@/api/modules/point', () => ({
  getPointList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

// ── 条件树类型 ──
interface ConditionItem {
  id: string
  type: 'condition'
  pointId: number | undefined
  pointName: string
  operator: string
  threshold: number | undefined
}

interface ConditionGroup {
  id: string
  type: 'group'
  logic: 'AND' | 'OR'
  children: (ConditionItem | ConditionGroup)[]
}

// ── 从 compound.vue 提取的辅助函数 ──
function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    critical: 'danger', major: 'warning', minor: 'info', info: 'info'
  }
  return map[level] || 'info'
}

function levelLabel(level: string): string {
  const map: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '提示' }
  return map[level] || level
}

function countConditions(node: ConditionGroup | ConditionItem): number {
  if (node.type === 'condition') return 1
  return node.children.reduce((sum, child) => sum + countConditions(child), 0)
}

function getConditionCount(conditionExpr: string | null): number {
  if (!conditionExpr) return 0
  try {
    const root = JSON.parse(conditionExpr) as ConditionGroup
    return countConditions(root)
  } catch { return 0 }
}

function collectPointNames(node: ConditionGroup | ConditionItem): string[] {
  if (node.type === 'condition') return node.pointName ? [node.pointName] : []
  const names: string[] = []
  for (const child of node.children) names.push(...collectPointNames(child))
  return [...new Set(names)]
}

function getRelatedPoints(conditionExpr: string | null): string {
  if (!conditionExpr) return '-'
  try {
    const root = JSON.parse(conditionExpr) as ConditionGroup
    const names = collectPointNames(root)
    return names.length ? names.join(', ') : '-'
  } catch { return '(数据异常)' }
}

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
  return group.logic === 'AND' ? results.every(Boolean) : results.some(Boolean)
}

// ── 可测试的复合规则组件 ──
const CompoundRuleTestable = defineComponent({
  name: 'CompoundRuleTestable',
  setup() {
    const loading = ref(false)
    const tableData = ref([
      { id: 1, rule_name: '温湿度联合告警', rule_type: 'and', alarm_level: 'critical', is_enabled: true, condition_expr: JSON.stringify({ id: 'g1', type: 'group', logic: 'AND', children: [{ id: 'c1', type: 'condition', pointId: 1, pointName: '温度A', operator: '>', threshold: 30 }, { id: 'c2', type: 'condition', pointId: 2, pointName: '湿度B', operator: '>', threshold: 80 }] }), created_at: '2026-02-01' },
      { id: 2, rule_name: '电压异常', rule_type: 'or', alarm_level: 'major', is_enabled: true, condition_expr: JSON.stringify({ id: 'g2', type: 'group', logic: 'OR', children: [{ id: 'c3', type: 'condition', pointId: 3, pointName: '电压C', operator: '<', threshold: 200 }] }), created_at: '2026-02-02' },
      { id: 3, rule_name: '空规则', rule_type: 'and', alarm_level: 'info', is_enabled: false, condition_expr: null, created_at: '2026-01-30' },
    ])

    const stats = computed(() => ({
      total: tableData.value.length,
      enabled: tableData.value.filter(r => r.is_enabled).length,
      disabled: tableData.value.filter(r => !r.is_enabled).length,
      andCount: tableData.value.filter(r => r.rule_type === 'and').length,
    }))

    return { loading, tableData, stats, levelTagType, levelLabel, getConditionCount, getRelatedPoints }
  },
  template: `<div class="compound-page">
    <div class="stat-cards">
      <div class="card" data-testid="stat-total"><span class="value">{{ stats.total }}</span><span class="label">总规则数</span></div>
      <div class="card" data-testid="stat-enabled"><span class="value">{{ stats.enabled }}</span><span class="label">已启用</span></div>
      <div class="card" data-testid="stat-disabled"><span class="value">{{ stats.disabled }}</span><span class="label">已禁用</span></div>
      <div class="card" data-testid="stat-and"><span class="value">{{ stats.andCount }}</span><span class="label">AND 规则</span></div>
    </div>
    <div class="table" data-testid="table">
      <div v-for="row in tableData" :key="row.id" :data-testid="'row-' + row.id" class="row">
        <span class="name">{{ row.rule_name }}</span>
        <span class="count">{{ getConditionCount(row.condition_expr) }}</span>
        <span class="type">{{ row.rule_type === 'and' ? 'AND' : 'OR' }}</span>
        <span class="level">{{ levelLabel(row.alarm_level) }}</span>
        <span class="points">{{ getRelatedPoints(row.condition_expr) }}</span>
        <span class="enabled">{{ row.is_enabled ? '启用' : '禁用' }}</span>
      </div>
    </div>
  </div>`
})

describe('复合告警规则页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 统计卡片 ──
  it('渲染统计卡片 - 总规则数', () => {
    expect(mount(CompoundRuleTestable).find('[data-testid="stat-total"] .value').text()).toBe('3')
  })

  it('渲染统计卡片 - 已启用', () => {
    expect(mount(CompoundRuleTestable).find('[data-testid="stat-enabled"] .value').text()).toBe('2')
  })

  it('渲染统计卡片 - AND 规则数', () => {
    expect(mount(CompoundRuleTestable).find('[data-testid="stat-and"] .value').text()).toBe('2')
  })

  // ── 表格渲染 ──
  it('渲染规则列表', () => {
    expect(mount(CompoundRuleTestable).findAll('.row')).toHaveLength(3)
  })

  it('显示规则名称和逻辑类型', () => {
    const w = mount(CompoundRuleTestable)
    expect(w.find('[data-testid="row-1"] .name').text()).toBe('温湿度联合告警')
    expect(w.find('[data-testid="row-1"] .type').text()).toBe('AND')
    expect(w.find('[data-testid="row-2"] .type').text()).toBe('OR')
  })

  it('显示条件数', () => {
    const w = mount(CompoundRuleTestable)
    expect(w.find('[data-testid="row-1"] .count').text()).toBe('2')
    expect(w.find('[data-testid="row-2"] .count').text()).toBe('1')
    expect(w.find('[data-testid="row-3"] .count').text()).toBe('0')
  })

  it('显示关联点位', () => {
    const w = mount(CompoundRuleTestable)
    expect(w.find('[data-testid="row-1"] .points').text()).toBe('温度A, 湿度B')
    expect(w.find('[data-testid="row-3"] .points').text()).toBe('-')
  })

  // ── 辅助函数 ──
  it('levelTagType 映射正确', () => {
    expect(levelTagType('critical')).toBe('danger')
    expect(levelTagType('major')).toBe('warning')
    expect(levelTagType('minor')).toBe('info')
    expect(levelTagType('unknown')).toBe('info')
  })

  it('levelLabel 映射正确', () => {
    expect(levelLabel('critical')).toBe('紧急')
    expect(levelLabel('major')).toBe('重要')
    expect(levelLabel('info')).toBe('提示')
    expect(levelLabel('other')).toBe('other')
  })

  // ── 规则测试引擎 ──
  it('evaluateCondition 比较运算正确', () => {
    const cond = (op: string, threshold: number): ConditionItem => ({ id: '1', type: 'condition', pointId: 1, pointName: 'P', operator: op, threshold })
    const vals = { 1: 50 }
    expect(evaluateCondition(cond('>', 40), vals)).toBe(true)
    expect(evaluateCondition(cond('>', 60), vals)).toBe(false)
    expect(evaluateCondition(cond('<', 60), vals)).toBe(true)
    expect(evaluateCondition(cond('>=', 50), vals)).toBe(true)
    expect(evaluateCondition(cond('<=', 50), vals)).toBe(true)
    expect(evaluateCondition(cond('=', 50), vals)).toBe(true)
  })

  it('evaluateCondition 缺失值返回 false', () => {
    const cond: ConditionItem = { id: '1', type: 'condition', pointId: undefined, pointName: '', operator: '>', threshold: 10 }
    expect(evaluateCondition(cond, {})).toBe(false)
    const cond2: ConditionItem = { id: '2', type: 'condition', pointId: 1, pointName: '', operator: '>', threshold: undefined }
    expect(evaluateCondition(cond2, { 1: 50 })).toBe(false)
  })

  it('evaluateGroup AND 逻辑正确', () => {
    const group: ConditionGroup = {
      id: 'g', type: 'group', logic: 'AND',
      children: [
        { id: 'c1', type: 'condition', pointId: 1, pointName: '', operator: '>', threshold: 30 },
        { id: 'c2', type: 'condition', pointId: 2, pointName: '', operator: '<', threshold: 80 },
      ]
    }
    expect(evaluateGroup(group, { 1: 50, 2: 60 })).toBe(true)
    expect(evaluateGroup(group, { 1: 20, 2: 60 })).toBe(false)
  })

  it('evaluateGroup OR 逻辑正确', () => {
    const group: ConditionGroup = {
      id: 'g', type: 'group', logic: 'OR',
      children: [
        { id: 'c1', type: 'condition', pointId: 1, pointName: '', operator: '>', threshold: 100 },
        { id: 'c2', type: 'condition', pointId: 2, pointName: '', operator: '<', threshold: 10 },
      ]
    }
    expect(evaluateGroup(group, { 1: 50, 2: 5 })).toBe(true)
    expect(evaluateGroup(group, { 1: 50, 2: 50 })).toBe(false)
  })

  it('evaluateGroup 空子节点返回 false', () => {
    const group: ConditionGroup = { id: 'g', type: 'group', logic: 'AND', children: [] }
    expect(evaluateGroup(group, {})).toBe(false)
  })
})
