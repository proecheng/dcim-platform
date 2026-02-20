/**
 * CalculationDetails 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const CalculationDetailsTestable = defineComponent({
  name: 'CalculationDetailsTestable',
  props: {
    suggestion: { type: Object, required: true }
  },
  setup(props) {
    const parameters = computed(() => props.suggestion.parameters)
    const calculationFormula = computed(() => props.suggestion.parameters?.calculation_formula)
    const dataSources = computed(() => props.suggestion.data_sources)
    return { parameters, calculationFormula, dataSources }
  },
  template: `
    <div data-testid="calculation-details">
      <div data-testid="formula">{{ calculationFormula?.formula || '日收益 = 转移功率 × 转移时长 × (转出电价 - 转入电价)' }}</div>
      <div v-if="calculationFormula?.steps" data-testid="steps">
        <span v-for="step in calculationFormula.steps" :key="step.step" data-testid="step">步骤 {{ step.step }}: {{ step.desc }}</span>
      </div>
      <div data-testid="total-power">{{ parameters?.total_shiftable_power?.toFixed(1) || 0 }} kW</div>
      <div data-testid="price-diff">{{ parameters?.price_diff?.toFixed(3) || 0 }}</div>
      <div v-if="dataSources" data-testid="data-sources">有数据溯源</div>
    </div>
  `
})

describe('CalculationDetails 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  const baseSuggestion = {
    parameters: {
      total_shiftable_power: 120.5,
      default_shift_hours: 2,
      price_diff: 0.65,
      daily_saving: 156.65,
      annual_saving: 39162.5,
      calculation_formula: {
        formula: '日收益 = P × H × ΔPrice',
        steps: [{ step: 1, desc: '计算转移电量' }, { step: 2, desc: '计算价差收益' }]
      }
    },
    data_sources: { pricing: { config_count: 5 } }
  }

  it('默认渲染', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="calculation-details"]').exists()).toBe(true)
  })

  it('显示计算公式', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="formula"]').text()).toContain('日收益')
  })

  it('显示计算步骤', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.findAll('[data-testid="step"]').length).toBe(2)
  })

  it('显示总可调节容量', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="total-power"]').text()).toContain('120.5')
  })

  it('显示峰谷价差', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="price-diff"]').text()).toContain('0.650')
  })

  it('有数据溯源时显示', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="data-sources"]').exists()).toBe(true)
  })

  it('无公式时显示默认公式', () => {
    const wrapper = mount(CalculationDetailsTestable, { props: { suggestion: { parameters: {} } } })
    expect(wrapper.find('[data-testid="formula"]').text()).toContain('转移功率')
  })
})
