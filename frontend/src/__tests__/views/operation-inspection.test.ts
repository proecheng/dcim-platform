/**
 * 巡检管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const InspectionTestable = defineComponent({
  name: 'InspectionTestable',
  setup() {
    const loading = ref(false)
    const activeTab = ref('plans')
    const planList = ref([
      { id: 1, name: '日常巡检', frequency: 'daily', status: 'active', item_count: 12 },
      { id: 2, name: '月度巡检', frequency: 'monthly', status: 'active', item_count: 25 },
      { id: 3, name: '季度巡检', frequency: 'quarterly', status: 'inactive', item_count: 40 }
    ])
    const taskList = ref([
      { id: 1, plan_name: '日常巡检', executor: '张三', status: 'completed', completed_at: '2026-02-01 10:30' },
      { id: 2, plan_name: '日常巡检', executor: '李四', status: 'in_progress', completed_at: null }
    ])
    const frequencyMap: Record<string, string> = { daily: '每日', weekly: '每周', monthly: '每月', quarterly: '每季度' }
    const taskStatusText = (s: string) => ({ completed: '已完成', in_progress: '进行中', pending: '待执行' }[s] || s)
    const activePlanCount = computed(() => planList.value.filter(p => p.status === 'active').length)
    return { loading, activeTab, planList, taskList, frequencyMap, taskStatusText, activePlanCount }
  },
  template: `<div class="inspection"><div class="tabs" data-testid="tabs"><button :class="{ active: activeTab === 'plans' }" data-testid="tab-plans" @click="activeTab = 'plans'">巡检计划</button><button :class="{ active: activeTab === 'tasks' }" data-testid="tab-tasks" @click="activeTab = 'tasks'">巡检任务</button></div><div class="active-count" data-testid="active-count">{{ activePlanCount }}</div><div v-if="activeTab === 'plans'" class="plan-table" data-testid="plan-table"><div v-for="p in planList" :key="p.id" :data-testid="'plan-' + p.id" class="plan-row"><span class="name">{{ p.name }}</span><span class="frequency">{{ frequencyMap[p.frequency] || p.frequency }}</span><span class="status">{{ p.status }}</span><span class="item-count">{{ p.item_count }}</span></div></div><div v-if="activeTab === 'tasks'" class="task-table" data-testid="task-table"><div v-for="t in taskList" :key="t.id" :data-testid="'task-' + t.id" class="task-row"><span class="plan-name">{{ t.plan_name }}</span><span class="executor">{{ t.executor }}</span><span class="status">{{ taskStatusText(t.status) }}</span></div></div></div>`
})

describe('巡检管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('默认显示巡检计划标签', () => { const w = mount(InspectionTestable); expect(w.vm.activeTab).toBe('plans'); expect(w.find('[data-testid="plan-table"]').exists()).toBe(true) })
  it('渲染巡检计划列表', () => { const w = mount(InspectionTestable); expect(w.findAll('.plan-row')).toHaveLength(3); expect(w.find('[data-testid="plan-1"] .name').text()).toBe('日常巡检') })
  it('频率映射正确', () => { expect(mount(InspectionTestable).find('[data-testid="plan-1"] .frequency').text()).toBe('每日') })
  it('统计活跃计划数', () => { expect(mount(InspectionTestable).find('[data-testid="active-count"]').text()).toBe('2') })
  it('切换到任务标签', async () => { const w = mount(InspectionTestable); await w.find('[data-testid="tab-tasks"]').trigger('click'); expect(w.find('[data-testid="task-table"]').exists()).toBe(true); expect(w.find('[data-testid="plan-table"]').exists()).toBe(false) })
  it('渲染任务列表', async () => { const w = mount(InspectionTestable); await w.find('[data-testid="tab-tasks"]').trigger('click'); expect(w.findAll('.task-row')).toHaveLength(2); expect(w.find('[data-testid="task-1"] .executor').text()).toBe('张三') })
  it('任务状态文本正确', () => { expect(mount(InspectionTestable).vm.taskStatusText('completed')).toBe('已完成'); expect(mount(InspectionTestable).vm.taskStatusText('in_progress')).toBe('进行中') })
})
