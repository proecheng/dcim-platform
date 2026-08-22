/**
 * Composables 额外覆盖测试
 * 覆盖: useDataQuality, useEnergy, useRealtime, useSiteFilter, useSound
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useDataQuality } from '@/composables/useDataQuality'

// ==================== Mock 依赖 ====================

// Mock WebSocket (systemWs)
const { mockWsConnect, mockWsOn, mockWsOff, mockNotification } = vi.hoisted(() => ({
  mockWsConnect: vi.fn(),
  mockWsOn: vi.fn(),
  mockWsOff: vi.fn(),
  mockNotification: vi.fn(),
}))
vi.mock('@/api/websocket', () => ({
  systemWs: { connect: mockWsConnect, on: mockWsOn, off: mockWsOff },
}))

// Mock useWebSocket composable
const mockSubscribe = vi.fn()
const mockWsConnectComposable = vi.fn()
const mockDisconnect = vi.fn()
const mockOnWs = vi.fn()
const mockOffWs = vi.fn()
const mockIsConnected = { value: false }
vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    isConnected: mockIsConnected,
    connect: mockWsConnectComposable,
    disconnect: mockDisconnect,
    subscribe: mockSubscribe,
    on: mockOnWs,
    off: mockOffWs,
    send: vi.fn(),
    unsubscribe: vi.fn(),
    lastMessage: { value: null },
    error: { value: null },
    client: {},
  }),
}))

// Mock ElNotification
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('element-plus')
  return { ...actual, ElNotification: mockNotification }
})

// Mock realtime API
vi.mock('@/api/modules/realtime', () => ({
  getAllRealtimeData: vi.fn().mockResolvedValue([
    { point_id: 1, point_type: 'AI', area_code: 'A1', status: 'normal', value: 25.5 },
    { point_id: 2, point_type: 'DI', area_code: 'A1', status: 'alarm', value: 1 },
    { point_id: 3, point_type: 'AI', area_code: 'B1', status: 'offline', value: null },
  ]),
  getRealtimeSummary: vi.fn().mockResolvedValue({ total: 3, normal: 1, alarm: 1, offline: 1 }),
}))

// Mock energy API
vi.mock('@/api/modules/energy', () => ({
  getRealtimePower: vi.fn().mockResolvedValue({ code: 0, data: [{ device_id: 1, power: 100 }] }),
  getPowerSummary: vi.fn().mockResolvedValue({ code: 0, data: { total_power: 500, it_power: 300, cooling_power: 150, today_energy: 1200 } }),
  getCurrentPUE: vi.fn().mockResolvedValue({ code: 0, data: { current_pue: 1.55 } }),
  getPUETrend: vi.fn().mockResolvedValue({ code: 0, data: { period: 'day', data_points: [] } }),
  getEnergySummary: vi.fn().mockResolvedValue({ code: 0, data: { total_energy: 5000 } }),
  getEnergyTrend: vi.fn().mockResolvedValue({ code: 0, data: { data_points: [] } }),
  getEnergyComparison: vi.fn().mockResolvedValue({ code: 0, data: { current: 100, previous: 90, change_rate: 0.11 } }),
  getSuggestions: vi.fn().mockResolvedValue({ code: 0, data: [{ id: 1, title: '建议1', status: 'pending' }] }),
  acceptSuggestion: vi.fn().mockResolvedValue({ code: 0 }),
  rejectSuggestion: vi.fn().mockResolvedValue({ code: 0 }),
  completeSuggestion: vi.fn().mockResolvedValue({ code: 0 }),
  getSavingPotential: vi.fn().mockResolvedValue({ code: 0, data: { total_potential: 30000 } }),
  getDistributionDiagram: vi.fn().mockResolvedValue({ code: 0, data: { nodes: [], edges: [] } }),
}))

// Mock auth API (needed by stores)
vi.mock('@/api/modules/auth', () => ({
  login: vi.fn(), logout: vi.fn(), getCurrentUser: vi.fn(), getPermissions: vi.fn(),
}))

// Mock spatial API (needed by site store)
vi.mock('@/api/modules/spatial', () => ({
  getSites: vi.fn().mockResolvedValue({ data: [{ id: 1, site_name: '站点A' }, { id: 2, site_name: '站点B' }] }),
  getSiteSummary: vi.fn().mockResolvedValue({ data: { total: 2 } }),
}))

// ==================== Helper ====================

function mountComposable<T>(composableFn: () => T, pinia: ReturnType<typeof createPinia>): { result: T; wrapper: ReturnType<typeof mount> } {
  let result!: T
  const Comp = defineComponent({
    setup() {
      result = composableFn()
      return {}
    },
    template: '<div />',
  })
  const wrapper = mount(Comp, { global: { plugins: [pinia] } })
  return { result, wrapper }
}

// ==================== useSound ====================

describe('useSound', () => {
  let mockAudio: Record<string, unknown>

  beforeEach(() => {
    mockAudio = {
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      volume: 1,
      loop: false,
      currentTime: 0,
      onplay: null,
      onended: null,
      onerror: null,
    }
    vi.stubGlobal('Audio', vi.fn().mockImplementation(function () { return mockAudio }))
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('初始状态', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    expect(result.isPlaying.value).toBe(false)
    expect(result.isMuted.value).toBe(false)
    expect(result.volume.value).toBe(1)
  })

  it('play 创建音频并播放', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.play('/test.mp3', { loop: true, volume: 0.5 })
    expect(Audio).toHaveBeenCalledWith('/test.mp3')
    expect(mockAudio.loop).toBe(true)
    expect(mockAudio.volume).toBe(0.5)
    expect(mockAudio.play).toHaveBeenCalled()
  })

  it('stop 停止播放并重置', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.play('/test.mp3')
    result.stop()
    expect(mockAudio.pause).toHaveBeenCalled()
    expect(mockAudio.currentTime).toBe(0)
  })

  it('pause / resume', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.play('/test.mp3')
    result.pause()
    expect(mockAudio.pause).toHaveBeenCalled()
    result.resume()
    expect(mockAudio.play).toHaveBeenCalledTimes(2)
  })

  it('setVolume 限制在 0-1 范围', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.setVolume(0.5)
    expect(result.volume.value).toBe(0.5)
    result.setVolume(2)
    expect(result.volume.value).toBe(1)
    result.setVolume(-1)
    expect(result.volume.value).toBe(0)
  })

  it('toggleMute / setMuted', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.play('/test.mp3')
    result.toggleMute()
    expect(result.isMuted.value).toBe(true)
    expect(mockAudio.volume).toBe(0)
    result.setMuted(false)
    expect(result.isMuted.value).toBe(false)
  })

  it('playAlarm 根据级别选择声音', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.playAlarm('critical')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_critical.mp3')
    expect(mockAudio.loop).toBe(true)
    result.playAlarm('minor')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_minor.mp3')
  })

  it('playNotification 播放提示音', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSound } = await import('@/composables/useSound')
    const { result } = mountComposable(() => useSound(), pinia)
    result.playNotification()
    expect(Audio).toHaveBeenCalledWith('/sounds/notification.mp3')
  })
})

// ==================== useDataQuality ====================

describe('useDataQuality', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockWsConnect.mockClear()
    mockWsOn.mockClear()
    mockWsOff.mockClear()
    mockNotification.mockClear()
  })

  it('onMounted 连接 WebSocket 并注册监听', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    mountComposable(() => useDataQuality(), pinia)
    expect(mockWsConnect).toHaveBeenCalled()
    expect(mockWsOn).toHaveBeenCalledWith('system', expect.any(Function))
  })

  it('onUnmounted 取消监听', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { wrapper } = mountComposable(() => useDataQuality(), pinia)
    wrapper.unmount()
    expect(mockWsOff).toHaveBeenCalledWith('system', expect.any(Function))
  })

  it('收到 quality=2 消息时弹出 warning 通知', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    mountComposable(() => useDataQuality(), pinia)
    const handler = mockWsOn.mock.calls.find((c: unknown[]) => c[0] === 'system')?.[1] as (msg: unknown) => void
    handler({ data: { type: 'data_quality_changed', quality: 2, affected_count: 5 } })
    expect(mockNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'warning' }))
  })

  it('收到 quality=0 消息时弹出 success 通知', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    mountComposable(() => useDataQuality(), pinia)
    const handler = mockWsOn.mock.calls.find((c: unknown[]) => c[0] === 'system')?.[1] as (msg: unknown) => void
    handler({ data: { type: 'data_quality_changed', quality: 0, affected_count: 5 } })
    expect(mockNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'success' }))
  })

  it('非 data_quality_changed 消息不触发通知', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    mountComposable(() => useDataQuality(), pinia)
    const handler = mockWsOn.mock.calls.find((c: unknown[]) => c[0] === 'system')?.[1] as (msg: unknown) => void
    handler({ data: { type: 'other_event' } })
    expect(mockNotification).not.toHaveBeenCalled()
  })
})

// ==================== useEnergy ====================

describe('useEnergy', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始状态', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    expect(result.loading.value).toBe(false)
    expect(result.error.value).toBeNull()
  })

  it('loadRealtimePower 加载实时电力', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    await result.loadRealtimePower()
    expect(result.loading.value).toBe(false)
    expect(result.error.value).toBeNull()
  })

  it('loadRealtimePower 错误处理', async () => {
    const energyApi = await import('@/api/modules/energy')
    vi.mocked(energyApi.getRealtimePower).mockRejectedValueOnce(new Error('网络错误'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    await result.loadRealtimePower()
    expect(result.error.value).toBe('网络错误')
  })

  it('handleAcceptSuggestion 接受建议', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    const ok = await result.handleAcceptSuggestion(1, '同意')
    expect(ok).toBe(true)
  })

  it('handleRejectSuggestion 拒绝建议', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    const ok = await result.handleRejectSuggestion(1, '不合适')
    expect(ok).toBe(true)
  })

  it('handleCompleteSuggestion 完成建议', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    const ok = await result.handleCompleteSuggestion(1, 5000, '已完成')
    expect(ok).toBe(true)
  })

  it('formatPower 格式化功率', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    expect(result.formatPower(null)).toBe('-')
    expect(result.formatPower(undefined)).toBe('-')
    expect(result.formatPower(500)).toBe('500.00 kW')
    expect(result.formatPower(1500)).toBe('1.50 MW')
  })

  it('formatEnergy 格式化电量', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    expect(result.formatEnergy(null)).toBe('-')
    expect(result.formatEnergy(500)).toBe('500.00 kWh')
    expect(result.formatEnergy(5000)).toBe('5.00 MWh')
    expect(result.formatEnergy(2000000)).toBe('2.00 GWh')
  })

  it('formatCost 格式化电费', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    expect(result.formatCost(null)).toBe('-')
    expect(result.formatCost(500)).toBe('500.00 元')
    expect(result.formatCost(50000)).toBe('5.00 万元')
  })

  it('formatPUE / getPUELevel / getLoadRateStatus', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    expect(result.formatPUE(null)).toBe('-')
    expect(result.formatPUE(1.55)).toBe('1.550')
    expect(result.getPUELevel(1.3).level).toBe('优秀')
    expect(result.getPUELevel(1.5).level).toBe('良好')
    expect(result.getPUELevel(1.7).level).toBe('一般')
    expect(result.getPUELevel(2.0).level).toBe('较差')
    expect(result.getLoadRateStatus(20).status).toBe('低负载')
    expect(result.getLoadRateStatus(50).status).toBe('正常')
    expect(result.getLoadRateStatus(70).status).toBe('较高')
    expect(result.getLoadRateStatus(90).status).toBe('高负载')
  })

  it('startPolling / stopPolling', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useEnergy } = await import('@/composables/useEnergy')
    const { result } = mountComposable(() => useEnergy(), pinia)
    const energyApi = await import('@/api/modules/energy')
    vi.mocked(energyApi.getRealtimePower).mockClear()
    result.startPolling(1000)
    vi.advanceTimersByTime(1000)
    expect(energyApi.getRealtimePower).toHaveBeenCalled()
    result.stopPolling()
    vi.mocked(energyApi.getRealtimePower).mockClear()
    vi.advanceTimersByTime(2000)
    expect(energyApi.getRealtimePower).not.toHaveBeenCalled()
  })
})

// ==================== useSiteFilter ====================

describe('useSiteFilter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('getSiteParams 无站点时返回空对象', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSiteFilter } = await import('@/composables/useSiteFilter')
    const { result } = mountComposable(() => useSiteFilter(), pinia)
    expect(result.getSiteParams()).toEqual({})
  })

  it('getSiteParams 有站点时返回 site_id', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSiteStore } = await import('@/stores')
    const siteStore = useSiteStore()
    siteStore.switchSite(1)
    const { useSiteFilter } = await import('@/composables/useSiteFilter')
    const { result } = mountComposable(() => useSiteFilter(), pinia)
    expect(result.getSiteParams()).toEqual({ site_id: 1 })
  })

  it('onSiteChange 监听站点切换', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const { useSiteStore } = await import('@/stores')
    const siteStore = useSiteStore()
    const { useSiteFilter } = await import('@/composables/useSiteFilter')
    const callback = vi.fn()
    const { result } = mountComposable(() => {
      const sf = useSiteFilter()
      sf.onSiteChange(callback)
      return sf
    }, pinia)
    siteStore.switchSite(2)
    await nextTick()
    expect(callback).toHaveBeenCalled()
  })
})
