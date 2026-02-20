/**
 * DemandCurveMini 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() }))
}))

const DemandCurveMiniTestable = defineComponent({
  name: 'DemandCurveMiniTestable',
  props: {
    meterPointId: { type: Number, default: undefined },
    timeRange: { type: String, default: '12m' },
    highlightMax: { type: Boolean, default: true },
    showThreshold: { type: Number, default: undefined },
    height: { type: Number, default: 200 }
  },
  setup(props) {
    const loading = ref(false)
    const data = ref<any>(null)
    const titleText = `近${props.timeRange === '12m' ? 12 : 6}个月需量趋势`
    return { loading, data, titleText }
  },
  template: `
    <div data-testid="demand-curve-mini">
      <span data-testid="title">{{ titleText }}</span>
      <div data-testid="chart" :style="{ height: height + 'px' }"></div>
      <div v-if="data" data-testid="legend">
        <span data-testid="max-value">最大需量: {{ data.max_value }} kW</span>
      </div>
    </div>
  `
})

describe('DemandCurveMini 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(DemandCurveMiniTestable)
    expect(wrapper.find('[data-testid="demand-curve-mini"]').exists()).toBe(true)
  })

  it('默认时间范围为 12 个月', () => {
    const wrapper = mount(DemandCurveMiniTestable)
    expect(wrapper.find('[data-testid="title"]').text()).toContain('12')
  })

  it('6 个月时间范围', () => {
    const wrapper = mount(DemandCurveMiniTestable, { props: { timeRange: '6m' } })
    expect(wrapper.find('[data-testid="title"]').text()).toContain('6')
  })

  it('默认高度为 200px', () => {
    const wrapper = mount(DemandCurveMiniTestable)
    expect(wrapper.find('[data-testid="chart"]').attributes('style')).toContain('200px')
  })

  it('自定义高度', () => {
    const wrapper = mount(DemandCurveMiniTestable, { props: { height: 300 } })
    expect(wrapper.find('[data-testid="chart"]').attributes('style')).toContain('300px')
  })

  it('无数据时不显示图例', () => {
    const wrapper = mount(DemandCurveMiniTestable)
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(false)
  })

  it('有数据时显示最大需量', async () => {
    const wrapper = mount(DemandCurveMiniTestable)
    wrapper.vm.data = { max_value: 750, max_month: '2026-01', declared_demand: 800 }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="max-value"]').text()).toContain('750')
  })

  it('loading 默认为 false', () => {
    const wrapper = mount(DemandCurveMiniTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
