import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { WebSocketClient } from '@/api/websocket'
import { degradationFlags } from '@/stores/degradation'


class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  static instances: MockWebSocket[] = []

  readonly url: string
  readyState = MockWebSocket.CONNECTING
  sent: string[] = []
  onopen: ((event: Event) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
  }

  serverClose(code = 1000) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code } as CloseEvent)
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  receive(message: object) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(message) }))
  }
}


describe('WebSocket first-frame authentication', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    localStorage.setItem('token', 'secret-access-token')
    degradationFlags.websocketDown = false
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('keeps the access token out of the URL and authenticates first', () => {
    const onOpen = vi.fn()
    const client = new WebSocketClient({ url: '/ws/realtime', onOpen })

    client.connect()
    const socket = MockWebSocket.instances[0]
    socket.open()

    expect(socket.url).not.toContain('token=')
    expect(JSON.parse(socket.sent[0])).toEqual({ action: 'authenticate', token: 'secret-access-token' })
    expect(onOpen).not.toHaveBeenCalled()
    expect(client.isConnected).toBe(false)
  })

  it('does not create duplicate sockets while a connection is pending', () => {
    const client = new WebSocketClient({ url: '/ws/realtime' })

    client.connect()
    client.connect()

    expect(MockWebSocket.instances).toHaveLength(1)
    client.close()
  })

  it('restores queued subscriptions only after authentication succeeds', () => {
    const onOpen = vi.fn()
    const client = new WebSocketClient({ url: '/ws/alarms', onOpen })
    client.connect()
    client.subscribe({ filters: { alarm_levels: ['critical'] } })
    const socket = MockWebSocket.instances[0]

    socket.open()
    expect(socket.sent).toHaveLength(1)

    socket.receive({ type: 'authenticated' })

    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(client.isConnected).toBe(true)
    expect(JSON.parse(socket.sent[1])).toEqual({
      action: 'subscribe',
      filters: { alarm_levels: ['critical'] },
    })
  })

  it('does not enter the connected state when authentication fails', () => {
    vi.useFakeTimers()
    const onOpen = vi.fn()
    const onClose = vi.fn()
    const client = new WebSocketClient({ url: '/ws/system', onOpen, onClose })

    client.connect()
    const socket = MockWebSocket.instances[0]
    socket.open()
    socket.receive({ type: 'authentication_failed' })
    socket.serverClose(4001)

    expect(onOpen).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(client.isConnected).toBe(false)
    expect(degradationFlags.websocketDown).toBe(false)

    client.close()
  })

  it('reauthenticates with a fresh token and restores subscriptions only after success', () => {
    vi.useFakeTimers()
    const onOpen = vi.fn()
    const client = new WebSocketClient({ url: '/ws/alarms', onOpen })
    client.subscribe({ filters: { alarm_levels: ['critical'] } })
    client.connect()

    const firstSocket = MockWebSocket.instances[0]
    firstSocket.open()
    firstSocket.receive({ type: 'authenticated' })
    expect(JSON.parse(firstSocket.sent[1])).toEqual({
      action: 'subscribe',
      filters: { alarm_levels: ['critical'] },
    })

    localStorage.setItem('token', 'refreshed-access-token')
    firstSocket.serverClose(4001)
    expect(degradationFlags.websocketDown).toBe(true)
    vi.advanceTimersByTime(1000)

    const secondSocket = MockWebSocket.instances[1]
    secondSocket.open()
    expect(JSON.parse(secondSocket.sent[0])).toEqual({
      action: 'authenticate',
      token: 'refreshed-access-token',
    })
    expect(secondSocket.sent).toHaveLength(1)
    expect(onOpen).toHaveBeenCalledTimes(1)

    secondSocket.receive({ type: 'authenticated' })
    expect(JSON.parse(secondSocket.sent[1])).toEqual({
      action: 'subscribe',
      filters: { alarm_levels: ['critical'] },
    })
    expect(onOpen).toHaveBeenCalledTimes(2)
    expect(degradationFlags.websocketDown).toBe(false)

    client.close()
  })

  it('stops after ten reconnect attempts and keeps the degradation flag active', () => {
    vi.useFakeTimers()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const client = new WebSocketClient({ url: '/ws/realtime', maxReconnectAttempts: 10 })
    client.connect()

    const firstSocket = MockWebSocket.instances[0]
    firstSocket.open()
    firstSocket.receive({ type: 'authenticated' })
    firstSocket.serverClose(1006)

    const reconnectDelays = [1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000, 30000, 30000]
    reconnectDelays.forEach((delay, index) => {
      vi.advanceTimersByTime(delay)
      const socket = MockWebSocket.instances[index + 1]
      socket.open()
      socket.serverClose(4001)
    })

    vi.advanceTimersByTime(30000)
    expect(MockWebSocket.instances).toHaveLength(11)
    expect(consoleError).toHaveBeenCalledWith('WebSocket 重连次数已达上限')
    expect(degradationFlags.websocketDown).toBe(true)

    client.close()
  })
})

