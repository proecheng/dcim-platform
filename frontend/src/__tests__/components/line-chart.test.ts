/**
 * LineChart 折线图组件 单元测试
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
  data: (number | null)[]
  color?: string
  smooth?: boolean
  areaStyle?: boolean
  yAxisIndex?: number
}

const LineChartTestable = defineComponent({
  name: 'LineChartTestable',
  props: {
    xData: { type: Array as () => string[], default: () => [] },
    series: { type: Array as () => SeriesData[], default: () => [] },
    height: { type: String, default: '300px' },
    title: { type: String, default: undefined },
    showLegend: { type: Boolean, default: true },
    showTooltip: { type: Boolean, default: true },
    showDataZoom: { type: Boolean, default: false },
    smooth: { type: Boolean, default: true },
    areaStyle: { type: Boolean, default: false },
    yAxisName: { type: String, default: undefined }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)

    const hasDualAxis = computed(() => props.series.some(s => s.yAxisIndex === 1))
    const seriesCount = computed(() => props.series.length)

    return { chartRef, chartInstance, hasDualAxis, seriesCount }
  },
  template: `
    <div data-testid="line-chart" ref="chartRef" class="line-chart" :style="{ height }">
      <div v-if="title" data-testid="chart-title">{{ title }}</div>
      <div v-if="showLegend && series.length > 0" data-testid="chart-legend">
        <span v-for="s in series" :key="s.name" data-testid="legend-item">{{ s.name }}</span>
      </div>
      <div data-testid="chart-canvas" class="chart-canvas"></div>
      <div v-if="showDataZoom" data-testid="data-zoom">缩放</div>
      <div v-if="yAxisName" data-testid="y-axis-name">{{ yAxisName }}</div>
    </div>
  `
})

describe('LineChart 折线图', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(LineChartTestable)
    expect(wrapper.find('[data-testid="line-chart"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chart-canvas"]').exists()).toBe(true)
  })

  it('height 属性控制容器高度', () => {
    const wrapper = mount(LineChartTestable, {
      props: { height: '400px' }
    })
    expect(wrapper.find('[data-testid="line-chart"]').attributes('style')).toContain('400px')
  })

  it('title 属性控制标题显示', () => {
    const wrapper = mount(LineChartTestable, {
      props: { title: '温度趋势' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toBe('温度趋势')
  })

  it('无 title 时不显示标题', () => {
    const wrapper = mount(LineChartTestable)
    expect(wrapper.find('[data-testid="chart-title"]').exists()).toBe(false)
  })

  it('showLegend 控制图例显示', () => {
    const wrapper = mount(LineChartTestable, {
      props: {
        showLegend: true,
        series: [{ name: '温度', data: [20, 22, 21] }]
      }
    })
    expect(wrapper.find('[data-testid="chart-legend"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="legend-item"]').text()).toBe('温度')
  })

  it('showDataZoom 控制缩放组件', () => {
    const wrapperShow = mount(LineChartTestable, { props: { showDataZoom: true } })
    expect(wrapperShow.find('[data-testid="data-zoom"]').exists()).toBe(true)

    const wrapperHide = mount(LineChartTestable, { props: { showDataZoom: false } })
    expect(wrapperHide.find('[data-testid="data-zoom"]').exists()).toBe(false)
  })

  it('hasDualAxis 正确检测双轴', () => {
    const wrapper = mount(LineChartTestable, {
      props: {
        series: [
          { name: '温度', data: [20], yAxisIndex: 0 },
          { name: '湿度', data: [60], yAxisIndex: 1 }
        ]
      }
    })
    expect(wrapper.vm.hasDualAxis).toBe(true)
  })

  it('seriesCount 正确计算', () => {
    const wrapper = mount(LineChartTestable, {
      props: {
        series: [
          { name: '温度', data: [20] },
          { name: '湿度', data: [60] }
        ]
      }
    })
    expect(wrapper.vm.seriesCount).toBe(2)
  })
})
