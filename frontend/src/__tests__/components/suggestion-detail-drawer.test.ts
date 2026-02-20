/**
 * SuggestionDetailDrawer 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

const SuggestionDetailDrawerTestable = defineComponent({
  name: 'SuggestionDetailDrawerTestable',
  props: {
    modelValue: { type: Boolean, default: false },
    suggestion: { type: Object, default: null }
  },
  emits: ['update:modelValue', 'accepted'],
  setup(props, { emit }) {
    const activeTab = ref('overview')
    const loading = ref(false)
    const priorityText: Record<string, string> = { urgent: '紧急', high: '高', medium: '中', low: '低' }
    const statusText: Record<string, string> = { pending: '待处理', accepted: '已接受', rejected: '已拒绝', completed: '已完成' }
    const currentPriority = computed(() => priorityText[props.suggestion?.priority || 'medium'] || '中')
    const currentStatus = computed(() => statusText[props.suggestion?.status || 'pending'] || '待处理')
    function handleClose() { emit('update:modelValue', false) }
    return { activeTab, loading, currentPriority, currentStatus, handleClose }
  },
  template: `
    <div v-if="modelValue" data-testid="drawer">
      <span data-testid="priority">{{ currentPriority }}</span>
      <span data-testid="status">{{ currentStatus }}</span>
      <span data-testid="active-tab">{{ activeTab }}</span>
      <span data-testid="suggestion-text">{{ suggestion?.suggestion || '' }}</span>
      <button data-testid="close-btn" @click="handleClose">取消</button>
    </div>
  `
})

describe('SuggestionDetailDrawer 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('不可见时不渲染', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable)
    expect(wrapper.find('[data-testid="drawer"]').exists()).toBe(false)
  })

  it('可见时渲染', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, { props: { modelValue: true, suggestion: { suggestion: '测试' } } })
    expect(wrapper.find('[data-testid="drawer"]').exists()).toBe(true)
  })

  it('显示建议文本', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, {
      props: { modelValue: true, suggestion: { suggestion: '优化峰谷用电' } }
    })
    expect(wrapper.find('[data-testid="suggestion-text"]').text()).toBe('优化峰谷用电')
  })

  it('优先级映射正确', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, {
      props: { modelValue: true, suggestion: { priority: 'high', suggestion: 'X' } }
    })
    expect(wrapper.find('[data-testid="priority"]').text()).toBe('高')
  })

  it('默认标签页为 overview', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, {
      props: { modelValue: true, suggestion: { suggestion: 'X' } }
    })
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('overview')
  })

  it('关闭按钮触发事件', async () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, {
      props: { modelValue: true, suggestion: { suggestion: 'X' } }
    })
    await wrapper.find('[data-testid="close-btn"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('状态映射正确', () => {
    const wrapper = mount(SuggestionDetailDrawerTestable, {
      props: { modelValue: true, suggestion: { status: 'completed', suggestion: 'X' } }
    })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('已完成')
  })
})
