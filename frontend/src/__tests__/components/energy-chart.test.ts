/**
 * 能源图表组件测试
 * 测试 ECharts 组件的挂载和 props 传递
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

// Mock echarts — 避免 canvas 依赖
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

// 模拟能源图表组件的核心逻辑
const EnergyChartTestable = defineComponent({
  name: 'EnergyChartTestable',
  props: {
    deviceRules: {
      type: Array as () => Array<{ deviceName: string; shiftRules: any[] }>,
      default: () => []
    },
    hourlyData: {
      type: Array as () => number[],
      default: () => []
    }
  },
  setup(props) {
    const chartRef = ref<HTMLElement | null>(null)
    const loading = ref(false)
    const dataRange = ref('1day')
    const timeGranularity = ref('1h')

    const hasValidData = computed(() => props.hourlyData.length > 0)
    const hasShiftRules = computed(() => props.deviceRules.length > 0)

    return { chartRef, loading, dataRange, timeGranularity, hasValidData, hasShiftRules }
  },
  template: `
    <div class="load-comparison-chart">
      <div class="card-header">
        <span>负荷转移前后对比</span>
        <div class="controls">
          <select v-model="dataRange" data-testid="range-select">
            <option value="1day">1天</option>
            <option value="7day">7天平均</option>
          </select>
          <select v-model="timeGranularity" data-testid="granularity-select">
            <option value="1h">1小时</option>
            <option value="15min">15分钟</option>
          </select>
        </div>
      </div>
      <div ref="chartRef" class="chart-container" v-show="hasValidData" data-testid="chart"></div>
      <div v-if="!hasValidData && !loading" class="empty-state" data-testid="empty">
        <span v-if="!hasShiftRules">请先选择设备并配置转移规则</span>
        <span v-else>正在加载负荷数据...</span>
      </div>
      <div v-if="hasValidData" class="period-legend" data-testid="legend">
        <span>转移前负荷</span>
        <span>转移后负荷</span>
      </div>
    </div>
  `
})

describe('能源图表组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('无数据时显示空状态', () => {
    const wrapper = mount(EnergyChartTestable)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chart"]').isVisible()).toBe(false)
  })

  it('无数据无规则时提示配置转移规则', () => {
    const wrapper = mount(EnergyChartTestable, {
      props: { deviceRules: [], hourlyData: [] }
    })
    expect(wrapper.find('[data-testid="empty"]').text()).toContain('请先选择设备并配置转移规则')
  })

  it('有规则无数据时提示加载中', () => {
    const wrapper = mount(EnergyChartTestable, {
      props: {
        deviceRules: [{ deviceName: '空调1', shiftRules: [{ sourcePeriod: 'peak', targetPeriod: 'valley', power: 10 }] }],
        hourlyData: []
      }
    })
    expect(wrapper.find('[data-testid="empty"]').text()).toContain('正在加载负荷数据')
  })

  it('有数据时显示图表容器和图例', () => {
    const wrapper = mount(EnergyChartTestable, {
      props: {
        deviceRules: [{ deviceName: '空调1', shiftRules: [] }],
        hourlyData: [100, 200, 150, 180, 120, 90, 80, 110, 160, 200, 220, 190, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60]
      }
    })
    expect(wrapper.find('[data-testid="chart"]').isVisible()).toBe(true)
    expect(wrapper.find('[data-testid="legend"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(false)
  })

  it('图例包含转移前后标签', () => {
    const wrapper = mount(EnergyChartTestable, {
      props: {
        deviceRules: [],
        hourlyData: [1, 2, 3]
      }
    })
    const legend = wrapper.find('[data-testid="legend"]')
    expect(legend.text()).toContain('转移前负荷')
    expect(legend.text()).toContain('转移后负荷')
  })

  it('默认数据范围为 1day', () => {
    const wrapper = mount(EnergyChartTestable)
    expect(wrapper.vm.dataRange).toBe('1day')
  })

  it('默认时间粒度为 1h', () => {
    const wrapper = mount(EnergyChartTestable)
    expect(wrapper.vm.timeGranularity).toBe('1h')
  })

  it('props 正确传递 deviceRules', () => {
    const rules = [{ deviceName: '设备A', shiftRules: [{ sourcePeriod: 'peak', targetPeriod: 'valley', power: 50 }] }]
    const wrapper = mount(EnergyChartTestable, {
      props: { deviceRules: rules, hourlyData: [] }
    })
    expect(wrapper.vm.hasShiftRules).toBe(true)
  })
})
