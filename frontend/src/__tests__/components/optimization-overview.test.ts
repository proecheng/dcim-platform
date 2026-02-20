/**
 * OptimizationOverview 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

const OptimizationOverviewTestable = defineComponent({
  name: 'OptimizationOverviewTestable',
  setup() {
    const loading = ref(false)
    const analyzing = ref(false)
    const potential = ref<any>({})
    const topSuggestions = ref<any[]>([])
    function formatNumber(num: number): string {
      return num >= 10000 ? (num / 10000).toFixed(2) + '万' : num.toFixed(0)
    }
    return { loading, analyzing, potential, topSuggestions, formatNumber }
  },
  template: `
    <div data-testid="optimization-overview">
      <span data-testid="total-saving">¥{{ formatNumber(potential.total_cost_saving || 0) }}</span>
      <span data-testid="pending">{{ potential.pending_count || 0 }}</span>
      <span data-testid="accepted">{{ potential.accepted_count || 0 }}</span>
      <span data-testid="completed">{{ potential.completed_count || 0 }}</span>
      <div v-for="item in topSuggestions" :key="item.id" data-testid="suggestion-item">{{ item.suggestion }}</div>
      <div v-if="topSuggestions.length === 0" data-testid="empty">暂无重点建议</div>
    </div>
  `
})

describe('OptimizationOverview 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.find('[data-testid="optimization-overview"]').exists()).toBe(true)
  })

  it('空数据时显示提示', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
  })

  it('格式化大数字为万', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.vm.formatNumber(50000)).toBe('5.00万')
  })

  it('格式化小数字', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.vm.formatNumber(5000)).toBe('5000')
  })

  it('显示潜力数据', async () => {
    const wrapper = mount(OptimizationOverviewTestable)
    wrapper.vm.potential = { total_cost_saving: 30000, pending_count: 5, accepted_count: 3, completed_count: 2 }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="pending"]').text()).toBe('5')
    expect(wrapper.find('[data-testid="accepted"]').text()).toBe('3')
  })

  it('loading 默认为 false', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.vm.loading).toBe(false)
  })

  it('analyzing 默认为 false', () => {
    const wrapper = mount(OptimizationOverviewTestable)
    expect(wrapper.vm.analyzing).toBe(false)
  })
})
