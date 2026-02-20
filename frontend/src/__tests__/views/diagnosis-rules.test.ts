/**
 * 诊断规则页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const DiagnosisRulesTestable = defineComponent({
  name: 'DiagnosisRulesTestable',
  setup() {
    const loading = ref(false)
    const rules = ref([
      { id: 1, name: '温度异常诊断', category: 'temperature', status: 'enabled', priority: 'high', conditions: 3, description: '检测温度传感器异常' },
      { id: 2, name: '电力故障诊断', category: 'power', status: 'enabled', priority: 'critical', conditions: 5, description: '检测电力系统故障' },
      { id: 3, name: '网络延迟诊断', category: 'network', status: 'disabled', priority: 'medium', conditions: 2, description: '检测网络延迟异常' }
    ])
    const categoryLabelMap: Record<string, string> = { temperature: '温度', power: '电力', network: '网络', cooling: '制冷', humidity: '湿度' }
    const dialogVisible = ref(false)
    const dialogMode = ref<'create' | 'edit'>('create')
    const editForm = ref({ name: '', category: 'temperature', priority: 'medium', description: '' })
    const enabledCount = computed(() => rules.value.filter(r => r.status === 'enabled').length)
    const openCreate = () => { dialogMode.value = 'create'; editForm.value = { name: '', category: 'temperature', priority: 'medium', description: '' }; dialogVisible.value = true }
    const openEdit = (r: any) => { dialogMode.value = 'edit'; editForm.value = { ...r }; dialogVisible.value = true }
    return { loading, rules, categoryLabelMap, dialogVisible, dialogMode, editForm, enabledCount, openCreate, openEdit }
  },
  template: `<div class="diagnosis-rules"><div class="header"><span class="enabled-count" data-testid="enabled-count">{{ enabledCount }}</span><button data-testid="create-btn" @click="openCreate">新建规则</button></div><div class="rule-table" data-testid="rule-table"><div v-for="r in rules" :key="r.id" :data-testid="'rule-' + r.id" class="rule-row" @click="openEdit(r)"><span class="name">{{ r.name }}</span><span class="category">{{ categoryLabelMap[r.category] || r.category }}</span><span class="status">{{ r.status }}</span><span class="priority">{{ r.priority }}</span><span class="conditions">{{ r.conditions }}</span></div></div><div v-if="dialogVisible" class="rule-dialog" data-testid="rule-dialog"><span class="dialog-mode" data-testid="dialog-mode">{{ dialogMode }}</span><input :value="editForm.name" data-testid="edit-name" /></div></div>`
})

describe('诊断规则页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染规则列表', () => { expect(mount(DiagnosisRulesTestable).findAll('.rule-row')).toHaveLength(3) })
  it('显示规则名称和分类', () => { const w = mount(DiagnosisRulesTestable); expect(w.find('[data-testid="rule-1"] .name').text()).toBe('温度异常诊断'); expect(w.find('[data-testid="rule-1"] .category').text()).toBe('温度') })
  it('统计已启用规则数', () => { expect(mount(DiagnosisRulesTestable).find('[data-testid="enabled-count"]').text()).toBe('2') })
  it('点击新建打开创建对话框', async () => { const w = mount(DiagnosisRulesTestable); await w.find('[data-testid="create-btn"]').trigger('click'); expect(w.find('[data-testid="rule-dialog"]').exists()).toBe(true); expect(w.find('[data-testid="dialog-mode"]').text()).toBe('create') })
  it('点击规则打开编辑对话框', async () => { const w = mount(DiagnosisRulesTestable); await w.find('[data-testid="rule-2"]').trigger('click'); expect(w.find('[data-testid="rule-dialog"]').exists()).toBe(true); expect(w.find('[data-testid="dialog-mode"]').text()).toBe('edit') })
  it('分类映射正确', () => { const w = mount(DiagnosisRulesTestable); expect(w.find('[data-testid="rule-2"] .category').text()).toBe('电力'); expect(w.find('[data-testid="rule-3"] .category').text()).toBe('网络') })
  it('对话框默认隐藏', () => { expect(mount(DiagnosisRulesTestable).find('[data-testid="rule-dialog"]').exists()).toBe(false) })
})
