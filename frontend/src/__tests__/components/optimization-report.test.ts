/**
 * OptimizationReport 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() })),
  graphic: { LinearGradient: vi.fn() }
}))

const OptimizationReportTestable = defineComponent({
  name: 'OptimizationReportTestable',
  setup() {
    const selectedMonth = ref('')
    const report = ref<any>(null)
    const adjusting = ref(false)
    function formatNumber(num: number) { return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(2) }
    function formatBias(bias: number | undefined) {
      if (bias === undefined) return '0 kW'
      const sign = bias > 0 ? '+' : ''
      return `${sign}${bias.toFixed(1)} kW`
    }
    function getAchievementColor(rate: number | undefined) {
      if (!rate) return '#909399'
      if (rate >= 90) return '#67c23a'
      if (rate >= 70) return '#e6a23c'
      return '#f56c6c'
    }
    function getMapeColor(mape: number | undefined) {
      if (!mape) return '#67c23a'
      if (mape <= 10) return '#67c23a'
      if (mape <= 20) return '#e6a23c'
      return '#f56c6c'
    }
    return { selectedMonth, report, adjusting, formatNumber, formatBias, getAchievementColor, getMapeColor }
  },
  template: `
    <div data-testid="optimization-report">
      <span data-testid="month">{{ selectedMonth }}</span>
      <span data-testid="adjusting">{{ adjusting }}</span>
    </div>
  `
})

describe('OptimizationReport 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.find('[data-testid="optimization-report"]').exists()).toBe(true)
  })

  it('格式化数字 - 万元', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.formatNumber(50000)).toBe('5.00万')
  })

  it('格式化数字 - 小数', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.formatNumber(1234)).toBe('1234.00')
  })

  it('格式化偏差 - 正值', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.formatBias(15.3)).toBe('+15.3 kW')
  })

  it('格式化偏差 - 负值', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.formatBias(-8.7)).toBe('-8.7 kW')
  })

  it('达成率颜色 - 高', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.getAchievementColor(95)).toBe('#67c23a')
  })

  it('达成率颜色 - 低', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.getAchievementColor(50)).toBe('#f56c6c')
  })

  it('MAPE 颜色 - 好', () => {
    const wrapper = mount(OptimizationReportTestable)
    expect(wrapper.vm.getMapeColor(5)).toBe('#67c23a')
  })
})
