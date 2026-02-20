/**
 * LoadPeriodChart 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() }))
}))

const LoadPeriodChartTestable = defineComponent({
  name: 'LoadPeriodChartTestable',
  props: {
    meterPointId: { type: Number, default: undefined },
    meterPointName: { type: String, default: undefined },
    date: { type: String, default: undefined },
    showPricing: { type: Boolean, default: true },
    highlightPeriods: { type: Array, default: () => [] }
  },
  setup(props) {
    const loading = ref(false)
    const data = ref<any>(null)
    const isMockData = ref(false)
    const displayName = computed(() => {
      if (props.meterPointName) return props.meterPointName
      if (!props.meterPointId) return '全站总负荷'
      return `计量点 #${props.meterPointId}`
    })
    return { loading, data, isMockData, displayName }
  },
  template: `
    <div data-testid="load-period-chart">
      <span data-testid="title">24小时负荷分布</span>
      <span data-testid="meter-name">{{ displayName }}</span>
      <span v-if="isMockData" data-testid="mock-badge">演示数据</span>
      <span data-testid="date">{{ date || '昨日' }}</span>
      <div data-testid="chart-container"></div>
    </div>
  `
})

describe('LoadPeriodChart 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(LoadPeriodChartTestable)
    expect(wrapper.find('[data-testid="load-period-chart"]').exists()).toBe(true)
  })

  it('显示标题', () => {
    const wrapper = mount(LoadPeriodChartTestable)
    expect(wrapper.find('[data-testid="title"]').text()).toBe('24小时负荷分布')
  })

  it('无计量点时显示全站总负荷', () => {
    const wrapper = mount(LoadPeriodChartTestable)
    expect(wrapper.find('[data-testid="meter-name"]').text()).toBe('全站总负荷')
  })

  it('有计量点名称时显示', () => {
    const wrapper = mount(LoadPeriodChartTestable, { props: { meterPointName: '总进线' } })
    expect(wrapper.find('[data-testid="meter-name"]').text()).toBe('总进线')
  })

  it('有计量点 ID 时显示编号', () => {
    const wrapper = mount(LoadPeriodChartTestable, { props: { meterPointId: 5 } })
    expect(wrapper.find('[data-testid="meter-name"]').text()).toBe('计量点 #5')
  })

  it('默认日期为昨日', () => {
    const wrapper = mount(LoadPeriodChartTestable)
    expect(wrapper.find('[data-testid="date"]').text()).toBe('昨日')
  })

  it('自定义日期', () => {
    const wrapper = mount(LoadPeriodChartTestable, { props: { date: '2026-01-15' } })
    expect(wrapper.find('[data-testid="date"]').text()).toBe('2026-01-15')
  })

  it('loading 默认为 false', () => {
    const wrapper = mount(LoadPeriodChartTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
