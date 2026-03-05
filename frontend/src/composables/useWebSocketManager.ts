/**
 * WebSocket 连接管理器（单例）
 *
 * 职责：
 * - 每个通道（alarms/realtime/system/linkage）最多维持 1 个 WebSocketClient 实例
 * - 复用 WebSocketClient 的重连、心跳、消息分发功能
 * - 提供统一的 API 供 composables 使用
 */
import { WebSocketClient } from '@/api/websocket'

// WebSocket 通道类型
export type WebSocketChannel = 'alarms' | 'realtime' | 'system' | 'linkage'

// 连接池：每个通道一个 WebSocketClient 实例
const clients = new Map<WebSocketChannel, WebSocketClient>()

// 辅助函数：获取客户端或警告
function getClientOrWarn(channel: WebSocketChannel): WebSocketClient | null {
  const client = clients.get(channel)
  if (!client) {
    console.warn(`WebSocket channel "${channel}" not connected. Call connect() first.`)
  }
  return client || null
}

// 单例管理器
const manager = {
  /**
   * 连接指定通道（如果已连接则复用）
   */
  connect(channel: WebSocketChannel): void {
    const existing = clients.get(channel)
    if (existing?.isConnected) {
      return
    }

    const client = new WebSocketClient({
      url: `/ws/${channel}`,
      heartbeatInterval: 30000,
      reconnectInterval: 3000,
      maxReconnectAttempts: 10,
    })

    client.connect()
    clients.set(channel, client)
  },

  /**
   * 断开指定通道
   */
  disconnect(channel: WebSocketChannel): void {
    const client = clients.get(channel)
    if (client) {
      client.close()
      clients.delete(channel)
    }
  },

  /**
   * 检查通道是否已连接
   */
  isConnected(channel: WebSocketChannel): boolean {
    const client = clients.get(channel)
    return client?.isConnected ?? false
  },

  /**
   * 注册消息处理器
   */
  on(channel: WebSocketChannel, type: string, handler: (data: any) => void): void {
    const client = getClientOrWarn(channel)
    if (client) {
      client.on(type, handler)
    }
  },

  /**
   * 移除消息处理器
   */
  off(channel: WebSocketChannel, type: string, handler?: (data: any) => void): void {
    const client = clients.get(channel)
    if (client) {
      client.off(type, handler)
    }
  },

  /**
   * 订阅频道/过滤器
   */
  subscribe(channel: WebSocketChannel, options: {
    channels?: string[]
    filters?: {
      point_ids?: number[]
      area_codes?: string[]
      alarm_levels?: string[]
    }
  }): void {
    const client = getClientOrWarn(channel)
    if (client) {
      client.subscribe(options)
    }
  },

  /**
   * 发送消息
   */
  send(channel: WebSocketChannel, data: any): void {
    const client = getClientOrWarn(channel)
    if (client) {
      client.send(data)
    }
  },
}

/**
 * 获取 WebSocket 管理器单例
 */
export function useWebSocketManager() {
  return manager
}
