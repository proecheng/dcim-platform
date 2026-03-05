/**
 * 水浸检测数据组合式函数
 * 封装水浸传感器数据获取、区域分组、统计计算
 * 水浸传感器为 DI 类型（干接点），只有正常/告警两种状态
 */
import { ref, computed, onMounted } from 'vue'
import { type RealtimeData } from '@/api/modules/realtime'
import { getAlarmList, type AlarmInfo } from '@/api/modules/alarm'
import { useRealtimeStore } from '@/stores/realtime'

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
  const realtimeStore = useRealtimeStore()
  const allData = computed(() => realtimeStore.dataMap)
  const recentAlarmCount = ref(0)
  const loading = computed(() => realtimeStore.loading)
  const wsConnected = computed(() => realtimeStore.wsConnected)

  // 筛选水浸传感器（device_type === 'WATER'）
  const wlSensors = computed(() =>
    Array.from(allData.value.values()).filter(d => d.device_type === 'WATER')
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

  // ── 数据获取（委托给 store）──
  async function fetchData() {
    try {
      await realtimeStore.fetchAllData()
    } catch (e) {
      console.error('水浸传感器数据加载失败', e)
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
        device_type: 'WATER', // 按水浸传感器设备类型过滤
        page: 1,
        page_size: 1, // 只需要 total 数
      })
      recentAlarmCount.value = res.total ?? 0
    } catch (e) {
      console.error('最近告警数据加载失败', e)
    }
  }

  // WS/轮询由 RealtimeStore + useRealtime composable 统一管理

  onMounted(() => {
    if (realtimeStore.totalPoints === 0) {
      fetchData()
    }
    fetchRecentAlarms()
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
