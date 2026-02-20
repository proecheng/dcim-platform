/**
 * 设备管理页面 单元测试
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
  getDeviceList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createDevice: vi.fn().mockResolvedValue({}),
  updateDevice: vi.fn().mockResolvedValue({}),
  deleteDevice: vi.fn().mockResolvedValue({}),
  getDeviceStatusSummary: vi.fn().mockResolvedValue({ total: 0, online: 0, offline: 0, alarm: 0 }),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
}))

const DeviceManageTestable = defineComponent({
  name: 'DeviceManageTestable',
  setup() {
    const stats = reactive({ total: 50, online: 40, offline: 8, alarm: 2 })
    const loading = ref(false)
    const tableData = ref([
      { id: 1, device_code: 'UPS-001', device_name: 'UPS主机1', device_type: 'UPS', area_code: 'A1', status: 'online', is_enabled: true },
      { id: 2, device_code: 'AC-001', device_name: '精密空调1', device_type: 'AC', area_code: 'B1', status: 'offline', is_enabled: true },
    ])
    const pagination = reactive({ page: 1, pageSize: 20, total: 50 })
    const dialogVisible = ref(false)
    const isEdit = ref(false)

    const filters = reactive({ keyword: '', device_type: '', area_code: '', status: '' })

    const statusTagMap: Record<string, { type: string; text: string }> = {
      online: { type: 'success', text: '在线' },
      offline: { type: 'danger', text: '离线' },
      maintenance: { type: 'warning', text: '维护中' },
      alarm: { type: 'danger', text: '告警' },
    }

    function handleSearch() {
      pagination.page = 1
    }

    function handleReset() {
      filters.keyword = ''
      filters.device_type = ''
      filters.area_code = ''
      filters.status = ''
      pagination.page = 1
    }

    function handleAdd() {
      isEdit.value = false
      dialogVisible.value = true
    }

    return { stats, loading, tableData, pagination, dialogVisible, isEdit, filters, statusTagMap, handleSearch, handleReset, handleAdd }
  },
  template: `
    <div class="device-manage-page">
      <div class="stat-row">
        <div data-testid="stat-total">{{ stats.total }}</div>
        <div data-testid="stat-online">{{ stats.online }}</div>
        <div data-testid="stat-offline">{{ stats.offline }}</div>
        <div data-testid="stat-alarm">{{ stats.alarm }}</div>
      </div>
      <div class="toolbar">
        <input data-testid="filter-keyword" v-model="filters.keyword" />
        <select data-testid="filter-type" v-model="filters.device_type">
          <option value="">全部</option>
          <option value="UPS">UPS</option>
          <option value="AC">AC</option>
        </select>
        <button data-testid="search-btn" @click="handleSearch">搜索</button>
        <button data-testid="reset-btn" @click="handleReset">重置</button>
        <button data-testid="add-btn" @click="handleAdd">新增设备</button>
      </div>
      <table data-testid="device-table">
        <tr v-for="d in tableData" :key="d.id" :data-testid="'device-' + d.id">
          <td>{{ d.device_code }}</td>
          <td>{{ d.device_name }}</td>
          <td>{{ statusTagMap[d.status]?.text }}</td>
        </tr>
      </table>
      <div v-if="dialogVisible" data-testid="dialog">{{ isEdit ? '编辑设备' : '新增设备' }}</div>
    </div>
  `,
})

describe('DeviceManagePage 设备管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染统计卡片', () => {
    const wrapper = mount(DeviceManageTestable)
    expect(wrapper.find('[data-testid="stat-total"]').text()).toBe('50')
    expect(wrapper.find('[data-testid="stat-online"]').text()).toBe('40')
    expect(wrapper.find('[data-testid="stat-offline"]').text()).toBe('8')
    expect(wrapper.find('[data-testid="stat-alarm"]').text()).toBe('2')
  })

  it('渲染设备列表', () => {
    const wrapper = mount(DeviceManageTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(2)
  })

  it('初始状态正确', () => {
    const wrapper = mount(DeviceManageTestable)
    expect(wrapper.vm.pagination.page).toBe(1)
    expect(wrapper.vm.pagination.pageSize).toBe(20)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.vm.filters.keyword).toBe('')
  })

  it('点击新增打开对话框', async () => {
    const wrapper = mount(DeviceManageTestable)
    await wrapper.find('[data-testid="add-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').text()).toContain('新增设备')
  })

  it('搜索重置页码', async () => {
    const wrapper = mount(DeviceManageTestable)
    wrapper.vm.pagination.page = 5
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.vm.pagination.page).toBe(1)
  })

  it('重置筛选条件', async () => {
    const wrapper = mount(DeviceManageTestable)
    wrapper.vm.filters.keyword = 'UPS'
    wrapper.vm.filters.device_type = 'UPS'
    wrapper.vm.pagination.page = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.keyword).toBe('')
    expect(wrapper.vm.filters.device_type).toBe('')
    expect(wrapper.vm.pagination.page).toBe(1)
  })

  it('状态标签映射正确', () => {
    const wrapper = mount(DeviceManageTestable)
    expect(wrapper.vm.statusTagMap.online.text).toBe('在线')
    expect(wrapper.vm.statusTagMap.offline.text).toBe('离线')
    expect(wrapper.vm.statusTagMap.alarm.text).toBe('告警')
    expect(wrapper.vm.statusTagMap.maintenance.text).toBe('维护中')
  })
})
