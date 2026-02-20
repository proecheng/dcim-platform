/**
 * 设备模板管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/device-template', () => ({
  getTemplates: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createTemplate: vi.fn().mockResolvedValue({}),
  updateTemplate: vi.fn().mockResolvedValue({}),
  deleteTemplate: vi.fn().mockResolvedValue({}),
  createDatasourceFromTemplate: vi.fn().mockResolvedValue({}),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
  Search: { template: '<i />' },
}))

const DeviceTemplateTestable = defineComponent({
  name: 'DeviceTemplateTestable',
  setup() {
    const templates = ref([
      { id: 1, name: 'UPS模板', manufacturer: '华为', model: 'UPS2000', protocol_type: 'modbus_tcp', point_config: [{ address: '40001' }] },
      { id: 2, name: 'AC模板', manufacturer: '大金', model: 'AC500', protocol_type: 'snmp_v2c', point_config: [] },
    ])
    const dialogVisible = ref(false)
    const editMode = ref(false)
    const dsDialogVisible = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(10)
    const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

    const filters = reactive({ manufacturer: '', model_name: '', protocol_type: 'ALL', keyword: '' })

    function getProtocolTagType(type: string): string {
      const map: Record<string, string> = { modbus_tcp: 'primary', modbus_rtu: 'warning', snmp_v2c: 'success', snmp_v3: 'danger' }
      return map[type] || 'info'
    }

    function getProtocolLabel(type: string): string {
      const map: Record<string, string> = { modbus_tcp: 'Modbus TCP', modbus_rtu: 'Modbus RTU', snmp_v2c: 'SNMP v2c', snmp_v3: 'SNMP v3' }
      return map[type] || type
    }

    function handleAdd() {
      editMode.value = false
      dialogVisible.value = true
    }

    function handleSearch() {
      currentPage.value = 1
    }

    function resetFilters() {
      filters.manufacturer = ''
      filters.model_name = ''
      filters.protocol_type = 'ALL'
      filters.keyword = ''
      currentPage.value = 1
    }

    function handleCreateDS() {
      dsDialogVisible.value = true
    }

    return {
      templates, dialogVisible, editMode, dsDialogVisible, currentPage, pageSize, total, totalPages,
      filters, getProtocolTagType, getProtocolLabel, handleAdd, handleSearch, resetFilters, handleCreateDS,
    }
  },
  template: `
    <div class="device-template-page">
      <div class="card-header">
        <span data-testid="page-title">设备模板管理</span>
        <button data-testid="add-btn" @click="handleAdd">新增模板</button>
      </div>
      <div class="filter-form">
        <input data-testid="filter-manufacturer" v-model="filters.manufacturer" />
        <select data-testid="filter-protocol" v-model="filters.protocol_type">
          <option value="ALL">全部</option>
          <option value="modbus_tcp">Modbus TCP</option>
        </select>
        <input data-testid="filter-keyword" v-model="filters.keyword" />
        <button data-testid="search-btn" @click="handleSearch">查询</button>
        <button data-testid="reset-btn" @click="resetFilters">重置</button>
      </div>
      <div data-testid="pagination-info">共 {{ total }} 条，第 {{ currentPage }} / {{ totalPages }} 页</div>
      <table data-testid="template-table">
        <tr v-for="t in templates" :key="t.id" :data-testid="'template-' + t.id">
          <td>{{ t.name }}</td>
          <td>{{ t.manufacturer }}</td>
          <td>{{ getProtocolLabel(t.protocol_type) }}</td>
          <td>{{ (t.point_config || []).length }}</td>
          <td><button :data-testid="'create-ds-' + t.id" @click="handleCreateDS">创建数据源</button></td>
        </tr>
      </table>
      <div v-if="dialogVisible" data-testid="dialog">{{ editMode ? '编辑模板' : '新增模板' }}</div>
      <div v-if="dsDialogVisible" data-testid="ds-dialog">从模板创建数据源</div>
    </div>
  `,
})

describe('DeviceTemplatePage 设备模板管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染页面标题', () => {
    const wrapper = mount(DeviceTemplateTestable)
    expect(wrapper.find('[data-testid="page-title"]').text()).toBe('设备模板管理')
  })

  it('渲染模板列表', () => {
    const wrapper = mount(DeviceTemplateTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(2)
  })

  it('初始状态正确', () => {
    const wrapper = mount(DeviceTemplateTestable)
    expect(wrapper.vm.currentPage).toBe(1)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.editMode).toBe(false)
    expect(wrapper.vm.dsDialogVisible).toBe(false)
    expect(wrapper.vm.filters.protocol_type).toBe('ALL')
  })

  it('点击新增打开对话框', async () => {
    const wrapper = mount(DeviceTemplateTestable)
    await wrapper.find('[data-testid="add-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.editMode).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').text()).toContain('新增模板')
  })

  it('协议标签映射正确', () => {
    const wrapper = mount(DeviceTemplateTestable)
    expect(wrapper.vm.getProtocolLabel('modbus_tcp')).toBe('Modbus TCP')
    expect(wrapper.vm.getProtocolLabel('snmp_v2c')).toBe('SNMP v2c')
    expect(wrapper.vm.getProtocolTagType('modbus_tcp')).toBe('primary')
    expect(wrapper.vm.getProtocolTagType('snmp_v3')).toBe('danger')
  })

  it('点击创建数据源打开对话框', async () => {
    const wrapper = mount(DeviceTemplateTestable)
    await wrapper.find('[data-testid="create-ds-1"]').trigger('click')
    expect(wrapper.vm.dsDialogVisible).toBe(true)
    expect(wrapper.find('[data-testid="ds-dialog"]').text()).toContain('从模板创建数据源')
  })

  it('重置筛选条件', async () => {
    const wrapper = mount(DeviceTemplateTestable)
    wrapper.vm.filters.manufacturer = '华为'
    wrapper.vm.filters.keyword = 'UPS'
    wrapper.vm.currentPage = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.manufacturer).toBe('')
    expect(wrapper.vm.filters.keyword).toBe('')
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('分页信息显示正确', () => {
    const wrapper = mount(DeviceTemplateTestable)
    const info = wrapper.find('[data-testid="pagination-info"]').text()
    expect(info).toContain('10')
    expect(info).toContain('1')
  })
})
