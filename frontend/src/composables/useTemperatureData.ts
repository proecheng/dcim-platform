/**
 * 温湿度监测数据组合式函数
 * 封装温湿度传感器数据获取、区域分组、统计计算
 * 预留热力图升级接口
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getAllRealtimeData, type RealtimeData } from '@/api/modules/realtime'
import { getDriftResults, type DriftDetectionResult } from '@/api/modules/drift'
import { realtimeWs } from '@/api/websocket'

/** 区域分组数据 */
export interface ZoneGroup {
  areaCode: string
  sensors: RealtimeData[]
  tempSensors: RealtimeData[]
  humiditySensors: RealtimeData[]
  avgTemp: number | null
  avgHumidity: number | null
  minTemp: number | null
  maxTemp: number | null
  alarmCount: number
  hasDrift: boolean
  hasAlarm: boolean
}

/** 热力图数据点（预留接口） */
export interface HeatmapPoint {
  x: number
  y: number
  value: number
  sensorId: number
  areaCode: string
}

export function useTemperatureData() {
  const allData = ref<RealtimeData[]>([])
  const driftPointIds = ref<Set<number>>(new Set())
  const loading = ref(false)
  const wsConnected = ref(false)
  let pollingTimer: number | null = null

  // 筛选温湿度传感器（device_type === 'TH'）
  const thSensors = computed(() =>
    allData.value.filter(d => d.device_type === 'TH')
  )

  const tempSensors = computed(() =>
    thSensors.value.filter(d => d.unit === '°C')
  )

  const humiditySensors = computed(() =>
    thSensors.value.filter(d => d.unit === '%')
  )

  // ── 统计数据 ──
  const totalCount = computed(() => thSensors.value.length)
  const onlineCount = computed(() => thSensors.value.filter(d => d.status !== 'offline').length)
  const alarmCount = computed(() => thSensors.value.filter(d => d.status === 'alarm').length)
  const driftCount = computed(() => thSensors.value.filter(d => driftPointIds.value.has(d.point_id)).length)

  const avgTemp = computed(() => {
    const valid = tempSensors.value.filter(d => d.value != null && d.status !== 'offline')
    if (!valid.length) return null
    return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
  })

  const avgHumidity = computed(() => {
    const valid = humiditySensors.value.filter(d => d.value != null && d.status !== 'offline')
    if (!valid.length) return null
    return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
  })

  // ── 区域分组 ──
  const zoneGroups = computed<ZoneGroup[]>(() => {
    const map = new Map<string, RealtimeData[]>()
    thSensors.value.forEach(d => {
      const area = d.area_code || '未分区'
      if (!map.has(area)) map.set(area, [])
      map.get(area)!.push(d)
    })

    return Array.from(map.entries()).map(([areaCode, sensors]) => {
      const temps = sensors.filter(s => s.unit === '°C')
      const humids = sensors.filter(s => s.unit === '%')
      const validTemps = temps.filter(s => s.value != null && s.status !== 'offline')
      const validHumids = humids.filter(s => s.value != null && s.status !== 'offline')

      const tempValues = validTemps.map(s => s.value ?? 0)
      const alarms = sensors.filter(s => s.status === 'alarm').length
      const hasDrift = sensors.some(s => driftPointIds.value.has(s.point_id))

      return {
        areaCode,
        sensors,
        tempSensors: temps,
        humiditySensors: humids,
        avgTemp: validTemps.length ? validTemps.reduce((s, d) => s + (d.value ?? 0), 0) / validTemps.length : null,
        avgHumidity: validHumids.length ? validHumids.reduce((s, d) => s + (d.value ?? 0), 0) / validHumids.length : null,
        minTemp: tempValues.length ? Math.min(...tempValues) : null,
        maxTemp: tempValues.length ? Math.max(...tempValues) : null,
        alarmCount: alarms,
        hasDrift,
        hasAlarm: alarms > 0,
      }
    }).sort((a, b) => a.areaCode.localeCompare(b.areaCode))
  })

  // ── 热力图数据接口（预留） ──
  function getHeatmapData(): HeatmapPoint[] {
    return tempSensors.value
      .filter(d => d.value != null)
      .map(d => ({
        x: 0, // 由热力图组件根据布局计算
        y: 0,
        value: d.value ?? 0,
        sensorId: d.point_id,
        areaCode: d.area_code,
      }))
  }

  // ── 判断传感器是否疑似漂移 ──
  function isDrift(pointId: number): boolean {
    return driftPointIds.value.has(pointId)
  }

  // ── 数据获取 ──
  async function fetchData() {
    loading.value = true
    try {
      allData.value = await getAllRealtimeData()
    } catch (e) {
      console.error('温湿度数据加载失败', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchDriftData() {
    try {
      const res = await getDriftResults({ page_size: 500, status: 'suspected' })
      const ids = new Set<number>()
      if (res && res.items) {
        res.items.forEach((d: DriftDetectionResult) => ids.add(d.point_id))
      }
      // 也获取 confirmed 状态
      const res2 = await getDriftResults({ page_size: 500, status: 'confirmed' })
      if (res2 && res2.items) {
        res2.items.forEach((d: DriftDetectionResult) => ids.add(d.point_id))
      }
      driftPointIds.value = ids
    } catch (e) {
      console.error('漂移检测数据加载失败', e)
    }
  }

  // ── WebSocket 实时更新 ──
  function handleWsMessage(message: Record<string, unknown>) {
    if (message.type === 'realtime' && message.data) {
      const data = message.data as RealtimeData
      const idx = allData.value.findIndex(d => d.point_id === data.point_id)
      if (idx >= 0) {
        allData.value[idx] = data
      } else {
        allData.value.push(data)
      }
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
    fetchDriftData()
    startPolling()

    // WebSocket 订阅
    realtimeWs.connect()
    realtimeWs.on('realtime', handleWsMessage)
    wsConnected.value = true
  })

  onUnmounted(() => {
    stopPolling()
    realtimeWs.off('realtime', handleWsMessage)
  })

  return {
    // 原始数据
    allData,
    thSensors,
    tempSensors,
    humiditySensors,
    loading,
    wsConnected,
    // 统计
    totalCount,
    onlineCount,
    alarmCount,
    driftCount,
    avgTemp,
    avgHumidity,
    // 分组
    zoneGroups,
    // 漂移
    driftPointIds,
    isDrift,
    // 热力图接口
    getHeatmapData,
    // 操作
    fetchData,
    fetchDriftData,
  }
}
