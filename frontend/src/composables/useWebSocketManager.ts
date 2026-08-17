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
import type { WebSocketSubscribeOptions } from '@/api/websocket'
import { siteEvents } from '@/utils/siteEvents'

// WebSocket 通道类型
export type WebSocketChannel = 'alarms' | 'realtime' | 'system' | 'linkage'

// 连接池：每个通道一个 WebSocketClient 实例
const clients = new Map<WebSocketChannel, WebSocketClient>()

type MessageHandler = (data: any) => void

// 处理器独立于连接保存，站点切换重连后可以自动恢复。
const handlers = new Map<WebSocketChannel, Map<string, Set<MessageHandler>>>()

// Story 27.6: 订阅记录，disconnect 不丢失
const subscriptions = new Map<WebSocketChannel, WebSocketSubscribeOptions>()

function getCurrentSiteId(): number | null {
  const storedSiteId = localStorage.getItem('current_site_id')
  if (storedSiteId === null) return null
  const siteId = Number(storedSiteId)
  return Number.isInteger(siteId) && siteId > 0 ? siteId : null
}

function withoutSiteScope(options: WebSocketSubscribeOptions): WebSocketSubscribeOptions {
  const filters = { ...options.filters }
  delete filters.site_ids
  return {
    channels: options.channels ? [...options.channels] : undefined,
    filters: Object.keys(filters).length > 0 ? filters : undefined,
  }
}

function withSiteScope(
  options: WebSocketSubscribeOptions,
  siteId: number | null,
): WebSocketSubscribeOptions {
  const filters = { ...options.filters }
  if (siteId === null) {
    delete filters.site_ids
  } else {
    filters.site_ids = [siteId]
  }
  return {
    channels: options.channels ? [...options.channels] : undefined,
    filters: Object.keys(filters).length > 0 ? filters : undefined,
  }
}

function attachHandlers(channel: WebSocketChannel, client: WebSocketClient): void {
  const channelHandlers = handlers.get(channel)
  if (!channelHandlers) return

  for (const [type, typeHandlers] of channelHandlers) {
    for (const handler of typeHandlers) {
      client.on(type, handler)
    }
  }
}

function createClient(
  channel: WebSocketChannel,
  siteId: number | null = getCurrentSiteId(),
): WebSocketClient {
  const client = new WebSocketClient({
    url: `/ws/${channel}`,
    heartbeatInterval: 30000,
    reconnectInterval: 3000,
    maxReconnectAttempts: 10,
  })

  clients.set(channel, client)
  attachHandlers(channel, client)

  const options = subscriptions.get(channel)
  if (options) {
    client.subscribe(withSiteScope(options, siteId))
  }

  client.connect()
  return client
}

function ensureClient(channel: WebSocketChannel): WebSocketClient {
  return clients.get(channel) || createClient(channel)
}

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
    ensureClient(channel)
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
    let channelHandlers = handlers.get(channel)
    if (!channelHandlers) {
      channelHandlers = new Map()
      handlers.set(channel, channelHandlers)
    }

    let typeHandlers = channelHandlers.get(type)
    if (!typeHandlers) {
      typeHandlers = new Set()
      channelHandlers.set(type, typeHandlers)
    }

    const isNewHandler = !typeHandlers.has(handler)
    typeHandlers.add(handler)

    const existing = clients.get(channel)
    if (existing) {
      if (isNewHandler) existing.on(type, handler)
    } else {
      ensureClient(channel)
    }
  },

  /**
   * 移除消息处理器
   */
  off(channel: WebSocketChannel, type: string, handler?: (data: any) => void): void {
    const channelHandlers = handlers.get(channel)
    if (handler) {
      channelHandlers?.get(type)?.delete(handler)
      if (channelHandlers?.get(type)?.size === 0) channelHandlers.delete(type)
    } else {
      channelHandlers?.delete(type)
    }
    if (channelHandlers?.size === 0) handlers.delete(channel)

    const client = clients.get(channel)
    if (client) {
      client.off(type, handler)
    }
  },

  /**
   * 订阅频道/过滤器（Story 27.6: 同时记录订阅信息）
   */
  subscribe(channel: WebSocketChannel, options: WebSocketSubscribeOptions): void {
    // 仅记录业务过滤器，站点范围始终由当前站点选择重新生成
    const baseOptions = withoutSiteScope(options)
    subscriptions.set(channel, baseOptions)
    const existing = clients.get(channel)
    if (existing) {
      existing.subscribe(withSiteScope(baseOptions, getCurrentSiteId()))
    } else {
      createClient(channel)
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
  reconnectAll(siteId: number | null = getCurrentSiteId()): void {
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
      createClient(channel, siteId)
    }
  },
}

// Story 27.6: 站点切换时自动重连 WebSocket
function handleSiteChange(siteId: number | null) {
  manager.reconnectAll(siteId)
}
siteEvents.on(handleSiteChange)

/**
 * 获取 WebSocket 管理器单例
 */
export function useWebSocketManager() {
  return manager
}
