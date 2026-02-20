/**
 * 6 Pinia Stores �ۺϵ�Ԫ����
 * ����: app, energy, realtime, site, degradation, bigscreen
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'
import { useEnergyStore } from '@/stores/energy'
import { useRealtimeStore } from '@/stores/realtime'
import { useSiteStore } from '@/stores/site'
import { useDegradationStore, degradationFlags } from '@/stores/degradation'
import { useBigscreenStore } from '@/stores/bigscreen'

// Mock API modules
vi.mock('@/api/modules/spatial', () => ({
  getSites: vi.fn().mockResolvedValue({ data: [
    { id: 1, site_code: 'S001', site_name: '����վ��', status: 'active', gateway_count: 2, device_count: 10, address: '', contact_person: '', contact_phone: '', contact_email: '', network_config: {}, description: '', created_at: '2026-01-01', updated_at: '2026-01-01' },
    { id: 2, site_code: 'S002', site_name: '�Ϻ�վ��', status: 'active', gateway_count: 1, device_count: 5, address: '', contact_person: '', contact_phone: '', contact_email: '', network_config: {}, description: '', created_at: '2026-01-01', updated_at: '2026-01-01' }
  ]}),
  getSiteSummary: vi.fn().mockResolvedValue({ data: { total_sites: 2, total_gateways: 3, total_devices: 15, total_alarms: 5, sites: [] } })
}))

vi.mock('@/api/modules/energy', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/api/modules/energy')
  return { ...actual }
})

vi.mock('@/api/modules/realtime', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/api/modules/realtime')
  return { ...actual }
})

vi.mock('@/types/bigscreen', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/types/bigscreen')
  return { ...actual }
})

// ==================== 1. useAppStore ====================
describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('��ʼ״̬��ȷ', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)
    expect(store.theme).toBe('light')
    expect(store.language).toBe('zh-CN')
    expect(store.alarmSoundEnabled).toBe(true)
    expect(store.alarmPopupEnabled).toBe(true)
    expect(store.refreshInterval).toBe(5)
    expect(store.isFullscreen).toBe(false)
    expect(store.globalLoading).toBe(false)
    expect(store.loadingText).toBe('')
    expect(store.breadcrumbs).toEqual([])
    expect(store.tabs).toEqual([])
    expect(store.activeTab).toBe('')
  })

  it('toggleSidebar �л���������־û�', () => {
    const store = useAppStore()
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'true')
    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'false')
  })

  it('setSidebarCollapsed ���ò����״̬', () => {
    const store = useAppStore()
    store.setSidebarCollapsed(true)
    expect(store.sidebarCollapsed).toBe(true)
    expect(localStorage.setItem).toHaveBeenCalledWith('sidebar_collapsed', 'true')
  })

  it('setTheme �������Ⲣ�־û�', () => {
    const store = useAppStore()
    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
  })

  it('toggleTheme �л�����', () => {
    const store = useAppStore()
    expect(store.theme).toBe('light')
    store.toggleTheme()
    expect(store.theme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
    store.toggleTheme()
    expect(store.theme).toBe('light')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'light')
  })

  it('setLanguage �������Բ��־û�', () => {
    const store = useAppStore()
    store.setLanguage('en-US')
    expect(store.language).toBe('en-US')
    expect(localStorage.setItem).toHaveBeenCalledWith('language', 'en-US')
  })

  it('toggleAlarmSound �л��澯����', () => {
    const store = useAppStore()
    store.toggleAlarmSound()
    expect(store.alarmSoundEnabled).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('alarm_sound', 'false')
    store.toggleAlarmSound()
    expect(store.alarmSoundEnabled).toBe(true)
  })

  it('toggleAlarmPopup �л��澯����', () => {
    const store = useAppStore()
    store.toggleAlarmPopup()
    expect(store.alarmPopupEnabled).toBe(false)
    expect(localStorage.setItem).toHaveBeenCalledWith('alarm_popup', 'false')
  })

  it('setRefreshInterval ����ˢ�¼��', () => {
    const store = useAppStore()
    store.setRefreshInterval(10)
    expect(store.refreshInterval).toBe(10)
    expect(localStorage.setItem).toHaveBeenCalledWith('refresh_interval', '10')
  })

  it('showLoading / hideLoading ���Ƽ���״̬', () => {
    const store = useAppStore()
    store.showLoading('���ڱ���...')
    expect(store.globalLoading).toBe(true)
    expect(store.loadingText).toBe('���ڱ���...')
    store.hideLoading()
    expect(store.globalLoading).toBe(false)
    expect(store.loadingText).toBe('')
  })

  it('showLoading default text', () => {
    const store = useAppStore()
    store.showLoading()
    expect(store.loadingText).toBe('加载中...')
  })

  it('setBreadcrumbs �������м', () => {
    const store = useAppStore()
    const items = [{ title: '��ҳ', path: '/' }, { title: '����' }]
    store.setBreadcrumbs(items)
    expect(store.breadcrumbs).toEqual(items)
  })

  it('addTab ���ӱ�ǩҳ�����û��ǩ', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    expect(store.tabs).toHaveLength(1)
    expect(store.activeTab).toBe('/')
  })

  it('addTab ���ظ�������ͬ·��', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    expect(store.tabs).toHaveLength(1)
    expect(store.activeTab).toBe('/')
  })

  it('removeTab �Ƴ���ǩҳ', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    store.addTab({ name: 'settings', path: '/settings', title: '����' })
    store.removeTab('/settings')
    expect(store.tabs).toHaveLength(1)
  })

  it('removeTab �رյ�ǰ��ǩʱ�л������һ��', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    store.addTab({ name: 'settings', path: '/settings', title: '����' })
    expect(store.activeTab).toBe('/settings')
    store.removeTab('/settings')
    expect(store.activeTab).toBe('/')
  })

  it('removeTab �Ƴ������ڵı�ǩ�޸�����', () => {
    const store = useAppStore()
    store.addTab({ name: 'home', path: '/', title: '��ҳ' })
    store.removeTab('/nonexistent')
    expect(store.tabs).toHaveLength(1)
  })

  it('initFromStorage �� localStorage �ָ�״̬', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    localStorage.setItem('theme', 'dark')
    localStorage.setItem('language', 'en-US')
    localStorage.setItem('alarm_sound', 'false')
    localStorage.setItem('alarm_popup', 'false')
    localStorage.setItem('refresh_interval', '15')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.sidebarCollapsed).toBe(true)
    expect(store.theme).toBe('dark')
    expect(store.language).toBe('en-US')
    expect(store.alarmSoundEnabled).toBe(false)
    expect(store.alarmPopupEnabled).toBe(false)
    expect(store.refreshInterval).toBe(15)
  })

  it('initFromStorage �޴洢ʱ����Ĭ��ֵ', () => {
    const store = useAppStore()
    store.initFromStorage()
    expect(store.sidebarCollapsed).toBe(false)
    expect(store.theme).toBe('light')
    expect(store.language).toBe('zh-CN')
    expect(store.alarmSoundEnabled).toBe(true)
    expect(store.refreshInterval).toBe(5)
  })

  it('initFromStorage �Ƿ� refresh_interval ����Ĭ��ֵ', () => {
    localStorage.setItem('refresh_interval', 'abc')
    const store = useAppStore()
    store.initFromStorage()
    expect(store.refreshInterval).toBe(5)
  })

  it('settings �������Ծۺ���������', () => {
    const store = useAppStore()
    store.setTheme('dark')
    store.setLanguage('en-US')
    store.setRefreshInterval(10)
    const s = store.settings
    expect(s.theme).toBe('dark')
    expect(s.language).toBe('en-US')
    expect(s.refreshInterval).toBe(10)
    expect(s.sidebarCollapsed).toBe(false)
    expect(s.alarmSoundEnabled).toBe(true)
    expect(s.alarmPopupEnabled).toBe(true)
  })
})

// ==================== 2. useEnergyStore ====================
describe('useEnergyStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  const makePowerData = (overrides: Record<string, unknown> = {}) => ({
    device_id: 1,
    device_code: 'D001',
    device_name: 'UPS-1',
    device_type: 'UPS',
    active_power: 100,
    status: 'normal' as const,
    update_time: '2026-01-01 00:00:00',
    ...overrides
  })

  const makeSuggestion = (overrides: Record<string, unknown> = {}) => ({
    id: 1,
    rule_id: 'R001',
    suggestion: '���齵�Ϳյ��¶�',
    priority: 'high' as const,
    status: 'pending' as const,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides
  })

  it('��ʼ״̬Ϊ��', () => {
    const store = useEnergyStore()
    expect(store.powerDataList).toEqual([])
    expect(store.powerSummary).toBeNull()
    expect(store.pueData).toBeNull()
    expect(store.suggestions).toEqual([])
    expect(store.distributionDiagram).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
    expect(store.wsConnected).toBe(false)
  })

  it('��������Ĭ��ֵ', () => {
    const store = useEnergyStore()
    expect(store.currentPUE).toBe(0)
    expect(store.totalPower).toBe(0)
    expect(store.itPower).toBe(0)
    expect(store.coolingPower).toBe(0)
    expect(store.todayEnergy).toBe(0)
    expect(store.todayCost).toBe(0)
    expect(store.monthEnergy).toBe(0)
    expect(store.monthCost).toBe(0)
    expect(store.pendingCount).toBe(0)
    expect(store.highPrioritySuggestions).toEqual([])
  })

  it('updatePowerData ���µ����豸����', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData() as any)
    expect(store.powerDataList).toHaveLength(1)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('updatePowerDataBatch ��������', () => {
    const store = useEnergyStore()
    store.updatePowerDataBatch([
      makePowerData({ device_id: 1 }) as any,
      makePowerData({ device_id: 2 }) as any
    ])
    expect(store.powerDataList).toHaveLength(2)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('setAllPowerData �滻ȫ������', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData({ device_id: 99 }) as any)
    store.setAllPowerData([makePowerData({ device_id: 1 }) as any])
    expect(store.powerDataList).toHaveLength(1)
    expect(store.getDevicePower(99)).toBeUndefined()
  })

  it('setPowerSummary ���õ�������', () => {
    const store = useEnergyStore()
    const summary = {
      total_power: 500, it_power: 300, cooling_power: 150,
      ups_power: 30, other_power: 20, current_pue: 1.67,
      today_energy: 1200, today_cost: 960,
      month_energy: 36000, month_cost: 28800
    }
    store.setPowerSummary(summary as any)
    expect(store.totalPower).toBe(500)
    expect(store.itPower).toBe(300)
    expect(store.coolingPower).toBe(150)
    expect(store.todayEnergy).toBe(1200)
    expect(store.todayCost).toBe(960)
    expect(store.monthEnergy).toBe(36000)
    expect(store.monthCost).toBe(28800)
  })

  it('setPUEData ���� PUE ����', () => {
    const store = useEnergyStore()
    store.setPUEData({ current_pue: 1.45, total_power: 500, it_power: 345, cooling_power: 100, ups_loss: 10, lighting_power: 5, other_power: 40, update_time: '2026-01-01' } as any)
    expect(store.currentPUE).toBe(1.45)
  })

  it('setSuggestions ���ý��ܽ����б�', () => {
    const store = useEnergyStore()
    store.setSuggestions([makeSuggestion() as any, makeSuggestion({ id: 2, status: 'accepted' }) as any])
    expect(store.suggestions).toHaveLength(2)
    expect(store.pendingCount).toBe(1)
  })

  it('addSuggestion �����������ͷ��', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1 }) as any)
    store.addSuggestion(makeSuggestion({ id: 2 }) as any)
    expect(store.suggestions).toHaveLength(2)
    expect(store.suggestions[0].id).toBe(2)
  })

  it('addSuggestion dedup — same id updates', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1, suggestion: 'old suggestion' }) as any)
    store.addSuggestion(makeSuggestion({ id: 1, suggestion: 'new suggestion' }) as any)
    expect(store.suggestions).toHaveLength(1)
    expect(store.suggestions[0].suggestion).toBe('new suggestion')
  })

  it('updateSuggestionStatus ���½���״̬', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1, status: 'pending' }) as any)
    store.updateSuggestionStatus(1, 'accepted', { accepted_at: '2026-01-02' })
    expect(store.suggestions[0].status).toBe('accepted')
    expect(store.suggestions[0].accepted_at).toBe('2026-01-02')
  })

  it('updateSuggestionStatus �����ڵ� id �޸�����', () => {
    const store = useEnergyStore()
    store.addSuggestion(makeSuggestion({ id: 1 }) as any)
    store.updateSuggestionStatus(999, 'accepted')
    expect(store.suggestions[0].status).toBe('pending')
  })

  it('setDistributionDiagram �������ͼ', () => {
    const store = useEnergyStore()
    const diagram = { root: { device_id: 1, device_code: 'D001', device_name: 'Main', device_type: 'MAIN', status: 'normal', children: [] }, total_power: 500, timestamp: '2026-01-01' }
    store.setDistributionDiagram(diagram as any)
    expect(store.distributionDiagram).not.toBeNull()
  })

  it('getDevicePower ��ȡ�豸��������', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData({ device_id: 42 }) as any)
    expect(store.getDevicePower(42)).toBeDefined()
    expect(store.getDevicePower(999)).toBeUndefined()
  })

  it('getPowerByType �����͹���', () => {
    const store = useEnergyStore()
    store.updatePowerDataBatch([
      makePowerData({ device_id: 1, device_type: 'UPS' }) as any,
      makePowerData({ device_id: 2, device_type: 'PDU' }) as any,
      makePowerData({ device_id: 3, device_type: 'UPS' }) as any
    ])
    expect(store.getPowerByType('UPS')).toHaveLength(2)
    expect(store.getPowerByType('PDU')).toHaveLength(1)
    expect(store.getPowerByType('AC')).toHaveLength(0)
  })

  it('setWsConnected ���� WebSocket ״̬', () => {
    const store = useEnergyStore()
    store.setWsConnected(true)
    expect(store.wsConnected).toBe(true)
    store.setWsConnected(false)
    expect(store.wsConnected).toBe(false)
  })

  it('clearData �����������', () => {
    const store = useEnergyStore()
    store.updatePowerData(makePowerData() as any)
    store.setPowerSummary({ total_power: 100 } as any)
    store.setPUEData({ current_pue: 1.5 } as any)
    store.setSuggestions([makeSuggestion() as any])
    store.setDistributionDiagram({ root: {} } as any)
    store.clearData()
    expect(store.powerDataList).toEqual([])
    expect(store.powerSummary).toBeNull()
    expect(store.pueData).toBeNull()
    expect(store.suggestions).toEqual([])
    expect(store.distributionDiagram).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
  })

  it('highPrioritySuggestions ���˸����ȼ�����������', () => {
    const store = useEnergyStore()
    store.setSuggestions([
      makeSuggestion({ id: 1, priority: 'high', status: 'pending' }) as any,
      makeSuggestion({ id: 2, priority: 'low', status: 'pending' }) as any,
      makeSuggestion({ id: 3, priority: 'high', status: 'accepted' }) as any
    ])
    expect(store.highPrioritySuggestions).toHaveLength(1)
    expect(store.highPrioritySuggestions[0].id).toBe(1)
  })

  it('pendingSuggestions ���˴���������', () => {
    const store = useEnergyStore()
    store.setSuggestions([
      makeSuggestion({ id: 1, status: 'pending' }) as any,
      makeSuggestion({ id: 2, status: 'accepted' }) as any,
      makeSuggestion({ id: 3, status: 'pending' }) as any
    ])
    expect(store.pendingSuggestions).toHaveLength(2)
    expect(store.pendingCount).toBe(2)
  })
})

// ==================== 3. useRealtimeStore ====================
describe('useRealtimeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  const makePoint = (overrides: Record<string, unknown> = {}) => ({
    point_id: 1,
    point_code: 'T001',
    point_name: '�¶ȴ�����1',
    point_type: 'AI' as const,
    device_type: 'sensor',
    area_code: 'A01',
    raw_value: 25.5,
    value: 25.5,
    value_text: '25.5',
    unit: '��C',
    quality: 100,
    status: 'normal' as const,
    alarm_level: null,
    change_count: 0,
    last_change_at: '2026-01-01',
    updated_at: '2026-01-01',
    ...overrides
  })

  it('��ʼ״̬Ϊ��', () => {
    const store = useRealtimeStore()
    expect(store.realtimeData).toEqual([])
    expect(store.totalPoints).toBe(0)
    expect(store.summary).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
    expect(store.wsConnected).toBe(false)
    expect(store.alarmCount).toBe(0)
    expect(store.offlineCount).toBe(0)
  })

  it('updatePoint ���µ�����λ', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint() as any)
    expect(store.totalPoints).toBe(1)
    expect(store.lastUpdateTime).not.toBeNull()
  })

  it('updatePoints ��������', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1 }) as any,
      makePoint({ point_id: 2 }) as any
    ])
    expect(store.totalPoints).toBe(2)
  })

  it('setAllData �滻ȫ������', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint({ point_id: 99 }) as any)
    store.setAllData([makePoint({ point_id: 1 }) as any])
    expect(store.totalPoints).toBe(1)
    expect(store.getPointData(99)).toBeUndefined()
  })

  it('setSummary ���û�������', () => {
    const store = useRealtimeStore()
    const summary = { total_points: 50, online_points: 48, offline_points: 2, alarm_points: 3, by_type: {}, by_area: {} }
    store.setSummary(summary as any)
    expect(store.summary).toEqual(summary)
  })

  it('getPointData ��ȡ��λ����', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint({ point_id: 42 }) as any)
    expect(store.getPointData(42)).toBeDefined()
    expect(store.getPointData(999)).toBeUndefined()
  })

  it('getDataByType �����͹���', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, point_type: 'AI' }) as any,
      makePoint({ point_id: 2, point_type: 'DI' }) as any,
      makePoint({ point_id: 3, point_type: 'AI' }) as any
    ])
    expect(store.getDataByType('AI')).toHaveLength(2)
    expect(store.getDataByType('DI')).toHaveLength(1)
    expect(store.getDataByType('AO')).toHaveLength(0)
  })

  it('getDataByArea ���������', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, area_code: 'A01' }) as any,
      makePoint({ point_id: 2, area_code: 'A02' }) as any,
      makePoint({ point_id: 3, area_code: 'A01' }) as any
    ])
    expect(store.getDataByArea('A01')).toHaveLength(2)
    expect(store.getDataByArea('A02')).toHaveLength(1)
    expect(store.getDataByArea('A99')).toHaveLength(0)
  })

  it('alarmPoints / alarmCount ����澯��λ', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, status: 'normal' }) as any,
      makePoint({ point_id: 2, status: 'alarm' }) as any,
      makePoint({ point_id: 3, status: 'alarm' }) as any
    ])
    expect(store.alarmPoints).toHaveLength(2)
    expect(store.alarmCount).toBe(2)
  })

  it('offlinePoints / offlineCount �������ߵ�λ', () => {
    const store = useRealtimeStore()
    store.updatePoints([
      makePoint({ point_id: 1, status: 'normal' }) as any,
      makePoint({ point_id: 2, status: 'offline' }) as any
    ])
    expect(store.offlinePoints).toHaveLength(1)
    expect(store.offlineCount).toBe(1)
  })

  it('setWsConnected ��������״̬', () => {
    const store = useRealtimeStore()
    store.setWsConnected(true)
    expect(store.wsConnected).toBe(true)
  })

  it('clearData �����������', () => {
    const store = useRealtimeStore()
    store.updatePoint(makePoint() as any)
    store.setSummary({ total_points: 1 } as any)
    store.clearData()
    expect(store.totalPoints).toBe(0)
    expect(store.summary).toBeNull()
    expect(store.lastUpdateTime).toBeNull()
  })
})
