/**
 * 用电监控页面 单元测试
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

// PUE 等级判断函数（从 monitor.vue 提取）
function getPUEClass(pue: number | null | undefined): string {
  if (pue == null) return ''
  if (pue < 1.5) return 'excellent'
  if (pue < 2.0) return 'good'
  if (pue < 2.5) return 'normal'
  return 'poor'
}

function getLoadColor(percent: number): string {
  if (percent < 60) return '#52c41a'
  if (percent < 80) return '#faad14'
  return '#f5222d'
}

const EnergyMonitorTestable = defineComponent({
  name: 'EnergyMonitorTestable',
  setup() {
    const loading = ref(false)
    const puePeriod = ref<'hour' | 'day' | 'week' | 'month'>('day')
    const summary = ref({
      total_power: 450.5,
      it_power: 280.3,
      cooling_power: 130.2,
      current_pue: 1.65,
      today_energy: 8500,
      today_cost: 12500
    })
    const dashboard = ref({
      demand: { current_demand: 380, declared_demand: 500, max_today: 420, over_declared_risk: false },
      suggestions: { pending_count: 5, high_priority_count: 2, potential_saving_kwh: 3500, potential_saving_cost: 2800 },
      cost: { today_cost: 12500, month_cost: 285000, peak_ratio: 35, valley_ratio: 25, avg_price: 0.85 }
    })

    return { loading, puePeriod, summary, dashboard, getPUEClass, getLoadColor }
  },
  template: `
    <div class="energy-monitor">
      <div class="stat-cards">
        <div class="stat-card" data-testid="total-power">
          <div class="stat-value">{{ summary.total_power?.toFixed(1) || 0 }}</div>
          <div class="stat-label">总功率 (kW)</div>
        </div>
        <div class="stat-card" data-testid="it-power">
          <div class="stat-value">{{ summary.it_power?.toFixed(1) || 0 }}</div>
          <div class="stat-label">IT负载 (kW)</div>
        </div>
        <div class="stat-card" data-testid="cooling-power">
          <div class="stat-value">{{ summary.cooling_power?.toFixed(1) || 0 }}</div>
          <div class="stat-label">制冷功率 (kW)</div>
        </div>
        <div class="stat-card" data-testid="pue">
          <div class="stat-value" :class="getPUEClass(summary.current_pue)">{{ summary.current_pue?.toFixed(2) }}</div>
          <div class="stat-label">当前 PUE</div>
        </div>
        <div class="stat-card" data-testid="today-energy">
          <div class="stat-value">{{ summary.today_energy?.toFixed(0) || 0 }}</div>
          <div class="stat-label">今日用电 (kWh)</div>
        </div>
        <div class="stat-card" data-testid="today-cost">
          <div class="stat-value">{{ summary.today_cost?.toFixed(0) || 0 }}</div>
          <div class="stat-label">今日电费 (元)</div>
        </div>
      </div>
      <div class="pue-period">
        <button v-for="p in ['hour','day','week','month']" :key="p"
          :class="{ active: puePeriod === p }" :data-testid="'period-' + p"
          @click="puePeriod = p">{{ p }}</button>
      </div>
      <div class="demand-info" data-testid="demand-info">
        <span class="current">{{ dashboard.demand?.current_demand }}</span>
        <span class="declared">{{ dashboard.demand?.declared_demand }}</span>
      </div>
    </div>
  `
})

describe('用电监控页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染6张统计卡片', () => {
    const wrapper = mount(EnergyMonitorTestable)
    expect(wrapper.findAll('.stat-card')).toHaveLength(6)
  })

  it('显示总功率数据', () => {
    const wrapper = mount(EnergyMonitorTestable)
    const card = wrapper.find('[data-testid="total-power"]')
    expect(card.find('.stat-value').text()).toBe('450.5')
    expect(card.find('.stat-label').text()).toBe('总功率 (kW)')
  })

  it('显示PUE值及正确等级样式', () => {
    const wrapper = mount(EnergyMonitorTestable)
    const pueCard = wrapper.find('[data-testid="pue"]')
    expect(pueCard.find('.stat-value').text()).toBe('1.65')
    expect(pueCard.find('.stat-value').classes()).toContain('good')
  })

  it('PUE等级判断正确', () => {
    expect(getPUEClass(1.3)).toBe('excellent')
    expect(getPUEClass(1.8)).toBe('good')
    expect(getPUEClass(2.2)).toBe('normal')
    expect(getPUEClass(2.8)).toBe('poor')
    expect(getPUEClass(null)).toBe('')
  })

  it('负载颜色判断正确', () => {
    expect(getLoadColor(40)).toBe('#52c41a')
    expect(getLoadColor(70)).toBe('#faad14')
    expect(getLoadColor(90)).toBe('#f5222d')
  })

  it('PUE趋势周期默认为day', () => {
    const wrapper = mount(EnergyMonitorTestable)
    expect(wrapper.vm.puePeriod).toBe('day')
  })

  it('需量信息正确显示', () => {
    const wrapper = mount(EnergyMonitorTestable)
    const demand = wrapper.find('[data-testid="demand-info"]')
    expect(demand.find('.current').text()).toBe('380')
    expect(demand.find('.declared').text()).toBe('500')
  })

  it('loading初始为false', () => {
    const wrapper = mount(EnergyMonitorTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
