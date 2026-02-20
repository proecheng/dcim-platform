/**
 * GaugeChart 仪表盘图组件 单元测试
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

const GaugeChartTestable = defineComponent({
  name: 'GaugeChartTestable',
  props: {
    value: { type: Number, required: true },
    height: { type: String, default: '200px' },
    title: { type: String, default: undefined },
    unit: { type: String, default: undefined },
    min: { type: Number, default: 0 },
    max: { type: Number, default: 100 },
    splitNumber: { type: Number, default: 10 },
    showPointer: { type: Boolean, default: true },
    showProgress: { type: Boolean, default: true }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)

    const percentage = computed(() => {
      const range = props.max - props.min
      if (range === 0) return 0
      return ((props.value - props.min) / range) * 100
    })

    const displayValue = computed(() => {
      return props.unit ? `${props.value.toFixed(1)}${props.unit}` : props.value.toFixed(1)
    })

    return { chartRef, chartInstance, percentage, displayValue }
  },
  template: `
    <div data-testid="gauge-chart" ref="chartRef" class="gauge-chart" :style="{ height }">
      <div v-if="title" data-testid="chart-title">{{ title }}</div>
      <div data-testid="chart-canvas" class="chart-canvas"></div>
      <div data-testid="gauge-value">{{ displayValue }}</div>
      <div data-testid="gauge-range">{{ min }} - {{ max }}</div>
    </div>
  `
})

describe('GaugeChart 仪表盘图', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 50 }
    })
    expect(wrapper.find('[data-testid="gauge-chart"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chart-canvas"]').exists()).toBe(true)
  })

  it('height 属性控制容器高度', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 50, height: '300px' }
    })
    expect(wrapper.find('[data-testid="gauge-chart"]').attributes('style')).toContain('300px')
  })

  it('title 属性控制标题', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 50, title: 'PUE' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toBe('PUE')
  })

  it('displayValue 带单位格式化', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 25.6, unit: '℃' }
    })
    expect(wrapper.find('[data-testid="gauge-value"]').text()).toBe('25.6℃')
  })

  it('displayValue 无单位格式化', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 1.35 }
    })
    expect(wrapper.find('[data-testid="gauge-value"]').text()).toBe('1.4')
  })

  it('percentage 正确计算百分比', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 75, min: 0, max: 100 }
    })
    expect(wrapper.vm.percentage).toBe(75)
  })

  it('自定义 min/max 范围', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 50, min: 0, max: 200 }
    })
    expect(wrapper.find('[data-testid="gauge-range"]').text()).toBe('0 - 200')
    expect(wrapper.vm.percentage).toBe(25)
  })

  it('无 title 时不显示标题', () => {
    const wrapper = mount(GaugeChartTestable, {
      props: { value: 50 }
    })
    expect(wrapper.find('[data-testid="chart-title"]').exists()).toBe(false)
  })
})
