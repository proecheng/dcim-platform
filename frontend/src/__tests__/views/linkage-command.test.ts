/**
 * 联动指令页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkageCommandTestable = defineComponent({
  name: 'LinkageCommandTestable',
  setup() {
    const loading = ref(false)
    const activeTab = ref('approvals')
    const approvals = ref([
      { id: 1, command_name: '启动备用空调', policy_name: '温度联动', risk_level: 'high', status: 'pending', requested_at: '2026-02-01 14:30' },
      { id: 2, command_name: '切换UPS', policy_name: 'UPS切换', risk_level: 'critical', status: 'approved', requested_at: '2026-02-01 15:00' }
    ])
    const auditLogs = ref([
      { id: 1, command_name: '调节除湿', operator: '张三', action: 'approve', timestamp: '2026-01-30 10:00' },
      { id: 2, command_name: '关闭空调', operator: '李四', action: 'reject', timestamp: '2026-01-29 09:00' }
    ])
    const riskConfigs = ref([
      { id: 1, risk_level: 'critical', require_approval: true, max_retries: 1 },
      { id: 2, risk_level: 'high', require_approval: true, max_retries: 3 },
      { id: 3, risk_level: 'low', require_approval: false, max_retries: 5 }
    ])
    const pendingCount = computed(() => approvals.value.filter(a => a.status === 'pending').length)
    const riskTagType = (r: string) => ({ critical: 'danger', high: 'warning', medium: '', low: 'info' }[r] || 'info')
    const approveCommand = (a: any) => { a.status = 'approved' }
    const rejectCommand = (a: any) => { a.status = 'rejected' }
    return { loading, activeTab, approvals, auditLogs, riskConfigs, pendingCount, riskTagType, approveCommand, rejectCommand }
  },
  template: `<div class="linkage-command"><div class="tabs"><button :class="{ active: activeTab === 'approvals' }" data-testid="tab-approvals" @click="activeTab = 'approvals'">审批</button><button :class="{ active: activeTab === 'audit' }" data-testid="tab-audit" @click="activeTab = 'audit'">审计日志</button><button :class="{ active: activeTab === 'risk' }" data-testid="tab-risk" @click="activeTab = 'risk'">风险配置</button></div><span class="pending-count" data-testid="pending-count">{{ pendingCount }}</span><div v-if="activeTab === 'approvals'" class="approval-list" data-testid="approval-list"><div v-for="a in approvals" :key="a.id" :data-testid="'approval-' + a.id" class="approval-row"><span class="command-name">{{ a.command_name }}</span><span class="risk-level">{{ a.risk_level }}</span><span class="status">{{ a.status }}</span><button v-if="a.status === 'pending'" class="approve-btn" @click="approveCommand(a)">批准</button><button v-if="a.status === 'pending'" class="reject-btn" @click="rejectCommand(a)">拒绝</button></div></div><div v-if="activeTab === 'audit'" class="audit-list" data-testid="audit-list"><div v-for="l in auditLogs" :key="l.id" :data-testid="'log-' + l.id" class="log-row"><span class="command-name">{{ l.command_name }}</span><span class="operator">{{ l.operator }}</span><span class="action">{{ l.action }}</span></div></div><div v-if="activeTab === 'risk'" class="risk-list" data-testid="risk-list"><div v-for="r in riskConfigs" :key="r.id" :data-testid="'risk-' + r.id" class="risk-row"><span class="risk-level">{{ r.risk_level }}</span><span class="require-approval">{{ r.require_approval ? '需要' : '不需要' }}</span><span class="max-retries">{{ r.max_retries }}</span></div></div></div>`
})

describe('联动指令页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('默认显示审批标签', () => { const w = mount(LinkageCommandTestable); expect(w.vm.activeTab).toBe('approvals'); expect(w.find('[data-testid="approval-list"]').exists()).toBe(true) })
  it('渲染审批列表', () => { const w = mount(LinkageCommandTestable); expect(w.findAll('.approval-row')).toHaveLength(2); expect(w.find('[data-testid="approval-1"] .command-name').text()).toBe('启动备用空调') })
  it('显示待审批数量', () => { expect(mount(LinkageCommandTestable).find('[data-testid="pending-count"]').text()).toBe('1') })
  it('切换到审计日志', async () => { const w = mount(LinkageCommandTestable); await w.find('[data-testid="tab-audit"]').trigger('click'); expect(w.find('[data-testid="audit-list"]').exists()).toBe(true); expect(w.findAll('.log-row')).toHaveLength(2) })
  it('切换到风险配置', async () => { const w = mount(LinkageCommandTestable); await w.find('[data-testid="tab-risk"]').trigger('click'); expect(w.find('[data-testid="risk-list"]').exists()).toBe(true); expect(w.findAll('.risk-row')).toHaveLength(3) })
  it('风险配置显示审批要求', async () => { const w = mount(LinkageCommandTestable); await w.find('[data-testid="tab-risk"]').trigger('click'); expect(w.find('[data-testid="risk-1"] .require-approval').text()).toBe('需要'); expect(w.find('[data-testid="risk-3"] .require-approval').text()).toBe('不需要') })
  it('风险标签类型正确', () => { const w = mount(LinkageCommandTestable); expect(w.vm.riskTagType('critical')).toBe('danger'); expect(w.vm.riskTagType('high')).toBe('warning') })
})
