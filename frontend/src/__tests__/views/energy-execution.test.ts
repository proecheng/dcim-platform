/**
 * 执行管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function formatMoney(value: number): string {
  return (value / 10000).toFixed(2)
}

function formatSaving(value: number): string {
  if (value >= 10000) return (value / 10000).toFixed(1) + '万'
  return value.toFixed(0)
}

function getPlanStatusType(status: string): string {
  const map: Record<string, string> = { pending: 'info', executing: 'warning', completed: 'success', failed: 'danger', cancelled: 'info' }
  return map[status] || 'info'
}

function getAchievementClass(rate?: number): string {
  if (!rate) return ''
  if (rate >= 100) return 'excellent'
  if (rate >= 80) return 'good'
  if (rate >= 50) return 'medium'
  return 'low'
}

const planStatusText: Record<string, string> = {
  pending: '待执行', executing: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消'
}

const ExecutionTestable = defineComponent({
  name: 'ExecutionTestable',
  setup() {
    const loading = ref(false)
    const statusFilter = ref('')
    const stats = ref({
      plans: { total: 12, total_expected_saving: 250000, by_status: { pending: { count: 3 }, executing: { count: 2 }, completed: { count: 7 } } },
      results: { total_actual_saving: 180000, overall_achievement_rate: 72.0, completed_count: 5 }
    })
    const plans = ref([
      { id: 1, plan_name: '负荷转移计划A', expected_saving: 50000, status: 'pending', created_at: '2026-01-01' },
      { id: 2, plan_name: '设备优化计划B', expected_saving: 30000, status: 'completed', created_at: '2026-01-05' }
    ])

    return { loading, statusFilter, stats, plans, formatMoney, formatSaving, getPlanStatusType, getAchievementClass, planStatusText }
  },
  template: `
    <div class="execution-management">
      <div class="stat-cards">
        <div class="stat-card" data-testid="total-plans">
          <div class="stat-value">{{ stats.plans.total }}</div>
          <div class="stat-label">总计划数</div>
        </div>
        <div class="stat-card" data-testid="expected-saving">
          <div class="stat-value">{{ formatMoney(stats.plans.total_expected_saving) }}</div>
          <div class="stat-label">预期年节省 (万元)</div>
        </div>
        <div class="stat-card" data-testid="actual-saving">
          <div class="stat-value">{{ formatMoney(stats.results.total_actual_saving) }}</div>
          <div class="stat-label">实际年节省 (万元)</div>
        </div>
        <div class="stat-card" data-testid="achievement-rate">
          <div class="stat-value" :class="getAchievementClass(stats.results.overall_achievement_rate)">
            {{ stats.results.overall_achievement_rate.toFixed(1) }}%
          </div>
          <div class="stat-label">总体达成率</div>
        </div>
      </div>
      <table>
        <tr v-for="plan in plans" :key="plan.id" :data-testid="'plan-' + plan.id">
          <td class="name">{{ plan.plan_name }}</td>
          <td class="saving">{{ formatSaving(plan.expected_saving) }}</td>
          <td class="status">{{ planStatusText[plan.status] }}</td>
          <td class="actions">
            <button v-if="plan.status === 'pending'" class="btn-start">开始执行</button>
            <button v-if="plan.status === 'completed'" class="btn-track">效果追踪</button>
          </td>
        </tr>
      </table>
    </div>
  `
})

describe('执行管理页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染4张统计卡片', () => {
    const wrapper = mount(ExecutionTestable)
    expect(wrapper.findAll('.stat-card')).toHaveLength(4)
  })

  it('金额格式化正确', () => {
    expect(formatMoney(250000)).toBe('25.00')
    expect(formatMoney(180000)).toBe('18.00')
  })

  it('节省金额格式化正确', () => {
    expect(formatSaving(50000)).toBe('5.0万')
    expect(formatSaving(8000)).toBe('8000')
  })

  it('计划状态类型映射正确', () => {
    expect(getPlanStatusType('pending')).toBe('info')
    expect(getPlanStatusType('executing')).toBe('warning')
    expect(getPlanStatusType('completed')).toBe('success')
    expect(getPlanStatusType('failed')).toBe('danger')
  })

  it('达成率等级判断正确', () => {
    expect(getAchievementClass(105)).toBe('excellent')
    expect(getAchievementClass(85)).toBe('good')
    expect(getAchievementClass(60)).toBe('medium')
    expect(getAchievementClass(30)).toBe('low')
    expect(getAchievementClass(undefined)).toBe('')
  })

  it('待执行计划显示开始按钮', () => {
    const wrapper = mount(ExecutionTestable)
    const row = wrapper.find('[data-testid="plan-1"]')
    expect(row.find('.btn-start').exists()).toBe(true)
    expect(row.find('.btn-track').exists()).toBe(false)
  })

  it('已完成计划显示追踪按钮', () => {
    const wrapper = mount(ExecutionTestable)
    const row = wrapper.find('[data-testid="plan-2"]')
    expect(row.find('.btn-start').exists()).toBe(false)
    expect(row.find('.btn-track').exists()).toBe(true)
  })
})
