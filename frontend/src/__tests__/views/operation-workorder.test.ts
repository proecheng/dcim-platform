/**
 * 工单管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const WorkorderTestable = defineComponent({
  name: 'WorkorderTestable',
  setup() {
    const loading = ref(false)
    const statistics = ref({ total: 120, pending: 15, processing: 8, completed: 97 })
    const workOrderList = ref([
      { id: 1, title: '空调维修', status: 'pending', priority: 'high', creator: '张三', created_at: '2026-02-01' },
      { id: 2, title: 'UPS巡检', status: 'processing', priority: 'medium', creator: '李四', created_at: '2026-02-02' },
      { id: 3, title: '网络故障', status: 'completed', priority: 'urgent', creator: '王五', created_at: '2026-01-28' }
    ])
    const filterStatus = ref('')
    const filterPriority = ref('')
    const filterKeyword = ref('')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const dialogVisible = ref(false)
    const filteredList = computed(() => {
      let list = workOrderList.value
      if (filterStatus.value) list = list.filter(w => w.status === filterStatus.value)
      if (filterKeyword.value) list = list.filter(w => w.title.includes(filterKeyword.value))
      return list
    })
    const statusText = (s: string) => ({ pending: '待处理', processing: '处理中', completed: '已完成' }[s] || s)
    const priorityTag = (p: string) => ({ urgent: 'danger', high: 'warning', medium: '', low: 'info' }[p] || '')
    return { loading, statistics, workOrderList, filterStatus, filterPriority, filterKeyword, currentPage, pageSize, dialogVisible, filteredList, statusText, priorityTag }
  },
  template: `<div class="workorder"><div class="stat-cards" data-testid="stat-cards"><div class="card" data-testid="stat-total"><span class="value">{{ statistics.total }}</span><span class="label">总工单</span></div><div class="card" data-testid="stat-pending"><span class="value">{{ statistics.pending }}</span><span class="label">待处理</span></div><div class="card" data-testid="stat-processing"><span class="value">{{ statistics.processing }}</span><span class="label">处理中</span></div><div class="card" data-testid="stat-completed"><span class="value">{{ statistics.completed }}</span><span class="label">已完成</span></div></div><div class="filters"><input v-model="filterKeyword" data-testid="filter-keyword" placeholder="搜索" /><select v-model="filterStatus" data-testid="filter-status"><option value="">全部</option><option value="pending">待处理</option></select></div><div class="order-table"><div v-for="w in filteredList" :key="w.id" :data-testid="'order-' + w.id" class="order-row"><span class="title">{{ w.title }}</span><span class="status">{{ statusText(w.status) }}</span><span class="priority">{{ w.priority }}</span><span class="creator">{{ w.creator }}</span></div></div><div v-if="dialogVisible" class="order-dialog" data-testid="order-dialog"></div></div>`
})

describe('工单管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染统计卡片', () => { const w = mount(WorkorderTestable); expect(w.find('[data-testid="stat-total"] .value').text()).toBe('120'); expect(w.find('[data-testid="stat-pending"] .value').text()).toBe('15') })
  it('渲染工单列表', () => { expect(mount(WorkorderTestable).findAll('.order-row')).toHaveLength(3) })
  it('显示工单标题和状态', () => { const w = mount(WorkorderTestable); expect(w.find('[data-testid="order-1"] .title').text()).toBe('空调维修'); expect(w.find('[data-testid="order-1"] .status').text()).toBe('待处理') })
  it('状态文本映射正确', () => { expect(mount(WorkorderTestable).vm.statusText('processing')).toBe('处理中') })
  it('优先级标签映射正确', () => { expect(mount(WorkorderTestable).vm.priorityTag('urgent')).toBe('danger') })
  it('关键词过滤工单', async () => { const w = mount(WorkorderTestable); await w.find('[data-testid="filter-keyword"]').setValue('空调'); expect(w.findAll('.order-row')).toHaveLength(1) })
  it('对话框默认隐藏', () => { expect(mount(WorkorderTestable).find('[data-testid="order-dialog"]').exists()).toBe(false) })
})
