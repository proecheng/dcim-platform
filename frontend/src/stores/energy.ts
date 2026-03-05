/**
 * 用电管理状态管理
 *
 * Story 27.3: 能源数据 SSOT (Single Source of Truth)
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getRealtimePower,
  getPowerSummary,
  getCurrentPUE,
} from '@/api/modules/energy'
import type {
  RealtimePowerData,
  RealtimePowerSummary,
  PUEData,
  EnergySuggestion,
  DistributionDiagram
} from '@/api/modules/energy'

export const useEnergyStore = defineStore('energy', () => {
  // 实时电力数据
  const realtimePowerData = ref<Map<number, RealtimePowerData>>(new Map())

  // 电力汇总
  const powerSummary = ref<RealtimePowerSummary | null>(null)

  // PUE数据
  const pueData = ref<PUEData | null>(null)

  // 节能建议
  const suggestions = ref<EnergySuggestion[]>([])
  const pendingSuggestions = computed(() =>
    suggestions.value.filter(s => s.status === 'pending')
  )

  // 配电图
  const distributionDiagram = ref<DistributionDiagram | null>(null)

  // 最后更新时间
  const lastUpdateTime = ref<Date | null>(null)

  // WebSocket连接状态
  const wsConnected = ref(false)

  // 加载状态（防重入）
  const loading = ref(false)

  // 计算属性
  const powerDataList = computed(() => Array.from(realtimePowerData.value.values()))

  const currentPUE = computed(() => pueData.value?.current_pue ?? 0)

  const totalPower = computed(() => powerSummary.value?.total_power ?? 0)

  const itPower = computed(() => powerSummary.value?.it_power ?? 0)

  const coolingPower = computed(() => powerSummary.value?.cooling_power ?? 0)

  const todayEnergy = computed(() => powerSummary.value?.today_energy ?? 0)

  const todayCost = computed(() => powerSummary.value?.today_cost ?? 0)

  const monthEnergy = computed(() => powerSummary.value?.month_energy ?? 0)

  const monthCost = computed(() => powerSummary.value?.month_cost ?? 0)

  const pendingCount = computed(() => pendingSuggestions.value.length)

  const highPrioritySuggestions = computed(() =>
    pendingSuggestions.value.filter(s => s.priority === 'high')
  )

  // 更新单个设备电力数据
  function updatePowerData(data: RealtimePowerData) {
    realtimePowerData.value.set(data.device_id, data)
    lastUpdateTime.value = new Date()
  }

  // 批量更新电力数据 — 单次替换减少 N 次响应触发
  function updatePowerDataBatch(dataList: RealtimePowerData[]) {
    const newMap = new Map(realtimePowerData.value)
    dataList.forEach(data => newMap.set(data.device_id, data))
    realtimePowerData.value = newMap
    lastUpdateTime.value = new Date()
  }

  // 设置全部电力数据 — new Map + 单次赋值，避免 clear-before-fill 数据空白
  function setAllPowerData(dataList: RealtimePowerData[]) {
    const newMap = new Map<number, RealtimePowerData>()
    dataList.forEach(data => newMap.set(data.device_id, data))
    realtimePowerData.value = newMap
    lastUpdateTime.value = new Date()
  }

  // 设置电力汇总
  function setPowerSummary(data: RealtimePowerSummary) {
    powerSummary.value = data
  }

  // 设置PUE数据
  function setPUEData(data: PUEData) {
    pueData.value = data
  }

  // 设置节能建议
  function setSuggestions(data: EnergySuggestion[]) {
    suggestions.value = data
  }

  // 添加节能建议
  function addSuggestion(suggestion: EnergySuggestion) {
    const index = suggestions.value.findIndex(s => s.id === suggestion.id)
    if (index >= 0) {
      suggestions.value[index] = suggestion
    } else {
      suggestions.value.unshift(suggestion)
    }
  }

  // 更新建议状态
  function updateSuggestionStatus(
    suggestionId: number,
    status: EnergySuggestion['status'],
    updates?: Partial<EnergySuggestion>
  ) {
    const suggestion = suggestions.value.find(s => s.id === suggestionId)
    if (suggestion) {
      suggestion.status = status
      if (updates) {
        Object.assign(suggestion, updates)
      }
    }
  }

  // 设置配电图数据
  function setDistributionDiagram(data: DistributionDiagram) {
    distributionDiagram.value = data
  }

  // 获取设备电力数据
  function getDevicePower(deviceId: number): RealtimePowerData | undefined {
    return realtimePowerData.value.get(deviceId)
  }

  // 按设备类型获取数据
  function getPowerByType(deviceType: string): RealtimePowerData[] {
    return powerDataList.value.filter(d => d.device_type === deviceType)
  }

  // 设置WebSocket连接状态
  function setWsConnected(connected: boolean) {
    wsConnected.value = connected
  }

  // 清空数据 — 替换引用以确保触发响应式更新
  function clearData() {
    realtimePowerData.value = new Map()
    powerSummary.value = null
    pueData.value = null
    suggestions.value = []
    distributionDiagram.value = null
    lastUpdateTime.value = null
  }

  // 重新加载数据（带防重入锁，返回 false 表示被跳过）
  async function reload(): Promise<boolean> {
    if (loading.value) return false
    loading.value = true
    try {
      const [powerRes, summaryRes, pueRes] = await Promise.allSettled([
        getRealtimePower(),
        getPowerSummary(),
        getCurrentPUE(),
      ])
      let anySuccess = false
      if (powerRes.status === 'fulfilled') {
        const res = powerRes.value as any
        if (res.code === 0 && res.data) {
          setAllPowerData(res.data)
          anySuccess = true
        }
      }
      if (summaryRes.status === 'fulfilled') {
        const res = summaryRes.value as any
        if (res.code === 0 && res.data) {
          setPowerSummary(res.data)
          anySuccess = true
        }
      }
      if (pueRes.status === 'fulfilled') {
        const res = pueRes.value as any
        if (res.code === 0 && res.data) {
          setPUEData(res.data)
          anySuccess = true
        }
      }
      if (anySuccess) {
        lastUpdateTime.value = new Date()
      }
      return true
    } catch {
      return true
    } finally {
      loading.value = false
    }
  }

  return {
    // 状态
    realtimePowerData,
    powerSummary,
    pueData,
    suggestions,
    pendingSuggestions,
    distributionDiagram,
    lastUpdateTime,
    wsConnected,
    loading,

    // 计算属性
    powerDataList,
    currentPUE,
    totalPower,
    itPower,
    coolingPower,
    todayEnergy,
    todayCost,
    monthEnergy,
    monthCost,
    pendingCount,
    highPrioritySuggestions,

    // 方法
    updatePowerData,
    updatePowerDataBatch,
    setAllPowerData,
    setPowerSummary,
    setPUEData,
    setSuggestions,
    addSuggestion,
    updateSuggestionStatus,
    setDistributionDiagram,
    getDevicePower,
    getPowerByType,
    setWsConnected,
    clearData,
    reload
  }
})
