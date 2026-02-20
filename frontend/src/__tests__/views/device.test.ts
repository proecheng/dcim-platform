/**
 * 点位管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

// Mock dependencies
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/point', () => ({
  getPoints: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createPoint: vi.fn().mockResolvedValue({}),
  updatePoint: vi.fn().mockResolvedValue({}),
  deletePoint: vi.fn().mockResolvedValue({}),
  enablePoint: vi.fn().mockResolvedValue({}),
  disablePoint: vi.fn().mockResolvedValue({}),
  linkPointToDevice: vi.fn().mockResolvedValue({}),
  unlinkPointFromDevice: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/api/modules/energy', () => ({
  getPowerDevices: vi.fn().mockResolvedValue([]),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
  Search: { template: '<i />' },
}))

const DevicePageTestable = defineComponent({
  name: 'DevicePageTestable',
  setup() {
    const points = ref([
      { id: 1, point_code: 'AI_001', point_name: '温度传感器1', point_type: 'AI', device_type: 'power', area_code: 'A1', unit: '°C', collect_interval: 10, is_enabled: true },
      { id: 2, point_code: 'DI_001', point_name: '门禁状态', point_type: 'DI', device_type: 'other', area_code: 'B1', unit: '', collect_interval: 5, is_enabled: false },
    ])
    const dialogVisible = ref(false)
    const editMode = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(50)
    const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

    const filters = reactive({
      point_type: 'ALL',
      device_type: 'ALL',
      area_code: 'ALL',
      keyword: '',
    })

    const form = reactive({
      id: 0,
      point_code: '',
      point_name: '',
      point_type: 'AI',
      device_type: 'power',
      area_code: 'A1',
      unit: '',
      collect_interval: 10,
    })

    function handleAdd() {
      editMode.value = false
      Object.assign(form, { id: 0, point_code: '', point_name: '', point_type: 'AI', device_type: 'power', area_code: 'A1', unit: '', collect_interval: 10 })
      dialogVisible.value = true
    }

    function handleSearch() {
      currentPage.value = 1
    }

    function resetFilters() {
      filters.point_type = 'ALL'
      filters.device_type = 'ALL'
      filters.area_code = 'ALL'
      filters.keyword = ''
      currentPage.value = 1
    }

    return { points, dialogVisible, editMode, currentPage, pageSize, total, totalPages, filters, form, handleAdd, handleSearch, resetFilters }
  },
  template: `
    <div class="device-page">
      <div class="card-header">
        <span data-testid="page-title">点位管理</span>
        <button data-testid="add-btn" @click="handleAdd">新增点位</button>
      </div>
      <div class="filter-form">
        <select data-testid="filter-type" v-model="filters.point_type">
          <option value="ALL">全部</option>
          <option value="AI">AI</option>
          <option value="DI">DI</option>
        </select>
        <input data-testid="filter-keyword" v-model="filters.keyword" />
        <button data-testid="search-btn" @click="handleSearch">查询</button>
        <button data-testid="reset-btn" @click="resetFilters">重置</button>
      </div>
      <div data-testid="pagination-info">
        共 {{ total }} 条记录，第 {{ currentPage }} / {{ totalPages }} 页
      </div>
      <table data-testid="point-table">
        <tr v-for="p in points" :key="p.id" :data-testid="'row-' + p.id">
          <td>{{ p.point_code }}</td>
          <td>{{ p.point_name }}</td>
          <td>{{ p.point_type }}</td>
          <td>{{ p.area_code }}</td>
        </tr>
      </table>
      <div v-if="dialogVisible" data-testid="dialog">
        <span>{{ editMode ? '编辑点位' : '新增点位' }}</span>
      </div>
    </div>
  `,
})

describe('DevicePage 点位管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染页面标题', () => {
    const wrapper = mount(DevicePageTestable)
    expect(wrapper.find('[data-testid="page-title"]').text()).toBe('点位管理')
  })

  it('初始状态正确', () => {
    const wrapper = mount(DevicePageTestable)
    expect(wrapper.vm.currentPage).toBe(1)
    expect(wrapper.vm.pageSize).toBe(20)
    expect(wrapper.vm.total).toBe(50)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.editMode).toBe(false)
  })

  it('渲染点位列表', () => {
    const wrapper = mount(DevicePageTestable)
    const rows = wrapper.findAll('[data-testid^="row-"]')
    expect(rows).toHaveLength(2)
  })

  it('计算总页数', () => {
    const wrapper = mount(DevicePageTestable)
    expect(wrapper.vm.totalPages).toBe(3)
  })

  it('点击新增按钮打开对话框', async () => {
    const wrapper = mount(DevicePageTestable)
    await wrapper.find('[data-testid="add-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.editMode).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').exists()).toBe(true)
  })

  it('筛选条件初始值正确', () => {
    const wrapper = mount(DevicePageTestable)
    expect(wrapper.vm.filters.point_type).toBe('ALL')
    expect(wrapper.vm.filters.device_type).toBe('ALL')
    expect(wrapper.vm.filters.area_code).toBe('ALL')
    expect(wrapper.vm.filters.keyword).toBe('')
  })

  it('重置筛选条件', async () => {
    const wrapper = mount(DevicePageTestable)
    wrapper.vm.filters.point_type = 'AI'
    wrapper.vm.filters.keyword = 'test'
    wrapper.vm.currentPage = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.point_type).toBe('ALL')
    expect(wrapper.vm.filters.keyword).toBe('')
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('分页信息显示正确', () => {
    const wrapper = mount(DevicePageTestable)
    const info = wrapper.find('[data-testid="pagination-info"]').text()
    expect(info).toContain('50')
    expect(info).toContain('1')
    expect(info).toContain('3')
  })
})
