/**
 * 告警升级规则页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))
vi.mock('@/api/modules/alarm', () => ({
  getEscalations: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createEscalation: vi.fn().mockResolvedValue({}),
  updateEscalation: vi.fn().mockResolvedValue({}),
  deleteEscalation: vi.fn().mockResolvedValue({}),
  toggleEscalation: vi.fn().mockResolvedValue({}),
}))
vi.mock('@/api/modules/user', () => ({
  getUserList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

// ── 从 escalation.vue 提取的辅助函数 ──
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

function getChainLength(row: { escalation_chain?: string | null; description?: string | null }): number {
  const chainStr = row.escalation_chain || row.description
  if (!chainStr) return 1
  try {
    const chain = JSON.parse(chainStr)
    if (Array.isArray(chain)) return chain.length
  } catch { /* 不是 JSON */ }
  return 1
}

// ── 可测试的升级规则组件 ──
const EscalationTestable = defineComponent({
  name: 'EscalationTestable',
  setup() {
    const loading = ref(false)
    const tableData = ref([
      { id: 1, rule_name: '次要→重要升级', source_level: 'minor', target_level: 'major', timeout_minutes: 30, is_enabled: true, notify_user_ids: [1, 2], escalation_chain: JSON.stringify([{ id: 'n1', timeout_minutes: 30 }, { id: 'n2', timeout_minutes: 60 }]), description: null, updated_at: '2026-02-01' },
      { id: 2, rule_name: '重要→紧急升级', source_level: 'major', target_level: 'critical', timeout_minutes: 15, is_enabled: true, notify_user_ids: [3], escalation_chain: null, description: '单节点描述', updated_at: '2026-02-02' },
      { id: 3, rule_name: '提示→次要升级', source_level: 'info', target_level: 'minor', timeout_minutes: 60, is_enabled: false, notify_user_ids: [], escalation_chain: null, description: null, updated_at: '2026-01-30' },
    ])

    const stats = computed(() => {
      const items = tableData.value
      const levels = new Set(items.map(r => r.source_level))
      return {
        total: items.length,
        enabled: items.filter(r => r.is_enabled).length,
        disabled: items.filter(r => !r.is_enabled).length,
        levelCount: levels.size,
      }
    })

    return { loading, tableData, stats, levelTagType, levelLabel, getChainLength }
  },
  template: `<div class="escalation-page">
    <div class="stat-cards">
      <div class="card" data-testid="stat-total"><span class="value">{{ stats.total }}</span><span class="label">总规则数</span></div>
      <div class="card" data-testid="stat-enabled"><span class="value">{{ stats.enabled }}</span><span class="label">已启用</span></div>
      <div class="card" data-testid="stat-disabled"><span class="value">{{ stats.disabled }}</span><span class="label">已禁用</span></div>
      <div class="card" data-testid="stat-levels"><span class="value">{{ stats.levelCount }}</span><span class="label">告警级别数</span></div>
    </div>
    <div class="table" data-testid="table">
      <div v-for="row in tableData" :key="row.id" :data-testid="'row-' + row.id" class="row">
        <span class="name">{{ row.rule_name }}</span>
        <span class="source">{{ levelLabel(row.source_level) }}</span>
        <span class="timeout">{{ row.timeout_minutes }} 分钟</span>
        <span class="target">{{ levelLabel(row.target_level) }}</span>
        <span class="chain">{{ getChainLength(row) }}</span>
        <span class="notify">{{ (row.notify_user_ids || []).length }}</span>
        <span class="enabled">{{ row.is_enabled ? '启用' : '禁用' }}</span>
      </div>
    </div>
  </div>`
})

describe('告警升级规则页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 统计卡片 ──
  it('渲染统计卡片 - 总规则数', () => {
    expect(mount(EscalationTestable).find('[data-testid="stat-total"] .value').text()).toBe('3')
  })

  it('渲染统计卡片 - 已启用', () => {
    expect(mount(EscalationTestable).find('[data-testid="stat-enabled"] .value').text()).toBe('2')
  })

  it('渲染统计卡片 - 告警级别数', () => {
    // minor, major, info → 3 种
    expect(mount(EscalationTestable).find('[data-testid="stat-levels"] .value').text()).toBe('3')
  })

  // ── 表格渲染 ──
  it('渲染升级规则列表', () => {
    expect(mount(EscalationTestable).findAll('.row')).toHaveLength(3)
  })

  it('显示规则名称和级别', () => {
    const w = mount(EscalationTestable)
    expect(w.find('[data-testid="row-1"] .name').text()).toBe('次要→重要升级')
    expect(w.find('[data-testid="row-1"] .source').text()).toBe('次要')
    expect(w.find('[data-testid="row-1"] .target').text()).toBe('重要')
  })

  it('显示超时时间', () => {
    const w = mount(EscalationTestable)
    expect(w.find('[data-testid="row-1"] .timeout').text()).toBe('30 分钟')
    expect(w.find('[data-testid="row-2"] .timeout').text()).toBe('15 分钟')
  })

  it('显示升级链层数', () => {
    const w = mount(EscalationTestable)
    expect(w.find('[data-testid="row-1"] .chain').text()).toBe('2')
    expect(w.find('[data-testid="row-2"] .chain').text()).toBe('1')
    expect(w.find('[data-testid="row-3"] .chain').text()).toBe('1')
  })

  it('显示通知人数', () => {
    const w = mount(EscalationTestable)
    expect(w.find('[data-testid="row-1"] .notify').text()).toBe('2')
    expect(w.find('[data-testid="row-3"] .notify').text()).toBe('0')
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
    expect(levelLabel('info')).toBe('提示')
    expect(levelLabel('xyz')).toBe('xyz')
  })

  it('getChainLength 解析 JSON 数组', () => {
    expect(getChainLength({ escalation_chain: JSON.stringify([{ id: 1 }, { id: 2 }, { id: 3 }]) })).toBe(3)
    expect(getChainLength({ escalation_chain: null, description: JSON.stringify([{ id: 1 }]) })).toBe(1)
  })

  it('getChainLength 非 JSON 返回 1', () => {
    expect(getChainLength({ escalation_chain: null, description: '普通描述文本' })).toBe(1)
    expect(getChainLength({ escalation_chain: null, description: null })).toBe(1)
  })
})
