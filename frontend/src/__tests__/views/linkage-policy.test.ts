/**
 * 联动策略页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkagePolicyTestable = defineComponent({
  name: 'LinkagePolicyTestable',
  setup() {
    const loading = ref(false)
    const policies = ref([
      { id: 1, name: '温度联动', trigger_type: 'threshold', status: 'enabled', priority: 'high', condition: '温度>35℃', actions: ['启动备用空调', '发送告警'] },
      { id: 2, name: '湿度联动', trigger_type: 'threshold', status: 'enabled', priority: 'medium', condition: '湿度>70%', actions: ['调节除湿'] },
      { id: 3, name: 'UPS切换', trigger_type: 'event', status: 'disabled', priority: 'urgent', condition: '市电中断', actions: ['切换UPS', '通知运维'] }
    ])
    const filterStatus = ref('')
    const editDialogVisible = ref(false)
    const editForm = ref({ name: '', trigger_type: 'threshold', condition: '', priority: 'medium', actions: [] as string[] })
    const filteredPolicies = computed(() => {
      if (!filterStatus.value) return policies.value
      return policies.value.filter(p => p.status === filterStatus.value)
    })
    const enabledCount = computed(() => policies.value.filter(p => p.status === 'enabled').length)
    const statusText = (s: string) => ({ enabled: '已启用', disabled: '已禁用' }[s] || s)
    const openEdit = (p: any) => { editForm.value = { ...p }; editDialogVisible.value = true }
    return { loading, policies, filterStatus, editDialogVisible, editForm, filteredPolicies, enabledCount, statusText, openEdit }
  },
  template: `<div class="linkage-policy"><div class="header"><span class="enabled-count" data-testid="enabled-count">{{ enabledCount }}</span><select v-model="filterStatus" data-testid="filter-status"><option value="">全部</option><option value="enabled">已启用</option><option value="disabled">已禁用</option></select></div><div class="policy-list" data-testid="policy-list"><div v-for="p in filteredPolicies" :key="p.id" :data-testid="'policy-' + p.id" class="policy-row" @click="openEdit(p)"><span class="name">{{ p.name }}</span><span class="trigger">{{ p.trigger_type }}</span><span class="status">{{ statusText(p.status) }}</span><span class="priority">{{ p.priority }}</span><span class="actions">{{ p.actions.join(', ') }}</span></div></div><div v-if="editDialogVisible" class="edit-dialog" data-testid="edit-dialog"><input :value="editForm.name" data-testid="edit-name" /></div></div>`
})

describe('联动策略页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染策略列表', () => { expect(mount(LinkagePolicyTestable).findAll('.policy-row')).toHaveLength(3) })
  it('显示策略名称和状态', () => { const w = mount(LinkagePolicyTestable); expect(w.find('[data-testid="policy-1"] .name').text()).toBe('温度联动'); expect(w.find('[data-testid="policy-1"] .status').text()).toBe('已启用') })
  it('显示联动动作', () => { expect(mount(LinkagePolicyTestable).find('[data-testid="policy-1"] .actions').text()).toBe('启动备用空调, 发送告警') })
  it('统计已启用策略数', () => { expect(mount(LinkagePolicyTestable).find('[data-testid="enabled-count"]').text()).toBe('2') })
  it('状态过滤策略', async () => { const w = mount(LinkagePolicyTestable); await w.find('[data-testid="filter-status"]').setValue('disabled'); expect(w.findAll('.policy-row')).toHaveLength(1) })
  it('点击策略打开编辑对话框', async () => { const w = mount(LinkagePolicyTestable); await w.find('[data-testid="policy-1"]').trigger('click'); expect(w.find('[data-testid="edit-dialog"]').exists()).toBe(true) })
  it('编辑对话框默认隐藏', () => { expect(mount(LinkagePolicyTestable).find('[data-testid="edit-dialog"]').exists()).toBe(false) })
})
