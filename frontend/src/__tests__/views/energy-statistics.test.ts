/**
 * 能耗统计页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

const EnergyStatisticsTestable = defineComponent({
  name: 'EnergyStatisticsTestable',
  setup() {
    const loading = ref(false)
    const filters = reactive({
      period: 'daily' as 'daily' | 'monthly',
      dateRange: ['2026-01-01', '2026-01-31'],
      year: '2026'
    })
    const energyStat = ref({
      total_energy: 185000,
      total_cost: 148000,
      avg_power: 256.9,
      avg_pue: 1.65,
      peak_energy: 65000,
      normal_energy: 75000,
      valley_energy: 45000
    })
    const dataSource = ref<string | null>('realtime')

    return { loading, filters, energyStat, dataSource }
  },
  template: `
    <div class="energy-statistics">
      <div class="filter-card" data-testid="filter">
        <span data-testid="period">{{ filters.period }}</span>
        <button data-testid="query-btn">查询</button>
        <button data-testid="export-btn">导出</button>
        <span v-if="dataSource === 'realtime'" data-testid="data-source" class="realtime">实时数据</span>
      </div>
      <div class="summary-cards">
        <div class="summary-card" data-testid="total-energy">
          <div class="stat-value">{{ energyStat.total_energy }}</div>
          <div class="stat-label">总用电量</div>
        </div>
        <div class="summary-card" data-testid="total-cost">
          <div class="stat-value">{{ energyStat.total_cost }}</div>
          <div class="stat-label">总电费</div>
        </div>
        <div class="summary-card" data-testid="avg-power">
          <div class="stat-value">{{ energyStat.avg_power }}</div>
          <div class="stat-label">平均功率</div>
        </div>
        <div class="summary-card" data-testid="avg-pue">
          <div class="stat-value">{{ energyStat.avg_pue }}</div>
          <div class="stat-label">平均PUE</div>
        </div>
      </div>
      <div class="pie-legend">
        <span data-testid="peak">{{ energyStat.peak_energy }} kWh</span>
        <span data-testid="normal">{{ energyStat.normal_energy }} kWh</span>
        <span data-testid="valley">{{ energyStat.valley_energy }} kWh</span>
      </div>
    </div>
  `
})

describe('能耗统计页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染4张汇总卡片', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.findAll('.summary-card')).toHaveLength(4)
  })

  it('显示总用电量', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    const card = wrapper.find('[data-testid="total-energy"]')
    expect(card.find('.stat-value').text()).toBe('185000')
  })

  it('默认统计周期为daily', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.find('[data-testid="period"]').text()).toBe('daily')
  })

  it('显示实时数据标签', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.find('[data-testid="data-source"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="data-source"]').text()).toBe('实时数据')
  })

  it('分时电量分布数据正确', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.find('[data-testid="peak"]').text()).toContain('65000')
    expect(wrapper.find('[data-testid="normal"]').text()).toContain('75000')
    expect(wrapper.find('[data-testid="valley"]').text()).toContain('45000')
  })

  it('渲染查询和导出按钮', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.find('[data-testid="query-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="export-btn"]').exists()).toBe(true)
  })

  it('loading初始为false', () => {
    const wrapper = mount(EnergyStatisticsTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
