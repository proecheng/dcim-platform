// frontend/src/composables/bigscreen/useBigscreenData.ts
import { ref, onMounted, onUnmounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { useAlarmStore } from '@/stores/alarm'
import { useRealtimeStore } from '@/stores/realtime'
import { useEnergyStore } from '@/stores/energy'
import type { DeviceRealtimeData } from '@/types/bigscreen'
import { PUBLIC_AUTH_UNAVAILABLE_EVENT } from '@/utils/authEvents'

export interface DataFetchOptions {
  refreshInterval?: number
  enableRealtime?: boolean
}

export function useBigscreenData(options: DataFetchOptions = {}) {
  const { refreshInterval = 5000, enableRealtime = true } = options

  const store = useBigscreenStore()
  const realtimeStore = useRealtimeStore()
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<Date | null>(null)

  let refreshTimer: number | null = null
  let currentInterval = refreshInterval
  let authUnavailable = false

  // Story 27.7 AC4: 移除 fetchEnvironmentData，environment 现在是 BigscreenStore 的 getter
  // 从 RealtimeStore 自动派生，无需手动更新

  // Story 27.7 AC3: 简化 fetchEnergyData，只确保 EnergyStore 有数据
  async function fetchEnergyData() {
    try {
      // 确保 EnergyStore 有最新数据，BigscreenStore.energy getter 会自动派生
      const energyStore = useEnergyStore()
      await energyStore.reload()
    } catch (e) {
      console.error('Failed to fetch energy data:', e)
    }
  }

  // 获取告警数据
  async function fetchAlarmData() {
    try {
      // 告警数据由 AlarmStore 统一管理，BigscreenStore.activeAlarms getter 自动派生
      await useAlarmStore().fetchActiveAlarms()
    } catch (e) {
      console.error('Failed to fetch alarm data:', e)
    }
  }

  // 获取设备实时数据（从 RealtimeStore 读取）
  async function fetchDeviceData() {
    try {
      // 确保 store 有数据
      if (realtimeStore.totalPoints === 0) {
        await realtimeStore.fetchAllData()
      }
      const allRealtimeData = realtimeStore.realtimeData

      if (store.layout) {
        for (const module of store.layout.modules) {
          for (const cabinet of module.cabinets) {
            // 根据机柜ID查找关联的点位数据
            const relatedPoints = allRealtimeData.filter(p =>
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
    if (authUnavailable) return

    isLoading.value = true
    error.value = null

    try {
      await Promise.all([
        realtimeStore.reload(), // 确保 RealtimeStore 有最新数据（environment 会自动派生）
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
    if (refreshTimer || authUnavailable) return

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

  function handlePublicAuthUnavailable() {
    authUnavailable = true
    stopRefresh()
  }

  onMounted(() => {
    window.addEventListener(PUBLIC_AUTH_UNAVAILABLE_EVENT, handlePublicAuthUnavailable)
    refreshAllData()
    if (enableRealtime) {
      startRefresh()
    }
  })

  onUnmounted(() => {
    stopRefresh()
    window.removeEventListener(PUBLIC_AUTH_UNAVAILABLE_EVENT, handlePublicAuthUnavailable)
  })

  return {
    isLoading,
    error,
    lastUpdate,
    refreshAllData,
    startRefresh,
    stopRefresh,
    setRefreshInterval,
    fetchEnergyData,
    fetchAlarmData,
    fetchDeviceData
  }
}
