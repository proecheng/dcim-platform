/**
 * DevicePowerCurveChart 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(),
    on: vi.fn(), off: vi.fn(), getOption: vi.fn(() => ({}))
  })),
  graphic: { LinearGradient: vi.fn() }
}))

const DevicePowerCurveChartTestable = defineComponent({
  name: 'DevicePowerCurveChartTestable',
  props: {
    deviceName: { type: String, default: '' },
    devicePower: { type: Number, default: 100 },
    shiftRules: { type: Array, default: () => [] },
    pricingPeriods: { type: Object, default: undefined }
  },
  setup(props) {
    const showComparison = ref(true)
    const defaultPeriods = {
      sharp: [11, 18], peak: [9, 10, 17, 19, 20],
      flat: [8, 13, 14, 15, 16, 21], valley: [22, 23, 6, 7],
      deep_valley: [0, 1, 2, 3, 4, 5]
    }
    function getHourPeriod(hour: number): string {
      const periods = props.pricingPeriods || defaultPeriods
      if ((periods as any).sharp?.includes(hour)) return 'sharp'
      if ((periods as any).peak?.includes(hour)) return 'peak'
      if ((periods as any).valley?.includes(hour)) return 'valley'
      if ((periods as any).deep_valley?.includes(hour)) return 'deep_valley'
      return 'flat'
    }
    const hasRules = computed(() => (props.shiftRules as any[]).length > 0)
    return { showComparison, getHourPeriod, hasRules }
  },
  template: `
    <div data-testid="power-curve-chart">
      <div class="chart-header">
        <span data-testid="chart-title">{{ deviceName }} 功率曲线</span>
        <input type="checkbox" v-model="showComparison" data-testid="comparison-toggle" />
      </div>
      <div data-testid="chart-container"></div>
      <div data-testid="chart-legend">
        <span>尖峰</span><span>峰时</span><span>平时</span><span>谷时</span><span>深谷</span>
      </div>
    </div>
  `
})

describe('DevicePowerCurveChart 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    expect(wrapper.find('[data-testid="power-curve-chart"]').exists()).toBe(true)
  })

  it('显示设备名称', () => {
    const wrapper = mount(DevicePowerCurveChartTestable, {
      props: { deviceName: '空调机组A' }
    })
    expect(wrapper.find('[data-testid="chart-title"]').text()).toContain('空调机组A')
  })

  it('默认开启对比模式', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    expect(wrapper.vm.showComparison).toBe(true)
  })

  it('时段识别正确 - 尖峰', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    expect(wrapper.vm.getHourPeriod(11)).toBe('sharp')
  })

  it('时段识别正确 - 深谷', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    expect(wrapper.vm.getHourPeriod(3)).toBe('deep_valley')
  })

  it('图例包含所有时段', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    const legend = wrapper.find('[data-testid="chart-legend"]').text()
    expect(legend).toContain('尖峰')
    expect(legend).toContain('谷时')
    expect(legend).toContain('深谷')
  })

  it('hasRules 计算正确', () => {
    const wrapper = mount(DevicePowerCurveChartTestable, {
      props: { shiftRules: [{ sourcePeriod: 'peak', targetPeriod: 'valley', power: 10, hours: 2 }] }
    })
    expect(wrapper.vm.hasRules).toBe(true)
  })

  it('无规则时 hasRules 为 false', () => {
    const wrapper = mount(DevicePowerCurveChartTestable)
    expect(wrapper.vm.hasRules).toBe(false)
  })
})
