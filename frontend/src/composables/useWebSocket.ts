/**
 * WebSocket 组合式函数
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { WebSocketClient } from '@/api/websocket'

interface UseWebSocketOptions {
  url: string
  autoConnect?: boolean
  heartbeatInterval?: number
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    autoConnect = true,
    heartbeatInterval = 30000,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10
  } = options

  const isConnected = ref(false)
  const lastMessage = ref<any>(null)
  const error = ref<Event | null>(null)

  const wsClient = new WebSocketClient({
    url,
    heartbeatInterval,
    reconnectInterval,
    maxReconnectAttempts,
    onOpen: () => {
      isConnected.value = true
      error.value = null
    },
    onClose: () => {
      isConnected.value = false
    },
    onError: (e) => {
      error.value = e
    }
  })

  const connect = () => {
    wsClient.connect()
  }

  const disconnect = () => {
    wsClient.close()
  }

  const send = (data: any) => {
    wsClient.send(data)
  }

  const subscribe = (options: {
    channels?: string[]
    filters?: {
      point_ids?: number[]
      area_codes?: string[]
      alarm_levels?: string[]
    }
  }) => {
    wsClient.subscribe(options)
  }

  const unsubscribe = (channels?: string[]) => {
    wsClient.unsubscribe(channels)
  }

  const on = (type: string, handler: (data: any) => void) => {
    wsClient.on(type, (message) => {
      lastMessage.value = message
      handler(message)
    })
  }

  const off = (type: string, handler?: (data: any) => void) => {
    wsClient.off(type, handler)
  }

  onMounted(() => {
    if (autoConnect) {
      connect()
    }
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected: computed(() => isConnected.value),
    lastMessage: computed(() => lastMessage.value),
    error: computed(() => error.value),
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    on,
    off,
    client: wsClient
  }
}

export default useWebSocket
