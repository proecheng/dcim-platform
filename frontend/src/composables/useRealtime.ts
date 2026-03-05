/**
 * 实时数据组合式函数
 *
 * Story 27.2: 状态委托给 RealtimeStore (SSOT)，
 * composable 负责 WS 订阅、轮询、生命周期管理。
 * Story 27.5: WebSocket 连接管理统一到 useWebSocketManager
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWebSocketManager } from './useWebSocketManager'
import { useRealtimeStore, type RealtimeData } from '@/stores/realtime'

interface UseRealtimeOptions {
  autoFetch?: boolean
  autoSubscribe?: boolean
  pollingInterval?: number
  pointIds?: number[]
}

export function useRealtime(options: UseRealtimeOptions = {}) {
  const {
    autoFetch = true,
    autoSubscribe = true,
    pollingInterval = 5000,
    pointIds
  } = options

  const store = useRealtimeStore()
  const wsManager = useWebSocketManager()
  const { realtimeData, summary, loading, lastUpdateTime, alarmPoints, offlinePoints } = storeToRefs(store)

  let pollingTimer: number | null = null

  // 获取所有实时数据 - 委托给 store
  const fetchRealtimeData = async () => {
    await store.fetchAllData(pointIds)
  }

  // 获取汇总数据 - 委托给 store
  const fetchSummary = async () => {
    await store.fetchSummary()
  }

  // 开始轮询（WebSocket 断开时的兜底）
  const startPolling = () => {
    stopPolling()
    pollingTimer = window.setInterval(() => {
      // 只在 WebSocket 未连接时轮询
      if (!wsManager.isConnected('realtime')) {
        store.fetchAllData(pointIds)
      }
    }, pollingInterval)
  }

  // 停止轮询
  const stopPolling = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  // 处理 WebSocket 消息 - 写入 store
  const handleRealtimeMessage = (message: any) => {
    if (message.type === 'realtime' && message.data) {
      store.updatePoint(message.data as RealtimeData)
    }
  }

  // 订阅实时数据（MainLayout 已预连接，这里只注册处理器）
  const subscribeRealtime = () => {
    wsManager.on('realtime', 'realtime', handleRealtimeMessage)
    wsManager.subscribe('realtime', {
      channels: ['realtime'],
      filters: pointIds ? { point_ids: pointIds } : undefined
    })
  }

  onMounted(() => {
    if (autoFetch) {
      fetchRealtimeData()
      fetchSummary()
    }

    if (autoSubscribe) {
      subscribeRealtime()
    }
    // 无条件启动轮询作为安全网（WebSocket 管理器保证连接，轮询作为兜底）
    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
    wsManager.off('realtime', 'realtime', handleRealtimeMessage)
  })

  return {
    realtimeData,
    summary,
    loading,
    lastUpdateTime,
    alarmPoints,
    offlinePoints,
    getPointData: store.getPointData,
    getDataByType: store.getDataByType,
    getDataByArea: store.getDataByArea,
    fetchRealtimeData,
    fetchSummary,
    startPolling,
    stopPolling
  }
}

export default useRealtime
