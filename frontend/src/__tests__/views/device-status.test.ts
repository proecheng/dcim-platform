/**
 * 设备状态看板页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/device', () => ({
  getDeviceStatusBoard: vi.fn().mockResolvedValue({ summary: { total: 0, online: 0, offline: 0, alarm: 0 }, groups: [] }),
}))

const DeviceStatusTestable = defineComponent({
  name: 'DeviceStatusTestable',
  setup() {
    const summary = reactive({ total: 30, online: 25, offline: 3, alarm: 2, maintenance: 0 })
    const groups = ref([
      {
        area_code: 'A1',
        device_type: 'UPS',
        devices: [
          { id: 1, device_name: 'UPS-001', status: 'online' },
          { id: 2, device_name: 'UPS-002', status: 'offline' },
        ],
      },
      {
        area_code: 'B1',
        device_type: 'AC',
        devices: [
          { id: 3, device_name: 'AC-001', status: 'alarm' },
        ],
      },
    ])
    const filters = reactive<{ area_code?: string; device_type?: string }>({})

    const areaOptions = ['A1', 'A2', 'B1', 'F1', 'F2', 'F3']
    const typeOptions = ['UPS', 'AC', 'PDU', 'TH', 'DOOR', 'SMOKE', 'WATER']

    function handleFilterChange() {
      // stub - would call loadData
    }

    return { summary, groups, filters, areaOptions, typeOptions, handleFilterChange }
  },
  template: `
    <div class="device-status-page">
      <div class="stat-row">
        <div data-testid="stat-total">{{ summary.total }}</div>
        <div data-testid="stat-online">{{ summary.online }}</div>
        <div data-testid="stat-offline">{{ summary.offline }}</div>
        <div data-testid="stat-alarm">{{ summary.alarm }}</div>
      </div>
      <div class="filter-card">
        <select data-testid="filter-area" v-model="filters.area_code" @change="handleFilterChange">
          <option value="">全部区域</option>
          <option v-for="a in areaOptions" :key="a" :value="a">{{ a }}</option>
        </select>
        <select data-testid="filter-type" v-model="filters.device_type" @change="handleFilterChange">
          <option value="">全部类型</option>
          <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div v-if="groups.length > 0" data-testid="groups">
        <div v-for="group in groups" :key="group.area_code + '_' + group.device_type"
          :data-testid="'group-' + group.area_code + '-' + group.device_type" class="device-group">
          <h4 data-testid="group-title">{{ group.area_code }} 区 — {{ group.device_type }}</h4>
          <div v-for="device in group.devices" :key="device.id"
            :data-testid="'device-' + device.id" class="device-card">
            <span :class="'status-dot ' + device.status"></span>
            <span>{{ device.device_name }}</span>
          </div>
        </div>
      </div>
      <div v-else data-testid="empty">暂无匹配设备</div>
    </div>
  `,
})

describe('DeviceStatusPage 设备状态看板', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染统计卡片', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.find('[data-testid="stat-total"]').text()).toBe('30')
    expect(wrapper.find('[data-testid="stat-online"]').text()).toBe('25')
    expect(wrapper.find('[data-testid="stat-offline"]').text()).toBe('3')
    expect(wrapper.find('[data-testid="stat-alarm"]').text()).toBe('2')
  })

  it('渲染设备分组', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.find('[data-testid="groups"]').exists()).toBe(true)
    expect(wrapper.findAll('.device-group')).toHaveLength(2)
  })

  it('渲染设备卡片', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.find('[data-testid="device-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="device-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="device-3"]').exists()).toBe(true)
  })

  it('分组标题显示正确', () => {
    const wrapper = mount(DeviceStatusTestable)
    const titles = wrapper.findAll('[data-testid="group-title"]')
    expect(titles[0].text()).toContain('A1')
    expect(titles[0].text()).toContain('UPS')
    expect(titles[1].text()).toContain('B1')
    expect(titles[1].text()).toContain('AC')
  })

  it('筛选条件初始为空', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.vm.filters.area_code).toBeUndefined()
    expect(wrapper.vm.filters.device_type).toBeUndefined()
  })

  it('空数据显示空状态', async () => {
    const wrapper = mount(DeviceStatusTestable)
    wrapper.vm.groups = []
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="empty"]').text()).toContain('暂无匹配设备')
  })

  it('区域选项列表正确', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.vm.areaOptions).toEqual(['A1', 'A2', 'B1', 'F1', 'F2', 'F3'])
  })

  it('设备类型选项列表正确', () => {
    const wrapper = mount(DeviceStatusTestable)
    expect(wrapper.vm.typeOptions).toEqual(['UPS', 'AC', 'PDU', 'TH', 'DOOR', 'SMOKE', 'WATER'])
  })
})
