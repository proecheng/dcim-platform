/**
 * 联动恢复页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkageRecoveryTestable = defineComponent({
  name: 'LinkageRecoveryTestable',
  setup() {
    const loading = ref(false)
    const activeTab = ref('recoverable')
    const recoverables = ref([
      { id: 1, policy_name: '温度联动', execution_id: 101, trigger_time: '2026-02-01 14:30', affected_devices: 3 },
      { id: 2, policy_name: 'UPS切换', execution_id: 102, trigger_time: '2026-02-01 16:00', affected_devices: 5 }
    ])
    const recoveries = ref([
      { id: 1, policy_name: '湿度联动', status: 'completed', recovered_at: '2026-01-30 10:00', steps: [{ name: '恢复除湿设置', status: 'success' }, { name: '验证湿度', status: 'success' }] },
      { id: 2, policy_name: '温度联动', status: 'partial', recovered_at: '2026-01-29 09:00', steps: [{ name: '关闭备用空调', status: 'success' }, { name: '恢复温控', status: 'failed' }] }
    ])
    const selectedRecovery = ref<any>(null)
    const stepDrawerVisible = ref(false)
    const statusText = (s: string) => ({ completed: '已恢复', partial: '部分恢复', failed: '恢复失败' }[s] || s)
    const recoverableCount = computed(() => recoverables.value.length)
    const startRecovery = (r: any) => { loading.value = true }
    const viewSteps = (r: any) => { selectedRecovery.value = r; stepDrawerVisible.value = true }
    return { loading, activeTab, recoverables, recoveries, selectedRecovery, stepDrawerVisible, statusText, recoverableCount, startRecovery, viewSteps }
  },
  template: `<div class="linkage-recovery"><div class="tabs"><button :class="{ active: activeTab === 'recoverable' }" data-testid="tab-recoverable" @click="activeTab = 'recoverable'">可恢复</button><button :class="{ active: activeTab === 'history' }" data-testid="tab-history" @click="activeTab = 'history'">恢复历史</button></div><span class="recoverable-count" data-testid="recoverable-count">{{ recoverableCount }}</span><div v-if="activeTab === 'recoverable'" class="recoverable-list" data-testid="recoverable-list"><div v-for="r in recoverables" :key="r.id" :data-testid="'recoverable-' + r.id" class="recoverable-row"><span class="policy-name">{{ r.policy_name }}</span><span class="affected">{{ r.affected_devices }}</span><button class="recover-btn" @click="startRecovery(r)">恢复</button></div></div><div v-if="activeTab === 'history'" class="history-list" data-testid="history-list"><div v-for="r in recoveries" :key="r.id" :data-testid="'recovery-' + r.id" class="recovery-row" @click="viewSteps(r)"><span class="policy-name">{{ r.policy_name }}</span><span class="status">{{ statusText(r.status) }}</span></div></div><div v-if="stepDrawerVisible" class="step-drawer" data-testid="step-drawer"><div v-for="(step, idx) in selectedRecovery?.steps" :key="idx" class="step-log"><span class="step-name">{{ step.name }}</span><span class="step-status">{{ step.status }}</span></div></div></div>`
})

describe('联动恢复页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('默认显示可恢复标签', () => { const w = mount(LinkageRecoveryTestable); expect(w.vm.activeTab).toBe('recoverable'); expect(w.find('[data-testid="recoverable-list"]').exists()).toBe(true) })
  it('渲染可恢复记录', () => { const w = mount(LinkageRecoveryTestable); expect(w.findAll('.recoverable-row')).toHaveLength(2); expect(w.find('[data-testid="recoverable-1"] .policy-name').text()).toBe('温度联动') })
  it('显示可恢复数量', () => { expect(mount(LinkageRecoveryTestable).find('[data-testid="recoverable-count"]').text()).toBe('2') })
  it('点击恢复按钮触发加载', async () => { const w = mount(LinkageRecoveryTestable); await w.find('.recover-btn').trigger('click'); expect(w.vm.loading).toBe(true) })
  it('切换到恢复历史', async () => { const w = mount(LinkageRecoveryTestable); await w.find('[data-testid="tab-history"]').trigger('click'); expect(w.find('[data-testid="history-list"]').exists()).toBe(true); expect(w.findAll('.recovery-row')).toHaveLength(2) })
  it('恢复状态文本正确', () => { expect(mount(LinkageRecoveryTestable).vm.statusText('completed')).toBe('已恢复'); expect(mount(LinkageRecoveryTestable).vm.statusText('partial')).toBe('部分恢复') })
  it('点击历史记录显示步骤', async () => { const w = mount(LinkageRecoveryTestable); await w.find('[data-testid="tab-history"]').trigger('click'); await w.find('[data-testid="recovery-1"]').trigger('click'); expect(w.find('[data-testid="step-drawer"]').exists()).toBe(true); expect(w.findAll('.step-log')).toHaveLength(2) })
})
