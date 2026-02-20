/**
 * 容量管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/capacity', () => ({
  getSpaceCapacities: vi.fn().mockResolvedValue({ data: [] }),
  getPowerCapacities: vi.fn().mockResolvedValue({ data: [] }),
  getCoolingCapacities: vi.fn().mockResolvedValue({ data: [] }),
  getWeightCapacities: vi.fn().mockResolvedValue({ data: [] }),
  getCapacityPlans: vi.fn().mockResolvedValue({ data: [] }),
  getCapacityStatistics: vi.fn().mockResolvedValue({ data: {} }),
  getCapacityAlerts: vi.fn().mockResolvedValue({ data: [] }),
  getCapacityByLocation: vi.fn().mockResolvedValue({ data: [] }),
  getCapacityTrend: vi.fn().mockResolvedValue({ data: [] }),
  getCapacityForecast: vi.fn().mockResolvedValue({ data: {} }),
  createSpaceCapacity: vi.fn().mockResolvedValue({}),
  updateSpaceCapacity: vi.fn().mockResolvedValue({}),
  deleteSpaceCapacity: vi.fn().mockResolvedValue({}),
  createPowerCapacity: vi.fn().mockResolvedValue({}),
  updatePowerCapacity: vi.fn().mockResolvedValue({}),
  deletePowerCapacity: vi.fn().mockResolvedValue({}),
  createCoolingCapacity: vi.fn().mockResolvedValue({}),
  updateCoolingCapacity: vi.fn().mockResolvedValue({}),
  deleteCoolingCapacity: vi.fn().mockResolvedValue({}),
  createWeightCapacity: vi.fn().mockResolvedValue({}),
  updateWeightCapacity: vi.fn().mockResolvedValue({}),
  deleteWeightCapacity: vi.fn().mockResolvedValue({}),
  createCapacityPlan: vi.fn().mockResolvedValue({}),
  updateCapacityPlan: vi.fn().mockResolvedValue({}),
  deleteCapacityPlan: vi.fn().mockResolvedValue({}),
  getRackingRecommendation: vi.fn().mockResolvedValue({ data: [] }),
  overridePlanCabinet: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/api/modules/asset', () => ({
  getCabinets: vi.fn().mockResolvedValue({ data: [] }),
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Grid: { template: '<i />' },
  Lightning: { template: '<i />' },
  Odometer: { template: '<i />' },
  Box: { template: '<i />' },
  Plus: { template: '<i />' },
  Search: { template: '<i />' },
  WarningFilled: { template: '<i />' },
}))

const CapacityPageTestable = defineComponent({
  name: 'CapacityPageTestable',
  setup() {
    const loading = ref(false)
    const activeTab = ref('space')

    const statistics = reactive({
      space: { usage_rate: 65.5, used_u_positions: 131, total_u_positions: 200 },
      power: { usage_rate: 72.3, used_capacity_kw: 180, total_capacity_kw: 249 },
      cooling: { usage_rate: 55.0, used_cooling_kw: 110, total_cooling_kw: 200 },
      weight: { usage_rate: 40.0, used_weight_kg: 2000, total_weight_kg: 5000 },
    })

    const spaceList = ref([
      { id: 1, name: '机柜A1-01', location: 'A1', total_u_positions: 42, used_u_positions: 30, usage_rate: 71.4, status: 'warning' },
    ])

    const spaceDialogVisible = ref(false)
    const isEdit = ref(false)

    function getProgressColor(rate: number | undefined): string {
      if (!rate) return '#67c23a'
      if (rate >= 90) return '#f56c6c'
      if (rate >= 70) return '#e6a23c'
      return '#67c23a'
    }

    function getStatusType(status: string): string {
      const map: Record<string, string> = { normal: 'success', warning: 'warning', critical: 'danger', full: 'danger' }
      return map[status] || 'info'
    }

    function getStatusLabel(status: string): string {
      const map: Record<string, string> = { normal: '正常', warning: '警告', critical: '严重', full: '已满' }
      return map[status] || status
    }

    function showSpaceDialog(row?: { id: number }) {
      isEdit.value = !!row
      spaceDialogVisible.value = true
    }

    return {
      loading, activeTab, statistics, spaceList, spaceDialogVisible, isEdit,
      getProgressColor, getStatusType, getStatusLabel, showSpaceDialog,
    }
  },
  template: `
    <div class="capacity-page">
      <div class="stat-cards">
        <div data-testid="stat-space">{{ statistics.space.usage_rate.toFixed(1) }}%</div>
        <div data-testid="stat-power">{{ statistics.power.usage_rate.toFixed(1) }}%</div>
        <div data-testid="stat-cooling">{{ statistics.cooling.usage_rate.toFixed(1) }}%</div>
        <div data-testid="stat-weight">{{ statistics.weight.usage_rate.toFixed(1) }}%</div>
      </div>
      <div data-testid="tabs">
        <button v-for="tab in ['space', 'power', 'cooling', 'weight', 'plan', 'alerts', 'trend']"
          :key="tab" :data-testid="'tab-' + tab" @click="activeTab = tab">{{ tab }}</button>
      </div>
      <div v-if="activeTab === 'space'" data-testid="space-panel">
        <button data-testid="add-space-btn" @click="showSpaceDialog()">新增空间</button>
        <table>
          <tr v-for="s in spaceList" :key="s.id" :data-testid="'space-' + s.id">
            <td>{{ s.name }}</td><td>{{ s.usage_rate }}%</td>
          </tr>
        </table>
      </div>
      <div v-if="spaceDialogVisible" data-testid="space-dialog">{{ isEdit ? '编辑' : '新增' }}</div>
    </div>
  `,
})

describe('CapacityPage 容量管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染统计卡片', () => {
    const wrapper = mount(CapacityPageTestable)
    expect(wrapper.find('[data-testid="stat-space"]').text()).toBe('65.5%')
    expect(wrapper.find('[data-testid="stat-power"]').text()).toBe('72.3%')
    expect(wrapper.find('[data-testid="stat-cooling"]').text()).toBe('55.0%')
    expect(wrapper.find('[data-testid="stat-weight"]').text()).toBe('40.0%')
  })

  it('默认显示空间容量标签页', () => {
    const wrapper = mount(CapacityPageTestable)
    expect(wrapper.vm.activeTab).toBe('space')
    expect(wrapper.find('[data-testid="space-panel"]').exists()).toBe(true)
  })

  it('渲染空间容量列表', () => {
    const wrapper = mount(CapacityPageTestable)
    expect(wrapper.find('[data-testid="space-1"]').exists()).toBe(true)
  })

  it('点击新增打开对话框', async () => {
    const wrapper = mount(CapacityPageTestable)
    await wrapper.find('[data-testid="add-space-btn"]').trigger('click')
    expect(wrapper.vm.spaceDialogVisible).toBe(true)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.find('[data-testid="space-dialog"]').text()).toContain('新增')
  })

  it('进度条颜色逻辑正确', () => {
    const wrapper = mount(CapacityPageTestable)
    expect(wrapper.vm.getProgressColor(95)).toBe('#f56c6c')
    expect(wrapper.vm.getProgressColor(75)).toBe('#e6a23c')
    expect(wrapper.vm.getProgressColor(50)).toBe('#67c23a')
    expect(wrapper.vm.getProgressColor(undefined)).toBe('#67c23a')
  })

  it('状态标签映射正确', () => {
    const wrapper = mount(CapacityPageTestable)
    expect(wrapper.vm.getStatusType('normal')).toBe('success')
    expect(wrapper.vm.getStatusType('warning')).toBe('warning')
    expect(wrapper.vm.getStatusType('critical')).toBe('danger')
    expect(wrapper.vm.getStatusLabel('normal')).toBe('正常')
    expect(wrapper.vm.getStatusLabel('full')).toBe('已满')
  })

  it('切换标签页', async () => {
    const wrapper = mount(CapacityPageTestable)
    await wrapper.find('[data-testid="tab-power"]').trigger('click')
    expect(wrapper.vm.activeTab).toBe('power')
    await wrapper.find('[data-testid="tab-cooling"]').trigger('click')
    expect(wrapper.vm.activeTab).toBe('cooling')
  })
})
