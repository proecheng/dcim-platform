/**
 * 水浸检测数据组合式函数
 * 封装水浸传感器数据获取、区域分组、统计计算
 * 水浸传感器为 DI 类型（干接点），只有正常/告警两种状态
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getAllRealtimeData, type RealtimeData } from '@/api/modules/realtime'
import { getAlarmList, type AlarmInfo } from '@/api/modules/alarm'
import { realtimeWs } from '@/api/websocket'

/** 水浸区域分组数据 */
export interface WaterLeakZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  normalCount: number
  alarmCount: number
  offlineCount: number
  hasAlarm: boolean
}

export function useWaterLeakData() {
  const allData = ref<Map<number, RealtimeData>>(new Map())
  const recentAlarmCount = ref(0)
  const loading = ref(false)
  const wsConnected = ref(false)
  let pollingTimer: number | null = null

  // 筛选水浸传感器（device_type === 'WL'）
  const wlSensors = computed(() =>
    Array.from(allData.value.values()).filter(d => d.device_type === 'WL')
  )

  // ── 统计数据 ──
  const totalCount = computed(() => wlSensors.value.length)
  const onlineCount = computed(() => wlSensors.value.filter(d => d.status !== 'offline').length)
  const alarmCount = computed(() => wlSensors.value.filter(d => d.status === 'alarm').length)

  // ── 区域分组 ──
  const zoneGroups = computed<WaterLeakZoneGroup[]>(() => {
    const map = new Map<string, RealtimeData[]>()
    wlSensors.value.forEach(d => {
      const area = d.area_code || '未分区'
      if (!map.has(area)) map.set(area, [])
      map.get(area)!.push(d)
    })

    return Array.from(map.entries()).map(([areaCode, sensors]) => {
      const normalCount = sensors.filter(s => s.status === 'normal').length
      const alarmCnt = sensors.filter(s => s.status === 'alarm').length
      const offlineCount = sensors.filter(s => s.status === 'offline').length

      return {
        areaCode,
        sensors,
        normalCount,
        alarmCount: alarmCnt,
        offlineCount,
        hasAlarm: alarmCnt > 0,
      }
    }).sort((a, b) => {
      // 有告警的区域排前面
      if (a.hasAlarm !== b.hasAlarm) return a.hasAlarm ? -1 : 1
      return a.areaCode.localeCompare(b.areaCode)
    })
  })

  // ── 数据获取 ──
  async function fetchData() {
    loading.value = true
    try {
      const dataArray = await getAllRealtimeData()
      allData.value.clear()
      dataArray.forEach(d => allData.value.set(d.point_id, d))
    } catch (e) {
      console.error('水浸传感器数据加载失败', e)
    } finally {
      loading.value = false
    }
  }

  /** 获取最近 24 小时告警数 */
  async function fetchRecentAlarms() {
    try {
      const now = new Date()
      const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000)
      const res = await getAlarmList({
        start_time: yesterday.toISOString(),
        end_time: now.toISOString(),
        device_type: 'WL', // 按水浸传感器设备类型过滤
        page: 1,
        page_size: 1, // 只需要 total 数
      })
      recentAlarmCount.value = res.total ?? 0
    } catch (e) {
      console.error('最近告警数据加载失败', e)
    }
  }

  // ── WebSocket 实时更新 ──
  function handleWsMessage(message: Record<string, unknown>) {
    if (message.type === 'realtime' && message.data) {
      const data = message.data as RealtimeData
      allData.value.set(data.point_id, data) // O(1) 更新
    }
  }

  function startPolling() {
    stopPolling()
    pollingTimer = window.setInterval(fetchData, 10000)
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  onMounted(() => {
    fetchData()
    fetchRecentAlarms()
    startPolling()

    // WebSocket 订阅
    realtimeWs.connect()
    realtimeWs.on('realtime', handleWsMessage)
    wsConnected.value = true
  })

  onUnmounted(() => {
    stopPolling()
    realtimeWs.off('realtime', handleWsMessage)
    wsConnected.value = false
    // 注意: 不调用 realtimeWs.close()，因为它是全局单例，close 会影响其他页面
  })

  return {
    // 原始数据
    allData,
    wlSensors,
    loading,
    wsConnected,
    // 统计
    totalCount,
    onlineCount,
    alarmCount,
    recentAlarmCount,
    // 分组
    zoneGroups,
    // 操作
    fetchData,
    fetchRecentAlarms,
  }
}
