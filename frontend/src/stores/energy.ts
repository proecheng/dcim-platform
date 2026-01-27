/**
 * 用电管理状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

  // 批量更新电力数据
  function updatePowerDataBatch(dataList: RealtimePowerData[]) {
    dataList.forEach(data => {
      realtimePowerData.value.set(data.device_id, data)
    })
    lastUpdateTime.value = new Date()
  }

  // 设置全部电力数据
  function setAllPowerData(dataList: RealtimePowerData[]) {
    realtimePowerData.value.clear()
    dataList.forEach(data => {
      realtimePowerData.value.set(data.device_id, data)
    })
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

  // 清空数据
  function clearData() {
    realtimePowerData.value.clear()
    powerSummary.value = null
    pueData.value = null
    suggestions.value = []
    distributionDiagram.value = null
    lastUpdateTime.value = null
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
    clearData
  }
})
