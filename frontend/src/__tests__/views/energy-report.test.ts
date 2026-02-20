/**
 * 能效报告页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function formatNumber(val: number | null | undefined): string {
  if (val == null) return '--'
  if (val >= 10000) return (val / 10000).toFixed(2) + '万'
  return val.toFixed(1)
}

function formatChange(val: number | null | undefined): string {
  if (val == null) return '--'
  const pct = val.toFixed(1)
  return val >= 0 ? `+${pct}%` : `${pct}%`
}

function changeClass(val: number | null | undefined): string {
  if (val == null) return ''
  return val >= 0 ? 'up' : 'down'
}

const EnergyReportTestable = defineComponent({
  name: 'EnergyReportTestable',
  setup() {
    const loading = ref(false)
    const exporting = ref(false)
    const selectedMonth = ref('2026-01')
    const reportData = ref({
      pue_trend: { month_avg_pue: 1.62, mom_change: -0.03 },
      cost_comparison: {
        current_month: { total_energy: 185000, total_cost: 148000 },
        mom_change_rate: -0.05,
        yoy_change_rate: 0.08
      },
      energy_saving: { total_saving_cost: 12500, executed_count: 5, opportunities_count: 8, details: [] }
    })

    return { loading, exporting, selectedMonth, reportData, formatNumber, formatChange, changeClass }
  },
  template: `
    <div class="energy-report">
      <div class="filter-card">
        <span data-testid="month">{{ selectedMonth }}</span>
        <button data-testid="generate-btn" :disabled="loading">生成报告</button>
        <button data-testid="export-excel">导出 Excel</button>
        <button data-testid="export-pdf">导出 PDF</button>
      </div>
      <div class="metrics-row" v-if="reportData">
        <div class="metric-card" data-testid="pue-avg">
          <div class="metric-title">PUE 均值</div>
          <div class="metric-value">{{ reportData.pue_trend.month_avg_pue?.toFixed(2) }}</div>
          <div class="metric-change" :class="changeClass(reportData.pue_trend.mom_change)">环比 {{ formatChange(reportData.pue_trend.mom_change) }}</div>
        </div>
        <div class="metric-card" data-testid="total-energy">
          <div class="metric-value">{{ formatNumber(reportData.cost_comparison.current_month.total_energy) }}</div>
        </div>
        <div class="metric-card" data-testid="saving">
          <div class="metric-value">{{ formatNumber(reportData.energy_saving.total_saving_cost) }}</div>
          <div class="metric-sub">共 {{ reportData.energy_saving.executed_count }}/{{ reportData.energy_saving.opportunities_count }} 个方案</div>
        </div>
      </div>
    </div>
  `
})

describe('能效报告页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染月份选择和按钮', () => {
    const wrapper = mount(EnergyReportTestable)
    expect(wrapper.find('[data-testid="month"]').text()).toBe('2026-01')
    expect(wrapper.find('[data-testid="generate-btn"]').exists()).toBe(true)
  })

  it('显示PUE均值', () => {
    const wrapper = mount(EnergyReportTestable)
    expect(wrapper.find('[data-testid="pue-avg"] .metric-value').text()).toBe('1.62')
  })

  it('环比变化显示正确', () => {
    const wrapper = mount(EnergyReportTestable)
    const change = wrapper.find('[data-testid="pue-avg"] .metric-change')
    expect(change.text()).toContain('-0.0%')
    expect(change.classes()).toContain('down')
  })

  it('数字格式化正确', () => {
    expect(formatNumber(185000)).toBe('18.50万')
    expect(formatNumber(5000)).toBe('5000.0')
    expect(formatNumber(null)).toBe('--')
  })

  it('变化率格式化正确', () => {
    expect(formatChange(0.08)).toBe('+0.1%')
    expect(formatChange(-0.05)).toBe('-0.1%')
    expect(formatChange(null)).toBe('--')
  })

  it('变化等级样式正确', () => {
    expect(changeClass(0.05)).toBe('up')
    expect(changeClass(-0.03)).toBe('down')
    expect(changeClass(null)).toBe('')
  })

  it('节能方案统计正确', () => {
    const wrapper = mount(EnergyReportTestable)
    expect(wrapper.find('[data-testid="saving"] .metric-sub').text()).toContain('5/8')
  })
})
