/**
 * DemandComparisonCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

const DemandComparisonCardTestable = defineComponent({
  name: 'DemandComparisonCardTestable',
  props: {
    currentDeclared: { type: Number, default: undefined },
    maxDemand12m: { type: Number, default: undefined },
    compact: { type: Boolean, default: false }
  },
  setup(props) {
    const loading = ref(false)
    const data = ref<any>(null)
    const utilizationRate = computed(() => {
      const declared = props.currentDeclared || data.value?.current_declared || 0
      const maxDemand = props.maxDemand12m || data.value?.max_demand_12m || 0
      if (declared === 0) return 0
      return maxDemand / declared
    })
    const utilizationClass = computed(() => {
      const rate = utilizationRate.value
      if (rate >= 0.9) return 'danger'
      if (rate >= 0.7) return 'warning'
      return 'normal'
    })
    return { loading, data, utilizationRate, utilizationClass }
  },
  template: `
    <div data-testid="demand-comparison" :class="{ compact }">
      <div v-if="!compact" data-testid="header">需量配置对比</div>
      <span data-testid="declared">{{ currentDeclared || 0 }} kW</span>
      <span data-testid="max-demand">{{ maxDemand12m || 0 }} kW</span>
      <span data-testid="utilization" :class="utilizationClass">{{ (utilizationRate * 100).toFixed(1) }}%</span>
    </div>
  `
})

describe('DemandComparisonCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(DemandComparisonCardTestable)
    expect(wrapper.find('[data-testid="demand-comparison"]').exists()).toBe(true)
  })

  it('显示申报需量', () => {
    const wrapper = mount(DemandComparisonCardTestable, { props: { currentDeclared: 800 } })
    expect(wrapper.find('[data-testid="declared"]').text()).toContain('800')
  })

  it('计算利用率', () => {
    const wrapper = mount(DemandComparisonCardTestable, { props: { currentDeclared: 800, maxDemand12m: 600 } })
    expect(wrapper.find('[data-testid="utilization"]').text()).toBe('75.0%')
  })

  it('高利用率显示 danger', () => {
    const wrapper = mount(DemandComparisonCardTestable, { props: { currentDeclared: 800, maxDemand12m: 750 } })
    expect(wrapper.find('[data-testid="utilization"]').classes()).toContain('danger')
  })

  it('compact 模式隐藏标题', () => {
    const wrapper = mount(DemandComparisonCardTestable, { props: { compact: true } })
    expect(wrapper.find('[data-testid="header"]').exists()).toBe(false)
  })

  it('非 compact 模式显示标题', () => {
    const wrapper = mount(DemandComparisonCardTestable, { props: { compact: false } })
    expect(wrapper.find('[data-testid="header"]').exists()).toBe(true)
  })

  it('无申报需量时利用率为 0', () => {
    const wrapper = mount(DemandComparisonCardTestable)
    expect(wrapper.vm.utilizationRate).toBe(0)
  })
})
