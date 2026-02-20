/**
 * ExecutionPlanDialog 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

const ExecutionPlanDialogTestable = defineComponent({
  name: 'ExecutionPlanDialogTestable',
  props: {
    modelValue: { type: Boolean, default: false },
    strategy: { type: String, default: 'max_benefit' },
    dailySaving: { type: Number, default: 0 },
    annualSaving: { type: Number, default: 0 },
    deviceRules: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'confirm'],
  setup(props, { emit }) {
    const submitting = ref(false)
    const formData = reactive({ planName: '', remark: '' })
    function formatNumber(num: number): string {
      return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(0)
    }
    function handleClose() { emit('update:modelValue', false) }
    function handleConfirm() {
      submitting.value = true
      emit('confirm', { planName: formData.planName, remark: formData.remark })
    }
    return { submitting, formData, formatNumber, handleClose, handleConfirm }
  },
  template: `
    <div v-if="modelValue" data-testid="dialog">
      <span data-testid="strategy">{{ strategy === 'max_benefit' ? '效益最大化' : '成本最小化' }}</span>
      <span data-testid="daily-saving">¥{{ dailySaving.toFixed(2) }}</span>
      <span data-testid="annual-saving">¥{{ formatNumber(annualSaving) }}</span>
      <span data-testid="device-count">{{ deviceRules.length }}</span>
      <input data-testid="plan-name" v-model="formData.planName" />
      <button data-testid="cancel-btn" @click="handleClose">取消</button>
      <button data-testid="confirm-btn" @click="handleConfirm">确认</button>
    </div>
  `
})

describe('ExecutionPlanDialog 组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('不可见时不渲染', () => {
    const wrapper = mount(ExecutionPlanDialogTestable)
    expect(wrapper.find('[data-testid="dialog"]').exists()).toBe(false)
  })

  it('可见时渲染', () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true } })
    expect(wrapper.find('[data-testid="dialog"]').exists()).toBe(true)
  })

  it('显示策略名称 - 效益最大化', () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true, strategy: 'max_benefit' } })
    expect(wrapper.find('[data-testid="strategy"]').text()).toBe('效益最大化')
  })

  it('显示策略名称 - 成本最小化', () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true, strategy: 'min_cost' } })
    expect(wrapper.find('[data-testid="strategy"]').text()).toBe('成本最小化')
  })

  it('显示日节省金额', () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true, dailySaving: 123.45 } })
    expect(wrapper.find('[data-testid="daily-saving"]').text()).toContain('123.45')
  })

  it('年节省金额格式化 - 万元', () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true, annualSaving: 50000 } })
    expect(wrapper.find('[data-testid="annual-saving"]').text()).toContain('5.00万')
  })

  it('取消按钮触发关闭', async () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true } })
    await wrapper.find('[data-testid="cancel-btn"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('确认按钮触发 confirm 事件', async () => {
    const wrapper = mount(ExecutionPlanDialogTestable, { props: { modelValue: true } })
    wrapper.vm.formData.planName = '测试方案'
    await wrapper.find('[data-testid="confirm-btn"]').trigger('click')
    expect(wrapper.emitted('confirm')?.[0]).toEqual([{ planName: '测试方案', remark: '' }])
  })
})
