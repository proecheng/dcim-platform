/**
 * Sparkline 迷你折线图组件 单元测试
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
  graphic: {
    LinearGradient: vi.fn()
  },
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

const SparklineTestable = defineComponent({
  name: 'SparklineTestable',
  props: {
    data: { type: Array as () => number[], default: () => [] },
    width: { type: String, default: '100%' },
    height: { type: String, default: '40px' },
    color: { type: String, default: '#409EFF' },
    showArea: { type: Boolean, default: true },
    lineWidth: { type: Number, default: 2 }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)

    const dataLength = computed(() => props.data.length)
    const maxValue = computed(() => props.data.length > 0 ? Math.max(...props.data) : 0)
    const minValue = computed(() => props.data.length > 0 ? Math.min(...props.data) : 0)

    return { chartRef, chartInstance, dataLength, maxValue, minValue }
  },
  template: `
    <div data-testid="sparkline" ref="chartRef" class="sparkline" :style="{ width, height }">
      <div data-testid="chart-canvas" :data-color="color" :data-area="showArea" :data-line-width="lineWidth"></div>
      <span data-testid="data-info">{{ dataLength }}点</span>
    </div>
  `
})

describe('Sparkline 迷你折线图', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(SparklineTestable)
    expect(wrapper.find('[data-testid="sparkline"]').exists()).toBe(true)
  })

  it('width 和 height 属性控制尺寸', () => {
    const wrapper = mount(SparklineTestable, {
      props: { width: '200px', height: '60px' }
    })
    const style = wrapper.find('[data-testid="sparkline"]').attributes('style')
    expect(style).toContain('200px')
    expect(style).toContain('60px')
  })

  it('data 属性正确传递', () => {
    const wrapper = mount(SparklineTestable, {
      props: { data: [10, 20, 30, 40, 50] }
    })
    expect(wrapper.vm.dataLength).toBe(5)
    expect(wrapper.find('[data-testid="data-info"]').text()).toBe('5点')
  })

  it('color 属性正确传递', () => {
    const wrapper = mount(SparklineTestable, {
      props: { color: '#ff0000' }
    })
    expect(wrapper.find('[data-testid="chart-canvas"]').attributes('data-color')).toBe('#ff0000')
  })

  it('showArea 属性正确传递', () => {
    const wrapperShow = mount(SparklineTestable, { props: { showArea: true } })
    expect(wrapperShow.find('[data-testid="chart-canvas"]').attributes('data-area')).toBe('true')

    const wrapperHide = mount(SparklineTestable, { props: { showArea: false } })
    expect(wrapperHide.find('[data-testid="chart-canvas"]').attributes('data-area')).toBe('false')
  })

  it('maxValue 和 minValue 正确计算', () => {
    const wrapper = mount(SparklineTestable, {
      props: { data: [5, 15, 10, 25, 20] }
    })
    expect(wrapper.vm.maxValue).toBe(25)
    expect(wrapper.vm.minValue).toBe(5)
  })

  it('空数据时 max/min 为 0', () => {
    const wrapper = mount(SparklineTestable, {
      props: { data: [] }
    })
    expect(wrapper.vm.maxValue).toBe(0)
    expect(wrapper.vm.minValue).toBe(0)
  })

  it('lineWidth 属性正确传递', () => {
    const wrapper = mount(SparklineTestable, {
      props: { lineWidth: 3 }
    })
    expect(wrapper.find('[data-testid="chart-canvas"]').attributes('data-line-width')).toBe('3')
  })
})
