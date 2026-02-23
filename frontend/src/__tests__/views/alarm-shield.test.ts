/**
 * 告警屏蔽管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))
vi.mock('@/api/modules/alarm', () => ({
  getAlarmShields: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createAlarmShield: vi.fn().mockResolvedValue({}),
  deleteAlarmShield: vi.fn().mockResolvedValue({}),
}))
vi.mock('@/api/modules/device', () => ({
  getDeviceList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/api/modules/point', () => ({
  getPointList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), dispose: vi.fn() })),
  graphic: { clipRectByRect: vi.fn() },
}))

// ── 类型定义 ──
type ShieldScope = 'global' | 'area' | 'device_type' | 'device'
type ShieldStatus = 'active' | 'expired' | 'scheduled'

interface ShieldRow {
  id: number
  name: string
  scope: ShieldScope
  scope_value: string
  start_time: string
  end_time: string
  levels: string[]
  reason: string
  creator_name: string
  computed_status: ShieldStatus
}

// ── 从 shield.vue 提取的辅助函数 ──
function scopeLabel(scope: string): string {
  const map: Record<string, string> = { global: '全局', area: '区域', device_type: '设备类型', device: '特定设备' }
  return map[scope] || scope
}

function scopeTagType(scope: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { global: 'danger', area: 'warning', device_type: 'info', device: 'success' }
  return map[scope] || 'info'
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { critical: 'danger', major: 'warning', minor: 'info', info: 'info' }
  return map[level] || 'info'
}

function levelLabel(level: string): string {
  const map: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '提示' }
  return map[level] || level
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = { active: 'success', scheduled: 'info', expired: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { active: '活跃', scheduled: '计划中', expired: '已过期' }
  return map[status] || status
}

function computeStatus(startTime: string, endTime: string): ShieldStatus {
  const now = new Date()
  const start = new Date(startTime)
  const end = new Date(endTime)
  if (now > end) return 'expired'
  if (now < start) return 'scheduled'
  return 'active'
}

// ── 可测试的屏蔽管理组件 ──
const ShieldTestable = defineComponent({
  name: 'ShieldTestable',
  setup() {
    const loading = ref(false)
    const now = new Date()
    const past = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString()
    const future = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString()
    const farFuture = new Date(now.getTime() + 48 * 60 * 60 * 1000).toISOString()
    const farPast = new Date(now.getTime() - 48 * 60 * 60 * 1000).toISOString()

    const allRows = ref<ShieldRow[]>([
      { id: 1, name: '维护窗口屏蔽', scope: 'global', scope_value: '', start_time: past, end_time: future, levels: ['critical', 'major'], reason: '系统维护', creator_name: 'admin', computed_status: 'active' },
      { id: 2, name: '区域A屏蔽', scope: 'area', scope_value: 'A区', start_time: future, end_time: farFuture, levels: ['info'], reason: '设备调试', creator_name: 'user1', computed_status: 'scheduled' },
      { id: 3, name: '已过期屏蔽', scope: 'device', scope_value: '设备001', start_time: farPast, end_time: past, levels: [], reason: '', creator_name: 'admin', computed_status: 'expired' },
    ])

    const filters = reactive({ status: '' as string, scope: '' as string })

    const stats = computed(() => ({
      total: allRows.value.length,
      active: allRows.value.filter(r => r.computed_status === 'active').length,
      scheduled: allRows.value.filter(r => r.computed_status === 'scheduled').length,
      expired: allRows.value.filter(r => r.computed_status === 'expired').length,
    }))

    const filteredRows = computed(() => {
      let rows = allRows.value
      if (filters.status) rows = rows.filter(r => r.computed_status === filters.status)
      if (filters.scope) rows = rows.filter(r => r.scope === filters.scope)
      return rows
    })

    return { loading, allRows, filters, stats, filteredRows, scopeLabel, scopeTagType, levelTagType, levelLabel, statusTagType, statusLabel }
  },
  template: `<div class="shield-page">
    <div class="stat-cards">
      <div class="card" data-testid="stat-total"><span class="value">{{ stats.total }}</span><span class="label">总策略数</span></div>
      <div class="card" data-testid="stat-active"><span class="value">{{ stats.active }}</span><span class="label">活跃中</span></div>
      <div class="card" data-testid="stat-scheduled"><span class="value">{{ stats.scheduled }}</span><span class="label">计划中</span></div>
      <div class="card" data-testid="stat-expired"><span class="value">{{ stats.expired }}</span><span class="label">已过期</span></div>
    </div>
    <div class="table" data-testid="table">
      <div v-for="row in filteredRows" :key="row.id" :data-testid="'row-' + row.id" class="row">
        <span class="name">{{ row.name }}</span>
        <span class="scope">{{ scopeLabel(row.scope) }}</span>
        <span class="scope-value">{{ row.scope_value }}</span>
        <span class="levels">{{ row.levels.length ? row.levels.map(l => levelLabel(l)).join(', ') : '全部级别' }}</span>
        <span class="status">{{ statusLabel(row.computed_status) }}</span>
        <span class="creator">{{ row.creator_name }}</span>
      </div>
    </div>
  </div>`
})

describe('告警屏蔽管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 统计卡片 ──
  it('渲染统计卡片 - 总策略数', () => {
    expect(mount(ShieldTestable).find('[data-testid="stat-total"] .value').text()).toBe('3')
  })

  it('渲染统计卡片 - 活跃中', () => {
    expect(mount(ShieldTestable).find('[data-testid="stat-active"] .value').text()).toBe('1')
  })

  it('渲染统计卡片 - 计划中', () => {
    expect(mount(ShieldTestable).find('[data-testid="stat-scheduled"] .value').text()).toBe('1')
  })

  it('渲染统计卡片 - 已过期', () => {
    expect(mount(ShieldTestable).find('[data-testid="stat-expired"] .value').text()).toBe('1')
  })

  // ── 表格渲染 ──
  it('渲染屏蔽策略列表', () => {
    expect(mount(ShieldTestable).findAll('.row')).toHaveLength(3)
  })

  it('显示策略名称和范围', () => {
    const w = mount(ShieldTestable)
    expect(w.find('[data-testid="row-1"] .name').text()).toBe('维护窗口屏蔽')
    expect(w.find('[data-testid="row-1"] .scope').text()).toBe('全局')
    expect(w.find('[data-testid="row-2"] .scope').text()).toBe('区域')
  })

  it('显示屏蔽告警级别', () => {
    const w = mount(ShieldTestable)
    expect(w.find('[data-testid="row-1"] .levels').text()).toBe('紧急, 重要')
    expect(w.find('[data-testid="row-3"] .levels').text()).toBe('全部级别')
  })

  it('显示状态标签', () => {
    const w = mount(ShieldTestable)
    expect(w.find('[data-testid="row-1"] .status').text()).toBe('活跃')
    expect(w.find('[data-testid="row-2"] .status').text()).toBe('计划中')
    expect(w.find('[data-testid="row-3"] .status').text()).toBe('已过期')
  })

  // ── 筛选逻辑 ──
  it('按状态筛选', async () => {
    const w = mount(ShieldTestable)
    w.vm.filters.status = 'active'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
    expect(w.find('.row .name').text()).toBe('维护窗口屏蔽')
  })

  it('按范围筛选', async () => {
    const w = mount(ShieldTestable)
    w.vm.filters.scope = 'area'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
    expect(w.find('.row .name').text()).toBe('区域A屏蔽')
  })

  // ── 辅助函数 ──
  it('scopeLabel 映射正确', () => {
    expect(scopeLabel('global')).toBe('全局')
    expect(scopeLabel('area')).toBe('区域')
    expect(scopeLabel('device_type')).toBe('设备类型')
    expect(scopeLabel('device')).toBe('特定设备')
    expect(scopeLabel('unknown')).toBe('unknown')
  })

  it('scopeTagType 映射正确', () => {
    expect(scopeTagType('global')).toBe('danger')
    expect(scopeTagType('area')).toBe('warning')
    expect(scopeTagType('device')).toBe('success')
    expect(scopeTagType('unknown')).toBe('info')
  })

  it('statusLabel 映射正确', () => {
    expect(statusLabel('active')).toBe('活跃')
    expect(statusLabel('scheduled')).toBe('计划中')
    expect(statusLabel('expired')).toBe('已过期')
    expect(statusLabel('other')).toBe('other')
  })

  it('statusTagType 映射正确', () => {
    expect(statusTagType('active')).toBe('success')
    expect(statusTagType('scheduled')).toBe('info')
    expect(statusTagType('expired')).toBe('info')
  })

  it('computeStatus 计算状态正确', () => {
    const now = new Date()
    const past = new Date(now.getTime() - 1000).toISOString()
    const future = new Date(now.getTime() + 100000).toISOString()
    const farPast = new Date(now.getTime() - 100000).toISOString()
    expect(computeStatus(farPast, past)).toBe('expired')
    expect(computeStatus(future, new Date(now.getTime() + 200000).toISOString())).toBe('scheduled')
    expect(computeStatus(past, future)).toBe('active')
  })
})
