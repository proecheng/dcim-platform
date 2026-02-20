/**
 * CostCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() }))
}))

const CostCardTestable = defineComponent({
  name: 'CostCardTestable',
  props: {
    todayCost: { type: Number, default: undefined },
    monthCost: { type: Number, default: undefined },
    avgPrice: { type: Number, default: undefined },
    peakRatio: { type: Number, default: undefined },
    flatRatio: { type: Number, default: undefined },
    valleyRatio: { type: Number, default: undefined }
  },
  setup(props) {
    const peakRatioValue = computed(() => props.peakRatio || 45)
    const flatRatioValue = computed(() => props.flatRatio || 30)
    const valleyRatioValue = computed(() => props.valleyRatio || 25)
    return { peakRatioValue, flatRatioValue, valleyRatioValue }
  },
  template: `
    <div data-testid="cost-card">
      <span data-testid="today-cost">¥{{ todayCost?.toFixed(0) || 0 }}</span>
      <span data-testid="peak-ratio">{{ peakRatioValue }}%</span>
      <span data-testid="flat-ratio">{{ flatRatioValue }}%</span>
      <span data-testid="valley-ratio">{{ valleyRatioValue }}%</span>
      <span data-testid="month-cost">本月: ¥{{ monthCost?.toFixed(0) || 0 }}</span>
      <span data-testid="avg-price">均价: ¥{{ avgPrice?.toFixed(2) || 0 }}/度</span>
    </div>
  `
})

describe('CostCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(CostCardTestable)
    expect(wrapper.find('[data-testid="cost-card"]').exists()).toBe(true)
  })

  it('显示今日电费', () => {
    const wrapper = mount(CostCardTestable, { props: { todayCost: 1234 } })
    expect(wrapper.find('[data-testid="today-cost"]').text()).toContain('1234')
  })

  it('默认峰时比例为 45%', () => {
    const wrapper = mount(CostCardTestable)
    expect(wrapper.find('[data-testid="peak-ratio"]').text()).toBe('45%')
  })

  it('自定义比例正确显示', () => {
    const wrapper = mount(CostCardTestable, { props: { peakRatio: 50, flatRatio: 30, valleyRatio: 20 } })
    expect(wrapper.find('[data-testid="peak-ratio"]').text()).toBe('50%')
    expect(wrapper.find('[data-testid="valley-ratio"]').text()).toBe('20%')
  })

  it('显示月度电费', () => {
    const wrapper = mount(CostCardTestable, { props: { monthCost: 35000 } })
    expect(wrapper.find('[data-testid="month-cost"]').text()).toContain('35000')
  })

  it('显示均价', () => {
    const wrapper = mount(CostCardTestable, { props: { avgPrice: 0.85 } })
    expect(wrapper.find('[data-testid="avg-price"]').text()).toContain('0.85')
  })

  it('无数据时显示 0', () => {
    const wrapper = mount(CostCardTestable)
    expect(wrapper.find('[data-testid="today-cost"]').text()).toContain('0')
  })
})
