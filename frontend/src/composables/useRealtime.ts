/**
 * 实时数据组合式函数
 *
 * Story 27.2: 状态委托给 RealtimeStore (SSOT)，
 * composable 负责 WS 订阅、轮询、生命周期管理。
 */
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWebSocket } from './useWebSocket'
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
  const { realtimeData, summary, loading, lastUpdateTime, alarmPoints, offlinePoints } = storeToRefs(store)

  let pollingTimer: number | null = null

  // WebSocket 连接
  const { isConnected, subscribe, on, off, connect, disconnect } = useWebSocket({
    url: '/ws/realtime',
    autoConnect: false
  })

  // 获取所有实时数据 - 委托给 store
  const fetchRealtimeData = async () => {
    await store.fetchAllData(pointIds)
  }

  // 获取汇总数据 - 委托给 store
  const fetchSummary = async () => {
    await store.fetchSummary()
  }

  // 开始轮询
  const startPolling = () => {
    stopPolling()
    pollingTimer = window.setInterval(() => {
      if (!isConnected.value) {
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

  // 订阅实时数据
  const subscribeRealtime = () => {
    if (!isConnected.value) {
      connect()
    }

    on('realtime', handleRealtimeMessage)

    subscribe({
      channels: ['realtime'],
      filters: pointIds ? { point_ids: pointIds } : undefined
    })
  }

  // 监听 WebSocket 连接状态
  watch(isConnected, (connected) => {
    store.setWsConnected(connected)
    if (connected) {
      stopPolling()
    } else {
      startPolling()
    }
  })

  onMounted(() => {
    if (autoFetch) {
      fetchRealtimeData()
      fetchSummary()
    }

    if (autoSubscribe) {
      subscribeRealtime()
    }

    startPolling()
  })

  onUnmounted(() => {
    stopPolling()
    off('realtime', handleRealtimeMessage)
    disconnect()
  })

  return {
    realtimeData,
    summary,
    loading,
    lastUpdateTime,
    alarmPoints,
    offlinePoints,
    isConnected,
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
