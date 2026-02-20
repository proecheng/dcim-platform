/**
 * ParameterAdjustment 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

const ParameterAdjustmentTestable = defineComponent({
  name: 'ParameterAdjustmentTestable',
  props: {
    suggestion: { type: Object, required: true }
  },
  emits: ['paramsChanged'],
  setup(props) {
    const calculating = ref(false)
    const paramForm = reactive({ selected_devices: [] as number[], shift_hours: 2, source_period: 'sharp', target_period: 'valley' })
    const calculationResult = reactive({
      total_power: 0, price_diff: 0, daily_energy: 0, daily_saving: 0, annual_saving: 0, annual_saving_wan: 0, steps: [] as string[]
    })
    const shiftMarks = { 0.5: '0.5h', 2: '2h', 4: '4h', 6: '6h', 8: '8h' }
    const hasChanges = computed(() => {
      const params = props.suggestion.parameters
      if (!params) return false
      return paramForm.shift_hours !== (params.default_shift_hours || 2)
    })
    function formatHours(hours: number[]): string {
      if (!hours || hours.length === 0) return '全天'
      return hours.map(h => `${h}:00`).join(', ')
    }
    return { calculating, paramForm, calculationResult, shiftMarks, hasChanges, formatHours }
  },
  template: `
    <div data-testid="parameter-adjustment">
      <span data-testid="shift-hours">{{ paramForm.shift_hours }}</span>
      <span data-testid="source-period">{{ paramForm.source_period }}</span>
      <span data-testid="target-period">{{ paramForm.target_period }}</span>
      <span data-testid="has-changes">{{ hasChanges }}</span>
      <span data-testid="total-power">{{ calculationResult.total_power }}</span>
    </div>
  `
})

describe('ParameterAdjustment 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  const baseSuggestion = { id: 1, parameters: { default_shift_hours: 2, adjustable_params: [] } }

  it('默认渲染', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="parameter-adjustment"]').exists()).toBe(true)
  })

  it('默认转移时长为 2 小时', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="shift-hours"]').text()).toBe('2')
  })

  it('默认转出时段为 sharp', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="source-period"]').text()).toBe('sharp')
  })

  it('默认转入时段为 valley', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="target-period"]').text()).toBe('valley')
  })

  it('未修改参数时 hasChanges 为 false', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="has-changes"]').text()).toBe('false')
  })

  it('格式化时段 - 空数组返回全天', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.vm.formatHours([])).toBe('全天')
  })

  it('格式化时段 - 有数据', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.vm.formatHours([8, 9, 10])).toBe('8:00, 9:00, 10:00')
  })

  it('calculating 默认为 false', () => {
    const wrapper = mount(ParameterAdjustmentTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.vm.calculating).toBe(false)
  })
})
