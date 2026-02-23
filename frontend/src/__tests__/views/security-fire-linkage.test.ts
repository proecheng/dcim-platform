/**
 * 消防联动页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

// ── 从 fire-linkage.vue 提取的辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function getLinkageLevel(policy: { trigger_type?: string; actions?: { action_type: string }[] }): string {
  const triggerType = policy.trigger_type || ''
  if (triggerType.includes('alarm') || triggerType.includes('fire')) return 'alarm'
  return 'warning'
}

function formatExecutionStatus(status: string): { type: TagType; label: string } {
  const map: Record<string, { type: TagType; label: string }> = {
    success: { type: 'success', label: '成功' },
    failed: { type: 'danger', label: '失败' },
    partial: { type: 'warning', label: '部分成功' },
    executing: { type: 'primary', label: '执行中' },
  }
  return map[status] || { type: 'info', label: status }
}

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '--'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function formatTriggerType(type: string): string {
  const map: Record<string, string> = {
    smoke_alarm: '烟雾告警',
    fire_alarm: '火灾告警',
    temperature_alarm: '温度告警',
    manual: '手动触发',
  }
  return map[type] || type
}

interface PolicyAction { id: number; action_type: string; sort_order?: number; timeout_seconds?: number; action_config?: Record<string, unknown> }
interface Policy { id: number; name: string; trigger_type: string; is_enabled: boolean; actions?: PolicyAction[] }

function sortedActions(policy: Policy): PolicyAction[] {
  if (!policy.actions) return []
  return [...policy.actions].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
}

function extractTarget(config: Record<string, unknown> | null | undefined): string {
  if (!config) return '--'
  const t = config.target || config.device || config.device_name || config.url || ''
  return String(t) || '--'
}

interface Recovery { id: number; status: string; logs?: { id: number; status: string }[] }

function recoveryProgress(recovery: Recovery): number {
  if (!recovery.logs?.length) return 0
  const done = recovery.logs.filter(l => l.status === 'completed' || l.status === 'skipped').length
  return Math.round((done / recovery.logs.length) * 100)
}

function recoveryDoneCount(recovery: Recovery): number {
  if (!recovery.logs?.length) return 0
  return recovery.logs.filter(l => l.status === 'completed' || l.status === 'skipped').length
}

const FireLinkageTestable = defineComponent({
  name: 'FireLinkageTestable',
  setup() {
    const policies = ref<Policy[]>([
      { id: 1, name: '烟雾联动策略', trigger_type: 'smoke_alarm', is_enabled: true, actions: [
        { id: 10, action_type: 'close_hvac', sort_order: 1 },
        { id: 11, action_type: 'open_door', sort_order: 2 },
      ] },
      { id: 2, name: '温度预警策略', trigger_type: 'temperature_alarm', is_enabled: false, actions: [
        { id: 20, action_type: 'ALARM_NOTIFY', sort_order: 1 },
      ] },
      { id: 3, name: '手动联动', trigger_type: 'manual', is_enabled: true, actions: [] },
    ])

    const totalPolicies = computed(() => policies.value.length)
    const enabledPolicies = computed(() => policies.value.filter(p => p.is_enabled).length)
    const recentTriggerCount = ref(7)
    const avgResponseTime = ref(350)

    const statCards = computed(() => [
      { label: '联动策略总数', value: totalPolicies.value, valueClass: 'primary' },
      { label: '已启用策略', value: enabledPolicies.value, valueClass: 'success' },
      { label: '30天触发次数', value: recentTriggerCount.value, valueClass: 'danger' },
      { label: '平均响应时间', value: avgResponseTime.value > 0 ? `${avgResponseTime.value}ms` : '--', valueClass: 'warning' },
    ])

    const expandedPolicyId = ref<number | null>(null)
    function togglePolicy(id: number) {
      expandedPolicyId.value = expandedPolicyId.value === id ? null : id
    }

    return {
      policies, statCards, totalPolicies, enabledPolicies,
      recentTriggerCount, avgResponseTime, expandedPolicyId, togglePolicy,
    }
  },
  template: `<div class="fire-linkage-page">
    <div class="stat-cards" data-testid="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.label">
        <span class="value" :class="card.valueClass">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
    </div>
    <div class="policy-list" data-testid="policy-list">
      <div v-for="p in policies" :key="p.id" :data-testid="'policy-' + p.id" class="policy-item">
        <span class="name">{{ p.name }}</span>
        <span class="enabled">{{ p.is_enabled ? '已启用' : '未启用' }}</span>
      </div>
    </div>
  </div>`,
})

describe('消防联动页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染统计卡片: 联动策略总数', () => {
    expect(mount(FireLinkageTestable).find('[data-testid="stat-联动策略总数"] .value').text()).toBe('3')
  })

  it('渲染统计卡片: 已启用策略', () => {
    expect(mount(FireLinkageTestable).find('[data-testid="stat-已启用策略"] .value').text()).toBe('2')
  })

  it('渲染统计卡片: 平均响应时间', () => {
    expect(mount(FireLinkageTestable).find('[data-testid="stat-平均响应时间"] .value').text()).toBe('350ms')
  })

  it('渲染策略列表', () => {
    expect(mount(FireLinkageTestable).findAll('.policy-item')).toHaveLength(3)
  })

  it('策略展开/折叠切换', async () => {
    const w = mount(FireLinkageTestable)
    w.vm.togglePolicy(1)
    expect(w.vm.expandedPolicyId).toBe(1)
    w.vm.togglePolicy(1)
    expect(w.vm.expandedPolicyId).toBeNull()
    w.vm.togglePolicy(2)
    expect(w.vm.expandedPolicyId).toBe(2)
  })
})

describe('消防联动 — 辅助函数', () => {
  it('getLinkageLevel: alarm 类型触发', () => {
    expect(getLinkageLevel({ trigger_type: 'smoke_alarm' })).toBe('alarm')
    expect(getLinkageLevel({ trigger_type: 'fire_alarm' })).toBe('alarm')
  })

  it('getLinkageLevel: warning 类型触发', () => {
    expect(getLinkageLevel({ trigger_type: 'manual' })).toBe('warning')
    expect(getLinkageLevel({ trigger_type: 'temperature_warning' })).toBe('warning')
  })

  it('formatExecutionStatus: 各状态映射', () => {
    expect(formatExecutionStatus('success')).toEqual({ type: 'success', label: '成功' })
    expect(formatExecutionStatus('failed')).toEqual({ type: 'danger', label: '失败' })
    expect(formatExecutionStatus('partial')).toEqual({ type: 'warning', label: '部分成功' })
    expect(formatExecutionStatus('unknown')).toEqual({ type: 'info', label: 'unknown' })
  })

  it('formatDuration: 毫秒和秒格式化', () => {
    expect(formatDuration(500)).toBe('500ms')
    expect(formatDuration(1500)).toBe('1.5s')
    expect(formatDuration(null)).toBe('--')
    expect(formatDuration(undefined)).toBe('--')
  })

  it('formatTime: 时间格式化', () => {
    expect(formatTime('2026-02-01T10:00:00.000Z')).toBe('2026-02-01 10:00:00')
    expect(formatTime(null)).toBe('--')
  })

  it('formatTriggerType: 触发类型映射', () => {
    expect(formatTriggerType('smoke_alarm')).toBe('烟雾告警')
    expect(formatTriggerType('fire_alarm')).toBe('火灾告警')
    expect(formatTriggerType('manual')).toBe('手动触发')
    expect(formatTriggerType('custom')).toBe('custom')
  })

  it('sortedActions: 按 sort_order 排序', () => {
    const policy: Policy = {
      id: 1, name: 'test', trigger_type: 'smoke_alarm', is_enabled: true,
      actions: [
        { id: 2, action_type: 'open_door', sort_order: 2 },
        { id: 1, action_type: 'close_hvac', sort_order: 1 },
        { id: 3, action_type: 'ALARM_NOTIFY', sort_order: 3 },
      ],
    }
    const sorted = sortedActions(policy)
    expect(sorted.map(a => a.action_type)).toEqual(['close_hvac', 'open_door', 'ALARM_NOTIFY'])
  })

  it('sortedActions: 空 actions 返回空数组', () => {
    expect(sortedActions({ id: 1, name: 'test', trigger_type: 'manual', is_enabled: true })).toEqual([])
  })

  it('extractTarget: 提取配置目标', () => {
    expect(extractTarget({ target: '设备A' })).toBe('设备A')
    expect(extractTarget({ device: '设备B' })).toBe('设备B')
    expect(extractTarget({ url: 'http://example.com' })).toBe('http://example.com')
    expect(extractTarget(null)).toBe('--')
    expect(extractTarget({})).toBe('--')
  })

  it('recoveryProgress: 计算恢复进度', () => {
    expect(recoveryProgress({ id: 1, status: 'executing', logs: [
      { id: 1, status: 'completed' },
      { id: 2, status: 'executing' },
      { id: 3, status: 'skipped' },
      { id: 4, status: 'pending' },
    ] })).toBe(50)
    expect(recoveryProgress({ id: 1, status: 'completed', logs: [] })).toBe(0)
  })

  it('recoveryDoneCount: 计算完成步骤数', () => {
    expect(recoveryDoneCount({ id: 1, status: 'executing', logs: [
      { id: 1, status: 'completed' },
      { id: 2, status: 'skipped' },
      { id: 3, status: 'pending' },
    ] })).toBe(2)
    expect(recoveryDoneCount({ id: 1, status: 'pending' })).toBe(0)
  })
})
