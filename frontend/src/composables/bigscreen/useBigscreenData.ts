// frontend/src/composables/bigscreen/useBigscreenData.ts
import { ref, onMounted, onUnmounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import type { DeviceRealtimeData, BigscreenAlarm } from '@/types/bigscreen'
import { getRealtimeSummary, getAllRealtimeData } from '@/api/modules/realtime'
import { getActiveAlarms } from '@/api/modules/alarm'
import { getEnergyDashboard } from '@/api/modules/energy'

export interface DataFetchOptions {
  refreshInterval?: number
  enableRealtime?: boolean
}

export function useBigscreenData(options: DataFetchOptions = {}) {
  const { refreshInterval = 5000, enableRealtime = true } = options

  const store = useBigscreenStore()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<Date | null>(null)

  let refreshTimer: number | null = null
  let currentInterval = refreshInterval

  // 获取环境数据
  async function fetchEnvironmentData() {
    try {
      const summary = await getRealtimeSummary()

      // 从实时数据中提取温湿度
      const realtimeData = await getAllRealtimeData()
      const tempPoints = realtimeData.filter(p => p.point_code.includes('_TH_') && p.point_code.includes('_001'))
      const humidPoints = realtimeData.filter(p => p.point_code.includes('_TH_') && p.point_code.includes('_002'))

      const temps = tempPoints.map(p => p.value).filter(v => v > 0)
      const humids = humidPoints.map(p => p.value).filter(v => v > 0)

      const data = {
        temperature: {
          max: temps.length > 0 ? Math.max(...temps) : 30,
          avg: temps.length > 0 ? temps.reduce((a, b) => a + b, 0) / temps.length : 24,
          min: temps.length > 0 ? Math.min(...temps) : 20
        },
        humidity: {
          max: humids.length > 0 ? Math.max(...humids) : 60,
          avg: humids.length > 0 ? humids.reduce((a, b) => a + b, 0) / humids.length : 50,
          min: humids.length > 0 ? Math.min(...humids) : 40
        }
      }

      store.updateEnvironment(data)
    } catch (e) {
      console.error('Failed to fetch environment data:', e)
    }
  }

  // 获取能耗数据
  async function fetchEnergyData() {
    try {
      const response = await getEnergyDashboard()
      // 处理可能的 ResponseModel 包装
      const dashboard = (response as any)?.data || response

      const data = {
        totalPower: dashboard.realtime?.total_power || 0,
        itPower: dashboard.realtime?.it_power || 0,
        coolingPower: dashboard.realtime?.cooling_power || 0,
        pue: dashboard.efficiency?.pue || 1.5,
        todayEnergy: dashboard.cost?.today_energy || dashboard.realtime?.today_energy || 0,
        todayCost: dashboard.cost?.today_cost || 0
      }

      store.updateEnergy(data)
    } catch (e) {
      console.error('Failed to fetch energy data:', e)
    }
  }

  // 获取告警数据
  async function fetchAlarmData() {
    try {
      const activeAlarms = await getActiveAlarms()

      const alarms: BigscreenAlarm[] = activeAlarms.map(alarm => ({
        id: alarm.id,
        deviceId: alarm.point_code.split('_').slice(0, 2).join('-'),
        deviceName: alarm.point_name,
        level: alarm.alarm_level as 'critical' | 'major' | 'minor' | 'warning' | 'info',
        message: alarm.alarm_message,
        value: alarm.trigger_value,
        threshold: alarm.threshold_value,
        time: new Date(alarm.created_at).getTime(),
        createdAt: alarm.created_at
      }))

      store.setAlarms(alarms)
    } catch (e) {
      console.error('Failed to fetch alarm data:', e)
    }
  }

  // 获取设备实时数据
  async function fetchDeviceData() {
    try {
      const realtimeData = await getAllRealtimeData()

      if (store.layout) {
        for (const module of store.layout.modules) {
          for (const cabinet of module.cabinets) {
            // 根据机柜ID查找关联的点位数据
            const relatedPoints = realtimeData.filter(p =>
              p.point_code.startsWith(cabinet.id.replace('-', '_'))
            )

            const tempPoint = relatedPoints.find(p => p.point_code.includes('_TH_') && p.point_code.endsWith('_001'))
            const humidPoint = relatedPoints.find(p => p.point_code.includes('_TH_') && p.point_code.endsWith('_002'))
            const powerPoint = relatedPoints.find(p => p.point_code.includes('_PDU_'))

            const hasAlarm = relatedPoints.some(p => p.status === 'alarm')
            const isOffline = relatedPoints.length > 0 && relatedPoints.every(p => p.status === 'offline')

            const deviceData: DeviceRealtimeData = {
              id: cabinet.id,
              status: isOffline ? 'offline' : (hasAlarm ? 'alarm' : 'normal'),
              temperature: tempPoint?.value || 24,
              humidity: humidPoint?.value || 50,
              power: powerPoint?.value || 5,
              load: Math.min(100, Math.max(0, ((powerPoint?.value || 5) / 10) * 100))
            }
            store.updateDeviceData(cabinet.id, deviceData)
          }
        }
      }
    } catch (e) {
      console.error('Failed to fetch device data:', e)
    }
  }

  // 刷新所有数据
  async function refreshAllData() {
    isLoading.value = true
    error.value = null

    try {
      await Promise.all([
        fetchEnvironmentData(),
        fetchEnergyData(),
        fetchAlarmData(),
        fetchDeviceData()
      ])
      lastUpdate.value = new Date()
    } catch (e) {
      error.value = '数据刷新失败'
      console.error('Failed to refresh data:', e)
    } finally {
      isLoading.value = false
    }
  }

  // 开始定时刷新
  function startRefresh() {
    if (refreshTimer) return

    refreshTimer = window.setInterval(() => {
      if (enableRealtime) {
        refreshAllData()
      }
    }, currentInterval)
  }

  // 停止定时刷新
  function stopRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  // 更新刷新间隔
  function setRefreshInterval(interval: number) {
    currentInterval = interval
    stopRefresh()
    if (enableRealtime) {
      startRefresh()
    }
  }

  onMounted(() => {
    refreshAllData()
    if (enableRealtime) {
      startRefresh()
    }
  })

  onUnmounted(() => {
    stopRefresh()
  })

  return {
    isLoading,
    error,
    lastUpdate,
    refreshAllData,
    startRefresh,
    stopRefresh,
    setRefreshInterval,
    fetchEnvironmentData,
    fetchEnergyData,
    fetchAlarmData,
    fetchDeviceData
  }
}
