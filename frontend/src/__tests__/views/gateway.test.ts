/**
 * 网关监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/gateway', () => ({
  getGatewayList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  getGatewaySummary: vi.fn().mockResolvedValue({ total: 0, online: 0, offline: 0 }),
  getGatewayDetail: vi.fn().mockResolvedValue({}),
  getGatewayEvents: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  pushGatewayConfig: vi.fn().mockResolvedValue({ id: 1, status: 'delivered' }),
}))

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: computed(() => false),
    on: vi.fn(),
    off: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Search: { template: '<i />' },
  Monitor: { template: '<i />' },
  Refresh: { template: '<i />' },
  WarningFilled: { template: '<i />' },
  CircleCheck: { template: '<i />' },
  CircleClose: { template: '<i />' },
  DataLine: { template: '<i />' },
  Setting: { template: '<i />' },
}))

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), dispose: vi.fn() })),
}))

// ── 从 gateway/index.vue 提取的辅助函数 ──

type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { online: 'success', offline: 'danger' }
  return map[status] || 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = { online: '在线', offline: '离线' }
  return map[status] || status
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function isOfflineAlert(row: { status: string; is_enabled: boolean; last_heartbeat: string | null }): boolean {
  if (row.status !== 'offline' || !row.is_enabled) return false
  if (!row.last_heartbeat) return true
  const diff = Date.now() - new Date(row.last_heartbeat).getTime()
  return diff > 5 * 60 * 1000
}

function progressColor(value: number | null): string {
  if (value == null) return '#909399'
  if (value >= 90) return '#f5222d'
  if (value >= 70) return '#faad14'
  return '#52c41a'
}

function getCapabilityTags(capabilities: Record<string, unknown> | unknown[] | null): string[] {
  if (!capabilities) return []
  if (Array.isArray(capabilities)) return capabilities.map(String).slice(0, 3)
  return Object.keys(capabilities).slice(0, 3)
}

// ── 可测试的网关监控组件 ──
const GatewayMonitorTestable = defineComponent({
  name: 'GatewayMonitorTestable',
  setup() {
    const summary = ref({ total: 8, online: 5, offline: 3 })
    const loading = ref(false)
    const tableData = ref([
      {
        id: 1, gateway_id: 'GW-001', name: '网关A', ip_address: '192.168.1.10',
        version: 'v2.1.0', status: 'online' as const, capabilities: { modbus_tcp: true, snmp: true },
        cpu_usage: 45.2, memory_usage: 62.8, disk_usage: 30.0,
        last_heartbeat: new Date().toISOString(), site_id: 1, is_enabled: true,
        created_at: '2026-01-01T00:00:00', updated_at: null,
      },
      {
        id: 2, gateway_id: 'GW-002', name: '网关B', ip_address: '192.168.1.11',
        version: 'v2.0.5', status: 'offline' as const, capabilities: { mqtt: true },
        cpu_usage: null, memory_usage: null, disk_usage: null,
        last_heartbeat: '2026-01-01T00:00:00', site_id: 1, is_enabled: true,
        created_at: '2026-01-01T00:00:00', updated_at: null,
      },
      {
        id: 3, gateway_id: 'GW-003', name: '网关C', ip_address: null,
        version: null, status: 'offline' as const, capabilities: null,
        cpu_usage: 92.5, memory_usage: 88.0, disk_usage: 75.0,
        last_heartbeat: null, site_id: null, is_enabled: false,
        created_at: null, updated_at: null,
      },
    ])
    const pagination = reactive({ page: 1, pageSize: 20, total: 3 })
    const filterStatus = ref('')
    const searchKeyword = ref('')
    const selectedGateways = ref<typeof tableData.value>([])
    const batchPushing = ref(false)
    const configDialogVisible = ref(false)
    const configGatewayId = ref<number | null>(null)
    const configGatewayName = ref('')

    // 告警数: 离线且启用的网关
    const alertCount = computed(() => {
      return tableData.value.filter(g => g.status === 'offline' && g.is_enabled).length
    })

    // 平均负载: 在线网关的平均 CPU 使用率
    const avgThroughput = computed(() => {
      const onlineGateways = tableData.value.filter(g => g.status === 'online' && g.cpu_usage != null)
      if (onlineGateways.length === 0) return '--'
      const avg = onlineGateways.reduce((sum, g) => sum + (g.cpu_usage ?? 0), 0) / onlineGateways.length
      return avg.toFixed(1) + '%'
    })

    const statCards = computed(() => [
      { label: '网关总数', value: summary.value.total, valueClass: 'primary' },
      { label: '在线数', value: summary.value.online, valueClass: 'success' },
      { label: '离线数', value: summary.value.offline, valueClass: 'danger' },
      { label: '告警网关', value: alertCount.value, valueClass: 'warning' },
      { label: '平均负载', value: avgThroughput.value, valueClass: 'primary' },
    ])

    function handleSearch() {
      pagination.page = 1
    }

    function handleRefresh() {
      // 刷新数据
    }

    function openConfigDialog(row: typeof tableData.value[0]) {
      configGatewayId.value = row.id
      configGatewayName.value = row.name
      configDialogVisible.value = true
    }

    function handleSelectionChange(rows: typeof tableData.value) {
      selectedGateways.value = rows
    }

    return {
      summary, loading, tableData, pagination, filterStatus, searchKeyword,
      selectedGateways, batchPushing, configDialogVisible, configGatewayId, configGatewayName,
      alertCount, avgThroughput, statCards,
      handleSearch, handleRefresh, openConfigDialog, handleSelectionChange,
      statusTagType, statusText, formatTime, isOfflineAlert, progressColor, getCapabilityTags,
    }
  },
  template: `
    <div class="gateway-monitor">
      <div class="stat-row">
        <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.valueClass">
          <div class="stat-value" :class="card.valueClass">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </div>
      <div class="toolbar">
        <select data-testid="filter-status" v-model="filterStatus">
          <option value="">全部状态</option>
          <option value="online">在线</option>
          <option value="offline">离线</option>
        </select>
        <input data-testid="filter-keyword" v-model="searchKeyword" placeholder="搜索网关名称/IP" />
        <button data-testid="search-btn" @click="handleSearch">搜索</button>
        <button data-testid="refresh-btn" @click="handleRefresh">刷新</button>
        <button v-if="selectedGateways.length > 0" data-testid="batch-push-btn" :disabled="batchPushing">
          批量配置下发 ({{ selectedGateways.length }})
        </button>
      </div>
      <table data-testid="gateway-table">
        <tr v-for="gw in tableData" :key="gw.id" :data-testid="'gw-' + gw.id">
          <td class="name">{{ gw.name }}</td>
          <td class="ip">{{ gw.ip_address || '--' }}</td>
          <td class="caps">
            <span v-for="cap in getCapabilityTags(gw.capabilities)" :key="cap" class="cap-tag">{{ cap }}</span>
            <span v-if="!gw.capabilities || Object.keys(gw.capabilities).length === 0" class="text-muted">--</span>
          </td>
          <td class="status">
            <span :class="'tag-' + statusTagType(gw.status)">{{ statusText(gw.status) }}</span>
          </td>
          <td class="resource">
            <span v-if="gw.cpu_usage != null || gw.memory_usage != null">
              {{ gw.cpu_usage != null ? gw.cpu_usage.toFixed(1) + '%' : '--' }}
              /
              {{ gw.memory_usage != null ? gw.memory_usage.toFixed(1) + '%' : '--' }}
            </span>
            <span v-else class="text-muted">--</span>
          </td>
          <td class="heartbeat">{{ formatTime(gw.last_heartbeat) }}</td>
          <td class="enabled">{{ gw.is_enabled ? '是' : '否' }}</td>
          <td class="actions">
            <button
              class="config-push-btn"
              :disabled="gw.status !== 'online' || !gw.is_enabled"
              @click="openConfigDialog(gw)"
            >配置下发</button>
          </td>
        </tr>
      </table>
      <div v-if="configDialogVisible" data-testid="config-dialog">
        配置下发: {{ configGatewayName }}
      </div>
    </div>
  `,
})

describe('GatewayMonitor 网关监控', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  // ── 统计卡片 ──
  it('渲染 5 张统计卡片', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const cards = wrapper.findAll('.stat-card')
    expect(cards).toHaveLength(5)
  })

  it('显示网关总数', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const card = wrapper.find('[data-testid="stat-primary"]')
    expect(card.find('.stat-value').text()).toBe('8')
    expect(card.find('.stat-label').text()).toBe('网关总数')
  })

  it('显示在线数', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const card = wrapper.find('[data-testid="stat-success"]')
    expect(card.find('.stat-value').text()).toBe('5')
    expect(card.find('.stat-label').text()).toBe('在线数')
  })

  it('显示离线数', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const card = wrapper.find('[data-testid="stat-danger"]')
    expect(card.find('.stat-value').text()).toBe('3')
    expect(card.find('.stat-label').text()).toBe('离线数')
  })

  it('告警网关数 = 离线且启用的网关', () => {
    const wrapper = mount(GatewayMonitorTestable)
    // GW-002 离线且启用 → 1 个告警
    const card = wrapper.find('[data-testid="stat-warning"]')
    expect(card.find('.stat-value').text()).toBe('1')
    expect(card.find('.stat-label').text()).toBe('告警网关')
  })

  it('平均负载 = 在线网关平均 CPU', () => {
    const wrapper = mount(GatewayMonitorTestable)
    // GW-001 在线 cpu_usage=45.2 → 平均 45.2%
    expect(wrapper.vm.avgThroughput).toBe('45.2%')
  })

  // ── 表格渲染 ──
  it('渲染网关列表', () => {
    const wrapper = mount(GatewayMonitorTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(3)
  })

  it('显示网关名称和 IP', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row1 = wrapper.find('[data-testid="gw-1"]')
    expect(row1.find('.name').text()).toBe('网关A')
    expect(row1.find('.ip').text()).toBe('192.168.1.10')
  })

  it('IP 为空时显示 --', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row3 = wrapper.find('[data-testid="gw-3"]')
    expect(row3.find('.ip').text()).toBe('--')
  })

  it('显示能力标签', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row1 = wrapper.find('[data-testid="gw-1"]')
    const tags = row1.findAll('.cap-tag')
    expect(tags).toHaveLength(2)
    expect(tags[0].text()).toBe('modbus_tcp')
    expect(tags[1].text()).toBe('snmp')
  })

  it('无能力标签时显示 --', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row3 = wrapper.find('[data-testid="gw-3"]')
    expect(row3.find('.caps .text-muted').text()).toBe('--')
  })

  it('显示状态标签', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row1 = wrapper.find('[data-testid="gw-1"]')
    expect(row1.find('.status span').text()).toBe('在线')
    expect(row1.find('.status span').classes()).toContain('tag-success')
  })

  it('显示 CPU / 内存', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row1 = wrapper.find('[data-testid="gw-1"]')
    expect(row1.find('.resource').text()).toContain('45.2%')
    expect(row1.find('.resource').text()).toContain('62.8%')
  })

  it('CPU/内存为空时显示 --', () => {
    const wrapper = mount(GatewayMonitorTestable)
    const row2 = wrapper.find('[data-testid="gw-2"]')
    expect(row2.find('.resource .text-muted').text()).toBe('--')
  })

  it('显示启用状态', () => {
    const wrapper = mount(GatewayMonitorTestable)
    expect(wrapper.find('[data-testid="gw-1"] .enabled').text()).toBe('是')
    expect(wrapper.find('[data-testid="gw-3"] .enabled').text()).toBe('否')
  })

  // ── 辅助函数 ──
  it('statusTagType 映射正确', () => {
    expect(statusTagType('online')).toBe('success')
    expect(statusTagType('offline')).toBe('danger')
    expect(statusTagType('unknown')).toBe('info')
  })

  it('statusText 映射正确', () => {
    expect(statusText('online')).toBe('在线')
    expect(statusText('offline')).toBe('离线')
    expect(statusText('other')).toBe('other')
  })

  it('formatTime 格式化时间', () => {
    expect(formatTime(null)).toBe('--')
    expect(formatTime(undefined)).toBe('--')
    expect(formatTime('2026-01-15T10:30:45.000Z')).toBe('2026-01-15 10:30:45')
  })

  it('isOfflineAlert 离线超 5 分钟告警', () => {
    // 在线网关不告警
    expect(isOfflineAlert({ status: 'online', is_enabled: true, last_heartbeat: null })).toBe(false)
    // 离线但未启用不告警
    expect(isOfflineAlert({ status: 'offline', is_enabled: false, last_heartbeat: null })).toBe(false)
    // 离线启用且无心跳 → 告警
    expect(isOfflineAlert({ status: 'offline', is_enabled: true, last_heartbeat: null })).toBe(true)
    // 离线启用且心跳超过 5 分钟 → 告警
    const oldTime = new Date(Date.now() - 10 * 60 * 1000).toISOString()
    expect(isOfflineAlert({ status: 'offline', is_enabled: true, last_heartbeat: oldTime })).toBe(true)
    // 离线启用但心跳在 5 分钟内 → 不告警
    const recentTime = new Date(Date.now() - 1 * 60 * 1000).toISOString()
    expect(isOfflineAlert({ status: 'offline', is_enabled: true, last_heartbeat: recentTime })).toBe(false)
  })

  it('progressColor 根据使用率返回颜色', () => {
    expect(progressColor(null)).toBe('#909399')
    expect(progressColor(50)).toBe('#52c41a')
    expect(progressColor(75)).toBe('#faad14')
    expect(progressColor(95)).toBe('#f5222d')
  })

  it('getCapabilityTags 提取能力标签', () => {
    expect(getCapabilityTags({ modbus_tcp: true, snmp: true })).toEqual(['modbus_tcp', 'snmp'])
    expect(getCapabilityTags(['mqtt', 'http'])).toEqual(['mqtt', 'http'])
    expect(getCapabilityTags(null)).toEqual([])
    // 最多 3 个
    expect(getCapabilityTags({ a: 1, b: 2, c: 3, d: 4 })).toHaveLength(3)
  })

  // ── 筛选与交互 ──
  it('初始状态正确', () => {
    const wrapper = mount(GatewayMonitorTestable)
    expect(wrapper.vm.pagination.page).toBe(1)
    expect(wrapper.vm.pagination.pageSize).toBe(20)
    expect(wrapper.vm.filterStatus).toBe('')
    expect(wrapper.vm.searchKeyword).toBe('')
    expect(wrapper.vm.configDialogVisible).toBe(false)
    expect(wrapper.vm.selectedGateways).toHaveLength(0)
    expect(wrapper.vm.batchPushing).toBe(false)
  })

  it('搜索重置页码', async () => {
    const wrapper = mount(GatewayMonitorTestable)
    wrapper.vm.pagination.page = 5
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.vm.pagination.page).toBe(1)
  })

  it('配置下发按钮: 在线且启用时可点击', () => {
    const wrapper = mount(GatewayMonitorTestable)
    // GW-001: 在线 + 启用 → 可点击
    const btn1 = wrapper.find('[data-testid="gw-1"] .config-push-btn')
    expect((btn1.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('配置下发按钮: 离线时禁用', () => {
    const wrapper = mount(GatewayMonitorTestable)
    // GW-002: 离线 → 禁用
    const btn2 = wrapper.find('[data-testid="gw-2"] .config-push-btn')
    expect((btn2.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('配置下发按钮: 未启用时禁用', () => {
    const wrapper = mount(GatewayMonitorTestable)
    // GW-003: 离线 + 未启用 → 禁用
    const btn3 = wrapper.find('[data-testid="gw-3"] .config-push-btn')
    expect((btn3.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('点击配置下发打开对话框', async () => {
    const wrapper = mount(GatewayMonitorTestable)
    await wrapper.find('[data-testid="gw-1"] .config-push-btn').trigger('click')
    expect(wrapper.vm.configDialogVisible).toBe(true)
    expect(wrapper.vm.configGatewayId).toBe(1)
    expect(wrapper.vm.configGatewayName).toBe('网关A')
    expect(wrapper.find('[data-testid="config-dialog"]').text()).toContain('网关A')
  })

  it('选中网关后显示批量下发按钮', async () => {
    const wrapper = mount(GatewayMonitorTestable)
    // 初始无选中 → 按钮不存在
    expect(wrapper.find('[data-testid="batch-push-btn"]').exists()).toBe(false)
    // 模拟选中
    wrapper.vm.handleSelectionChange([wrapper.vm.tableData[0]])
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="batch-push-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="batch-push-btn"]').text()).toContain('1')
  })

  it('数据更新后视图同步', async () => {
    const wrapper = mount(GatewayMonitorTestable)
    wrapper.vm.summary.total = 20
    wrapper.vm.summary.online = 15
    await wrapper.vm.$nextTick()
    const primaryCard = wrapper.find('[data-testid="stat-primary"]')
    expect(primaryCard.find('.stat-value').text()).toBe('20')
  })
})
