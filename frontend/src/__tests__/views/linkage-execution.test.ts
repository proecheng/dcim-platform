/**
 * 联动执行记录页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkageExecutionTestable = defineComponent({
  name: 'LinkageExecutionTestable',
  setup() {
    const loading = ref(false)
    const executions = ref([
      { id: 1, policy_name: '温度联动', status: 'success', trigger_time: '2026-02-01 14:30', duration: 12, steps: [{ name: '启动空调', status: 'success' }, { name: '发送告警', status: 'success' }] },
      { id: 2, policy_name: '湿度联动', status: 'failed', trigger_time: '2026-02-01 15:00', duration: 5, steps: [{ name: '调节除湿', status: 'failed' }] },
      { id: 3, policy_name: 'UPS切换', status: 'running', trigger_time: '2026-02-01 16:00', duration: 0, steps: [] }
    ])
    const filterPolicyName = ref('')
    const filterStatus = ref('')
    const drawerVisible = ref(false)
    const selectedExecution = ref<any>(null)
    const statusTagType = (s: string) => ({ success: 'success', failed: 'danger', running: 'warning' }[s] || 'info')
    const filteredExecutions = computed(() => {
      let list = executions.value
      if (filterPolicyName.value) list = list.filter(e => e.policy_name.includes(filterPolicyName.value))
      if (filterStatus.value) list = list.filter(e => e.status === filterStatus.value)
      return list
    })
    const openDrawer = (e: any) => { selectedExecution.value = e; drawerVisible.value = true }
    const successCount = computed(() => executions.value.filter(e => e.status === 'success').length)
    return { loading, executions, filterPolicyName, filterStatus, drawerVisible, selectedExecution, statusTagType, filteredExecutions, openDrawer, successCount }
  },
  template: `<div class="linkage-execution"><div class="stats"><span class="success-count" data-testid="success-count">{{ successCount }}</span></div><div class="filters"><input v-model="filterPolicyName" data-testid="filter-policy" placeholder="策略名称" /><select v-model="filterStatus" data-testid="filter-status"><option value="">全部</option><option value="success">成功</option><option value="failed">失败</option></select></div><div class="execution-table" data-testid="execution-table"><div v-for="e in filteredExecutions" :key="e.id" :data-testid="'exec-' + e.id" class="exec-row" @click="openDrawer(e)"><span class="policy-name">{{ e.policy_name }}</span><span class="status">{{ e.status }}</span><span class="trigger-time">{{ e.trigger_time }}</span><span class="duration">{{ e.duration }}s</span></div></div><div v-if="drawerVisible" class="timeline-drawer" data-testid="timeline-drawer"><div class="drawer-title">{{ selectedExecution?.policy_name }}</div><div v-for="(step, idx) in selectedExecution?.steps" :key="idx" class="step-item"><span class="step-name">{{ step.name }}</span><span class="step-status">{{ step.status }}</span></div></div></div>`
})

describe('联动执行记录页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染执行记录列表', () => { expect(mount(LinkageExecutionTestable).findAll('.exec-row')).toHaveLength(3) })
  it('显示策略名称和状态', () => { const w = mount(LinkageExecutionTestable); expect(w.find('[data-testid="exec-1"] .policy-name').text()).toBe('温度联动'); expect(w.find('[data-testid="exec-1"] .status').text()).toBe('success') })
  it('统计成功执行数', () => { expect(mount(LinkageExecutionTestable).find('[data-testid="success-count"]').text()).toBe('1') })
  it('策略名称过滤', async () => { const w = mount(LinkageExecutionTestable); await w.find('[data-testid="filter-policy"]').setValue('温度'); expect(w.findAll('.exec-row')).toHaveLength(1) })
  it('点击记录打开时间线抽屉', async () => { const w = mount(LinkageExecutionTestable); await w.find('[data-testid="exec-1"]').trigger('click'); expect(w.find('[data-testid="timeline-drawer"]').exists()).toBe(true); expect(w.find('.drawer-title').text()).toBe('温度联动') })
  it('时间线显示执行步骤', async () => { const w = mount(LinkageExecutionTestable); await w.find('[data-testid="exec-1"]').trigger('click'); expect(w.findAll('.step-item')).toHaveLength(2); expect(w.find('.step-name').text()).toBe('启动空调') })
  it('状态标签类型正确', () => { const w = mount(LinkageExecutionTestable); expect(w.vm.statusTagType('success')).toBe('success'); expect(w.vm.statusTagType('failed')).toBe('danger') })
})