describe('WebSocket manager site-scoped subscriptions', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    localStorage.setItem('token', 'secret-access-token')
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('narrows a selected site and omits site_ids again for all authorized sites', async () => {
    vi.resetModules()
    const { siteEvents } = await import('@/utils/siteEvents')
    siteEvents.clear()
    const { useWebSocketManager } = await import('@/composables/useWebSocketManager')
    const manager = useWebSocketManager()

    manager.connect('alarms')
    manager.subscribe('alarms', {
      channels: ['alarms'],
      filters: { alarm_levels: ['critical'] },
    })

    const initialSocket = MockWebSocket.instances[0]
    initialSocket.open()
    initialSocket.receive({ type: 'authenticated' })
    expect(JSON.parse(initialSocket.sent[1])).toEqual({
      action: 'subscribe',
      channels: ['alarms'],
      filters: { alarm_levels: ['critical'] },
    })

    siteEvents.emit(7)
    const selectedSiteSocket = MockWebSocket.instances[1]
    selectedSiteSocket.open()
    expect(selectedSiteSocket.sent).toHaveLength(1)
    selectedSiteSocket.receive({ type: 'authenticated' })
    expect(JSON.parse(selectedSiteSocket.sent[1])).toEqual({
      action: 'subscribe',
      channels: ['alarms'],
      filters: { alarm_levels: ['critical'], site_ids: [7] },
    })

    siteEvents.emit(null)
    const allSitesSocket = MockWebSocket.instances[2]
    allSitesSocket.open()
    expect(allSitesSocket.sent).toHaveLength(1)
    allSitesSocket.receive({ type: 'authenticated' })
    expect(JSON.parse(allSitesSocket.sent[1])).toEqual({
      action: 'subscribe',
      channels: ['alarms'],
      filters: { alarm_levels: ['critical'] },
    })

    manager.disconnect('alarms')
    siteEvents.clear()
  })

  it('connects when handlers subscribe before an explicit connect and restores them after reconnect', async () => {
    vi.resetModules()
    const { siteEvents } = await import('@/utils/siteEvents')
    siteEvents.clear()
    const { useWebSocketManager } = await import('@/composables/useWebSocketManager')
    const manager = useWebSocketManager()
    const handler = vi.fn()

    manager.on('realtime', 'realtime', handler)
    manager.subscribe('realtime', { channels: ['realtime'] })

    expect(MockWebSocket.instances).toHaveLength(1)
    const initialSocket = MockWebSocket.instances[0]
    initialSocket.open()
    initialSocket.receive({ type: 'authenticated' })
    initialSocket.receive({ type: 'realtime', data: { point_id: 1 } })
    expect(handler).toHaveBeenCalledTimes(1)

    siteEvents.emit(7)
    const reconnectedSocket = MockWebSocket.instances[1]
    reconnectedSocket.open()
    reconnectedSocket.receive({ type: 'authenticated' })
    reconnectedSocket.receive({ type: 'realtime', data: { point_id: 2 } })
    expect(handler).toHaveBeenCalledTimes(2)

    manager.disconnect('realtime')
    siteEvents.clear()
  })

  it('retries an existing disconnected channel when connect is called again', async () => {
    vi.useFakeTimers()
    vi.resetModules()
    const { siteEvents } = await import('@/utils/siteEvents')
    siteEvents.clear()
    const { useWebSocketManager } = await import('@/composables/useWebSocketManager')
    const manager = useWebSocketManager()

    manager.connect('system')
    const firstSocket = MockWebSocket.instances[0]
    firstSocket.open()
    firstSocket.receive({ type: 'authenticated' })
    firstSocket.serverClose(1006)

    manager.connect('system')

    expect(MockWebSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1000)
    expect(MockWebSocket.instances).toHaveLength(2)

    manager.disconnect('system')
    siteEvents.clear()
  })
})
