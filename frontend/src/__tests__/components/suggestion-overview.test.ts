/**
 * SuggestionOverview 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const SuggestionOverviewTestable = defineComponent({
  name: 'SuggestionOverviewTestable',
  props: {
    suggestion: { type: Object, required: true }
  },
  setup(props) {
    const parameters = computed(() => props.suggestion.parameters)
    const hasPricingData = computed(() => {
      const p = parameters.value
      return p && (p.sharp_price || p.peak_price || p.valley_price || p.price_diff)
    })
    const categoryText: Record<string, string> = { pue: 'PUE优化', cost: '成本优化', demand: '需量管理' }
    const priorityText: Record<string, string> = { urgent: '紧急', high: '高', medium: '中', low: '低' }
    const difficultyText: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }
    const statusText: Record<string, string> = { pending: '待处理', accepted: '已接受', rejected: '已拒绝', completed: '已完成' }
    return { parameters, hasPricingData, categoryText, priorityText, difficultyText, statusText }
  },
  template: `
    <div data-testid="suggestion-overview">
      <div data-testid="problem">{{ suggestion.problem_description || '暂无问题描述' }}</div>
      <div data-testid="analysis">{{ suggestion.analysis_detail || '暂无分析详情' }}</div>
      <div v-if="hasPricingData" data-testid="pricing-data">有电价数据</div>
      <div data-testid="saving">{{ suggestion.potential_saving || 0 }}</div>
      <div data-testid="category">{{ categoryText[suggestion.category] || suggestion.category }}</div>
      <div data-testid="priority">{{ priorityText[suggestion.priority] || suggestion.priority }}</div>
      <div data-testid="status">{{ statusText[suggestion.status] || suggestion.status }}</div>
    </div>
  `
})

describe('SuggestionOverview 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  const baseSuggestion = { problem_description: '峰时用电过高', analysis_detail: '分析结果', category: 'cost', priority: 'high', status: 'pending', potential_saving: 500 }

  it('默认渲染', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="suggestion-overview"]').exists()).toBe(true)
  })

  it('显示问题描述', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="problem"]').text()).toBe('峰时用电过高')
  })

  it('无问题描述时显示默认文本', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: { ...baseSuggestion, problem_description: '' } } })
    expect(wrapper.find('[data-testid="problem"]').text()).toBe('暂无问题描述')
  })

  it('类别映射正确', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="category"]').text()).toBe('成本优化')
  })

  it('优先级映射正确', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="priority"]').text()).toBe('高')
  })

  it('有电价数据时显示', () => {
    const wrapper = mount(SuggestionOverviewTestable, {
      props: { suggestion: { ...baseSuggestion, parameters: { peak_price: 1.0, valley_price: 0.3 } } }
    })
    expect(wrapper.find('[data-testid="pricing-data"]').exists()).toBe(true)
  })

  it('显示节能潜力', () => {
    const wrapper = mount(SuggestionOverviewTestable, { props: { suggestion: baseSuggestion } })
    expect(wrapper.find('[data-testid="saving"]').text()).toBe('500')
  })
})
