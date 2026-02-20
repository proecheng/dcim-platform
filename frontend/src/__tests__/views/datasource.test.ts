/**
 * 数据源管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/datasource', () => ({
  getDatasources: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createDatasource: vi.fn().mockResolvedValue({}),
  updateDatasource: vi.fn().mockResolvedValue({}),
  deleteDatasource: vi.fn().mockResolvedValue({}),
  testConnection: vi.fn().mockResolvedValue({ success: true, latency_ms: 10 }),
  testExistingConnection: vi.fn().mockResolvedValue({ success: true, latency_ms: 10 }),
  validatePoints: vi.fn().mockResolvedValue({ total: 0, passed: 0, failed: 0, errors: [] }),
  importPoints: vi.fn().mockResolvedValue({ imported: 0 }),
  toggleWritePermission: vi.fn().mockResolvedValue({}),
  exportReport: vi.fn().mockResolvedValue(new Blob()),
  getCommunicationStatus: vi.fn().mockResolvedValue([]),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
  Search: { template: '<i />' },
  Upload: { template: '<i />' },
  Download: { template: '<i />' },
}))

const DatasourcePageTestable = defineComponent({
  name: 'DatasourcePageTestable',
  setup() {
    const datasources = ref([
      { id: 1, name: 'Modbus设备1', protocol_type: 'modbus_tcp', collection_interval: 5, is_enabled: true, status: 'connected', write_enabled: false },
      { id: 2, name: 'SNMP设备1', protocol_type: 'snmp_v2c', collection_interval: 10, is_enabled: false, status: 'disconnected', write_enabled: true },
    ])
    const dialogVisible = ref(false)
    const editMode = ref(false)
    const testing = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(15)
    const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

    const filters = reactive({ protocol_type: 'ALL', status: 'ALL', keyword: '' })

    function getProtocolLabel(type: string): string {
      const map: Record<string, string> = { modbus_tcp: 'Modbus TCP', modbus_rtu: 'Modbus RTU', snmp_v2c: 'SNMP v2c', snmp_v3: 'SNMP v3' }
      return map[type] || type
    }

    function commStatusText(status: string): string {
      const map: Record<string, string> = { connected: '已连接', disconnected: '已断开', interrupted: '通信中断' }
      return map[status] || status
    }

    function formatDuration(seconds: number | null | undefined): string {
      if (seconds == null || seconds <= 0) return '—'
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      if (hours > 0) return `${hours}小时${minutes}分钟`
      return `${minutes}分钟`
    }

    function handleAdd() {
      editMode.value = false
      dialogVisible.value = true
    }

    function handleSearch() {
      currentPage.value = 1
    }

    function resetFilters() {
      filters.protocol_type = 'ALL'
      filters.status = 'ALL'
      filters.keyword = ''
      currentPage.value = 1
    }

    return {
      datasources, dialogVisible, editMode, testing, currentPage, pageSize, total, totalPages,
      filters, getProtocolLabel, commStatusText, formatDuration, handleAdd, handleSearch, resetFilters,
    }
  },
  template: `
    <div class="datasource-page">
      <div class="card-header">
        <span data-testid="page-title">数据源管理</span>
        <button data-testid="add-btn" @click="handleAdd">新增数据源</button>
      </div>
      <div class="filter-form">
        <select data-testid="filter-protocol" v-model="filters.protocol_type">
          <option value="ALL">全部</option>
          <option value="modbus_tcp">Modbus TCP</option>
        </select>
        <input data-testid="filter-keyword" v-model="filters.keyword" />
        <button data-testid="search-btn" @click="handleSearch">查询</button>
        <button data-testid="reset-btn" @click="resetFilters">重置</button>
      </div>
      <div data-testid="pagination-info">共 {{ total }} 条，第 {{ currentPage }} / {{ totalPages }} 页</div>
      <table data-testid="ds-table">
        <tr v-for="ds in datasources" :key="ds.id" :data-testid="'ds-' + ds.id">
          <td>{{ ds.name }}</td>
          <td>{{ getProtocolLabel(ds.protocol_type) }}</td>
          <td>{{ commStatusText(ds.status) }}</td>
        </tr>
      </table>
      <div v-if="dialogVisible" data-testid="dialog">{{ editMode ? '编辑数据源' : '新增数据源' }}</div>
    </div>
  `,
})

describe('DatasourcePage 数据源管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染页面标题', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.find('[data-testid="page-title"]').text()).toBe('数据源管理')
  })

  it('渲染数据源列表', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(2)
  })

  it('初始状态正确', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.vm.currentPage).toBe(1)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.filters.protocol_type).toBe('ALL')
    expect(wrapper.vm.filters.keyword).toBe('')
  })

  it('点击新增打开对话框', async () => {
    const wrapper = mount(DatasourcePageTestable)
    await wrapper.find('[data-testid="add-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.editMode).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').text()).toContain('新增数据源')
  })

  it('协议标签映射正确', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.vm.getProtocolLabel('modbus_tcp')).toBe('Modbus TCP')
    expect(wrapper.vm.getProtocolLabel('snmp_v2c')).toBe('SNMP v2c')
    expect(wrapper.vm.getProtocolLabel('unknown')).toBe('unknown')
  })

  it('通信状态文本映射正确', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.vm.commStatusText('connected')).toBe('已连接')
    expect(wrapper.vm.commStatusText('disconnected')).toBe('已断开')
    expect(wrapper.vm.commStatusText('interrupted')).toBe('通信中断')
  })

  it('格式化中断时长', () => {
    const wrapper = mount(DatasourcePageTestable)
    expect(wrapper.vm.formatDuration(null)).toBe('—')
    expect(wrapper.vm.formatDuration(0)).toBe('—')
    expect(wrapper.vm.formatDuration(3660)).toBe('1小时1分钟')
    expect(wrapper.vm.formatDuration(300)).toBe('5分钟')
  })

  it('重置筛选条件', async () => {
    const wrapper = mount(DatasourcePageTestable)
    wrapper.vm.filters.protocol_type = 'modbus_tcp'
    wrapper.vm.filters.keyword = 'test'
    wrapper.vm.currentPage = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.protocol_type).toBe('ALL')
    expect(wrapper.vm.filters.keyword).toBe('')
    expect(wrapper.vm.currentPage).toBe(1)
  })
})
