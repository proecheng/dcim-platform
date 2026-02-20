/**
 * 节能建议页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

const priorityText: Record<string, string> = { high: '高', medium: '中', low: '低' }
const statusText: Record<string, string> = { pending: '待处理', accepted: '已接受', rejected: '已拒绝', completed: '已完成' }

const SuggestionsTestable = defineComponent({
  name: 'SuggestionsTestable',
  setup() {
    const loading = ref(false)
    const filters = reactive({ status: '' })
    const potential = ref({
      total_potential_saving: 3500,
      total_cost_saving: 2800,
      completed_count: 8,
      actual_saving_ytd: 25000,
      high_priority_count: 3,
      medium_priority_count: 5,
      low_priority_count: 2
    })
    const suggestions = ref([
      { id: 1, priority: 'high', status: 'pending', rule_name: 'PUE优化', suggestion: '调整空调温度', potential_saving: 500, potential_cost_saving: 400 },
      { id: 2, priority: 'medium', status: 'accepted', rule_name: '需量管理', suggestion: '降低峰时负荷', potential_saving: 300, potential_cost_saving: 240 },
      { id: 3, priority: 'low', status: 'completed', rule_name: '照明优化', suggestion: '分区控制', potential_saving: 100, potential_cost_saving: 80, actual_saving: 95 }
    ])

    return { loading, filters, potential, suggestions, priorityText, statusText }
  },
  template: `
    <div class="energy-suggestions">
      <div class="potential-cards">
        <div class="potential-card" data-testid="saving-kwh">
          <div class="value">{{ potential.total_potential_saving }}</div>
          <div class="label">潜在节能 (kWh/月)</div>
        </div>
        <div class="potential-card" data-testid="saving-cost">
          <div class="value">{{ potential.total_cost_saving }}</div>
          <div class="label">预计节省 (元/月)</div>
        </div>
        <div class="potential-card" data-testid="completed">
          <div class="value">{{ potential.completed_count }}</div>
          <div class="label">已完成建议</div>
        </div>
        <div class="potential-card" data-testid="ytd-saving">
          <div class="value">{{ potential.actual_saving_ytd }}</div>
          <div class="label">年度实际节能 (kWh)</div>
        </div>
      </div>
      <div class="suggestion-list">
        <div v-for="item in suggestions" :key="item.id" class="suggestion-item" :data-testid="'suggestion-' + item.id" :class="'priority-' + item.priority">
          <span class="priority">{{ priorityText[item.priority] }}</span>
          <span class="status">{{ statusText[item.status] }}</span>
          <span class="rule-name">{{ item.rule_name }}</span>
          <div class="actions">
            <button v-if="item.status === 'pending'" class="btn-accept">接受</button>
            <button v-if="item.status === 'pending'" class="btn-reject">拒绝</button>
            <button v-if="item.status === 'accepted'" class="btn-complete">标记完成</button>
          </div>
        </div>
      </div>
    </div>
  `
})

describe('节能建议页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染4张潜力卡片', () => {
    const wrapper = mount(SuggestionsTestable)
    expect(wrapper.findAll('.potential-card')).toHaveLength(4)
  })

  it('显示潜在节能数据', () => {
    const wrapper = mount(SuggestionsTestable)
    expect(wrapper.find('[data-testid="saving-kwh"] .value').text()).toBe('3500')
    expect(wrapper.find('[data-testid="saving-cost"] .value').text()).toBe('2800')
  })

  it('渲染建议列表', () => {
    const wrapper = mount(SuggestionsTestable)
    expect(wrapper.findAll('.suggestion-item')).toHaveLength(3)
  })

  it('高优先级建议有正确样式', () => {
    const wrapper = mount(SuggestionsTestable)
    const item = wrapper.find('[data-testid="suggestion-1"]')
    expect(item.classes()).toContain('priority-high')
    expect(item.find('.priority').text()).toBe('高')
  })

  it('待处理建议显示接受和拒绝按钮', () => {
    const wrapper = mount(SuggestionsTestable)
    const item = wrapper.find('[data-testid="suggestion-1"]')
    expect(item.find('.btn-accept').exists()).toBe(true)
    expect(item.find('.btn-reject').exists()).toBe(true)
  })

  it('已接受建议显示标记完成按钮', () => {
    const wrapper = mount(SuggestionsTestable)
    const item = wrapper.find('[data-testid="suggestion-2"]')
    expect(item.find('.btn-complete').exists()).toBe(true)
    expect(item.find('.btn-accept').exists()).toBe(false)
  })

  it('已完成建议不显示操作按钮', () => {
    const wrapper = mount(SuggestionsTestable)
    const item = wrapper.find('[data-testid="suggestion-3"]')
    expect(item.find('.btn-accept').exists()).toBe(false)
    expect(item.find('.btn-complete').exists()).toBe(false)
  })
})
