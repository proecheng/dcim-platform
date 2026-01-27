/**
 * 实时数据组合式函数
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from './useWebSocket'
import { getAllRealtimeData, getRealtimeSummary, type RealtimeData, type RealtimeSummary } from '@/api/modules/realtime'

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

  const realtimeData = ref<Map<number, RealtimeData>>(new Map())
  const summary = ref<RealtimeSummary | null>(null)
  const loading = ref(false)
  const error = ref<Error | null>(null)
  const lastUpdateTime = ref<Date | null>(null)

  let pollingTimer: number | null = null
  let wsConnected = false

  // WebSocket 连接
  const { isConnected, subscribe, on, off, connect, disconnect } = useWebSocket({
    url: '/ws/realtime',
    autoConnect: false
  })

  // 获取所有实时数据
  const fetchRealtimeData = async () => {
    loading.value = true
    try {
      const data = await getAllRealtimeData({ point_ids: pointIds })
      data.forEach(item => {
        realtimeData.value.set(item.point_id, item)
      })
      lastUpdateTime.value = new Date()
      error.value = null
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  // 获取汇总数据
  const fetchSummary = async () => {
    try {
      summary.value = await getRealtimeSummary()
    } catch (e) {
      console.error('获取汇总数据失败:', e)
    }
  }

  // 开始轮询
  const startPolling = () => {
    stopPolling()
    pollingTimer = window.setInterval(() => {
      if (!wsConnected) {
        fetchRealtimeData()
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

  // 处理 WebSocket 消息
  const handleRealtimeMessage = (message: any) => {
    if (message.type === 'realtime' && message.data) {
      const data = message.data as RealtimeData
      realtimeData.value.set(data.point_id, data)
      lastUpdateTime.value = new Date()
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

  // 根据点位 ID 获取数据
  const getPointData = (pointId: number): RealtimeData | undefined => {
    return realtimeData.value.get(pointId)
  }

  // 根据类型获取数据
  const getDataByType = (type: 'AI' | 'DI' | 'AO' | 'DO'): RealtimeData[] => {
    return Array.from(realtimeData.value.values()).filter(d => d.point_type === type)
  }

  // 根据区域获取数据
  const getDataByArea = (areaCode: string): RealtimeData[] => {
    return Array.from(realtimeData.value.values()).filter(d => d.area_code === areaCode)
  }

  // 获取告警点位
  const alarmPoints = computed(() => {
    return Array.from(realtimeData.value.values()).filter(d => d.status === 'alarm')
  })

  // 获取离线点位
  const offlinePoints = computed(() => {
    return Array.from(realtimeData.value.values()).filter(d => d.status === 'offline')
  })

  // 监听 WebSocket 连接状态
  watch(isConnected, (connected) => {
    wsConnected = connected
    if (connected) {
      // WebSocket 连接成功，减少轮询频率
      stopPolling()
    } else {
      // WebSocket 断开，恢复轮询
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
    realtimeData: computed(() => Array.from(realtimeData.value.values())),
    summary: computed(() => summary.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    lastUpdateTime: computed(() => lastUpdateTime.value),
    alarmPoints,
    offlinePoints,
    isConnected,
    getPointData,
    getDataByType,
    getDataByArea,
    fetchRealtimeData,
    fetchSummary,
    startPolling,
    stopPolling
  }
}

export default useRealtime
