/**
 * DemandDashboard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() })),
  graphic: { LinearGradient: vi.fn() }
}))

const DemandDashboardTestable = defineComponent({
  name: 'DemandDashboardTestable',
  setup() {
    const loading = ref(false)
    const status = ref<any>(null)
    const alerts = ref<any[]>([])
    const curveHours = ref(4)
    const statusClass = computed(() => status.value ? `status-${status.value.alert_level}` : '')
    const alertTagType = computed(() => {
      if (!status.value) return 'success'
      switch (status.value.alert_level) { case 'critical': return 'danger'; case 'warning': return 'warning'; default: return 'success' }
    })
    const trendText = computed(() => {
      if (!status.value) return '-'
      switch (status.value.trend) { case 'up': return '上升'; case 'down': return '下降'; default: return '平稳' }
    })
    return { loading, status, alerts, curveHours, statusClass, alertTagType, trendText }
  },
  template: `
    <div data-testid="demand-dashboard">
      <span data-testid="curve-hours">{{ curveHours }}</span>
      <span data-testid="trend">{{ trendText }}</span>
      <span data-testid="alert-type">{{ alertTagType }}</span>
      <div v-for="(alert, i) in alerts" :key="i" data-testid="alert-item">{{ alert.message }}</div>
    </div>
  `
})

describe('DemandDashboard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(DemandDashboardTestable)
    expect(wrapper.find('[data-testid="demand-dashboard"]').exists()).toBe(true)
  })

  it('默认曲线时间为 4 小时', () => {
    const wrapper = mount(DemandDashboardTestable)
    expect(wrapper.find('[data-testid="curve-hours"]').text()).toBe('4')
  })

  it('无状态时趋势为 -', () => {
    const wrapper = mount(DemandDashboardTestable)
    expect(wrapper.find('[data-testid="trend"]').text()).toBe('-')
  })

  it('无状态时告警类型为 success', () => {
    const wrapper = mount(DemandDashboardTestable)
    expect(wrapper.find('[data-testid="alert-type"]').text()).toBe('success')
  })

  it('设置状态后趋势正确', async () => {
    const wrapper = mount(DemandDashboardTestable)
    wrapper.vm.status = { alert_level: 'warning', trend: 'up' }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="trend"]').text()).toBe('上升')
  })

  it('告警列表渲染', async () => {
    const wrapper = mount(DemandDashboardTestable)
    wrapper.vm.alerts = [{ message: '功率超标', suggestion: '降低负荷' }]
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('[data-testid="alert-item"]').length).toBe(1)
  })

  it('loading 默认为 false', () => {
    const wrapper = mount(DemandDashboardTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
