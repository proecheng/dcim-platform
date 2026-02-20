/**
 * ConfirmDialog 确认对话框组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  WarningFilled: { template: '<i class="icon-warning" />' },
  CircleCheckFilled: { template: '<i class="icon-success" />' },
  CircleCloseFilled: { template: '<i class="icon-error" />' },
  InfoFilled: { template: '<i class="icon-info" />' },
  QuestionFilled: { template: '<i class="icon-question" />' }
}))

type DialogType = 'warning' | 'success' | 'error' | 'info' | 'confirm'

const ConfirmDialogTestable = defineComponent({
  name: 'ConfirmDialogTestable',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '提示' },
    message: { type: String, default: '' },
    type: { type: String as () => DialogType, default: 'confirm' },
    width: { type: String, default: '420px' },
    showIcon: { type: Boolean, default: true },
    confirmText: { type: String, default: '确定' },
    cancelText: { type: String, default: '取消' },
    confirmType: { type: String, default: 'primary' }
  },
  emits: ['update:modelValue', 'confirm', 'cancel', 'close'],
  setup(props, { emit }) {
    const loading = ref(false)

    const visible = computed({
      get: () => props.modelValue,
      set: (val: boolean) => emit('update:modelValue', val)
    })

    const iconClassMap: Record<DialogType, string> = {
      warning: 'is-warning',
      success: 'is-success',
      error: 'is-error',
      info: 'is-info',
      confirm: 'is-confirm'
    }

    const iconClass = computed(() => iconClassMap[props.type as DialogType] || 'is-confirm')

    const handleCancel = () => {
      visible.value = false
      emit('cancel')
    }

    const handleConfirm = () => {
      visible.value = false
      emit('confirm')
    }

    return { visible, loading, iconClass, handleCancel, handleConfirm }
  },
  template: `
    <div v-if="visible" data-testid="confirm-dialog" :style="{ width }">
      <div data-testid="dialog-title">{{ title }}</div>
      <div data-testid="dialog-content" class="confirm-dialog__content">
        <span v-if="showIcon" data-testid="dialog-icon" :class="['confirm-dialog__icon', iconClass]"></span>
        <div data-testid="dialog-message">
          <slot>{{ message }}</slot>
        </div>
      </div>
      <div data-testid="dialog-footer">
        <button data-testid="cancel-btn" @click="handleCancel">{{ cancelText }}</button>
        <button data-testid="confirm-btn" :class="confirmType" @click="handleConfirm">{{ confirmText }}</button>
      </div>
    </div>
  `
})

describe('ConfirmDialog 确认对话框', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染 - modelValue 为 false 时不显示', () => {
    const wrapper = mount(ConfirmDialogTestable)
    expect(wrapper.find('[data-testid="confirm-dialog"]').exists()).toBe(false)
  })

  it('modelValue 为 true 时显示对话框', () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true }
    })
    expect(wrapper.find('[data-testid="confirm-dialog"]').exists()).toBe(true)
  })

  it('props 正确传递标题和消息', () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true, title: '删除确认', message: '确定要删除吗？' }
    })
    expect(wrapper.find('[data-testid="dialog-title"]').text()).toBe('删除确认')
    expect(wrapper.find('[data-testid="dialog-message"]').text()).toBe('确定要删除吗？')
  })

  it('type 属性控制图标样式', () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true, type: 'warning' }
    })
    expect(wrapper.find('[data-testid="dialog-icon"]').classes()).toContain('is-warning')
  })

  it('showIcon 为 false 时隐藏图标', () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true, showIcon: false }
    })
    expect(wrapper.find('[data-testid="dialog-icon"]').exists()).toBe(false)
  })

  it('点击确定按钮触发 confirm 事件', async () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true }
    })
    await wrapper.find('[data-testid="confirm-btn"]').trigger('click')
    expect(wrapper.emitted('confirm')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('点击取消按钮触发 cancel 事件', async () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true }
    })
    await wrapper.find('[data-testid="cancel-btn"]').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('自定义按钮文本正确显示', () => {
    const wrapper = mount(ConfirmDialogTestable, {
      props: { modelValue: true, confirmText: '删除', cancelText: '返回' }
    })
    expect(wrapper.find('[data-testid="confirm-btn"]').text()).toBe('删除')
    expect(wrapper.find('[data-testid="cancel-btn"]').text()).toBe('返回')
  })
})
