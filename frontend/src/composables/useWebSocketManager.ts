/**
 * WebSocket 连接管理器（单例）
 *
 * 职责：
 * - 每个通道（alarms/realtime/system/linkage）最多维持 1 个 WebSocketClient 实例
 * - 复用 WebSocketClient 的重连、心跳、消息分发功能
 * - 提供统一的 API 供 composables 使用
 * - Story 27.6: 记录订阅信息，站点切换时 reconnectAll
 */
import { WebSocketClient } from '@/api/websocket'
import { siteEvents } from '@/utils/siteEvents'

// WebSocket 通道类型
export type WebSocketChannel = 'alarms' | 'realtime' | 'system' | 'linkage'

// 订阅选项类型
interface SubscribeOptions {
  channels?: string[]
  filters?: {
    point_ids?: number[]
    area_codes?: string[]
    alarm_levels?: string[]
  }
}

// 连接池：每个通道一个 WebSocketClient 实例
const clients = new Map<WebSocketChannel, WebSocketClient>()

// Story 27.6: 订阅记录，disconnect 不丢失
const subscriptions = new Map<WebSocketChannel, SubscribeOptions>()

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
   * 断开指定通道（同时清除订阅记录）
   */
  disconnect(channel: WebSocketChannel): void {
    const client = clients.get(channel)
    if (client) {
      client.close()
      clients.delete(channel)
    }
    subscriptions.delete(channel)
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
   * 订阅频道/过滤器（Story 27.6: 同时记录订阅信息）
   */
  subscribe(channel: WebSocketChannel, options: SubscribeOptions): void {
    // 记录订阅信息，reconnectAll 时恢复
    subscriptions.set(channel, options)
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

  /**
   * Story 27.6: 断开所有连接并基于订阅记录重连
   * 站点切换时调用，确保 WebSocket 推送数据与新站点一致
   */
  reconnectAll(): void {
    // 收集所有需要重连的通道（已连接或有订阅记录的）
    const channelsToReconnect = new Set<WebSocketChannel>([
      ...clients.keys(),
      ...subscriptions.keys(),
    ])

    // 1. 关闭所有现有连接
    for (const [, client] of clients) {
      client.close()
    }
    clients.clear()

    // 2. 重新连接所有通道
    for (const channel of channelsToReconnect) {
      const options = subscriptions.get(channel)
      const client = new WebSocketClient({
        url: `/ws/${channel}`,
        heartbeatInterval: 30000,
        reconnectInterval: 3000,
        maxReconnectAttempts: 10,
        onOpen: () => {
          // 重连成功后自动重新订阅（如果有订阅记录）
          if (options) {
            client.subscribe(options)
          }
        },
      })
      client.connect()
      clients.set(channel, client)
    }
  },
}

// Story 27.6: 站点切换时自动重连 WebSocket
function handleSiteChange() {
  manager.reconnectAll()
}
siteEvents.on(handleSiteChange)

/**
 * 获取 WebSocket 管理器单例
 */
export function useWebSocketManager() {
  return manager
}
