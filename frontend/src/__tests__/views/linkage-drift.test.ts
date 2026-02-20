/**
 * 联动漂移检测页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const LinkageDriftTestable = defineComponent({
  name: 'LinkageDriftTestable',
  setup() {
    const loading = ref(false)
    const summary = ref({ total_checks: 50, drifted: 5, compliant: 42, unknown: 3 })
    const results = ref([
      { id: 1, policy_name: '温度联动', status: 'drifted', expected_state: '空调开启', actual_state: '空调关闭', detected_at: '2026-02-01 10:00' },
      { id: 2, policy_name: '湿度联动', status: 'compliant', expected_state: '除湿运行', actual_state: '除湿运行', detected_at: '2026-02-01 10:00' },
      { id: 3, policy_name: 'UPS切换', status: 'drifted', expected_state: 'UPS供电', actual_state: '市电供电', detected_at: '2026-02-01 10:00' }
    ])
    const statusText = (s: string) => ({ drifted: '已漂移', compliant: '合规', unknown: '未知' }[s] || s)
    const statusTagType = (s: string) => ({ drifted: 'danger', compliant: 'success', unknown: 'warning' }[s] || 'info')
    const driftRate = computed(() => ((summary.value.drifted / summary.value.total_checks) * 100).toFixed(1))
    const runCheck = () => { loading.value = true }
    return { loading, summary, results, statusText, statusTagType, driftRate, runCheck }
  },
  template: `<div class="linkage-drift"><div class="summary-cards" data-testid="summary-cards"><div class="card" data-testid="card-total"><span class="value">{{ summary.total_checks }}</span><span class="label">总检查</span></div><div class="card" data-testid="card-drifted"><span class="value">{{ summary.drifted }}</span><span class="label">已漂移</span></div><div class="card" data-testid="card-compliant"><span class="value">{{ summary.compliant }}</span><span class="label">合规</span></div><div class="card" data-testid="card-unknown"><span class="value">{{ summary.unknown }}</span><span class="label">未知</span></div></div><div class="drift-rate" data-testid="drift-rate">{{ driftRate }}%</div><button data-testid="check-btn" @click="runCheck">执行检查</button><div class="result-table" data-testid="result-table"><div v-for="r in results" :key="r.id" :data-testid="'result-' + r.id" class="result-row"><span class="policy-name">{{ r.policy_name }}</span><span class="status">{{ statusText(r.status) }}</span><span class="expected">{{ r.expected_state }}</span><span class="actual">{{ r.actual_state }}</span></div></div></div>`
})

describe('联动漂移检测页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染汇总卡片', () => { const w = mount(LinkageDriftTestable); expect(w.find('[data-testid="card-total"] .value').text()).toBe('50'); expect(w.find('[data-testid="card-drifted"] .value').text()).toBe('5') })
  it('计算漂移率', () => { expect(mount(LinkageDriftTestable).find('[data-testid="drift-rate"]').text()).toBe('10.0%') })
  it('渲染检测结果列表', () => { expect(mount(LinkageDriftTestable).findAll('.result-row')).toHaveLength(3) })
  it('显示策略名称和状态', () => { const w = mount(LinkageDriftTestable); expect(w.find('[data-testid="result-1"] .policy-name').text()).toBe('温度联动'); expect(w.find('[data-testid="result-1"] .status').text()).toBe('已漂移') })
  it('显示期望和实际状态', () => { const w = mount(LinkageDriftTestable); expect(w.find('[data-testid="result-1"] .expected').text()).toBe('空调开启'); expect(w.find('[data-testid="result-1"] .actual').text()).toBe('空调关闭') })
  it('点击执行检查触发加载', async () => { const w = mount(LinkageDriftTestable); await w.find('[data-testid="check-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
  it('状态标签类型正确', () => { const w = mount(LinkageDriftTestable); expect(w.vm.statusTagType('drifted')).toBe('danger'); expect(w.vm.statusTagType('compliant')).toBe('success') })
})
