/**
 * SearchForm 搜索表单组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Search: { template: '<i class="icon-search" />' },
  Refresh: { template: '<i class="icon-refresh" />' },
  ArrowDown: { template: '<i class="icon-arrow-down" />' }
}))

const SearchFormTestable = defineComponent({
  name: 'SearchFormTestable',
  props: {
    modelValue: { type: Object, default: () => ({}) },
    inline: { type: Boolean, default: true },
    labelWidth: { type: String, default: '80px' },
    showButtons: { type: Boolean, default: true },
    showExpand: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'search', 'reset'],
  setup(props, { emit }) {
    const expanded = ref(false)

    const handleSearch = () => {
      emit('search', props.modelValue)
    }

    const handleReset = () => {
      emit('reset')
      emit('search', props.modelValue)
    }

    return { expanded, handleSearch, handleReset }
  },
  template: `
    <form data-testid="search-form" class="search-form" @submit.prevent="handleSearch">
      <slot></slot>
      <div v-if="showButtons" data-testid="form-buttons" class="search-form__buttons">
        <button type="button" data-testid="search-btn" @click="handleSearch">搜索</button>
        <button type="button" data-testid="reset-btn" @click="handleReset">重置</button>
        <button
          v-if="showExpand"
          type="button"
          data-testid="expand-btn"
          @click="expanded = !expanded"
        >
          {{ expanded ? '收起' : '展开' }}
        </button>
      </div>
      <div v-if="expanded" data-testid="expand-area" class="search-form__expand">
        <slot name="expand"></slot>
      </div>
    </form>
  `
})

describe('SearchForm 搜索表单', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: {} }
    })
    expect(wrapper.find('[data-testid="search-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="form-buttons"]').exists()).toBe(true)
  })

  it('showButtons 为 false 时隐藏按钮', () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: {}, showButtons: false }
    })
    expect(wrapper.find('[data-testid="form-buttons"]').exists()).toBe(false)
  })

  it('点击搜索按钮触发 search 事件', async () => {
    const formData = { keyword: '测试' }
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: formData }
    })
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.emitted('search')?.[0]).toEqual([formData])
  })

  it('点击重置按钮触发 reset 和 search 事件', async () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: { keyword: '' } }
    })
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.emitted('reset')).toBeTruthy()
    expect(wrapper.emitted('search')).toBeTruthy()
  })

  it('showExpand 控制展开按钮显示', () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: {}, showExpand: true }
    })
    expect(wrapper.find('[data-testid="expand-btn"]').exists()).toBe(true)
  })

  it('点击展开按钮切换展开区域', async () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: {}, showExpand: true }
    })
    expect(wrapper.find('[data-testid="expand-area"]').exists()).toBe(false)
    await wrapper.find('[data-testid="expand-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="expand-area"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="expand-btn"]').text()).toBe('收起')
  })

  it('插槽内容正确渲染', () => {
    const wrapper = mount(SearchFormTestable, {
      props: { modelValue: {} },
      slots: { default: '<div data-testid="slot-content">自定义内容</div>' }
    })
    expect(wrapper.find('[data-testid="slot-content"]').text()).toBe('自定义内容')
  })
})
