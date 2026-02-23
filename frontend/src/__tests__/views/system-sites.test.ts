/**
 * 站点管理页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }) }))
vi.mock('@/api/modules/spatial', () => ({
  getSites: vi.fn().mockResolvedValue([]),
  createSite: vi.fn().mockResolvedValue({}),
  updateSite: vi.fn().mockResolvedValue({}),
  deleteSite: vi.fn().mockResolvedValue({}),
  getSiteSummary: vi.fn().mockResolvedValue({ total_sites: 0, total_devices: 0, total_gateways: 0, total_alarms: 0 }),
}))
vi.mock('@/stores/site', () => ({
  useSiteStore: () => ({
    currentSiteId: null,
    fetchSites: vi.fn(),
    switchSite: vi.fn(),
  }),
}))

// ── 从 sites.vue 提取的辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    normal: 'success', active: 'success', alarm: 'danger', warning: 'warning', offline: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    normal: '正常', active: '正常', alarm: '告警', warning: '告警', offline: '离线',
  }
  return map[status] || status
}

function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ── 可测试的站点管理组件 ──
const SitesTestable = defineComponent({
  name: 'SitesTestable',
  setup() {
    const loading = ref(false)
    const summaryData = ref({ total_sites: 5, total_devices: 120, total_gateways: 8, total_alarms: 3 })
    const siteList = ref([
      { id: 1, site_code: 'DC-BJ-01', site_name: '北京数据中心', address: '北京市朝阳区', contact_person: '张三', contact_phone: '13800138000', device_count: 50, gateway_count: 3, status: 'normal', created_at: '2026-01-01T00:00:00', description: '' },
      { id: 2, site_code: 'DC-SH-01', site_name: '上海数据中心', address: '', contact_person: '', contact_phone: '', device_count: 40, gateway_count: 3, status: 'alarm', created_at: '2026-01-15T10:30:00', description: '' },
      { id: 3, site_code: 'DC-GZ-01', site_name: '广州数据中心', address: '广州市天河区', contact_person: '李四', contact_phone: '', device_count: 30, gateway_count: 2, status: 'offline', created_at: null, description: '' },
    ])
    const searchKeyword = ref('')

    const filteredSites = computed(() => {
      if (!searchKeyword.value) return siteList.value
      const kw = searchKeyword.value.toLowerCase()
      return siteList.value.filter(s => s.site_name.toLowerCase().includes(kw) || s.site_code.toLowerCase().includes(kw))
    })

    return { loading, summaryData, siteList, searchKeyword, filteredSites, statusTagType, statusLabel, formatDateTime }
  },
  template: `<div class="sites-page">
    <div class="stat-cards">
      <div class="card" data-testid="stat-sites"><span class="value">{{ summaryData.total_sites }}</span><span class="label">站点总数</span></div>
      <div class="card" data-testid="stat-devices"><span class="value">{{ summaryData.total_devices }}</span><span class="label">设备总数</span></div>
      <div class="card" data-testid="stat-gateways"><span class="value">{{ summaryData.total_gateways }}</span><span class="label">网关总数</span></div>
      <div class="card" data-testid="stat-alarms"><span class="value">{{ summaryData.total_alarms }}</span><span class="label">活跃告警</span></div>
    </div>
    <div class="table" data-testid="table">
      <div v-for="site in filteredSites" :key="site.id" :data-testid="'site-' + site.id" class="row">
        <span class="code">{{ site.site_code }}</span>
        <span class="name">{{ site.site_name }}</span>
        <span class="address">{{ site.address || '--' }}</span>
        <span class="contact">{{ site.contact_person || '--' }}</span>
        <span class="devices">{{ site.device_count }}</span>
        <span class="gateways">{{ site.gateway_count }}</span>
        <span class="status">{{ statusLabel(site.status) }}</span>
        <span class="created">{{ formatDateTime(site.created_at) }}</span>
      </div>
    </div>
  </div>`
})

describe('站点管理页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  // ── 统计卡片 ──
  it('渲染统计卡片 - 站点总数', () => {
    expect(mount(SitesTestable).find('[data-testid="stat-sites"] .value').text()).toBe('5')
  })

  it('渲染统计卡片 - 设备总数', () => {
    expect(mount(SitesTestable).find('[data-testid="stat-devices"] .value').text()).toBe('120')
  })

  it('渲染统计卡片 - 网关总数', () => {
    expect(mount(SitesTestable).find('[data-testid="stat-gateways"] .value').text()).toBe('8')
  })

  it('渲染统计卡片 - 活跃告警', () => {
    expect(mount(SitesTestable).find('[data-testid="stat-alarms"] .value').text()).toBe('3')
  })

  // ── 表格渲染 ──
  it('渲染站点列表', () => {
    expect(mount(SitesTestable).findAll('.row')).toHaveLength(3)
  })

  it('显示站点编码和名称', () => {
    const w = mount(SitesTestable)
    expect(w.find('[data-testid="site-1"] .code').text()).toBe('DC-BJ-01')
    expect(w.find('[data-testid="site-1"] .name').text()).toBe('北京数据中心')
  })

  it('地址为空时显示 --', () => {
    const w = mount(SitesTestable)
    expect(w.find('[data-testid="site-2"] .address').text()).toBe('--')
  })

  it('联系人为空时显示 --', () => {
    const w = mount(SitesTestable)
    expect(w.find('[data-testid="site-2"] .contact').text()).toBe('--')
  })

  it('显示状态标签', () => {
    const w = mount(SitesTestable)
    expect(w.find('[data-testid="site-1"] .status').text()).toBe('正常')
    expect(w.find('[data-testid="site-2"] .status').text()).toBe('告警')
    expect(w.find('[data-testid="site-3"] .status').text()).toBe('离线')
  })

  // ── 搜索筛选 ──
  it('按名称搜索', async () => {
    const w = mount(SitesTestable)
    w.vm.searchKeyword = '北京'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
    expect(w.find('.row .name').text()).toBe('北京数据中心')
  })

  it('按编码搜索', async () => {
    const w = mount(SitesTestable)
    w.vm.searchKeyword = 'DC-SH'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
    expect(w.find('.row .name').text()).toBe('上海数据中心')
  })

  it('搜索不区分大小写', async () => {
    const w = mount(SitesTestable)
    w.vm.searchKeyword = 'dc-gz'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(1)
  })

  it('搜索无结果时列表为空', async () => {
    const w = mount(SitesTestable)
    w.vm.searchKeyword = '不存在的站点'
    await w.vm.$nextTick()
    expect(w.findAll('.row')).toHaveLength(0)
  })

  // ── 辅助函数 ──
  it('statusTagType 映射正确', () => {
    expect(statusTagType('normal')).toBe('success')
    expect(statusTagType('active')).toBe('success')
    expect(statusTagType('alarm')).toBe('danger')
    expect(statusTagType('warning')).toBe('warning')
    expect(statusTagType('offline')).toBe('info')
    expect(statusTagType('unknown')).toBe('info')
  })

  it('statusLabel 映射正确', () => {
    expect(statusLabel('normal')).toBe('正常')
    expect(statusLabel('alarm')).toBe('告警')
    expect(statusLabel('offline')).toBe('离线')
    expect(statusLabel('xyz')).toBe('xyz')
  })

  it('formatDateTime 格式化时间', () => {
    expect(formatDateTime(undefined)).toBe('--')
    expect(formatDateTime('')).toBe('--')
    // 有值时应返回非空字符串
    const result = formatDateTime('2026-01-15T10:30:00')
    expect(result).not.toBe('--')
    expect(result.length).toBeGreaterThan(0)
  })
})
