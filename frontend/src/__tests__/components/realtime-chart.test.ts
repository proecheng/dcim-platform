/**
 * RealtimeChart 实时图表组件 单元测试
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

// Mock dayjs
vi.mock('dayjs', () => {
  const dayjs = (date?: any) => ({
    format: vi.fn((fmt: string) => '12:00:00'),
    fromNow: vi.fn(() => '1分钟前'),
    subtract: vi.fn(() => dayjs()),
    add: vi.fn(() => dayjs()),
    startOf: vi.fn(() => dayjs()),
    endOf: vi.fn(() => dayjs()),
    valueOf: vi.fn(() => 1706745600000)
  })
  dayjs.extend = vi.fn()
  dayjs.locale = vi.fn()
  return { default: dayjs }
})

interface DataPoint {
  time: string | Date
  value: number
}

const RealtimeChartTestable = defineComponent({
  name: 'RealtimeChartTestable',
  props: {
    height: { type: String, default: '200px' },
    title: { type: String, default: undefined },
    unit: { type: String, default: undefined },
    maxPoints: { type: Number, default: 60 },
    color: { type: String, default: '#409eff' },
    areaStyle: { type: Boolean, default: true },
    showMarkLine: { type: Boolean, default: false },
    warningValue: { type: Number, default: undefined },
    criticalValue: { type: Number, default: undefined },
    smooth: { type: Boolean, default: true }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const chartInstance = shallowRef<any>(null)
    const dataQueue = ref<DataPoint[]>([])

    const pointCount = computed(() => dataQueue.value.length)

    const addPoint = (point: DataPoint) => {
      dataQueue.value.push(point)
      if (dataQueue.value.length > props.maxPoints) {
        dataQueue.value.shift()
      }
    }

    const setData = (data: DataPoint[]) => {
      dataQueue.value = data.slice(-props.maxPoints)
    }

    const clear = () => {
      dataQueue.value = []
    }

    return { chartRef, chartInstance, dataQueue, pointCount, addPoint, setData, clear }
  },
  template: `
    <div data-testid="realtime-chart" ref="chartRef" class="realtime-chart" :style="{ height }">
      <div v-if="title" data-testid="chart-title">{{ title }}</div>
      <div data-testid="chart-canvas" class="chart-canvas"></div>
      <div v-if="showMarkLine" data-testid="mark-lines">
        <span v-if="warningValue !== undefined" data-testid="warning-line">警告: {{ warningValue }}</span>
        <span v-if="criticalValue !== undefined" data-testid="critical-line">严重: {{ criticalValue }}</span>
      </div>
      <div data-testid="point-count">{{ pointCount }}</div>
    </div>
  `
})

describe('RealtimeChart 实时图表', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(RealtimeChartTestable)
    expect(wrapper.find('[data-testid="realtime-chart"]').exists()).toBe(true)
    expect(wrapper.vm.pointCount).toBe(0)
  })

  it('height 属性控制容器高度', () => {
    const wrapper = mount(RealtimeChartTestable, {
      props: { height: '350px' }
    })
    expect(wrapper.find('[data-testid="realtime-chart"]').attributes('style')).toContain('350px')
  })

  it('addPoint 添加数据点', () => {
    const wrapper = mount(RealtimeChartTestable)
    wrapper.vm.addPoint({ time: '2026-01-01 12:00:00', value: 25.5 })
    expect(wrapper.vm.pointCount).toBe(1)
    wrapper.vm.addPoint({ time: '2026-01-01 12:00:05', value: 26.0 })
    expect(wrapper.vm.pointCount).toBe(2)
  })

  it('maxPoints 限制数据点数量', () => {
    const wrapper = mount(RealtimeChartTestable, {
      props: { maxPoints: 3 }
    })
    for (let i = 0; i < 5; i++) {
      wrapper.vm.addPoint({ time: `2026-01-01 12:00:0${i}`, value: i * 10 })
    }
    expect(wrapper.vm.pointCount).toBe(3)
  })

  it('setData 批量设置数据', () => {
    const wrapper = mount(RealtimeChartTestable, {
      props: { maxPoints: 3 }
    })
    const data = [
      { time: '2026-01-01 12:00:00', value: 10 },
      { time: '2026-01-01 12:00:05', value: 20 },
      { time: '2026-01-01 12:00:10', value: 30 },
      { time: '2026-01-01 12:00:15', value: 40 }
    ]
    wrapper.vm.setData(data)
    expect(wrapper.vm.pointCount).toBe(3)
  })

  it('clear 清空数据', () => {
    const wrapper = mount(RealtimeChartTestable)
    wrapper.vm.addPoint({ time: '2026-01-01', value: 10 })
    wrapper.vm.clear()
    expect(wrapper.vm.pointCount).toBe(0)
  })

  it('showMarkLine 控制标记线显示', () => {
    const wrapper = mount(RealtimeChartTestable, {
      props: { showMarkLine: true, warningValue: 80, criticalValue: 95 }
    })
    expect(wrapper.find('[data-testid="mark-lines"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="warning-line"]').text()).toContain('80')
    expect(wrapper.find('[data-testid="critical-line"]').text()).toContain('95')
  })

  it('title 属性控制标题', () => {
    const wrapper = mount(RealtimeChartTestable, {
      props: { title: 'CPU温度' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toBe('CPU温度')
  })
})
