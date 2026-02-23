/**
 * 阈值配置页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))
vi.mock('@/api/modules/threshold', () => ({
  getThresholdList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createThreshold: vi.fn().mockResolvedValue({}),
  updateThreshold: vi.fn().mockResolvedValue({}),
  deleteThreshold: vi.fn().mockResolvedValue({}),
  setFourLevelThresholds: vi.fn().mockResolvedValue({}),
  batchSetByDeviceType: vi.fn().mockResolvedValue({ success_count: 0 }),
}))
vi.mock('@/api/modules/point', () => ({
  getPointList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))
vi.mock('@/api/modules/history', () => ({
  getPointTrend: vi.fn().mockResolvedValue([]),
}))
vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), dispose: vi.fn() })),
}))

// ── 从 thresholds.vue 提取的辅助函数 ──
function formatThVal(val: number | null): string {
  return val != null ? String(val) : '-'
}

// ── 聚合行类型 ──
interface ThresholdRow {
  point_id: number
  point_name: string
  point_code: string
  device_type: string
  info_value: number | null
  minor_value: number | null
  major_value: number | null
  critical_value: number | null
  is_enabled: boolean
  updated_at: string
  ids: Record<string, number>
}

// ── 可测试的阈值配置组件 ──
const ThresholdTestable = defineComponent({
  name: 'ThresholdTestable',
  setup() {
    const loading = ref(false)
    const tableData = ref<ThresholdRow[]>([
      { point_id: 1, point_name: '温度传感器A', point_code: 'TEMP-A01', device_type: 'UPS', info_value: 20, minor_value: 25, major_value: 30, critical_value: 35, is_enabled: true, updated_at: '2026-02-01', ids: { low_low: 1, low: 2, high: 3, high_high: 4 } },
      { point_id: 2, point_name: '湿度传感器B', point_code: 'HUM-B01', device_type: '空调', info_value: null, minor_value: 60, major_value: 80, critical_value: null, is_enabled: true, updated_at: '2026-02-02', ids: { low: 5, high: 6 } },
      { point_id: 3, point_name: '电压传感器C', point_code: 'VOLT-C01', device_type: 'UPS', info_value: null, minor_value: null, major_value: null, critical_value: null, is_enabled: false, updated_at: '2026-01-30', ids: {} },
    ])
    const selectedRows = ref<ThresholdRow[]>([])
    const filters = reactive({ deviceType: '', thresholdType: '', isEnabled: undefined as boolean | undefined })

    const stats = computed(() => {
      const all = tableData.value
      const dtSet = new Set(all.map(r => r.device_type).filter(Boolean))
      return {
        total: all.length,
        enabled: all.filter(r => r.is_enabled).length,
        disabled: all.filter(r => !r.is_enabled).length,
        deviceTypes: dtSet.size,
      }
    })

    const filteredData = computed(() => {
      let rows = tableData.value
      if (filters.deviceType) rows = rows.filter(r => r.device_type === filters.deviceType)
      if (typeof filters.isEnabled === 'boolean') rows = rows.filter(r => r.is_enabled === filters.isEnabled)
      return rows
    })

    const deviceTypeOptions = computed(() => {
      const types = new Set<string>()
      tableData.value.forEach(r => { if (r.device_type) types.add(r.device_type) })
      return Array.from(types)
    })

    function handleSelectionChange(rows: ThresholdRow[]) { selectedRows.value = rows }

    return { loading, tableData, selectedRows, filters, stats, filteredData, deviceTypeOptions, handleSelectionChange, formatThVal }
  },
  template: `<div class="threshold-page">
    <div class="stat-cards">
      <div class="card" data-testid="stat-total"><span class="value">{{ stats.total }}</span><span class="label">总规则数</span></div>
      <div class="card" data-testid="stat-enabled"><span class="value">{{ stats.enabled }}</span><span class="label">已启用</span></div>
      <div class="card" data-testid="stat-disabled"><span class="value">{{ stats.disabled }}</span><span class="label">已禁用</span></div>
      <div class="card" data-testid="stat-types"><span class="value">{{ stats.deviceTypes }}</span><span class="label">设备类型数</span></div>
    </div>
    <div class="table" data-testid="table">
      <div v-for="row in filteredData" :key="row.point_id" :data-testid="'row-' + row.point_id" class="row">
        <span class="name">{{ row.point_name }}</span>
        <span class="code">{{ row.point_code }}</span>
        <span class="dt">{{ row.device_type || '-' }}</span>
        <span class="info">{{ formatThVal(row.info_value) }}</span>
        <span class="minor">{{ formatThVal(row.minor_value) }}</span>
        <span class="major">{{ formatThVal(row.major_value) }}</span>
        <span class="critical">{{ formatThVal(row.critical_value) }}</span>
        <span class="enabled">{{ row.is_enabled ? '启用' : '禁用' }}</span>
      </div>
    </div>
    <span data-testid="selected-count">{{ selectedRows.length }}</span>
  </div>`
})

describe('阈值配置页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 统计卡片 ──
  it('渲染统计卡片 - 总规则数', () => {
    const w = mount(ThresholdTestable)
    expect(w.find('[data-testid="stat-total"] .value').text()).toBe('3')
  })

  it('渲染统计卡片 - 已启用', () => {
    const w = mount(ThresholdTestable)
    expect(w.find('[data-testid="stat-enabled"] .value').text()).toBe('2')
  })

  it('渲染统计卡片 - 已禁用', () => {
    const w = mount(ThresholdTestable)
    expect(w.find('[data-testid="stat-disabled"] .value').text()).toBe('1')
  })

  it('渲染统计卡片 - 设备类型数', () => {
    const w = mount(ThresholdTestable)
    expect(w.find('[data-testid="stat-types"] .value').text()).toBe('2')
  })

  // ── 表格渲染 ──
  it('渲染阈值列表', () => {
    const w = mount(ThresholdTestable)
    expect(w.findAll('.row')).toHaveLength(3)
  })

  it('显示点位名称和编码', () => {
    const w = mount(ThresholdTestable)
    const row1 = w.find('[data-testid="row-1"]')
    expect(row1.find('.name').text()).toBe('温度传感器A')
    expect(row1.find('.code').text()).toBe('TEMP-A01')
  })

  it('显示阈值数值', () => {
    const w = mount(ThresholdTestable)
    const row1 = w.find('[data-testid="row-1"]')
    expect(row1.find('.info').text()).toBe('20')
    expect(row1.find('.minor').text()).toBe('25')
    expect(row1.find('.major').text()).toBe('30')
    expect(row1.find('.critical').text()).toBe('35')
  })

  it('阈值为 null 时显示 -', () => {
    const w = mount(ThresholdTestable)
    const row2 = w.find('[data-testid="row-2"]')
    expect(row2.find('.info').text()).toBe('-')
    expect(row2.find('.critical').text()).toBe('-')
  })

  // ── 辅助函数 ──
  it('formatThVal 格式化阈值', () => {
    expect(formatThVal(42)).toBe('42')
    expect(formatThVal(0)).toBe('0')
    expect(formatThVal(null)).toBe('-')
  })

  // ── 筛选逻辑 ──
  it('按设备类型筛选', async () => {
    const w = mount(ThresholdTestable)
    w.vm.filters.deviceType = 'UPS'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(2)
  })

  it('按启用状态筛选', async () => {
    const w = mount(ThresholdTestable)
    w.vm.filters.isEnabled = false
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
    expect(w.find('.row .name').text()).toBe('电压传感器C')
  })

  it('设备类型选项正确', () => {
    const w = mount(ThresholdTestable)
    expect(w.vm.deviceTypeOptions).toContain('UPS')
    expect(w.vm.deviceTypeOptions).toContain('空调')
    expect(w.vm.deviceTypeOptions).toHaveLength(2)
  })
})
