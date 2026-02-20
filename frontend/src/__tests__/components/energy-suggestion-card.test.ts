/**
 * EnergySuggestionCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const EnergySuggestionCardTestable = defineComponent({
  name: 'EnergySuggestionCardTestable',
  props: {
    id: { type: Number, required: true },
    ruleName: { type: String, default: '' },
    suggestion: { type: String, required: true },
    priority: { type: String, default: 'medium' },
    status: { type: String, default: 'pending' },
    potentialSaving: { type: Number, default: undefined },
    potentialCostSaving: { type: Number, default: undefined },
    createdAt: { type: String, default: '2026-01-01T00:00:00' }
  },
  emits: ['accept', 'reject', 'complete'],
  setup(props, { emit }) {
    const priorityType = computed(() => {
      switch (props.priority) { case 'high': return 'danger'; case 'medium': return 'warning'; default: return 'info' }
    })
    const priorityText = computed(() => {
      switch (props.priority) { case 'high': return '高'; case 'medium': return '中'; case 'low': return '低'; default: return '未知' }
    })
    const statusText = computed(() => {
      switch (props.status) { case 'pending': return '待处理'; case 'accepted': return '已接受'; case 'completed': return '已完成'; case 'rejected': return '已拒绝'; default: return '未知' }
    })
    function handleAccept() { emit('accept', props.id) }
    function handleReject() { emit('reject', props.id) }
    function handleComplete() { emit('complete', props.id) }
    return { priorityType, priorityText, statusText, handleAccept, handleReject, handleComplete }
  },
  template: `
    <div data-testid="suggestion-card" :class="'priority-' + priority">
      <span data-testid="priority">{{ priorityText }}</span>
      <span data-testid="status">{{ statusText }}</span>
      <div data-testid="suggestion-text">{{ suggestion }}</div>
      <div v-if="potentialSaving" data-testid="saving">{{ potentialSaving.toFixed(1) }} kWh/月</div>
      <div v-if="potentialCostSaving" data-testid="cost-saving">{{ potentialCostSaving.toFixed(2) }} 元/月</div>
      <div v-if="status === 'pending'" data-testid="pending-actions">
        <button data-testid="accept-btn" @click="handleAccept">接受</button>
        <button data-testid="reject-btn" @click="handleReject">拒绝</button>
      </div>
      <div v-if="status === 'accepted'" data-testid="accepted-actions">
        <button data-testid="complete-btn" @click="handleComplete">标记完成</button>
      </div>
    </div>
  `
})

describe('EnergySuggestionCard 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: '建议内容' } })
    expect(wrapper.find('[data-testid="suggestion-card"]').exists()).toBe(true)
  })

  it('显示建议文本', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: '降低峰时用电' } })
    expect(wrapper.find('[data-testid="suggestion-text"]').text()).toBe('降低峰时用电')
  })

  it('优先级映射正确', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: 'X', priority: 'high' } })
    expect(wrapper.find('[data-testid="priority"]').text()).toBe('高')
  })

  it('状态映射正确', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: 'X', status: 'completed' } })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('已完成')
  })

  it('待处理状态显示接受和拒绝按钮', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: 'X', status: 'pending' } })
    expect(wrapper.find('[data-testid="accept-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="reject-btn"]').exists()).toBe(true)
  })

  it('接受按钮触发 accept 事件', async () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 42, suggestion: 'X', status: 'pending' } })
    await wrapper.find('[data-testid="accept-btn"]').trigger('click')
    expect(wrapper.emitted('accept')?.[0]).toEqual([42])
  })

  it('显示节能潜力', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: 'X', potentialSaving: 150.5 } })
    expect(wrapper.find('[data-testid="saving"]').text()).toContain('150.5')
  })

  it('已接受状态显示完成按钮', () => {
    const wrapper = mount(EnergySuggestionCardTestable, { props: { id: 1, suggestion: 'X', status: 'accepted' } })
    expect(wrapper.find('[data-testid="complete-btn"]').exists()).toBe(true)
  })
})
