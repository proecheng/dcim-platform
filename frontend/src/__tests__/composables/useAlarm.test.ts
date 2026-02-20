/**
 * useAlarm 组合式函数单元测试
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'

// Mock alarm API
vi.mock('@/api/modules/alarm', () => ({
  getActiveAlarms: vi.fn().mockResolvedValue([
    { id: 1, alarm_no: 'ALM-001', point_id: 1, point_code: 'T001', point_name: '温度1', threshold_id: 1, alarm_level: 'critical', alarm_type: 'threshold', alarm_message: '温度过高', trigger_value: 40, threshold_value: 35, status: 'active', acknowledged_by: null, acknowledged_at: null, ack_remark: null, resolved_by: null, resolved_at: null, resolve_remark: null, resolve_type: null, duration_seconds: null, is_notified: false, notify_count: 0, created_at: '2026-01-01' },
    { id: 2, alarm_no: 'ALM-002', point_id: 2, point_code: 'T002', point_name: '温度2', threshold_id: 2, alarm_level: 'major', alarm_type: 'threshold', alarm_message: '温度偏高', trigger_value: 35, threshold_value: 30, status: 'active', acknowledged_by: null, acknowledged_at: null, ack_remark: null, resolved_by: null, resolved_at: null, resolve_remark: null, resolve_type: null, duration_seconds: null, is_notified: false, notify_count: 0, created_at: '2026-01-01' }
  ]),
  getAlarmCount: vi.fn().mockResolvedValue({ critical: 1, major: 1, minor: 0, info: 0, total: 2 }),
  acknowledgeAlarm: vi.fn().mockResolvedValue(undefined),
  resolveAlarm: vi.fn().mockResolvedValue(undefined)
}))

// Mock auth API (needed by alarm store -> user store)
vi.mock('@/api/modules/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getPermissions: vi.fn()
}))

// Mock WebSocket composable
const mockWsConnect = vi.fn()
const mockWsDisconnect = vi.fn()
const mockWsSubscribe = vi.fn()
const mockWsOn = vi.fn()
const mockWsOff = vi.fn()

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({
    isConnected: { value: false },
    connect: mockWsConnect,
    disconnect: mockWsDisconnect,
    subscribe: mockWsSubscribe,
    on: mockWsOn,
    off: mockWsOff,
    send: vi.fn(),
    unsubscribe: vi.fn(),
    lastMessage: { value: null },
    error: { value: null },
    client: {}
  })
}))

// Mock sound composable
vi.mock('@/composables/useSound', () => ({
  useSound: vi.fn().mockReturnValue({
    play: vi.fn(),
    stop: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    setVolume: vi.fn(),
    toggleMute: vi.fn(),
    setMuted: vi.fn(),
    playAlarm: vi.fn(),
    playNotification: vi.fn(),
    isPlaying: { value: false },
    isMuted: { value: false },
    volume: { value: 1 }
  })
}))

// Mock ElNotification
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<any>('element-plus')
  return {
    ...actual,
    ElNotification: vi.fn()
  }
})

async function setupAlarm(options: Record<string, unknown> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const { useAlarm } = await import('@/composables/useAlarm')
  let result!: ReturnType<typeof useAlarm>

  const Comp = defineComponent({
    setup() {
      result = useAlarm({
        autoFetch: false,
        autoSubscribe: false,
        playSound: false,
        showNotification: false,
        ...options
      })
      return {}
    },
    template: '<div />'
  })

  const wrapper = mount(Comp, { global: { plugins: [pinia] } })
  return { result, wrapper }
}

describe('useAlarm', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    localStorage.clear()
    // 重置 mock 调用记录但保留实现
    mockWsConnect.mockClear()
    mockWsDisconnect.mockClear()
    mockWsSubscribe.mockClear()
    mockWsOn.mockClear()
    mockWsOff.mockClear()
    // 重新设置 alarm API mock 返回值
    const alarmApi = await import('@/api/modules/alarm')
    vi.mocked(alarmApi.getActiveAlarms).mockResolvedValue([
      { id: 1, alarm_no: 'ALM-001', point_id: 1, point_code: 'T001', point_name: '温度1', threshold_id: 1, alarm_level: 'critical', alarm_type: 'threshold', alarm_message: '温度过高', trigger_value: 40, threshold_value: 35, status: 'active', acknowledged_by: null, acknowledged_at: null, ack_remark: null, resolved_by: null, resolved_at: null, resolve_remark: null, resolve_type: null, duration_seconds: null, is_notified: false, notify_count: 0, created_at: '2026-01-01' } as any,
      { id: 2, alarm_no: 'ALM-002', point_id: 2, point_code: 'T002', point_name: '温度2', threshold_id: 2, alarm_level: 'major', alarm_type: 'threshold', alarm_message: '温度偏高', trigger_value: 35, threshold_value: 30, status: 'active', acknowledged_by: null, acknowledged_at: null, ack_remark: null, resolved_by: null, resolved_at: null, resolve_remark: null, resolve_type: null, duration_seconds: null, is_notified: false, notify_count: 0, created_at: '2026-01-01' } as any
    ])
    vi.mocked(alarmApi.getAlarmCount).mockResolvedValue({ critical: 1, major: 1, minor: 0, info: 0, total: 2 })
    vi.mocked(alarmApi.acknowledgeAlarm).mockResolvedValue(undefined)
    vi.mocked(alarmApi.resolveAlarm).mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('初始状态 — 空告警列表', async () => {
    const { result } = await setupAlarm()
    expect(result.activeAlarms.value).toEqual([])
    expect(result.alarmCount.value.total).toBe(0)
    expect(result.loading.value).toBe(false)
    expect(result.error.value).toBeNull()
  })

  it('fetchActiveAlarms 加载活动告警', async () => {
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    expect(result.activeAlarms.value).toHaveLength(2)
    expect(result.loading.value).toBe(false)
    expect(result.error.value).toBeNull()
  })

  it('fetchAlarmCount 加载告警计数', async () => {
    const { result } = await setupAlarm()
    await result.fetchAlarmCount()
    expect(result.alarmCount.value.total).toBe(2)
    expect(result.alarmCount.value.critical).toBe(1)
    expect(result.alarmCount.value.major).toBe(1)
  })

  it('fetchActiveAlarms 错误处理', async () => {
    const { getActiveAlarms } = await import('@/api/modules/alarm')
    vi.mocked(getActiveAlarms).mockRejectedValueOnce(new Error('网络错误'))
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    expect(result.error.value).not.toBeNull()
    expect(result.loading.value).toBe(false)
  })

  it('ackAlarm 确认告警', async () => {
    const { acknowledgeAlarm } = await import('@/api/modules/alarm')
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    await result.ackAlarm(1, '已处理')
    expect(acknowledgeAlarm).toHaveBeenCalledWith(1, { remark: '已处理' })
  })

  it('resolveAlarm 解决告警', async () => {
    const { resolveAlarm } = await import('@/api/modules/alarm')
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    await result.resolveAlarm(1, '已修复')
    expect(resolveAlarm).toHaveBeenCalledWith(1, { remark: '已修复', resolve_type: 'manual' })
  })

  it('getAlarmsByLevel 按级别过滤告警', async () => {
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    expect(result.getAlarmsByLevel('critical')).toHaveLength(1)
    expect(result.getAlarmsByLevel('major')).toHaveLength(1)
    expect(result.getAlarmsByLevel('minor')).toHaveLength(0)
  })

  it('criticalAlarms 计算属性', async () => {
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    expect(result.criticalAlarms.value).toHaveLength(1)
    expect(result.criticalAlarms.value[0].alarm_level).toBe('critical')
  })

  it('hasActiveAlarms / hasCriticalAlarms 计算属性', async () => {
    const { result } = await setupAlarm()
    expect(result.hasActiveAlarms.value).toBe(false)
    await result.fetchActiveAlarms()
    expect(result.hasActiveAlarms.value).toBe(true)
    expect(result.hasCriticalAlarms.value).toBe(true)
  })

  it('batchAck 批量确认', async () => {
    const { acknowledgeAlarm } = await import('@/api/modules/alarm')
    vi.mocked(acknowledgeAlarm).mockClear()
    const { result } = await setupAlarm()
    await result.fetchActiveAlarms()
    await result.batchAck([1, 2], '批量处理')
    expect(acknowledgeAlarm).toHaveBeenCalledTimes(2)
  })

  it('组件卸载时断开连接', async () => {
    const { wrapper } = await setupAlarm()
    wrapper.unmount()
    expect(mockWsDisconnect).toHaveBeenCalled()
  })
})
