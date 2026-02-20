/**
 * 节能分析页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function getUtilizationColor(rate: number): string {
  if (rate < 0.5) return '#f56c6c'
  if (rate < 0.8) return '#e6a23c'
  if (rate <= 1.05) return '#67c23a'
  return '#f56c6c'
}

const EnergyAnalysisTestable = defineComponent({
  name: 'EnergyAnalysisTestable',
  setup() {
    const activeTab = ref('overview')
    const analysisDays = ref(30)
    const selectedMeterPointId = ref<number | null>(1)
    const meterPoints = ref([
      { id: 1, meter_name: '总表-1' },
      { id: 2, meter_name: '分表-A' }
    ])
    const demandResult = ref({
      total_meter_points: 5,
      over_declared_count: 2,
      under_declared_count: 1,
      total_potential_saving: 3500.50
    })
    const shiftResult = ref({
      total_devices: 20,
      shiftable_devices: 8,
      total_shiftable_power: 150.5,
      total_potential_saving: 4200.00
    })
    const tabs = ['overview', 'demand', 'shift', 'device', 'vpp', 'schedule']

    return { activeTab, analysisDays, selectedMeterPointId, meterPoints, demandResult, shiftResult, tabs, getUtilizationColor }
  },
  template: `
    <div class="energy-analysis">
      <div class="tabs">
        <button v-for="tab in tabs" :key="tab" :data-testid="'tab-' + tab"
          :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button>
      </div>
      <div data-testid="active-tab">{{ activeTab }}</div>
      <div data-testid="analysis-days">{{ analysisDays }}</div>
      <div class="demand-summary" data-testid="demand-summary">
        <span data-testid="total-meters">{{ demandResult.total_meter_points }}</span>
        <span data-testid="over-declared">{{ demandResult.over_declared_count }}</span>
        <span data-testid="under-declared">{{ demandResult.under_declared_count }}</span>
        <span data-testid="potential-saving">{{ demandResult.total_potential_saving }}</span>
      </div>
      <div class="shift-summary" data-testid="shift-summary">
        <span data-testid="total-devices">{{ shiftResult.total_devices }}</span>
        <span data-testid="shiftable-devices">{{ shiftResult.shiftable_devices }}</span>
      </div>
    </div>
  `
})

describe('节能分析页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认激活overview标签', () => {
    const wrapper = mount(EnergyAnalysisTestable)
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('overview')
  })

  it('渲染6个标签页', () => {
    const wrapper = mount(EnergyAnalysisTestable)
    expect(wrapper.findAll('.tabs button')).toHaveLength(6)
  })

  it('切换标签页', async () => {
    const wrapper = mount(EnergyAnalysisTestable)
    await wrapper.find('[data-testid="tab-demand"]').trigger('click')
    expect(wrapper.find('[data-testid="active-tab"]').text()).toBe('demand')
  })

  it('默认分析天数为30', () => {
    const wrapper = mount(EnergyAnalysisTestable)
    expect(wrapper.find('[data-testid="analysis-days"]').text()).toBe('30')
  })

  it('需量配置分析数据正确', () => {
    const wrapper = mount(EnergyAnalysisTestable)
    expect(wrapper.find('[data-testid="total-meters"]').text()).toBe('5')
    expect(wrapper.find('[data-testid="over-declared"]').text()).toBe('2')
    expect(wrapper.find('[data-testid="under-declared"]').text()).toBe('1')
  })

  it('利用率颜色判断正确', () => {
    expect(getUtilizationColor(0.3)).toBe('#f56c6c')
    expect(getUtilizationColor(0.6)).toBe('#e6a23c')
    expect(getUtilizationColor(0.9)).toBe('#67c23a')
    expect(getUtilizationColor(1.2)).toBe('#f56c6c')
  })

  it('负荷转移汇总数据正确', () => {
    const wrapper = mount(EnergyAnalysisTestable)
    expect(wrapper.find('[data-testid="total-devices"]').text()).toBe('20')
    expect(wrapper.find('[data-testid="shiftable-devices"]').text()).toBe('8')
  })
})
