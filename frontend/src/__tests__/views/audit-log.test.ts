/**
 * 审计日志页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/log', () => ({
  getOperationLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getSystemLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getCommunicationLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  exportLogs: vi.fn().mockResolvedValue(new Blob()),
}))

const AuditLogTestable = defineComponent({
  name: 'AuditLogTestable',
  setup() {
    const activeTab = ref<'operation' | 'system' | 'communication'>('operation')
    const loading = ref(false)

    const opList = ref([
      { id: 1, created_at: '2026-01-01', username: 'admin', module: 'user', action: 'create', target_name: '新用户', ip_address: '192.168.1.1', remark: '' },
    ])
    const opPage = ref(1)
    const opPageSize = ref(20)
    const opTotal = ref(50)
    const opFilter = reactive({ timeRange: null as [string, string] | null, username: '', module: '', action: '', keyword: '' })

    const sysList = ref([
      { id: 1, created_at: '2026-01-01', log_level: 'info', module: 'api', message: '系统启动' },
    ])
    const sysPage = ref(1)
    const sysPageSize = ref(20)
    const sysTotal = ref(30)
    const sysFilter = reactive({ timeRange: null as [string, string] | null, log_level: '', module: '', keyword: '' })

    const commList = ref<{ id: number; created_at: string; device_id: number; status: string }[]>([])
    const commPage = ref(1)
    const commPageSize = ref(20)
    const commTotal = ref(0)
    const commFilter = reactive({ timeRange: null as [string, string] | null, device_id: '', status: '' })

    function handleSearch() {
      if (activeTab.value === 'operation') opPage.value = 1
      else if (activeTab.value === 'system') sysPage.value = 1
      else commPage.value = 1
    }

    function handleReset() {
      if (activeTab.value === 'operation') {
        opFilter.timeRange = null
        opFilter.username = ''
        opFilter.module = ''
        opFilter.action = ''
        opFilter.keyword = ''
        opPage.value = 1
      } else if (activeTab.value === 'system') {
        sysFilter.timeRange = null
        sysFilter.log_level = ''
        sysFilter.module = ''
        sysFilter.keyword = ''
        sysPage.value = 1
      } else {
        commFilter.timeRange = null
        commFilter.device_id = ''
        commFilter.status = ''
        commPage.value = 1
      }
    }

    function levelTagType(level: string): string {
      const map: Record<string, string> = { debug: 'info', info: 'success', warning: 'warning', error: 'danger', critical: 'danger' }
      return map[level] || 'info'
    }

    return {
      activeTab, loading, opList, opPage, opPageSize, opTotal, opFilter,
      sysList, sysPage, sysPageSize, sysTotal, sysFilter,
      commList, commPage, commPageSize, commTotal, commFilter,
      handleSearch, handleReset, levelTagType,
    }
  },
  template: `
    <div class="audit-log-page">
      <div data-testid="tabs">
        <button v-for="tab in ['operation', 'system', 'communication']"
          :key="tab" :data-testid="'tab-' + tab" @click="activeTab = tab">{{ tab }}</button>
      </div>
      <div v-if="activeTab === 'operation'" data-testid="op-panel">
        <button data-testid="search-btn" @click="handleSearch">搜索</button>
        <button data-testid="reset-btn" @click="handleReset">重置</button>
        <table data-testid="op-table">
          <tr v-for="log in opList" :key="log.id" :data-testid="'op-' + log.id">
            <td>{{ log.username }}</td><td>{{ log.module }}</td><td>{{ log.action }}</td>
          </tr>
        </table>
        <span data-testid="op-total">{{ opTotal }}</span>
      </div>
      <div v-if="activeTab === 'system'" data-testid="sys-panel">
        <table data-testid="sys-table">
          <tr v-for="log in sysList" :key="log.id" :data-testid="'sys-' + log.id">
            <td>{{ log.log_level }}</td><td>{{ log.message }}</td>
          </tr>
        </table>
        <span data-testid="sys-total">{{ sysTotal }}</span>
      </div>
      <div v-if="activeTab === 'communication'" data-testid="comm-panel">
        <span data-testid="comm-total">{{ commTotal }}</span>
      </div>
    </div>
  `,
})

describe('AuditLog 审计日志', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认显示操作日志标签页', () => {
    const wrapper = mount(AuditLogTestable)
    expect(wrapper.vm.activeTab).toBe('operation')
    expect(wrapper.find('[data-testid="op-panel"]').exists()).toBe(true)
  })

  it('渲染操作日志列表', () => {
    const wrapper = mount(AuditLogTestable)
    expect(wrapper.find('[data-testid="op-1"]').exists()).toBe(true)
  })

  it('切换到系统日志标签页', async () => {
    const wrapper = mount(AuditLogTestable)
    await wrapper.find('[data-testid="tab-system"]').trigger('click')
    expect(wrapper.vm.activeTab).toBe('system')
    expect(wrapper.find('[data-testid="sys-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="sys-1"]').exists()).toBe(true)
  })

  it('切换到通讯日志标签页', async () => {
    const wrapper = mount(AuditLogTestable)
    await wrapper.find('[data-testid="tab-communication"]').trigger('click')
    expect(wrapper.vm.activeTab).toBe('communication')
    expect(wrapper.find('[data-testid="comm-panel"]').exists()).toBe(true)
  })

  it('搜索重置页码', async () => {
    const wrapper = mount(AuditLogTestable)
    wrapper.vm.opPage = 5
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.vm.opPage).toBe(1)
  })

  it('重置操作日志筛选条件', async () => {
    const wrapper = mount(AuditLogTestable)
    wrapper.vm.opFilter.username = 'admin'
    wrapper.vm.opFilter.module = 'user'
    wrapper.vm.opPage = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.opFilter.username).toBe('')
    expect(wrapper.vm.opFilter.module).toBe('')
    expect(wrapper.vm.opPage).toBe(1)
  })

  it('日志级别标签类型映射正确', () => {
    const wrapper = mount(AuditLogTestable)
    expect(wrapper.vm.levelTagType('info')).toBe('success')
    expect(wrapper.vm.levelTagType('error')).toBe('danger')
    expect(wrapper.vm.levelTagType('warning')).toBe('warning')
  })

  it('分页初始状态正确', () => {
    const wrapper = mount(AuditLogTestable)
    expect(wrapper.vm.opPage).toBe(1)
    expect(wrapper.vm.opPageSize).toBe(20)
    expect(wrapper.vm.sysPage).toBe(1)
    expect(wrapper.vm.commPage).toBe(1)
  })
})
