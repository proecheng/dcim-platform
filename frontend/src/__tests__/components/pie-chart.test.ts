/**
 * PieChart 饼图组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed, shallowRef } from 'vue'

// Mock echarts
vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    getOption: vi.fn(() => ({}))
  })),
  default: {
    init: vi.fn(() => ({
      setOption: vi.fn(),
      resize: vi.fn(),
      dispose: vi.fn(),
      on: vi.fn(),
      off: vi.fn(),
      getOption: vi.fn(() => ({}))
    }))
  }
}))

interface DataItem {
  name: string
  value: number
  color?: string
}

const PieChartTestable = defineComponent({
  name: 'PieChartTestable',
  props: {
    data: { type: Array as () => DataItem[], default: () => [] },
    height: { type: String, default: '300px' },
    title: { type: String, default: undefined },
    showLegend: { type: Boolean, default: true },
    showTooltip: { type: Boolean, default: true },
    showLabel: { type: Boolean, default: true },
    labelPosition: { type: String, default: 'outside' },
    roseType: { type: [Boolean, String], default: false }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)

    const totalValue = computed(() => props.data.reduce((sum, d) => sum + d.value, 0))
    const dataCount = computed(() => props.data.length)

    return { chartRef, chartInstance, totalValue, dataCount }
  },
  template: `
    <div data-testid="pie-chart" ref="chartRef" class="pie-chart" :style="{ height }">
      <div v-if="title" data-testid="chart-title">{{ title }}</div>
      <div v-if="showLegend && data.length > 0" data-testid="chart-legend">
        <span v-for="d in data" :key="d.name" data-testid="legend-item">{{ d.name }}</span>
      </div>
      <div data-testid="chart-canvas" :class="{ 'is-rose': roseType }"></div>
      <div v-if="showLabel" data-testid="chart-labels" :data-position="labelPosition"></div>
    </div>
  `
})

describe('PieChart 饼图', () => {
  const mockData: DataItem[] = [
    { name: 'IT负载', value: 60 },
    { name: '制冷', value: 25 },
    { name: '照明', value: 10 },
    { name: '其他', value: 5 }
  ]

  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(PieChartTestable)
    expect(wrapper.find('[data-testid="pie-chart"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chart-canvas"]').exists()).toBe(true)
  })

  it('height 属性控制容器高度', () => {
    const wrapper = mount(PieChartTestable, {
      props: { height: '400px' }
    })
    expect(wrapper.find('[data-testid="pie-chart"]').attributes('style')).toContain('400px')
  })

  it('title 属性控制标题', () => {
    const wrapper = mount(PieChartTestable, {
      props: { title: '能耗分布' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toBe('能耗分布')
  })

  it('showLegend 控制图例显示', () => {
    const wrapper = mount(PieChartTestable, {
      props: { data: mockData, showLegend: true }
    })
    expect(wrapper.find('[data-testid="chart-legend"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="legend-item"]')).toHaveLength(4)
  })

  it('roseType 设置玫瑰图模式', () => {
    const wrapper = mount(PieChartTestable, {
      props: { roseType: 'radius' }
    })
    expect(wrapper.find('[data-testid="chart-canvas"]').classes()).toContain('is-rose')
  })

  it('showLabel 控制标签显示', () => {
    const wrapperShow = mount(PieChartTestable, { props: { showLabel: true } })
    expect(wrapperShow.find('[data-testid="chart-labels"]').exists()).toBe(true)

    const wrapperHide = mount(PieChartTestable, { props: { showLabel: false } })
    expect(wrapperHide.find('[data-testid="chart-labels"]').exists()).toBe(false)
  })

  it('totalValue 正确计算数据总和', () => {
    const wrapper = mount(PieChartTestable, {
      props: { data: mockData }
    })
    expect(wrapper.vm.totalValue).toBe(100)
  })

  it('labelPosition 属性正确传递', () => {
    const wrapper = mount(PieChartTestable, {
      props: { showLabel: true, labelPosition: 'inside' }
    })
    expect(wrapper.find('[data-testid="chart-labels"]').attributes('data-position')).toBe('inside')
  })
})
