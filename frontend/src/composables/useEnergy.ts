/**
 * 用电管理组合式函数
 */
import { ref } from 'vue'
import { useEnergyStore } from '@/stores'
import {
  getRealtimePower,
  getPowerSummary,
  getCurrentPUE,
  getPUETrend,
  getEnergySummary,
  getEnergyTrend,
  getEnergyComparison,
  getSuggestions,
  acceptSuggestion,
  rejectSuggestion,
  completeSuggestion,
  getSavingPotential,
  getDistributionDiagram
} from '@/api/modules/energy'
import type {
  PUETrend,
  EnergyStat,
  EnergyTrend,
  EnergyComparison,
  SavingPotential
} from '@/api/modules/energy'

export function useEnergy() {
  const energyStore = useEnergyStore()

  // 加载状态
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 轮询定时器
  let pollTimer: number | null = null

  // 加载实时电力数据
  async function loadRealtimePower(params?: { device_type?: string; area_code?: string }) {
    try {
      loading.value = true
      error.value = null
      const res = await getRealtimePower(params)
      // res 是 ResponseModel<T>，res.data 是实际数据
      if (res.code === 0 && res.data) {
        energyStore.setAllPowerData(res.data)
      }
    } catch (e: any) {
      error.value = e.message || '加载实时电力数据失败'
      console.error('加载实时电力数据失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 加载电力汇总
  async function loadPowerSummary() {
    try {
      const res = await getPowerSummary()
      if (res.code === 0 && res.data) {
        energyStore.setPowerSummary(res.data)
      }
    } catch (e: any) {
      console.error('加载电力汇总失败:', e)
    }
  }

  // 加载PUE数据
  async function loadPUE() {
    try {
      const res = await getCurrentPUE()
      if (res.code === 0 && res.data) {
        energyStore.setPUEData(res.data)
      }
    } catch (e: any) {
      console.error('加载PUE数据失败:', e)
    }
  }

  // 加载PUE趋势
  async function loadPUETrend(params?: {
    period?: 'hour' | 'day' | 'week' | 'month'
    start_time?: string
    end_time?: string
  }): Promise<PUETrend | null> {
    try {
      const res = await getPUETrend(params)
      if (res.code === 0 && res.data) {
        return res.data
      }
    } catch (e: any) {
      console.error('加载PUE趋势失败:', e)
    }
    return null
  }

  // 加载能耗汇总
  async function loadEnergySummary(params: {
    device_id?: number
    device_type?: string
    area_code?: string
    start_date: string
    end_date: string
  }): Promise<EnergyStat | null> {
    try {
      const res = await getEnergySummary(params)
      if (res.code === 0 && res.data) {
        return res.data
      }
    } catch (e: any) {
      console.error('加载能耗汇总失败:', e)
    }
    return null
  }

  // 加载能耗趋势
  async function loadEnergyTrend(params: {
    device_id?: number
    device_type?: string
    start_date: string
    end_date: string
    granularity?: 'hourly' | 'daily' | 'monthly'
  }): Promise<EnergyTrend | null> {
    try {
      const res = await getEnergyTrend(params)
      if (res.code === 0 && res.data) {
        return res.data
      }
    } catch (e: any) {
      console.error('加载能耗趋势失败:', e)
    }
    return null
  }

  // 加载能耗对比
  async function loadEnergyComparison(params: {
    device_id?: number
    comparison_type?: 'mom' | 'yoy'
    period?: 'day' | 'week' | 'month'
  }): Promise<EnergyComparison | null> {
    try {
      const res = await getEnergyComparison(params)
      if (res.code === 0 && res.data) {
        return res.data
      }
    } catch (e: any) {
      console.error('加载能耗对比失败:', e)
    }
    return null
  }

  // 加载节能建议
  async function loadSuggestions(params?: {
    status?: string
    priority?: string
    page?: number
    page_size?: number
  }) {
    try {
      const res = await getSuggestions(params)
      if (res.code === 0 && res.data) {
        energyStore.setSuggestions(res.data)
      }
    } catch (e: any) {
      console.error('加载节能建议失败:', e)
    }
  }

  // 接受建议
  async function handleAcceptSuggestion(suggestionId: number, remark?: string): Promise<boolean> {
    try {
      const res = await acceptSuggestion(suggestionId, { remark })
      if (res.code === 0) {
        energyStore.updateSuggestionStatus(suggestionId, 'accepted', {
          accepted_at: new Date().toISOString(),
          remark
        })
        return true
      }
    } catch (e: any) {
      console.error('接受建议失败:', e)
    }
    return false
  }

  // 拒绝建议
  async function handleRejectSuggestion(suggestionId: number, remark: string): Promise<boolean> {
    try {
      const res = await rejectSuggestion(suggestionId, { remark })
      if (res.code === 0) {
        energyStore.updateSuggestionStatus(suggestionId, 'rejected', { remark })
        return true
      }
    } catch (e: any) {
      console.error('拒绝建议失败:', e)
    }
    return false
  }

  // 完成建议
  async function handleCompleteSuggestion(
    suggestionId: number,
    actualSaving?: number,
    remark?: string
  ): Promise<boolean> {
    try {
      const res = await completeSuggestion(suggestionId, {
        actual_saving: actualSaving,
        remark
      })
      if (res.code === 0) {
        energyStore.updateSuggestionStatus(suggestionId, 'completed', {
          completed_at: new Date().toISOString(),
          actual_saving: actualSaving,
          remark
        })
        return true
      }
    } catch (e: any) {
      console.error('完成建议失败:', e)
    }
    return false
  }

  // 加载节能潜力
  async function loadSavingPotential(): Promise<SavingPotential | null> {
    try {
      const res = await getSavingPotential()
      if (res.code === 0 && res.data) {
        return res.data
      }
    } catch (e: any) {
      console.error('加载节能潜力失败:', e)
    }
    return null
  }

  // 加载配电图
  async function loadDistributionDiagram() {
    try {
      const res = await getDistributionDiagram()
      if (res.code === 0 && res.data) {
        energyStore.setDistributionDiagram(res.data)
      }
    } catch (e: any) {
      console.error('加载配电图失败:', e)
    }
  }

  // 加载所有数据
  async function loadAllData() {
    await Promise.all([
      loadRealtimePower(),
      loadPowerSummary(),
      loadPUE(),
      loadSuggestions({ status: 'pending' })
    ])
  }

  // 开始轮询
  function startPolling(interval = 5000) {
    stopPolling()
    pollTimer = window.setInterval(() => {
      loadRealtimePower()
      loadPowerSummary()
      loadPUE()
    }, interval)
  }

  // 停止轮询
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // 格式化功率显示
  function formatPower(power: number | undefined | null): string {
    if (power === undefined || power === null) return '-'
    if (power >= 1000) {
      return `${(power / 1000).toFixed(2)} MW`
    }
    return `${power.toFixed(2)} kW`
  }

  // 格式化电量显示
  function formatEnergy(energy: number | undefined | null): string {
    if (energy === undefined || energy === null) return '-'
    if (energy >= 1000000) {
      return `${(energy / 1000000).toFixed(2)} GWh`
    }
    if (energy >= 1000) {
      return `${(energy / 1000).toFixed(2)} MWh`
    }
    return `${energy.toFixed(2)} kWh`
  }

  // 格式化电费显示
  function formatCost(cost: number | undefined | null): string {
    if (cost === undefined || cost === null) return '-'
    if (cost >= 10000) {
      return `${(cost / 10000).toFixed(2)} 万元`
    }
    return `${cost.toFixed(2)} 元`
  }

  // 格式化PUE显示
  function formatPUE(pue: number | undefined | null): string {
    if (pue === undefined || pue === null) return '-'
    return pue.toFixed(3)
  }

  // 获取PUE等级
  function getPUELevel(pue: number): { level: string; color: string } {
    if (pue <= 1.4) return { level: '优秀', color: '#67C23A' }
    if (pue <= 1.6) return { level: '良好', color: '#409EFF' }
    if (pue <= 1.8) return { level: '一般', color: '#E6A23C' }
    return { level: '较差', color: '#F56C6C' }
  }

  // 获取负载率状态
  function getLoadRateStatus(rate: number): { status: string; color: string } {
    if (rate < 30) return { status: '低负载', color: '#909399' }
    if (rate < 60) return { status: '正常', color: '#67C23A' }
    if (rate < 80) return { status: '较高', color: '#E6A23C' }
    return { status: '高负载', color: '#F56C6C' }
  }

  return {
    // 状态
    loading,
    error,

    // Store
    energyStore,

    // 数据加载
    loadRealtimePower,
    loadPowerSummary,
    loadPUE,
    loadPUETrend,
    loadEnergySummary,
    loadEnergyTrend,
    loadEnergyComparison,
    loadSuggestions,
    loadSavingPotential,
    loadDistributionDiagram,
    loadAllData,

    // 建议操作
    handleAcceptSuggestion,
    handleRejectSuggestion,
    handleCompleteSuggestion,

    // 轮询控制
    startPolling,
    stopPolling,

    // 格式化
    formatPower,
    formatEnergy,
    formatCost,
    formatPUE,
    getPUELevel,
    getLoadRateStatus
  }
}
