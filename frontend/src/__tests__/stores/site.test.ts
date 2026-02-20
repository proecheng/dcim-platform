/**
 * Site Store 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSiteStore } from '@/stores/site'

// Mock spatial API
vi.mock('@/api/modules/spatial', () => ({
  getSites: vi.fn().mockResolvedValue({
    data: [
      { id: 1, site_code: 'S001', site_name: '北京站点', status: 'active', gateway_count: 2, device_count: 10, address: '', contact_person: '', contact_phone: '', contact_email: '', network_config: {}, description: '', created_at: '2026-01-01', updated_at: '2026-01-01' },
      { id: 2, site_code: 'S002', site_name: '上海站点', status: 'active', gateway_count: 1, device_count: 5, address: '', contact_person: '', contact_phone: '', contact_email: '', network_config: {}, description: '', created_at: '2026-01-01', updated_at: '2026-01-01' }
    ]
  }),
  getSiteSummary: vi.fn().mockResolvedValue({
    data: { total_sites: 2, total_gateways: 3, total_devices: 15, total_alarms: 5, sites: [] }
  })
}))

describe('useSiteStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('初始状态正确', () => {
    const store = useSiteStore()
    expect(store.currentSiteId).toBeNull()
    expect(store.sites).toEqual([])
    expect(store.summary).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('currentSite — 无选中站点时返回 null', () => {
    const store = useSiteStore()
    expect(store.currentSite).toBeNull()
  })

  it('currentSiteName — 无选中站点时返回全部站点', () => {
    const store = useSiteStore()
    expect(store.currentSiteName).toBe('全部站点')
  })

  it('fetchSites 加载站点列表', async () => {
    const store = useSiteStore()
    await store.fetchSites()
    expect(store.sites).toHaveLength(2)
    expect(store.sites[0].site_name).toBe('北京站点')
    expect(store.loading).toBe(false)
  })

  it('fetchSummary 加载站点汇总', async () => {
    const store = useSiteStore()
    await store.fetchSummary()
    expect(store.summary).not.toBeNull()
    expect(store.summary?.total_sites).toBe(2)
  })

  it('switchSite 切换站点并持久化', () => {
    const store = useSiteStore()
    store.switchSite(1)
    expect(store.currentSiteId).toBe(1)
    expect(localStorage.setItem).toHaveBeenCalledWith('current_site_id', '1')
  })

  it('switchSite null 清除站点选择', () => {
    const store = useSiteStore()
    store.switchSite(1)
    store.switchSite(null)
    expect(store.currentSiteId).toBeNull()
    expect(localStorage.removeItem).toHaveBeenCalledWith('current_site_id')
  })

  it('currentSite — 选中站点后返回对应站点', async () => {
    const store = useSiteStore()
    await store.fetchSites()
    store.switchSite(1)
    expect(store.currentSite).not.toBeNull()
    expect(store.currentSite?.site_name).toBe('北京站点')
  })

  it('currentSiteName — 选中站点后返回站点名称', async () => {
    const store = useSiteStore()
    await store.fetchSites()
    store.switchSite(2)
    expect(store.currentSiteName).toBe('上海站点')
  })

  it('currentSite — 选中不存在的站点返回 null', async () => {
    const store = useSiteStore()
    await store.fetchSites()
    store.switchSite(999)
    expect(store.currentSite).toBeNull()
  })

  it('fetchSites 错误处理 — 不抛出异常', async () => {
    const { getSites } = await import('@/api/modules/spatial')
    vi.mocked(getSites).mockRejectedValueOnce(new Error('网络错误'))
    const store = useSiteStore()
    await store.fetchSites()
    expect(store.sites).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchSummary 错误处理 — 不抛出异常', async () => {
    const { getSiteSummary } = await import('@/api/modules/spatial')
    vi.mocked(getSiteSummary).mockRejectedValueOnce(new Error('网络错误'))
    const store = useSiteStore()
    await store.fetchSummary()
    expect(store.summary).toBeNull()
  })
})
