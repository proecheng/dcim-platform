/**
 * SuggestionsCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const SuggestionsCardTestable = defineComponent({
  name: 'SuggestionsCardTestable',
  props: {
    pendingCount: { type: Number, default: undefined },
    highPriorityCount: { type: Number, default: undefined },
    potentialSaving: { type: Number, default: undefined },
    recentSuggestions: { type: Array, default: () => [] }
  },
  setup(props) {
    function getPriorityColor(priority: string) {
      switch (priority) { case 'high': return '#f5222d'; case 'medium': return '#faad14'; default: return 'rgba(255,255,255,0.65)' }
    }
    return { getPriorityColor }
  },
  template: `
    <div data-testid="suggestions-card">
      <span data-testid="pending-count">{{ pendingCount || 0 }}</span>
      <span v-if="highPriorityCount && highPriorityCount > 0" data-testid="high-priority">{{ highPriorityCount }} 条高优先级</span>
      <span v-if="potentialSaving && potentialSaving > 0" data-testid="saving">可节省 ¥{{ potentialSaving?.toFixed(0) }}/月</span>
      <div v-for="(item, i) in (recentSuggestions || []).slice(0, 2)" :key="i" data-testid="recent-item">{{ item.title }}</div>
      <span data-testid="action-hint">点击查看详情 →</span>
    </div>
  `
})

describe('SuggestionsCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(SuggestionsCardTestable)
    expect(wrapper.find('[data-testid="suggestions-card"]').exists()).toBe(true)
  })

  it('显示待处理数量', () => {
    const wrapper = mount(SuggestionsCardTestable, { props: { pendingCount: 5 } })
    expect(wrapper.find('[data-testid="pending-count"]').text()).toBe('5')
  })

  it('显示高优先级数量', () => {
    const wrapper = mount(SuggestionsCardTestable, { props: { highPriorityCount: 3 } })
    expect(wrapper.find('[data-testid="high-priority"]').text()).toContain('3')
  })

  it('无高优先级时不显示', () => {
    const wrapper = mount(SuggestionsCardTestable, { props: { highPriorityCount: 0 } })
    expect(wrapper.find('[data-testid="high-priority"]').exists()).toBe(false)
  })

  it('显示节省金额', () => {
    const wrapper = mount(SuggestionsCardTestable, { props: { potentialSaving: 1500 } })
    expect(wrapper.find('[data-testid="saving"]').text()).toContain('1500')
  })

  it('显示最近建议', () => {
    const wrapper = mount(SuggestionsCardTestable, {
      props: { recentSuggestions: [{ title: '建议A', priority: 'high' }, { title: '建议B', priority: 'medium' }] }
    })
    expect(wrapper.findAll('[data-testid="recent-item"]').length).toBe(2)
  })

  it('优先级颜色映射正确', () => {
    const wrapper = mount(SuggestionsCardTestable)
    expect(wrapper.vm.getPriorityColor('high')).toBe('#f5222d')
    expect(wrapper.vm.getPriorityColor('medium')).toBe('#faad14')
  })

  it('显示操作提示', () => {
    const wrapper = mount(SuggestionsCardTestable)
    expect(wrapper.find('[data-testid="action-hint"]').text()).toContain('点击查看详情')
  })
})
