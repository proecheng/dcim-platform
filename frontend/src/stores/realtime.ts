/**
 * 实时数据状态管理 - 单一事实来源 (SSOT)
 *
 * Story 27.2: 所有页面的实时点位数据从此 Store 读取，
 * useRealtime composable 负责 WS/轮询，但状态写入此 Store。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAllRealtimeData, getRealtimeSummary, type RealtimeData, type RealtimeSummary } from '@/api/modules/realtime'

export type { RealtimeData, RealtimeSummary }

export const useRealtimeStore = defineStore('realtime', () => {
  // 实时数据映射表
  const dataMap = ref<Map<number, RealtimeData>>(new Map())

  // 汇总数据
  const summary = ref<RealtimeSummary | null>(null)

  // 最后更新时间
  const lastUpdateTime = ref<Date | null>(null)

  // WebSocket 连接状态
  const wsConnected = ref(false)

  // 加载状态（防重入）
  const loading = ref(false)

  // 计算属性
  const realtimeData = computed(() => Array.from(dataMap.value.values()))
  const totalPoints = computed(() => dataMap.value.size)
  const alarmPoints = computed(() => realtimeData.value.filter(d => d.status === 'alarm'))
  const offlinePoints = computed(() => realtimeData.value.filter(d => d.status === 'offline'))
  const alarmCount = computed(() => alarmPoints.value.length)
  const offlineCount = computed(() => offlinePoints.value.length)

  // 简化汇总（供 dashboard 使用）
  const simpleSummary = computed(() => ({
    total: summary.value?.total_points ?? totalPoints.value,
    normal: summary.value?.online_points ?? (totalPoints.value - alarmCount.value - offlineCount.value),
    alarm: summary.value?.alarm_points ?? alarmCount.value,
    offline: summary.value?.offline_points ?? offlineCount.value,
  }))

  // 从 API 加载全量实时数据（带防重入锁，返回 false 表示被跳过）
  async function fetchAllData(pointIds?: number[]): Promise<boolean> {
    if (loading.value) return false
    loading.value = true
    try {
      const data = await getAllRealtimeData(pointIds ? { point_ids: pointIds } : undefined)
      // API 成功后才替换数据，避免 API 失败时清空导致页面空白
      const newMap = new Map<number, RealtimeData>()
      data.forEach(d => newMap.set(d.point_id, d))
      dataMap.value = newMap
      lastUpdateTime.value = new Date()
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  // 从 API 加载汇总数据
  async function fetchSummary() {
    try {
      summary.value = await getRealtimeSummary()
    } catch (e) {
      console.error('获取实时汇总失败:', e)
    }
  }

  // 加载全部（数据+汇总）
  async function reload() {
    await Promise.all([fetchAllData(), fetchSummary()])
  }

  // 更新单个点位数据（WS 推送用）— 原地修改 Map（Vue 3 reactive 追踪 Map.set）
  // 注意：Vue 3 ref() 对 Map 做深度响应式代理，.set() 能触发依赖更新。
  // 此处不使用 new Map 复制模式，因为 WS 高频推送时每条消息都复制整个 Map 代价太大。
  function updatePoint(data: RealtimeData) {
    dataMap.value.set(data.point_id, data)
    lastUpdateTime.value = new Date()
  }

  // 批量更新数据（WS 批量推送用）— 单次替换 Map 减少 N 次响应触发
  function updatePoints(data: RealtimeData[]) {
    const newMap = new Map(dataMap.value)
    data.forEach(d => newMap.set(d.point_id, d))
    dataMap.value = newMap
    lastUpdateTime.value = new Date()
  }

  // 设置全部数据（外部整体替换）— 单次赋值减少响应触发
  function setAllData(data: RealtimeData[]) {
    const newMap = new Map<number, RealtimeData>()
    data.forEach(d => newMap.set(d.point_id, d))
    dataMap.value = newMap
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

  // 清空数据 — 替换引用以确保触发响应式更新
  function clearData() {
    dataMap.value = new Map()
    summary.value = null
    lastUpdateTime.value = null
  }

  return {
    dataMap,
    summary,
    lastUpdateTime,
    wsConnected,
    loading,
    realtimeData,
    totalPoints,
    alarmPoints,
    offlinePoints,
    alarmCount,
    offlineCount,
    simpleSummary,
    fetchAllData,
    fetchSummary,
    reload,
    updatePoint,
    updatePoints,
    setAllData,
    setSummary,
    getPointData,
    getDataByType,
    getDataByArea,
    setWsConnected,
    clearData,
  }
})
