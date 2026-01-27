/**
 * WebSocket 封装
 * 支持自动重连、心跳检测、订阅机制
 */

type MessageHandler = (data: any) => void
type ConnectionHandler = () => void

interface WebSocketOptions {
  url: string
  heartbeatInterval?: number
  reconnectInterval?: number
  maxReconnectAttempts?: number
  onOpen?: ConnectionHandler
  onClose?: ConnectionHandler
  onError?: (error: Event) => void
}

interface SubscribeOptions {
  channels?: string[]
  filters?: {
    point_ids?: number[]
    area_codes?: string[]
    alarm_levels?: string[]
  }
}

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private heartbeatInterval: number
  private reconnectInterval: number
  private maxReconnectAttempts: number
  private reconnectAttempts: number = 0
  private heartbeatTimer: number | null = null
  private reconnectTimer: number | null = null
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map()
  private isManualClose: boolean = false
  private onOpenCallback?: ConnectionHandler
  private onCloseCallback?: ConnectionHandler
  private onErrorCallback?: (error: Event) => void

  constructor(options: WebSocketOptions) {
    this.url = options.url
    this.heartbeatInterval = options.heartbeatInterval || 30000
    this.reconnectInterval = options.reconnectInterval || 3000
    this.maxReconnectAttempts = options.maxReconnectAttempts || 10
    this.onOpenCallback = options.onOpen
    this.onCloseCallback = options.onClose
    this.onErrorCallback = options.onError
  }

  /**
   * 连接 WebSocket
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    this.isManualClose = false
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}${this.url}`

    try {
      this.ws = new WebSocket(wsUrl)
      this.setupEventListeners()
    } catch (error) {
      console.error('WebSocket 连接失败:', error)
      this.scheduleReconnect()
    }
  }

  /**
   * 设置事件监听器
   */
  private setupEventListeners(): void {
    if (!this.ws) return

    this.ws.onopen = () => {
      console.log('WebSocket 已连接:', this.url)
      this.reconnectAttempts = 0
      this.startHeartbeat()
      this.onOpenCallback?.()
    }

    this.ws.onclose = () => {
      console.log('WebSocket 已关闭:', this.url)
      this.stopHeartbeat()
      this.onCloseCallback?.()

      if (!this.isManualClose) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      this.onErrorCallback?.(error)
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (error) {
        console.error('消息解析失败:', error)
      }
    }
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(message: any): void {
    const { type } = message

    // 心跳响应
    if (type === 'pong') {
      return
    }

    // 触发对应类型的处理器
    const handlers = this.messageHandlers.get(type)
    if (handlers) {
      handlers.forEach(handler => handler(message))
    }

    // 触发通用处理器
    const allHandlers = this.messageHandlers.get('*')
    if (allHandlers) {
      allHandlers.forEach(handler => handler(message))
    }
  }

  /**
   * 开始心跳检测
   */
  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ type: 'ping' })
    }, this.heartbeatInterval)
  }

  /**
   * 停止心跳检测
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * 安排重连
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('WebSocket 重连次数已达上限')
      return
    }

    this.reconnectAttempts++
    console.log(`WebSocket 将在 ${this.reconnectInterval}ms 后重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    this.reconnectTimer = window.setTimeout(() => {
      this.connect()
    }, this.reconnectInterval)
  }

  /**
   * 发送消息
   */
  send(data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket 未连接，消息未发送:', data)
    }
  }

  /**
   * 订阅消息
   */
  subscribe(options: SubscribeOptions): void {
    this.send({
      action: 'subscribe',
      ...options
    })
  }

  /**
   * 取消订阅
   */
  unsubscribe(channels?: string[]): void {
    this.send({
      action: 'unsubscribe',
      channels
    })
  }

  /**
   * 注册消息处理器
   * @param type 消息类型，使用 '*' 监听所有消息
   * @param handler 处理函数
   */
  on(type: string, handler: MessageHandler): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set())
    }
    this.messageHandlers.get(type)!.add(handler)
  }

  /**
   * 移除消息处理器
   */
  off(type: string, handler?: MessageHandler): void {
    if (handler) {
      this.messageHandlers.get(type)?.delete(handler)
    } else {
      this.messageHandlers.delete(type)
    }
  }

  /**
   * 关闭连接
   */
  close(): void {
    this.isManualClose = true
    this.stopHeartbeat()

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * 获取连接状态
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  /**
   * 获取 WebSocket 实例
   */
  get instance(): WebSocket | null {
    return this.ws
  }
}

// 创建默认实例
export const realtimeWs = new WebSocketClient({
  url: '/ws/realtime',
  heartbeatInterval: 30000,
  reconnectInterval: 3000,
  maxReconnectAttempts: 10
})

export const alarmWs = new WebSocketClient({
  url: '/ws/alarms',
  heartbeatInterval: 30000,
  reconnectInterval: 3000,
  maxReconnectAttempts: 10
})

export const systemWs = new WebSocketClient({
  url: '/ws/system',
  heartbeatInterval: 30000,
  reconnectInterval: 3000,
  maxReconnectAttempts: 10
})

export default WebSocketClient
