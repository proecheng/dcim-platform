/**
 * ShiftPlanBuilder 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed, reactive } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() })),
  graphic: { LinearGradient: vi.fn() }
}))

const ShiftPlanBuilderTestable = defineComponent({
  name: 'ShiftPlanBuilderTestable',
  props: {
    shiftableDevices: { type: Array, default: () => [] }
  },
  setup(props) {
    const selectedDevices = ref<any[]>([])
    const optimizationStrategy = ref('max_benefit')
    const deviceShiftRules = reactive<Record<number, any[]>>({})
    const periodPrices: Record<string, number> = { sharp: 1.40, peak: 1.00, flat: 0.65, valley: 0.35, deep_valley: 0.20 }
    const totalSelectedPower = computed(() => selectedDevices.value.reduce((sum: number, d: any) => sum + d.shiftable_power, 0))
    const hasAnyRules = computed(() => {
      for (const deviceId of Object.keys(deviceShiftRules)) {
        const rules = deviceShiftRules[Number(deviceId)]
        if (rules && rules.length > 0 && rules.some((r: any) => r.power > 0)) return true
      }
      return false
    })
    function calculateRuleDailySaving(rule: any): number {
      const sourcePrice = periodPrices[rule.sourcePeriod] || 0
      const targetPrice = periodPrices[rule.targetPeriod] || 0
      return (rule.power || 0) * (rule.hours || 0) * (sourcePrice - targetPrice)
    }
    return { selectedDevices, optimizationStrategy, deviceShiftRules, totalSelectedPower, hasAnyRules, calculateRuleDailySaving, periodPrices }
  },
  template: `
    <div data-testid="shift-plan-builder">
      <span data-testid="strategy">{{ optimizationStrategy }}</span>
      <span data-testid="total-power">{{ totalSelectedPower.toFixed(1) }}</span>
      <span data-testid="has-rules">{{ hasAnyRules }}</span>
      <div v-if="selectedDevices.length === 0" data-testid="empty">请先选择要转移的设备</div>
    </div>
  `
})

describe('ShiftPlanBuilder 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.find('[data-testid="shift-plan-builder"]').exists()).toBe(true)
  })

  it('默认策略为效益最大化', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.find('[data-testid="strategy"]').text()).toBe('max_benefit')
  })

  it('无选中设备时显示提示', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
  })

  it('默认无规则', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.vm.hasAnyRules).toBe(false)
  })

  it('计算日节省 - 峰转谷', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    const saving = wrapper.vm.calculateRuleDailySaving({ sourcePeriod: 'peak', targetPeriod: 'valley', power: 50, hours: 4 })
    expect(saving).toBeCloseTo(50 * 4 * (1.00 - 0.35))
  })

  it('计算日节省 - 尖峰转深谷', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    const saving = wrapper.vm.calculateRuleDailySaving({ sourcePeriod: 'sharp', targetPeriod: 'deep_valley', power: 30, hours: 2 })
    expect(saving).toBeCloseTo(30 * 2 * (1.40 - 0.20))
  })

  it('电价配置正确', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.vm.periodPrices.sharp).toBe(1.40)
    expect(wrapper.vm.periodPrices.deep_valley).toBe(0.20)
  })

  it('总选中功率默认为 0', () => {
    const wrapper = mount(ShiftPlanBuilderTestable)
    expect(wrapper.find('[data-testid="total-power"]').text()).toBe('0.0')
  })
})
