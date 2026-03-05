/**
 * 烟雾/红外检测数据组合式函数
 * 封装烟雾+红外传感器数据获取、区域分组、统计计算
 * 烟雾(SMOKE)和红外(IR)传感器均为 DI 类型（干接点），只有正常/告警两种状态
 */
import { ref, computed, onMounted } from 'vue'
import { type RealtimeData } from '@/api/modules/realtime'
import { getAlarmList } from '@/api/modules/alarm'
import { getLinkagePolicies, type LinkagePolicy } from '@/api/modules/linkage'
import { useRealtimeStore } from '@/stores/realtime'

/** 烟雾/红外区域分组数据 */
export interface SmokeIRZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  smokeCount: number
  irCount: number
  smokeAlarmCount: number
  irAlarmCount: number
  normalCount: number
  alarmCount: number
  offlineCount: number
  hasAlarm: boolean
}

export function useSmokeInfraredData() {
  const realtimeStore = useRealtimeStore()
  const allData = computed(() => realtimeStore.dataMap)
  const recentAlarmCount = ref(0)
  const firePolicies = ref<LinkagePolicy[]>([])
  const loading = computed(() => realtimeStore.loading)
  const wsConnected = computed(() => realtimeStore.wsConnected)

  // 筛选烟雾+红外传感器
  const siSensors = computed(() =>
    Array.from(allData.value.values()).filter(d => d.device_type === 'SMOKE' || d.device_type === 'IR')
  )

  // ── 按类型分别统计 ──
  const smokeSensors = computed(() => siSensors.value.filter(d => d.device_type === 'SMOKE'))
  const irSensors = computed(() => siSensors.value.filter(d => d.device_type === 'IR'))

  const smokeTotal = computed(() => smokeSensors.value.length)
  const smokeAlarm = computed(() => smokeSensors.value.filter(d => d.status === 'alarm').length)
  const irTotal = computed(() => irSensors.value.length)
  const irAlarm = computed(() => irSensors.value.filter(d => d.status === 'alarm').length)

  // ── 区域分组 ──
  const zoneGroups = computed<SmokeIRZoneGroup[]>(() => {
    const map = new Map<string, RealtimeData[]>()
    siSensors.value.forEach(d => {
      const area = d.area_code || '未分区'
      if (!map.has(area)) map.set(area, [])
      map.get(area)!.push(d)
    })

    return Array.from(map.entries()).map(([areaCode, sensors]) => {
      const smokeSensorsInZone = sensors.filter(s => s.device_type === 'SMOKE')
      const irSensorsInZone = sensors.filter(s => s.device_type === 'IR')
      const normalCount = sensors.filter(s => s.status === 'normal').length
      const alarmCnt = sensors.filter(s => s.status === 'alarm').length
      const offlineCount = sensors.filter(s => s.status === 'offline').length

      return {
        areaCode,
        sensors,
        smokeCount: smokeSensorsInZone.length,
        irCount: irSensorsInZone.length,
        smokeAlarmCount: smokeSensorsInZone.filter(s => s.status === 'alarm').length,
        irAlarmCount: irSensorsInZone.filter(s => s.status === 'alarm').length,
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
      console.error('烟雾/红外传感器数据加载失败', e)
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
        device_type: 'SM', // 按烟雾/红外传感器设备类型过滤
        page: 1,
        page_size: 1,
      })
      recentAlarmCount.value = res.total ?? 0
    } catch (e) {
      console.error('最近告警数据加载失败', e)
    }
  }

  /** 获取消防联动策略 */
  async function fetchFirePolicies() {
    try {
      const res = await getLinkagePolicies({
        trigger_type: 'fire_alarm',
        page: 1,
        page_size: 100,
      })
      firePolicies.value = res.items ?? []
    } catch {
      firePolicies.value = []
    }
  }

  // WS/轮询由 RealtimeStore + useRealtime composable 统一管理

  onMounted(() => {
    if (realtimeStore.totalPoints === 0) {
      fetchData()
    }
    fetchRecentAlarms()
    fetchFirePolicies()
  })

  return {
    // 原始数据
    allData,
    siSensors,
    smokeSensors,
    irSensors,
    loading,
    wsConnected,
    // 统计
    smokeTotal,
    smokeAlarm,
    irTotal,
    irAlarm,
    recentAlarmCount,
    // 分组
    zoneGroups,
    // 联动策略
    firePolicies,
    // 操作
    fetchData,
    fetchRecentAlarms,
    fetchFirePolicies,
  }
}
