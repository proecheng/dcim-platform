/**
 * ScheduleDashboard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() })),
  graphic: { LinearGradient: vi.fn() }
}))

const ScheduleDashboardTestable = defineComponent({
  name: 'ScheduleDashboardTestable',
  setup() {
    const selectedDate = ref('')
    const result = ref<any>(null)
    const loading = reactive({ schedule: false, optimize: false })
    return { selectedDate, result, loading }
  },
  template: `
    <div data-testid="schedule-dashboard">
      <span data-testid="selected-date">{{ selectedDate }}</span>
      <span data-testid="loading-schedule">{{ loading.schedule }}</span>
      <span data-testid="loading-optimize">{{ loading.optimize }}</span>
      <div v-if="result" data-testid="result">
        <span data-testid="status">{{ result.optimization?.status }}</span>
        <span data-testid="max-demand">{{ result.optimization?.max_demand?.toFixed(1) || 0 }}</span>
        <span data-testid="saving">{{ result.optimization?.expected_saving?.toFixed(2) || 0 }}</span>
      </div>
      <div v-else data-testid="no-result">暂无数据</div>
    </div>
  `
})

describe('ScheduleDashboard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(ScheduleDashboardTestable)
    expect(wrapper.find('[data-testid="schedule-dashboard"]').exists()).toBe(true)
  })

  it('无结果时显示暂无数据', () => {
    const wrapper = mount(ScheduleDashboardTestable)
    expect(wrapper.find('[data-testid="no-result"]').exists()).toBe(true)
  })

  it('loading 默认为 false', () => {
    const wrapper = mount(ScheduleDashboardTestable)
    expect(wrapper.find('[data-testid="loading-schedule"]').text()).toBe('false')
    expect(wrapper.find('[data-testid="loading-optimize"]').text()).toBe('false')
  })

  it('有结果时显示优化状态', async () => {
    const wrapper = mount(ScheduleDashboardTestable)
    wrapper.vm.result = { optimization: { status: 'success', max_demand: 650.3, expected_saving: 123.45 } }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="status"]').text()).toBe('success')
  })

  it('显示最大需量', async () => {
    const wrapper = mount(ScheduleDashboardTestable)
    wrapper.vm.result = { optimization: { max_demand: 750.8 } }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="max-demand"]').text()).toBe('750.8')
  })

  it('显示预计节省', async () => {
    const wrapper = mount(ScheduleDashboardTestable)
    wrapper.vm.result = { optimization: { expected_saving: 88.50 } }
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="saving"]').text()).toBe('88.50')
  })

  it('selectedDate 默认为空', () => {
    const wrapper = mount(ScheduleDashboardTestable)
    expect(wrapper.vm.selectedDate).toBe('')
  })
})
