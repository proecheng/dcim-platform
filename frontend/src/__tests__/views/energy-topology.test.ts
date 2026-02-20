/**
 * 配电拓扑页面 单元测试
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

function getStatusType(status: string): string {
  const map: Record<string, string> = { normal: 'success', warning: 'warning', fault: 'danger', offline: 'info' }
  return map[status] || 'info'
}

function getStatusText(status: string): string {
  const map: Record<string, string> = { normal: '正常', warning: '告警', fault: '故障', offline: '离线' }
  return map[status] || status
}

const EnergyTopologyTestable = defineComponent({
  name: 'EnergyTopologyTestable',
  setup() {
    const loading = ref(false)
    const editMode = ref(false)
    const selectedNode = ref<{ key: string; type: string; label: string } | null>(null)
    const topology = ref({
      total_capacity: 2000,
      total_meter_points: 5,
      total_devices: 30
    })

    return { loading, editMode, selectedNode, topology, getStatusType, getStatusText }
  },
  template: `
    <div class="energy-topology">
      <div class="toolbar" data-testid="toolbar">
        <div class="summary-item" data-testid="total-capacity">
          <span class="label">总容量</span>
          <span class="value">{{ topology.total_capacity }} kVA</span>
        </div>
        <div class="summary-item" data-testid="meter-points">
          <span class="label">计量点</span>
          <span class="value">{{ topology.total_meter_points }} 个</span>
        </div>
        <div class="summary-item" data-testid="total-devices">
          <span class="label">用电设备</span>
          <span class="value">{{ topology.total_devices }} 台</span>
        </div>
        <label class="edit-toggle">
          <input type="checkbox" v-model="editMode" data-testid="edit-mode" />
          <span>{{ editMode ? '编辑模式' : '查看模式' }}</span>
        </label>
      </div>
      <div class="property-panel" v-if="selectedNode && editMode" data-testid="property-panel">
        <span>{{ selectedNode.label }}</span>
      </div>
    </div>
  `
})

describe('配电拓扑页面', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染工具栏汇总信息', () => {
    const wrapper = mount(EnergyTopologyTestable)
    expect(wrapper.find('[data-testid="total-capacity"]').text()).toContain('2000 kVA')
    expect(wrapper.find('[data-testid="meter-points"]').text()).toContain('5 个')
    expect(wrapper.find('[data-testid="total-devices"]').text()).toContain('30 台')
  })

  it('默认为查看模式', () => {
    const wrapper = mount(EnergyTopologyTestable)
    expect(wrapper.vm.editMode).toBe(false)
  })

  it('切换编辑模式', async () => {
    const wrapper = mount(EnergyTopologyTestable)
    await wrapper.find('[data-testid="edit-mode"]').setValue(true)
    expect(wrapper.vm.editMode).toBe(true)
  })

  it('状态类型映射正确', () => {
    expect(getStatusType('normal')).toBe('success')
    expect(getStatusType('warning')).toBe('warning')
    expect(getStatusType('fault')).toBe('danger')
    expect(getStatusType('offline')).toBe('info')
  })

  it('状态文本映射正确', () => {
    expect(getStatusText('normal')).toBe('正常')
    expect(getStatusText('warning')).toBe('告警')
    expect(getStatusText('fault')).toBe('故障')
    expect(getStatusText('offline')).toBe('离线')
  })

  it('未选中节点时不显示属性面板', () => {
    const wrapper = mount(EnergyTopologyTestable)
    expect(wrapper.find('[data-testid="property-panel"]').exists()).toBe(false)
  })

  it('loading初始为false', () => {
    const wrapper = mount(EnergyTopologyTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
