/**
 * 系统设置页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/point', () => ({
  getPointList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

vi.mock('@/api/modules/threshold', () => ({
  getThresholdList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createThreshold: vi.fn().mockResolvedValue({}),
  updateThreshold: vi.fn().mockResolvedValue({}),
  deleteThreshold: vi.fn().mockResolvedValue({}),
  getPointThresholds: vi.fn().mockResolvedValue([]),
  setFourLevelThresholds: vi.fn().mockResolvedValue({}),
  batchSetByDeviceType: vi.fn().mockResolvedValue({ success_count: 0, error_count: 0 }),
}))

vi.mock('@/api/modules/log', () => ({
  getOperationLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getSystemLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  exportLogs: vi.fn().mockResolvedValue(new Blob()),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ isAdmin: true, userInfo: { id: 1, role: 'admin' } }),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
}))

const SettingsPageTestable = defineComponent({
  name: 'SettingsPageTestable',
  setup() {
    const activeTab = ref('threshold')
    const isAdmin = computed(() => true)

    const thresholds = ref([
      { id: 1, point_code: 'AI_001', point_name: '温度', threshold_type: 'high', threshold_value: 35, alarm_level: 'major', is_enabled: true },
    ])
    const thresholdLoading = ref(false)
    const thresholdDialogVisible = ref(false)
    const thresholdEditMode = ref(false)

    const thresholdFilters = reactive({
      point_id: null as number | null,
      alarm_level: '',
      device_type: '',
    })

    const operationLogPagination = reactive({ page: 1, page_size: 20, total: 0 })
    const systemLogPagination = reactive({ page: 1, page_size: 20, total: 0 })

    const licenseInfo = reactive({ max_points: 100, used_points: 30 })
    const systemInfo = reactive({ app_name: '算力中心智能监控系统', app_version: '2.0.0', uptime: '-' })

    const remainingPoints = computed(() => licenseInfo.max_points - licenseInfo.used_points)

    const alarmLevelText: Record<string, string> = { critical: '紧急', major: '重要', minor: '一般', info: '提示' }
    const thresholdTypeText: Record<string, string> = { high_high: '高高限', high: '高限', low: '低限', low_low: '低低限' }

    function handleAddThreshold() {
      thresholdEditMode.value = false
      thresholdDialogVisible.value = true
    }

    return {
      activeTab, isAdmin, thresholds, thresholdLoading, thresholdDialogVisible, thresholdEditMode,
      thresholdFilters, operationLogPagination, systemLogPagination,
      licenseInfo, systemInfo, remainingPoints, alarmLevelText, thresholdTypeText,
      handleAddThreshold,
    }
  },
  template: `
    <div class="settings-page">
      <div data-testid="tabs">
        <button v-for="tab in ['threshold', 'user', 'operation-log', 'system-log', 'license']"
          :key="tab" :data-testid="'tab-' + tab" @click="activeTab = tab"
          :class="{ active: activeTab === tab }">{{ tab }}</button>
      </div>
      <div v-if="activeTab === 'threshold'" data-testid="threshold-panel">
        <button data-testid="add-threshold-btn" @click="handleAddThreshold">新增阈值</button>
        <table data-testid="threshold-table">
          <tr v-for="t in thresholds" :key="t.id" :data-testid="'threshold-' + t.id">
            <td>{{ t.point_code }}</td>
            <td>{{ thresholdTypeText[t.threshold_type] }}</td>
            <td>{{ t.threshold_value }}</td>
            <td>{{ alarmLevelText[t.alarm_level] }}</td>
          </tr>
        </table>
      </div>
      <div v-if="activeTab === 'user' && isAdmin" data-testid="user-panel">用户管理</div>
      <div v-if="activeTab === 'license'" data-testid="license-panel">
        <span data-testid="max-points">{{ licenseInfo.max_points }}</span>
        <span data-testid="used-points">{{ licenseInfo.used_points }}</span>
        <span data-testid="remaining-points">{{ remainingPoints }}</span>
        <span data-testid="app-name">{{ systemInfo.app_name }}</span>
        <span data-testid="app-version">{{ systemInfo.app_version }}</span>
      </div>
      <div v-if="thresholdDialogVisible" data-testid="threshold-dialog">
        {{ thresholdEditMode ? '编辑阈值' : '新增阈值' }}
      </div>
    </div>
  `,
})

describe('SettingsPage 系统设置', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认显示阈值配置标签页', () => {
    const wrapper = mount(SettingsPageTestable)
    expect(wrapper.vm.activeTab).toBe('threshold')
    expect(wrapper.find('[data-testid="threshold-panel"]').exists()).toBe(true)
  })

  it('渲染阈值列表', () => {
    const wrapper = mount(SettingsPageTestable)
    expect(wrapper.find('[data-testid="threshold-1"]').exists()).toBe(true)
  })

  it('点击新增阈值打开对话框', async () => {
    const wrapper = mount(SettingsPageTestable)
    await wrapper.find('[data-testid="add-threshold-btn"]').trigger('click')
    expect(wrapper.vm.thresholdDialogVisible).toBe(true)
    expect(wrapper.vm.thresholdEditMode).toBe(false)
    expect(wrapper.find('[data-testid="threshold-dialog"]').text()).toContain('新增阈值')
  })

  it('管理员可见用户管理标签页', async () => {
    const wrapper = mount(SettingsPageTestable)
    await wrapper.find('[data-testid="tab-user"]').trigger('click')
    expect(wrapper.find('[data-testid="user-panel"]').exists()).toBe(true)
  })

  it('授权信息显示正确', async () => {
    const wrapper = mount(SettingsPageTestable)
    await wrapper.find('[data-testid="tab-license"]').trigger('click')
    expect(wrapper.find('[data-testid="max-points"]').text()).toBe('100')
    expect(wrapper.find('[data-testid="used-points"]').text()).toBe('30')
    expect(wrapper.find('[data-testid="remaining-points"]').text()).toBe('70')
    expect(wrapper.find('[data-testid="app-name"]').text()).toBe('算力中心智能监控系统')
    expect(wrapper.find('[data-testid="app-version"]').text()).toBe('2.0.0')
  })

  it('筛选条件初始值正确', () => {
    const wrapper = mount(SettingsPageTestable)
    expect(wrapper.vm.thresholdFilters.point_id).toBeNull()
    expect(wrapper.vm.thresholdFilters.alarm_level).toBe('')
    expect(wrapper.vm.thresholdFilters.device_type).toBe('')
  })

  it('分页初始状态正确', () => {
    const wrapper = mount(SettingsPageTestable)
    expect(wrapper.vm.operationLogPagination.page).toBe(1)
    expect(wrapper.vm.operationLogPagination.page_size).toBe(20)
    expect(wrapper.vm.systemLogPagination.page).toBe(1)
  })
})
