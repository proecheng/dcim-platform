/**
 * useWebSocket 组合式函数单元测试
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'

// Mock WebSocketClient
const mockConnect = vi.fn()
const mockClose = vi.fn()
const mockSend = vi.fn()
const mockSubscribe = vi.fn()
const mockUnsubscribe = vi.fn()
const mockOn = vi.fn()
const mockOff = vi.fn()

vi.mock('@/api/websocket', () => {
  class MockWebSocketClient {
    private _options: any
    connect: any
    close: any
    send: any
    subscribe: any
    unsubscribe: any
    on: any
    off: any

    constructor(options: any) {
      this._options = options
      this.connect = mockConnect.mockImplementation(() => {
        options.onOpen?.()
      })
      this.close = mockClose.mockImplementation(() => {
        options.onClose?.()
      })
      this.send = mockSend
      this.subscribe = mockSubscribe
      this.unsubscribe = mockUnsubscribe
      this.on = mockOn
      this.off = mockOff
    }

    get isConnected() { return false }
  }
  return { WebSocketClient: MockWebSocketClient }
})

function withSetup<T>(composable: () => T, autoConnect = false): { result: T; wrapper: any } {
  let result!: T
  const Comp = defineComponent({
    setup() {
      result = composable()
      return {}
    },
    template: '<div />'
  })
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(Comp, { global: { plugins: [pinia] } })
  return { result, wrapper }
}

describe('useWebSocket', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  async function setup(opts: Record<string, unknown> = {}) {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    return withSetup(() => useWebSocket({ url: '/ws/test', autoConnect: false, ...opts }))
  }

  it('初始状态 — 未连接', async () => {
    const { result } = await setup()
    expect(result.isConnected.value).toBe(false)
    expect(result.lastMessage.value).toBeNull()
    expect(result.error.value).toBeNull()
  })

  it('connect 调用 WebSocketClient.connect', async () => {
    const { result } = await setup()
    result.connect()
    expect(mockConnect).toHaveBeenCalled()
  })

  it('disconnect 调用 WebSocketClient.close', async () => {
    const { result } = await setup()
    result.disconnect()
    expect(mockClose).toHaveBeenCalled()
  })

  it('send 调用 WebSocketClient.send', async () => {
    const { result } = await setup()
    result.send({ type: 'test', data: 'hello' })
    expect(mockSend).toHaveBeenCalledWith({ type: 'test', data: 'hello' })
  })

  it('subscribe 调用 WebSocketClient.subscribe', async () => {
    const { result } = await setup()
    result.subscribe({ channels: ['alarms'] })
    expect(mockSubscribe).toHaveBeenCalledWith({ channels: ['alarms'] })
  })

  it('unsubscribe 调用 WebSocketClient.unsubscribe', async () => {
    const { result } = await setup()
    result.unsubscribe(['alarms'])
    expect(mockUnsubscribe).toHaveBeenCalledWith(['alarms'])
  })

  it('on 注册消息处理器', async () => {
    const { result } = await setup()
    const handler = vi.fn()
    result.on('test', handler)
    expect(mockOn).toHaveBeenCalledWith('test', expect.any(Function))
  })

  it('off 移除消息处理器', async () => {
    const { result } = await setup()
    const handler = vi.fn()
    result.off('test', handler)
    expect(mockOff).toHaveBeenCalledWith('test', handler)
  })

  it('autoConnect=true 时自动连接', async () => {
    const { useWebSocket } = await import('@/composables/useWebSocket')
    withSetup(() => useWebSocket({ url: '/ws/test', autoConnect: true }))
    expect(mockConnect).toHaveBeenCalled()
  })

  it('组件卸载时自动断开连接', async () => {
    const { wrapper } = await setup()
    wrapper.unmount()
    expect(mockClose).toHaveBeenCalled()
  })

  it('client 属性暴露 WebSocketClient 实例', async () => {
    const { result } = await setup()
    expect(result.client).toBeDefined()
    expect(result.client.connect).toBeDefined()
    expect(result.client.close).toBeDefined()
  })
})
