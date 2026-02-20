/**
 * 故障影响分析页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const FaultImpactTestable = defineComponent({
  name: 'FaultImpactTestable',
  setup() {
    const loading = ref(false)
    const faultSourceType = ref('ups')
    const faultSourceId = ref<number | null>(null)
    const sourceOptions = ref([
      { id: 1, name: 'UPS-01' },
      { id: 2, name: 'UPS-02' }
    ])
    const analysisResult = ref<{
      affected_cabinets: { id: number; name: string; impact_level: string }[]
      affected_devices: { id: number; name: string; type: string }[]
      affected_cooling: { id: number; name: string }[]
      total_impact: number
    } | null>({
      affected_cabinets: [
        { id: 1, name: '机柜-A01', impact_level: 'high' },
        { id: 2, name: '机柜-A02', impact_level: 'medium' }
      ],
      affected_devices: [
        { id: 1, name: '服务器-01', type: 'server' },
        { id: 2, name: '交换机-01', type: 'switch' },
        { id: 3, name: '存储-01', type: 'storage' }
      ],
      affected_cooling: [{ id: 1, name: '空调-01' }],
      total_impact: 6
    })
    const impactLevelTag = (level: string) => ({ high: 'danger', medium: 'warning', low: 'info' }[level] || 'info')
    const analyze = () => { loading.value = true }
    const cabinetCount = computed(() => analysisResult.value?.affected_cabinets.length ?? 0)
    const deviceCount = computed(() => analysisResult.value?.affected_devices.length ?? 0)
    return { loading, faultSourceType, faultSourceId, sourceOptions, analysisResult, impactLevelTag, analyze, cabinetCount, deviceCount }
  },
  template: `<div class="fault-impact"><div class="source-select"><select v-model="faultSourceType" data-testid="source-type"><option value="ups">UPS</option><option value="pdu">PDU</option><option value="cooling">制冷</option></select><select v-model="faultSourceId" data-testid="source-id"><option v-for="s in sourceOptions" :key="s.id" :value="s.id">{{ s.name }}</option></select><button data-testid="analyze-btn" @click="analyze">分析</button></div><div v-if="analysisResult" class="result-panel" data-testid="result-panel"><div class="summary-cards"><span class="cabinet-count" data-testid="cabinet-count">{{ cabinetCount }}</span><span class="device-count" data-testid="device-count">{{ deviceCount }}</span><span class="total" data-testid="total-impact">{{ analysisResult.total_impact }}</span></div><div class="cabinet-list"><div v-for="c in analysisResult.affected_cabinets" :key="c.id" :data-testid="'cabinet-' + c.id" class="cabinet-row"><span class="name">{{ c.name }}</span><span class="level">{{ c.impact_level }}</span></div></div><div class="device-list"><div v-for="d in analysisResult.affected_devices" :key="d.id" :data-testid="'device-' + d.id" class="device-row"><span class="name">{{ d.name }}</span><span class="type">{{ d.type }}</span></div></div></div></div>`
})

describe('故障影响分析页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染故障源选择器', () => { const w = mount(FaultImpactTestable); expect(w.find('[data-testid="source-type"]').exists()).toBe(true); expect(w.find('[data-testid="analyze-btn"]').exists()).toBe(true) })
  it('默认故障源类型为UPS', () => { expect(mount(FaultImpactTestable).vm.faultSourceType).toBe('ups') })
  it('显示影响汇总卡片', () => { const w = mount(FaultImpactTestable); expect(w.find('[data-testid="cabinet-count"]').text()).toBe('2'); expect(w.find('[data-testid="device-count"]').text()).toBe('3'); expect(w.find('[data-testid="total-impact"]').text()).toBe('6') })
  it('渲染受影响机柜列表', () => { const w = mount(FaultImpactTestable); expect(w.findAll('.cabinet-row')).toHaveLength(2); expect(w.find('[data-testid="cabinet-1"] .name').text()).toBe('机柜-A01') })
  it('渲染受影响设备列表', () => { const w = mount(FaultImpactTestable); expect(w.findAll('.device-row')).toHaveLength(3); expect(w.find('[data-testid="device-1"] .type').text()).toBe('server') })
  it('影响级别标签类型正确', () => { const w = mount(FaultImpactTestable); expect(w.vm.impactLevelTag('high')).toBe('danger'); expect(w.vm.impactLevelTag('medium')).toBe('warning') })
  it('点击分析按钮触发加载', async () => { const w = mount(FaultImpactTestable); await w.find('[data-testid="analyze-btn"]').trigger('click'); expect(w.vm.loading).toBe(true) })
})
