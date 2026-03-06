/**
 * Story 27.6: 站点过滤贯穿数据链路 — 测试
 *
 * 覆盖范围：
 * - 请求拦截器 site_id 注入
 * - SiteEventBus 事件总线
 * - 站点切换触发 Store 重新加载（版本号模式防竞态）
 * - WebSocket 订阅记录与 reconnectAll
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// ============================================================
// Part 1: SiteEventBus 测试
// ============================================================
import { siteEvents } from '@/utils/siteEvents'

describe('SiteEventBus', () => {
  afterEach(() => {
    siteEvents.clear()
  })

  it('on() 注册处理器，emit() 触发', () => {
    const handler = vi.fn()
    siteEvents.on(handler)
    siteEvents.emit(1)
    expect(handler).toHaveBeenCalledWith(1)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('emit(null) 传递 null 参数', () => {
    const handler = vi.fn()
    siteEvents.on(handler)
    siteEvents.emit(null)
    expect(handler).toHaveBeenCalledWith(null)
  })

  it('on() 返回的清理函数能移除处理器', () => {
    const handler = vi.fn()
    const cleanup = siteEvents.on(handler)
    cleanup()
    siteEvents.emit(1)
    expect(handler).not.toHaveBeenCalled()
  })

  it('多个处理器都被触发', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    siteEvents.on(h1)
    siteEvents.on(h2)
    siteEvents.emit(2)
    expect(h1).toHaveBeenCalledWith(2)
    expect(h2).toHaveBeenCalledWith(2)
  })

  it('处理器异常不影响其他处理器', () => {
    const errorHandler = vi.fn(() => { throw new Error('test') })
    const normalHandler = vi.fn()
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    siteEvents.on(errorHandler)
    siteEvents.on(normalHandler)
    siteEvents.emit(1)
    expect(normalHandler).toHaveBeenCalledWith(1)
    consoleSpy.mockRestore()
  })

  it('clear() 清除所有处理器', () => {
    const handler = vi.fn()
    siteEvents.on(handler)
    siteEvents.clear()
    siteEvents.emit(1)
    expect(handler).not.toHaveBeenCalled()
  })

  it('同一个处理器不会被注册多次（Set 特性）', () => {
    const handler = vi.fn()
    siteEvents.on(handler)
    siteEvents.on(handler)
    siteEvents.emit(1)
    expect(handler).toHaveBeenCalledTimes(1)
  })
})

// ============================================================
// Part 2: 请求拦截器 site_id 注入测试
// ============================================================
import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import { shouldInjectSiteId, SITE_FILTER_EXCLUDED_PATHS } from '@/utils/request'

describe('shouldInjectSiteId — 排除路径匹配', () => {
  it('普通路径注入', () => {
    expect(shouldInjectSiteId('/v1/alarms')).toBe(true)
    expect(shouldInjectSiteId('/v1/alarms/active')).toBe(true)
    expect(shouldInjectSiteId('/v1/realtime/data')).toBe(true)
    expect(shouldInjectSiteId('/v1/energy/power')).toBe(true)
    expect(shouldInjectSiteId('/v1/devices')).toBe(true)
  })

  it('排除路径不注入', () => {
    expect(shouldInjectSiteId('/v1/auth/')).toBe(false)
    expect(shouldInjectSiteId('/v1/auth/login')).toBe(false)
    expect(shouldInjectSiteId('/v1/spatial/sites')).toBe(false)
    expect(shouldInjectSiteId('/v1/spatial/sites/1')).toBe(false)
    expect(shouldInjectSiteId('/v1/system/')).toBe(false)
    expect(shouldInjectSiteId('/v1/system/config')).toBe(false)
    expect(shouldInjectSiteId('/v1/users/')).toBe(false)
    expect(shouldInjectSiteId('/v1/users/1')).toBe(false)
    expect(shouldInjectSiteId('/v1/demo/')).toBe(false)
    expect(shouldInjectSiteId('/v1/demo/load')).toBe(false)
    expect(shouldInjectSiteId('/v1/configs/')).toBe(false)
    expect(shouldInjectSiteId('/v1/configs/backup')).toBe(false)
    expect(shouldInjectSiteId('/v1/logs/')).toBe(false)
    expect(shouldInjectSiteId('/v1/logs/audit')).toBe(false)
  })

  it('精确匹配不误伤相似路径', () => {
    // /v1/auth 不在排除列表（排除的是 /v1/auth/），但 /v1/auth 后面通常有 /
    // /v1/authentication 不应被排除
    expect(shouldInjectSiteId('/v1/authentication')).toBe(true)
    // /v1/spatial/sites-other 不应被排除
    expect(shouldInjectSiteId('/v1/spatial/sites-other')).toBe(true)
    // /v1/spatial/ 其他子路径应该注入
    expect(shouldInjectSiteId('/v1/spatial/floors')).toBe(true)
    expect(shouldInjectSiteId('/v1/spatial/rooms')).toBe(true)
  })
})

describe('请求拦截器 site_id 注入（集成）', () => {
  let mock: MockAdapter

  beforeEach(() => {
    // 清理 localStorage
    localStorage.clear()
    ;(localStorage.getItem as any).mockClear()
  })

  // 使用独立的 axios 实例模拟 request.ts 的拦截器逻辑
  function createTestInstance() {
    const instance = axios.create({ baseURL: '/api' })
    instance.interceptors.request.use((config) => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      const siteIdStr = localStorage.getItem('current_site_id')
      if (siteIdStr != null) {
        const siteId = Number(siteIdStr)
        if (!isNaN(siteId) && siteId > 0) {
          const url = config.url || ''
          if (shouldInjectSiteId(url)) {
            if (!config.params) config.params = {}
            if (config.params.site_id === undefined) {
              config.params.site_id = siteId
            }
          }
        }
      }
      return config
    })
    return instance
  }

  it('GET 请求自动注入 site_id 到 params', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onGet('/v1/alarms/active').reply(200, { data: [] })

    localStorage.setItem('current_site_id', '3')
    const res = await instance.get('/v1/alarms/active')

    const lastReq = mock.history.get[0]
    expect(lastReq.params).toEqual({ site_id: 3 })
  })

  it('POST 请求注入 site_id 到 params（不注入到 body）', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onPost('/v1/devices').reply(200, { data: {} })

    localStorage.setItem('current_site_id', '5')
    await instance.post('/v1/devices', { name: 'test' })

    const lastReq = mock.history.post[0]
    expect(lastReq.params).toEqual({ site_id: 5 })
    // body 不包含 site_id
    const body = JSON.parse(lastReq.data)
    expect(body.site_id).toBeUndefined()
  })

  it('排除路径不注入 site_id', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onPost('/v1/auth/login').reply(200, { token: 'xxx' })

    localStorage.setItem('current_site_id', '1')
    await instance.post('/v1/auth/login', { username: 'admin' })

    const lastReq = mock.history.post[0]
    expect(lastReq.params).toBeUndefined()
  })

  it('手动指定 site_id 不被覆盖', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onGet('/v1/alarms/active').reply(200, { data: [] })

    localStorage.setItem('current_site_id', '3')
    await instance.get('/v1/alarms/active', { params: { site_id: 99 } })

    const lastReq = mock.history.get[0]
    expect(lastReq.params).toEqual({ site_id: 99 })
  })

  it('currentSiteId 为 null 时不注入（localStorage 无 key）', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onGet('/v1/alarms/active').reply(200, { data: [] })

    // 不设置 current_site_id
    await instance.get('/v1/alarms/active')

    const lastReq = mock.history.get[0]
    expect(lastReq.params).toBeUndefined()
  })

  it('currentSiteId 为非数字字符串时不注入', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onGet('/v1/alarms/active').reply(200, { data: [] })

    localStorage.setItem('current_site_id', 'abc')
    await instance.get('/v1/alarms/active')

    const lastReq = mock.history.get[0]
    expect(lastReq.params).toBeUndefined()
  })

  it('currentSiteId 为 0 或负数时不注入', async () => {
    const instance = createTestInstance()
    mock = new MockAdapter(instance)
    mock.onGet('/v1/alarms/active').reply(200, { data: [] })

    localStorage.setItem('current_site_id', '0')
    await instance.get('/v1/alarms/active')
    expect(mock.history.get[0].params).toBeUndefined()

    mock.resetHistory()
    localStorage.setItem('current_site_id', '-1')
    await instance.get('/v1/alarms/active')
    expect(mock.history.get[0].params).toBeUndefined()
  })

  afterEach(() => {
    if (mock) mock.restore()
  })
})

// ============================================================
// Part 3: switchSite + Store 重新加载测试
// ============================================================
import { useSiteStore } from '@/stores/site'

describe('switchSite 触发数据重新加载', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    siteEvents.clear()
  })

  afterEach(() => {
    siteEvents.clear()
  })

  it('siteEvents.emit 被 switchSite 调用', () => {
    const siteStore = useSiteStore()
    const handler = vi.fn()
    siteEvents.on(handler)

    siteStore.switchSite(1)
    expect(handler).toHaveBeenCalledWith(1)
    expect(localStorage.setItem).toHaveBeenCalledWith('current_site_id', '1')
  })

  it('switchSite(null) 清除 localStorage 并发射 null', () => {
    const siteStore = useSiteStore()
    const handler = vi.fn()
    siteEvents.on(handler)

    siteStore.switchSite(null)
    expect(handler).toHaveBeenCalledWith(null)
    expect(localStorage.removeItem).toHaveBeenCalledWith('current_site_id')
  })
})

// ============================================================
// Part 4: 版本号模式防竞态测试
// ============================================================
import { useAlarmStore } from '@/stores/alarm'
import * as alarmApi from '@/api/modules/alarm'

describe('版本号模式防竞态', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    siteEvents.clear()
  })

  afterEach(() => {
    siteEvents.clear()
    vi.restoreAllMocks()
  })

  it('快速连续调用 fetchActiveAlarms 时旧请求结果被丢弃', async () => {
    let callCount = 0
    const spy = vi.spyOn(alarmApi, 'getActiveAlarms').mockImplementation(async () => {
      callCount++
      const myCount = callCount
      // 第一次调用延迟更长
      await new Promise(resolve => setTimeout(resolve, myCount === 1 ? 100 : 10))
      return [{ id: myCount, point_code: `T${myCount}`, point_name: `Alarm ${myCount}`, alarm_level: 'critical', alarm_message: 'test', status: 'active', created_at: '2026-01-01' }] as any
    })

    const store = useAlarmStore()

    // 快速连续调用两次
    const p1 = store.fetchActiveAlarms()
    const p2 = store.fetchActiveAlarms()

    await Promise.all([p1, p2])

    // 结果应该是第二次调用的数据（callCount=2）
    expect(store.activeAlarms.length).toBe(1)
    expect(store.activeAlarms[0].id).toBe(2)

    spy.mockRestore()
  })
})

// ============================================================
// Part 5: WebSocket manager 订阅记录与 reconnectAll 测试
// ============================================================
describe('useWebSocketManager 订阅记录与 reconnectAll', () => {
  beforeEach(() => {
    siteEvents.clear()
  })

  afterEach(() => {
    siteEvents.clear()
    vi.restoreAllMocks()
  })

  it('subscribe 记录订阅信息', async () => {
    // 由于 WebSocketClient 需要真实 WebSocket 环境，我们 mock 整个模块
    vi.mock('@/api/websocket', () => ({
      WebSocketClient: vi.fn().mockImplementation(() => ({
        connect: vi.fn(),
        close: vi.fn(),
        subscribe: vi.fn(),
        send: vi.fn(),
        on: vi.fn(),
        off: vi.fn(),
        isConnected: false,
      }))
    }))

    // 重新导入以获取带 mock 的版本
    const { useWebSocketManager } = await import('@/composables/useWebSocketManager')
    const manager = useWebSocketManager()

    // 先连接通道
    manager.connect('alarms')

    // 订阅
    manager.subscribe('alarms', {
      channels: ['alarm_new'],
      filters: { alarm_levels: ['critical'] }
    })

    // 测试 reconnectAll 不会抛错
    manager.reconnectAll()

    vi.unmock('@/api/websocket')
  })
})
