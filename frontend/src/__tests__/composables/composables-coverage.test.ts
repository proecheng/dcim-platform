/**
 * 组合式函数综合单元测试
 * 覆盖: usePermission, useEnergy, useSiteFilter, useSound
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick, defineComponent } from 'vue'
import { mount } from '@vue/test-utils'

// ==================== Mocks ====================

vi.mock('@/api/modules/auth', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
  getPermissions: vi.fn()
}))

vi.mock('@/api/modules/energy', () => ({
  getRealtimePower: vi.fn(),
  getPowerSummary: vi.fn(),
  getCurrentPUE: vi.fn(),
  getPUETrend: vi.fn(),
  getEnergySummary: vi.fn(),
  getEnergyTrend: vi.fn(),
  getEnergyComparison: vi.fn(),
  getSuggestions: vi.fn(),
  acceptSuggestion: vi.fn(),
  rejectSuggestion: vi.fn(),
  completeSuggestion: vi.fn(),
  getSavingPotential: vi.fn(),
  getDistributionDiagram: vi.fn()
}))

vi.mock('@/api/modules/spatial', () => ({
  getSites: vi.fn(),
  getSiteSummary: vi.fn()
}))

// ==================== Helper ====================

function withSetup<T>(composable: () => T): { result: T; wrapper: any } {
  let result!: T
  const Comp = defineComponent({
    setup() {
      result = composable()
      return {}
    },
    template: '<div />'
  })
  const wrapper = mount(Comp, { global: { plugins: [createPinia()] } })
  return { result, wrapper }
}

// ==================== usePermission ====================

describe('usePermission', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  // 延迟导入以确保 mock 生效
  async function setup(role: string, perms: string[]) {
    const { useUserStore } = await import('@/stores/user')
    const { usePermission } = await import('@/composables/usePermission')
    const userStore = useUserStore()
    userStore.permissions = perms
    userStore.userInfo = {
      id: 1,
      username: 'test',
      real_name: '测试用户',
      email: 'test@test.com',
      phone: '13800000000',
      role,
      department: '运维部',
      avatar: '',
      is_active: true,
      last_login_at: '2026-01-01',
      permissions: perms
    }
    const perm = usePermission()
    return { userStore, perm }
  }

  // --- hasPermission ---

  it('hasPermission — 有权限时返回 true', async () => {
    const { perm } = await setup('admin', ['user:read', 'alarm:read'])
    expect(perm.hasPermission('user:read')).toBe(true)
  })

  it('hasPermission — 无权限时返回 false', async () => {
    const { perm } = await setup('viewer', ['user:read'])
    expect(perm.hasPermission('user:write')).toBe(false)
  })

  it('hasPermission — 权限列表为空时返回 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.hasPermission('user:read')).toBe(false)
  })

  // --- hasAnyPermission ---

  it('hasAnyPermission — 匹配任一权限返回 true', async () => {
    const { perm } = await setup('operator', ['alarm:read'])
    expect(perm.hasAnyPermission(['user:write', 'alarm:read'])).toBe(true)
  })

  it('hasAnyPermission — 全部不匹配返回 false', async () => {
    const { perm } = await setup('viewer', ['log:read'])
    expect(perm.hasAnyPermission(['user:write', 'alarm:write'])).toBe(false)
  })

  // --- hasAllPermissions ---

  it('hasAllPermissions — 全部匹配返回 true', async () => {
    const { perm } = await setup('admin', ['user:read', 'user:write', 'alarm:read'])
    expect(perm.hasAllPermissions(['user:read', 'user:write'])).toBe(true)
  })

  it('hasAllPermissions — 部分缺失返回 false', async () => {
    const { perm } = await setup('operator', ['user:read'])
    expect(perm.hasAllPermissions(['user:read', 'user:write'])).toBe(false)
  })

  // --- hasRole ---

  it('hasRole — 角色匹配返回 true', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.hasRole('admin')).toBe(true)
  })

  it('hasRole — 角色不匹配返回 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.hasRole('admin')).toBe(false)
  })

  // --- isAdmin / isOperator / isViewer ---

  it('isAdmin — admin 角色为 true', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.isAdmin.value).toBe(true)
    expect(perm.isOperator.value).toBe(true)
    expect(perm.isViewer.value).toBe(true)
  })

  it('isOperator — operator 角色', async () => {
    const { perm } = await setup('operator', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(true)
    expect(perm.isViewer.value).toBe(true)
  })

  it('isViewer — viewer 角色', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(false)
    expect(perm.isViewer.value).toBe(true)
  })

  it('空角色 — 所有角色计算属性为 false', async () => {
    const { perm } = await setup('', [])
    expect(perm.isAdmin.value).toBe(false)
    expect(perm.isOperator.value).toBe(false)
    expect(perm.isViewer.value).toBe(false)
  })

  // --- permissions 常量 ---

  it('permissions 常量包含所有权限键', async () => {
    const { perm } = await setup('admin', [])
    expect(perm.permissions.USER_READ).toBe('user:read')
    expect(perm.permissions.USER_WRITE).toBe('user:write')
    expect(perm.permissions.USER_DELETE).toBe('user:delete')
    expect(perm.permissions.POINT_READ).toBe('point:read')
    expect(perm.permissions.ALARM_ACK).toBe('alarm:ack')
    expect(perm.permissions.CONFIG_WRITE).toBe('config:write')
    expect(perm.permissions.LOG_READ).toBe('log:read')
    expect(perm.permissions.REPORT_WRITE).toBe('report:write')
  })

  // --- canXxx 快捷权限 ---

  it('canReadUsers — 有 user:read 权限时为 true', async () => {
    const { perm } = await setup('admin', ['user:read', 'user:write', 'user:delete'])
    expect(perm.canReadUsers.value).toBe(true)
    expect(perm.canWriteUsers.value).toBe(true)
    expect(perm.canDeleteUsers.value).toBe(true)
  })

  it('canReadPoints / canWritePoints / canDeletePoints', async () => {
    const { perm } = await setup('operator', ['point:read', 'point:write', 'point:delete'])
    expect(perm.canReadPoints.value).toBe(true)
    expect(perm.canWritePoints.value).toBe(true)
    expect(perm.canDeletePoints.value).toBe(true)
  })

  it('canReadAlarms / canWriteAlarms / canAckAlarms', async () => {
    const { perm } = await setup('operator', ['alarm:read', 'alarm:write', 'alarm:ack'])
    expect(perm.canReadAlarms.value).toBe(true)
    expect(perm.canWriteAlarms.value).toBe(true)
    expect(perm.canAckAlarms.value).toBe(true)
  })

  it('canReadConfig / canWriteConfig', async () => {
    const { perm } = await setup('admin', ['config:read', 'config:write'])
    expect(perm.canReadConfig.value).toBe(true)
    expect(perm.canWriteConfig.value).toBe(true)
  })

  it('canReadLogs', async () => {
    const { perm } = await setup('admin', ['log:read'])
    expect(perm.canReadLogs.value).toBe(true)
  })

  it('canReadReports / canWriteReports', async () => {
    const { perm } = await setup('admin', ['report:read', 'report:write'])
    expect(perm.canReadReports.value).toBe(true)
    expect(perm.canWriteReports.value).toBe(true)
  })

  it('无权限时所有 canXxx 为 false', async () => {
    const { perm } = await setup('viewer', [])
    expect(perm.canReadUsers.value).toBe(false)
    expect(perm.canWriteUsers.value).toBe(false)
    expect(perm.canDeleteUsers.value).toBe(false)
    expect(perm.canReadPoints.value).toBe(false)
    expect(perm.canWritePoints.value).toBe(false)
    expect(perm.canDeletePoints.value).toBe(false)
    expect(perm.canReadAlarms.value).toBe(false)
    expect(perm.canWriteAlarms.value).toBe(false)
    expect(perm.canAckAlarms.value).toBe(false)
    expect(perm.canReadConfig.value).toBe(false)
    expect(perm.canWriteConfig.value).toBe(false)
    expect(perm.canReadLogs.value).toBe(false)
    expect(perm.canReadReports.value).toBe(false)
    expect(perm.canWriteReports.value).toBe(false)
  })
})

// ==================== useEnergy (格式化 + 轮询) ====================

describe('useEnergy', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  async function setup() {
    const { useEnergy } = await import('@/composables/useEnergy')
    return useEnergy()
  }

  // --- formatPower ---

  describe('formatPower', () => {
    it('null/undefined 返回 "-"', async () => {
      const e = await setup()
      expect(e.formatPower(null)).toBe('-')
      expect(e.formatPower(undefined)).toBe('-')
    })

    it('小于 1000 显示 kW', async () => {
      const e = await setup()
      expect(e.formatPower(500)).toBe('500.00 kW')
      expect(e.formatPower(0)).toBe('0.00 kW')
      expect(e.formatPower(999.99)).toBe('999.99 kW')
    })

    it('大于等于 1000 显示 MW', async () => {
      const e = await setup()
      expect(e.formatPower(1000)).toBe('1.00 MW')
      expect(e.formatPower(1500)).toBe('1.50 MW')
      expect(e.formatPower(2500)).toBe('2.50 MW')
    })
  })

  // --- formatEnergy ---

  describe('formatEnergy', () => {
    it('null/undefined 返回 "-"', async () => {
      const e = await setup()
      expect(e.formatEnergy(null)).toBe('-')
      expect(e.formatEnergy(undefined)).toBe('-')
    })

    it('小于 1000 显示 kWh', async () => {
      const e = await setup()
      expect(e.formatEnergy(500)).toBe('500.00 kWh')
      expect(e.formatEnergy(0)).toBe('0.00 kWh')
    })

    it('1000~999999 显示 MWh', async () => {
      const e = await setup()
      expect(e.formatEnergy(1500)).toBe('1.50 MWh')
      expect(e.formatEnergy(1000)).toBe('1.00 MWh')
    })

    it('大于等于 1000000 显示 GWh', async () => {
      const e = await setup()
      expect(e.formatEnergy(1500000)).toBe('1.50 GWh')
      expect(e.formatEnergy(1000000)).toBe('1.00 GWh')
    })
  })

  // --- formatCost ---

  describe('formatCost', () => {
    it('null/undefined 返回 "-"', async () => {
      const e = await setup()
      expect(e.formatCost(null)).toBe('-')
      expect(e.formatCost(undefined)).toBe('-')
    })

    it('小于 10000 显示 元', async () => {
      const e = await setup()
      expect(e.formatCost(5000)).toBe('5000.00 元')
      expect(e.formatCost(0)).toBe('0.00 元')
    })

    it('大于等于 10000 显示 万元', async () => {
      const e = await setup()
      expect(e.formatCost(15000)).toBe('1.50 万元')
      expect(e.formatCost(10000)).toBe('1.00 万元')
    })
  })

  // --- formatPUE ---

  describe('formatPUE', () => {
    it('null/undefined 返回 "-"', async () => {
      const e = await setup()
      expect(e.formatPUE(null)).toBe('-')
      expect(e.formatPUE(undefined)).toBe('-')
    })

    it('正常数值保留 3 位小数', async () => {
      const e = await setup()
      expect(e.formatPUE(1.456)).toBe('1.456')
      expect(e.formatPUE(1.2)).toBe('1.200')
      expect(e.formatPUE(2)).toBe('2.000')
    })
  })

  // --- getPUELevel ---

  describe('getPUELevel', () => {
    it('≤1.4 → 优秀/绿色', async () => {
      const e = await setup()
      expect(e.getPUELevel(1.2)).toEqual({ level: '优秀', color: '#67C23A' })
      expect(e.getPUELevel(1.4)).toEqual({ level: '优秀', color: '#67C23A' })
    })

    it('1.4~1.6 → 良好/蓝色', async () => {
      const e = await setup()
      expect(e.getPUELevel(1.5)).toEqual({ level: '良好', color: '#409EFF' })
      expect(e.getPUELevel(1.6)).toEqual({ level: '良好', color: '#409EFF' })
    })

    it('1.6~1.8 → 一般/橙色', async () => {
      const e = await setup()
      expect(e.getPUELevel(1.7)).toEqual({ level: '一般', color: '#E6A23C' })
      expect(e.getPUELevel(1.8)).toEqual({ level: '一般', color: '#E6A23C' })
    })

    it('>1.8 → 较差/红色', async () => {
      const e = await setup()
      expect(e.getPUELevel(1.9)).toEqual({ level: '较差', color: '#F56C6C' })
      expect(e.getPUELevel(3.0)).toEqual({ level: '较差', color: '#F56C6C' })
    })
  })

  // --- getLoadRateStatus ---

  describe('getLoadRateStatus', () => {
    it('<30 → 低负载', async () => {
      const e = await setup()
      expect(e.getLoadRateStatus(10)).toEqual({ status: '低负载', color: '#909399' })
      expect(e.getLoadRateStatus(29)).toEqual({ status: '低负载', color: '#909399' })
    })

    it('30~59 → 正常', async () => {
      const e = await setup()
      expect(e.getLoadRateStatus(30)).toEqual({ status: '正常', color: '#67C23A' })
      expect(e.getLoadRateStatus(59)).toEqual({ status: '正常', color: '#67C23A' })
    })

    it('60~79 → 较高', async () => {
      const e = await setup()
      expect(e.getLoadRateStatus(60)).toEqual({ status: '较高', color: '#E6A23C' })
      expect(e.getLoadRateStatus(79)).toEqual({ status: '较高', color: '#E6A23C' })
    })

    it('≥80 → 高负载', async () => {
      const e = await setup()
      expect(e.getLoadRateStatus(80)).toEqual({ status: '高负载', color: '#F56C6C' })
      expect(e.getLoadRateStatus(100)).toEqual({ status: '高负载', color: '#F56C6C' })
    })
  })

  // --- startPolling / stopPolling ---

  describe('轮询控制', () => {
    it('startPolling 创建定时器', async () => {
      const e = await setup()
      e.startPolling(10000)
      // 定时器已创建，推进时间不会报错
      vi.advanceTimersByTime(10000)
      e.stopPolling()
    })

    it('stopPolling 清除定时器', async () => {
      const e = await setup()
      e.startPolling(5000)
      e.stopPolling()
      // 推进时间后不应有额外调用
      vi.advanceTimersByTime(10000)
    })

    it('重复 startPolling 先清除旧定时器', async () => {
      const e = await setup()
      e.startPolling(5000)
      e.startPolling(3000) // 应先清除旧的
      e.stopPolling()
    })

    it('stopPolling 无定时器时不报错', async () => {
      const e = await setup()
      expect(() => e.stopPolling()).not.toThrow()
    })
  })
})

// ==================== useSiteFilter ====================

describe('useSiteFilter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  async function setup() {
    const { useSiteStore } = await import('@/stores/site')
    const { useSiteFilter } = await import('@/composables/useSiteFilter')
    const siteStore = useSiteStore()
    const filter = useSiteFilter()
    return { siteStore, filter }
  }

  it('getSiteParams — currentSiteId 为 null 时返回空对象', async () => {
    const { siteStore, filter } = await setup()
    siteStore.currentSiteId = null
    expect(filter.getSiteParams()).toEqual({})
  })

  it('getSiteParams — currentSiteId 有值时返回 { site_id }', async () => {
    const { siteStore, filter } = await setup()
    siteStore.currentSiteId = 42
    expect(filter.getSiteParams()).toEqual({ site_id: 42 })
  })

  it('onSiteChange — 站点切换时触发回调', async () => {
    const { useSiteStore } = await import('@/stores/site')
    const { useSiteFilter } = await import('@/composables/useSiteFilter')

    let callCount = 0
    let siteStoreRef: ReturnType<typeof useSiteStore>

    const Comp = defineComponent({
      setup() {
        siteStoreRef = useSiteStore()
        const filter = useSiteFilter()
        filter.onSiteChange(() => {
          callCount++
        })
        return {}
      },
      template: '<div />'
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    // 需要在 mount 前重新获取 store（mount 会用 pinia plugin）
    const wrapper = mount(Comp, { global: { plugins: [pinia] } })

    siteStoreRef!.currentSiteId = 5
    await nextTick()
    expect(callCount).toBe(1)

    wrapper.unmount()
  })
})

// ==================== useSound ====================

describe('useSound', () => {
  let mockPlay: ReturnType<typeof vi.fn>
  let mockPause: ReturnType<typeof vi.fn>

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()

    mockPlay = vi.fn().mockResolvedValue(undefined)
    mockPause = vi.fn()

    const MockAudio = vi.fn(function (this: any) {
      this.play = mockPlay
      this.pause = mockPause
      this.currentTime = 0
      this.volume = 1
      this.loop = false
      this.onplay = null
      this.onended = null
      this.onerror = null
    })
    vi.stubGlobal('Audio', MockAudio)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function setup() {
    const { useSound } = await import('@/composables/useSound')
    return withSetup(() => useSound())
  }

  // --- play ---

  it('play — 创建 Audio 并调用 play()', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    expect(Audio).toHaveBeenCalledWith('/sounds/test.mp3')
    expect(mockPlay).toHaveBeenCalled()
  })

  it('play — 设置 loop 选项', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3', { loop: true })
    expect(Audio).toHaveBeenCalled()
  })

  it('play — 设置 volume 选项', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3', { volume: 0.5 })
    expect(Audio).toHaveBeenCalled()
  })

  // --- stop ---

  it('stop — 暂停并重置', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.stop()
    expect(mockPause).toHaveBeenCalled()
  })

  it('stop — 无音频时不报错', async () => {
    const { result } = await setup()
    expect(() => result.stop()).not.toThrow()
  })

  // --- pause / resume ---

  it('pause — 暂停当前音频', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.pause()
    expect(mockPause).toHaveBeenCalled()
  })

  it('pause — 无音频时不报错', async () => {
    const { result } = await setup()
    expect(() => result.pause()).not.toThrow()
  })

  it('resume — 继续播放', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.pause()
    result.resume()
    // play 被调用两次：初始 play + resume
    expect(mockPlay).toHaveBeenCalledTimes(2)
  })

  it('resume — 无音频时不报错', async () => {
    const { result } = await setup()
    expect(() => result.resume()).not.toThrow()
  })

  // --- setVolume ---

  it('setVolume — 正常范围', async () => {
    const { result } = await setup()
    result.setVolume(0.5)
    expect(result.volume.value).toBe(0.5)
  })

  it('setVolume — 超出范围被钳制', async () => {
    const { result } = await setup()
    result.setVolume(1.5)
    expect(result.volume.value).toBe(1)
    result.setVolume(-0.5)
    expect(result.volume.value).toBe(0)
  })

  it('setVolume — 有音频时同步更新', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.setVolume(0.3)
    expect(result.volume.value).toBe(0.3)
  })

  // --- toggleMute / setMuted ---

  it('toggleMute — 切换静音状态', async () => {
    const { result } = await setup()
    expect(result.isMuted.value).toBe(false)
    result.toggleMute()
    expect(result.isMuted.value).toBe(true)
    result.toggleMute()
    expect(result.isMuted.value).toBe(false)
  })

  it('toggleMute — 有音频时同步更新', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.toggleMute()
    expect(result.isMuted.value).toBe(true)
  })

  it('setMuted — 设置静音', async () => {
    const { result } = await setup()
    result.setMuted(true)
    expect(result.isMuted.value).toBe(true)
    result.setMuted(false)
    expect(result.isMuted.value).toBe(false)
  })

  it('setMuted — 有音频时同步更新', async () => {
    const { result } = await setup()
    result.play('/sounds/test.mp3')
    result.setMuted(true)
    expect(result.isMuted.value).toBe(true)
  })

  // --- playAlarm ---

  it('playAlarm — critical 播放对应文件并循环', async () => {
    const { result } = await setup()
    result.playAlarm('critical')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_critical.mp3')
  })

  it('playAlarm — major 播放对应文件', async () => {
    const { result } = await setup()
    result.playAlarm('major')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_major.mp3')
  })

  it('playAlarm — minor 播放对应文件', async () => {
    const { result } = await setup()
    result.playAlarm('minor')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_minor.mp3')
  })

  it('playAlarm — info 播放对应文件', async () => {
    const { result } = await setup()
    result.playAlarm('info')
    expect(Audio).toHaveBeenCalledWith('/sounds/alarm_info.mp3')
  })

  // --- playNotification ---

  it('playNotification — 播放通知音', async () => {
    const { result } = await setup()
    result.playNotification()
    expect(Audio).toHaveBeenCalledWith('/sounds/notification.mp3')
  })

  // --- computed 属性初始值 ---

  it('初始状态 — isPlaying=false, isMuted=false, volume=1', async () => {
    const { result } = await setup()
    expect(result.isPlaying.value).toBe(false)
    expect(result.isMuted.value).toBe(false)
    expect(result.volume.value).toBe(1)
  })
})
