/**
 * 实时数据状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { RealtimeData, RealtimeSummary } from '@/api/modules/realtime'

export const useRealtimeStore = defineStore('realtime', () => {
  // 实时数据映射表
  const dataMap = ref<Map<number, RealtimeData>>(new Map())

  // 汇总数据
  const summary = ref<RealtimeSummary | null>(null)

  // 最后更新时间
  const lastUpdateTime = ref<Date | null>(null)

  // WebSocket 连接状态
  const wsConnected = ref(false)

  // 计算属性
  const realtimeData = computed(() => Array.from(dataMap.value.values()))
  const totalPoints = computed(() => dataMap.value.size)
  const alarmPoints = computed(() => realtimeData.value.filter(d => d.status === 'alarm'))
  const offlinePoints = computed(() => realtimeData.value.filter(d => d.status === 'offline'))
  const alarmCount = computed(() => alarmPoints.value.length)
  const offlineCount = computed(() => offlinePoints.value.length)

  // 更新单个点位数据
  function updatePoint(data: RealtimeData) {
    dataMap.value.set(data.point_id, data)
    lastUpdateTime.value = new Date()
  }

  // 批量更新数据
  function updatePoints(data: RealtimeData[]) {
    data.forEach(d => dataMap.value.set(d.point_id, d))
    lastUpdateTime.value = new Date()
  }

  // 设置全部数据
  function setAllData(data: RealtimeData[]) {
    dataMap.value.clear()
    data.forEach(d => dataMap.value.set(d.point_id, d))
    lastUpdateTime.value = new Date()
  }

  // 设置汇总数据
  function setSummary(data: RealtimeSummary) {
    summary.value = data
  }

  // 获取点位数据
  function getPointData(pointId: number): RealtimeData | undefined {
    return dataMap.value.get(pointId)
  }

  // 按类型获取数据
  function getDataByType(type: 'AI' | 'DI' | 'AO' | 'DO'): RealtimeData[] {
    return realtimeData.value.filter(d => d.point_type === type)
  }

  // 按区域获取数据
  function getDataByArea(areaCode: string): RealtimeData[] {
    return realtimeData.value.filter(d => d.area_code === areaCode)
  }

  // 设置 WebSocket 连接状态
  function setWsConnected(connected: boolean) {
    wsConnected.value = connected
  }

  // 清空数据
  function clearData() {
    dataMap.value.clear()
    summary.value = null
    lastUpdateTime.value = null
  }

  return {
    dataMap,
    summary,
    lastUpdateTime,
    wsConnected,
    realtimeData,
    totalPoints,
    alarmPoints,
    offlinePoints,
    alarmCount,
    offlineCount,
    updatePoint,
    updatePoints,
    setAllData,
    setSummary,
    getPointData,
    getDataByType,
    getDataByArea,
    setWsConnected,
    clearData
  }
})
