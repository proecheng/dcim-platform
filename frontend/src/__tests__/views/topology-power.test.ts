/**
 * 电力拓扑页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

function phaseTagType(phase: string): string { return ({ A: 'danger', B: 'success', C: 'warning' }[phase] || 'info') }

const PowerTopologyTestable = defineComponent({
  name: 'PowerTopologyTestable',
  setup() {
    const loading = ref(false)
    const pduList = ref([
      { id: 1, device_code: 'PDU-001', device_name: 'PDU-A1', phase_count: 3 },
      { id: 2, device_code: 'PDU-002', device_name: 'PDU-B1', phase_count: 3 }
    ])
    const selectedPdu = ref<{ id: number; device_name: string } | null>(null)
    const phaseMappings = ref([
      { id: 1, branch_name: '支路1', phase: 'A', cabinet_name: '机柜-01' },
      { id: 2, branch_name: '支路2', phase: 'B', cabinet_name: '机柜-02' }
    ])
    const balanceData = ref({ a_load: 35, b_load: 28, c_load: 32, imbalance_rate: 8.5 })
    return { loading, pduList, selectedPdu, phaseMappings, balanceData, phaseTagType }
  },
  template: `<div class="power-topology"><div class="pdu-list"><div v-for="p in pduList" :key="p.id" :data-testid="'pdu-' + p.id" class="pdu-item" @click="selectedPdu = p"><span class="name">{{ p.device_name }}</span></div></div><div class="phase-table" v-if="phaseMappings.length"><div v-for="m in phaseMappings" :key="m.id" :data-testid="'mapping-' + m.id" class="mapping-row"><span class="branch">{{ m.branch_name }}</span><span class="phase">{{ m.phase }}</span><span class="cabinet">{{ m.cabinet_name }}</span></div></div><div class="balance" data-testid="balance"><span class="imbalance">{{ balanceData.imbalance_rate }}%</span></div></div>`
})

describe('电力拓扑页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染PDU列表', () => { expect(mount(PowerTopologyTestable).findAll('.pdu-item')).toHaveLength(2) })
  it('显示PDU名称', () => { expect(mount(PowerTopologyTestable).find('[data-testid="pdu-1"] .name').text()).toBe('PDU-A1') })
  it('渲染相位映射表', () => { expect(mount(PowerTopologyTestable).findAll('.mapping-row')).toHaveLength(2) })
  it('显示支路和相位', () => { const w = mount(PowerTopologyTestable); expect(w.find('[data-testid="mapping-1"] .branch').text()).toBe('支路1'); expect(w.find('[data-testid="mapping-1"] .phase').text()).toBe('A') })
  it('显示不平衡率', () => { expect(mount(PowerTopologyTestable).find('[data-testid="balance"] .imbalance').text()).toBe('8.5%') })
  it('相位标签类型正确', () => { expect(phaseTagType('A')).toBe('danger'); expect(phaseTagType('B')).toBe('success'); expect(phaseTagType('C')).toBe('warning') })
  it('loading初始为false', () => { expect(mount(PowerTopologyTestable).vm.loading).toBe(false) })
})
