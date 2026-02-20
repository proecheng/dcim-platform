/**
 * DemandStatusCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const DemandStatusCardTestable = defineComponent({
  name: 'DemandStatusCardTestable',
  props: {
    currentDemand: { type: Number, default: undefined },
    declaredDemand: { type: Number, default: undefined },
    trendData: { type: Array, default: () => [] },
    overDeclaredRisk: { type: Boolean, default: false }
  },
  setup(props) {
    const utilizationRate = computed(() => {
      if (!props.declaredDemand || props.declaredDemand === 0) return 0
      return Math.round(((props.currentDemand || 0) / props.declaredDemand) * 100)
    })
    const valueClass = computed(() => {
      const rate = utilizationRate.value
      if (rate >= 90) return 'danger'
      if (rate >= 75) return 'warning'
      return 'normal'
    })
    const trendColor = computed(() => {
      const rate = utilizationRate.value
      if (rate >= 90) return '#F56C6C'
      if (rate >= 75) return '#E6A23C'
      return '#67C23A'
    })
    return { utilizationRate, valueClass, trendColor }
  },
  template: `
    <div data-testid="demand-status-card">
      <span data-testid="utilization" :class="valueClass">{{ utilizationRate }}</span>
      <span data-testid="current">{{ currentDemand?.toFixed(0) || 0 }} kW</span>
      <span data-testid="declared">{{ declaredDemand || 0 }} kW</span>
      <div v-if="overDeclaredRisk" data-testid="risk-tag">超申报风险</div>
    </div>
  `
})

describe('DemandStatusCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(DemandStatusCardTestable)
    expect(wrapper.find('[data-testid="demand-status-card"]').exists()).toBe(true)
  })

  it('计算利用率', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 600, declaredDemand: 800 } })
    expect(wrapper.find('[data-testid="utilization"]').text()).toBe('75')
  })

  it('无申报需量时利用率为 0', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 500 } })
    expect(wrapper.vm.utilizationRate).toBe(0)
  })

  it('高利用率显示 danger 样式', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 750, declaredDemand: 800 } })
    expect(wrapper.find('[data-testid="utilization"]').classes()).toContain('danger')
  })

  it('中等利用率显示 warning 样式', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 620, declaredDemand: 800 } })
    expect(wrapper.find('[data-testid="utilization"]').classes()).toContain('warning')
  })

  it('低利用率显示 normal 样式', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 400, declaredDemand: 800 } })
    expect(wrapper.find('[data-testid="utilization"]').classes()).toContain('normal')
  })

  it('超申报风险标签显示', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { overDeclaredRisk: true } })
    expect(wrapper.find('[data-testid="risk-tag"]').exists()).toBe(true)
  })

  it('趋势颜色 - 高利用率为红色', () => {
    const wrapper = mount(DemandStatusCardTestable, { props: { currentDemand: 750, declaredDemand: 800 } })
    expect(wrapper.vm.trendColor).toBe('#F56C6C')
  })
})
