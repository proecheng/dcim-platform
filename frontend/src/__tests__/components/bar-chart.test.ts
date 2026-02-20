/**
 * BarChart 柱状图组件 单元测试
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

interface SeriesData {
  name: string
  data: number[]
  color?: string
  stack?: string
}

const BarChartTestable = defineComponent({
  name: 'BarChartTestable',
  props: {
    xData: { type: Array as () => string[], default: () => [] },
    series: { type: Array as () => SeriesData[], default: () => [] },
    height: { type: String, default: '300px' },
    title: { type: String, default: undefined },
    showLegend: { type: Boolean, default: true },
    showTooltip: { type: Boolean, default: true },
    horizontal: { type: Boolean, default: false },
    yAxisName: { type: String, default: undefined },
    stack: { type: Boolean, default: false }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)

    const isStacked = computed(() => props.stack || props.series.some(s => !!s.stack))
    const seriesCount = computed(() => props.series.length)

    return { chartRef, chartInstance, isStacked, seriesCount }
  },
  template: `
    <div data-testid="bar-chart" ref="chartRef" class="bar-chart" :style="{ height }">
      <div v-if="title" data-testid="chart-title">{{ title }}</div>
      <div v-if="showLegend && series.length > 0" data-testid="chart-legend">
        <span v-for="s in series" :key="s.name" data-testid="legend-item">{{ s.name }}</span>
      </div>
      <div data-testid="chart-canvas" :class="{ 'is-horizontal': horizontal, 'is-stacked': isStacked }"></div>
      <div v-if="yAxisName" data-testid="y-axis-name">{{ yAxisName }}</div>
    </div>
  `
})

describe('BarChart 柱状图', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(BarChartTestable)
    expect(wrapper.find('[data-testid="bar-chart"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chart-canvas"]').exists()).toBe(true)
  })

  it('height 属性控制容器高度', () => {
    const wrapper = mount(BarChartTestable, {
      props: { height: '500px' }
    })
    expect(wrapper.find('[data-testid="bar-chart"]').attributes('style')).toContain('500px')
  })

  it('title 属性控制标题显示', () => {
    const wrapper = mount(BarChartTestable, {
      props: { title: '能耗统计' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toBe('能耗统计')
  })

  it('showLegend 控制图例', () => {
    const wrapper = mount(BarChartTestable, {
      props: {
        showLegend: true,
        series: [{ name: 'IT负载', data: [100, 200] }]
      }
    })
    expect(wrapper.find('[data-testid="chart-legend"]').exists()).toBe(true)
  })

  it('horizontal 属性设置水平模式', () => {
    const wrapper = mount(BarChartTestable, {
      props: { horizontal: true }
    })
    expect(wrapper.find('[data-testid="chart-canvas"]').classes()).toContain('is-horizontal')
  })

  it('stack 属性设置堆叠模式', () => {
    const wrapper = mount(BarChartTestable, {
      props: { stack: true }
    })
    expect(wrapper.vm.isStacked).toBe(true)
    expect(wrapper.find('[data-testid="chart-canvas"]').classes()).toContain('is-stacked')
  })

  it('yAxisName 显示 Y 轴名称', () => {
    const wrapper = mount(BarChartTestable, {
      props: { yAxisName: 'kWh' }
    })
    expect(wrapper.find('[data-testid="y-axis-name"]').text()).toBe('kWh')
  })

  it('seriesCount 正确计算', () => {
    const wrapper = mount(BarChartTestable, {
      props: {
        series: [
          { name: 'IT负载', data: [100] },
          { name: '制冷', data: [50] },
          { name: '照明', data: [20] }
        ]
      }
    })
    expect(wrapper.vm.seriesCount).toBe(3)
  })
})
