/**
 * 节能机会状态管理
 * V2.5 - 管理机会列表、执行计划、模拟结果
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DashboardResponse,
  EnergyOpportunity,
  OpportunityMeasure,
  OpportunitySummary,
  SimulationResponse,
  DeviceCapability,
  ExecutionPlan,
  ExecutionTask,
  ExecutionResult,
  PlanDetail,
  ExecutionStats,
  OpportunityCategory
} from '@/api/modules/opportunities'
import {
  getOpportunityDashboard,
  getOpportunities,
  getOpportunityDetail,
  getExecutionPlans,
  getExecutionPlanDetail,
  getExecutionStats,
  getAvailableDevices,
  OpportunityCategoryNames,
  OpportunityCategoryKeys
} from '@/api/modules/opportunities'

export const useOpportunityStore = defineStore('opportunity', () => {
  // ==================== 状态 ====================

  // 仪表盘数据
  const dashboard = ref<DashboardResponse | null>(null)
  const dashboardLoading = ref(false)

  // 机会列表
  const opportunities = ref<EnergyOpportunity[]>([])
  const opportunitiesTotal = ref(0)
  const opportunitiesLoading = ref(false)

  // 当前选中的机会
  const currentOpportunity = ref<(EnergyOpportunity & { measures: OpportunityMeasure[] }) | null>(null)
  const currentOpportunityLoading = ref(false)

  // 模拟结果
  const simulationResult = ref<SimulationResponse | null>(null)
  const simulationLoading = ref(false)

  // 可选设备列表
  const availableDevices = ref<DeviceCapability[]>([])
  const selectedDeviceIds = ref<number[]>([])
  const devicesLoading = ref(false)

  // 执行计划
  const executionPlans = ref<ExecutionPlan[]>([])
  const plansTotal = ref(0)
  const plansLoading = ref(false)

  // 当前计划详情
  const currentPlan = ref<PlanDetail | null>(null)
  const currentPlanLoading = ref(false)

  // 执行统计
  const executionStats = ref<ExecutionStats | null>(null)

  // 最后更新时间
  const lastUpdateTime = ref<Date | null>(null)

  // ==================== 计算属性 ====================

  // 待处理机会数量
  const pendingCount = computed(() =>
    dashboard.value?.summary_cards.pending_opportunities ?? 0
  )

  // 执行中计划数量
  const executingCount = computed(() =>
    dashboard.value?.summary_cards.executing_plans ?? 0
  )

  // 年度潜在节省
  const annualPotentialSaving = computed(() =>
    dashboard.value?.summary_cards.annual_potential_saving ?? 0
  )

  // 月度实际节省
  const monthlyActualSaving = computed(() =>
    dashboard.value?.summary_cards.monthly_actual_saving ?? 0
  )

  // 按分类分组的机会
  const opportunitiesByCategory = computed(() =>
    dashboard.value?.by_category ?? {}
  )

  // 高优先级机会
  const highPriorityOpportunities = computed(() =>
    dashboard.value?.opportunities.filter(o => o.priority === 'high') ?? []
  )

  // 选中设备的总可调功率
  const totalSelectedPower = computed(() => {
    return availableDevices.value
      .filter(d => selectedDeviceIds.value.includes(d.device_id))
      .reduce((sum, d) => sum + d.total_adjustable_power, 0)
  })

  // 当前计划进度
  const currentPlanProgress = computed(() =>
    currentPlan.value?.progress_percentage ?? 0
  )

  // ==================== 方法 ====================

  // 加载仪表盘数据
  async function loadDashboard() {
    dashboardLoading.value = true
    try {
      const res = await getOpportunityDashboard()
      if (res.code === 0 && res.data) {
        dashboard.value = res.data
        lastUpdateTime.value = new Date()
      }
    } catch (e) {
      console.error('加载仪表盘失败', e)
    } finally {
      dashboardLoading.value = false
    }
  }

  // 加载机会列表
  async function loadOpportunities(params?: {
    category?: OpportunityCategory
    status?: string
    priority?: string
    skip?: number
    limit?: number
  }) {
    opportunitiesLoading.value = true
    try {
      const res = await getOpportunities(params as any)
      if (res.code === 0 && res.data) {
        opportunities.value = res.data.items
        opportunitiesTotal.value = res.data.total
      }
    } catch (e) {
      console.error('加载机会列表失败', e)
    } finally {
      opportunitiesLoading.value = false
    }
  }

  // 加载机会详情
  async function loadOpportunityDetail(opportunityId: number) {
    currentOpportunityLoading.value = true
    try {
      const res = await getOpportunityDetail(opportunityId)
      if (res.code === 0 && res.data) {
        currentOpportunity.value = res.data
      }
    } catch (e) {
      console.error('加载机会详情失败', e)
    } finally {
      currentOpportunityLoading.value = false
    }
  }

  // 加载可选设备
  async function loadAvailableDevices(opportunityId: number, params?: {
    regulation_type?: string
    execution_mode?: 'auto' | 'manual'
  }) {
    devicesLoading.value = true
    try {
      const res = await getAvailableDevices(opportunityId, params)
      if (res.code === 0 && res.data) {
        availableDevices.value = res.data.available_devices
      }
    } catch (e) {
      console.error('加载可选设备失败', e)
    } finally {
      devicesLoading.value = false
    }
  }

  // 设置模拟结果
  function setSimulationResult(result: SimulationResponse | null) {
    simulationResult.value = result
  }

  // 选择/取消选择设备
  function toggleDeviceSelection(deviceId: number) {
    const idx = selectedDeviceIds.value.indexOf(deviceId)
    if (idx >= 0) {
      selectedDeviceIds.value.splice(idx, 1)
    } else {
      selectedDeviceIds.value.push(deviceId)
    }
  }

  // 全选/取消全选设备
  function selectAllDevices(select: boolean) {
    if (select) {
      selectedDeviceIds.value = availableDevices.value.map(d => d.device_id)
    } else {
      selectedDeviceIds.value = []
    }
  }

  // 加载执行计划列表
  async function loadExecutionPlans(params?: {
    status?: string
    skip?: number
    limit?: number
  }) {
    plansLoading.value = true
    try {
      const res = await getExecutionPlans(params)
      if (res.code === 0 && res.data) {
        executionPlans.value = res.data.items
        plansTotal.value = res.data.total
      }
    } catch (e) {
      console.error('加载执行计划失败', e)
    } finally {
      plansLoading.value = false
    }
  }

  // 加载计划详情
  async function loadPlanDetail(planId: number) {
    currentPlanLoading.value = true
    try {
      const res = await getExecutionPlanDetail(planId)
      if (res.code === 0 && res.data) {
        currentPlan.value = res.data
      }
    } catch (e) {
      console.error('加载计划详情失败', e)
    } finally {
      currentPlanLoading.value = false
    }
  }

  // 加载执行统计
  async function loadExecutionStats() {
    try {
      const res = await getExecutionStats()
      if (res.code === 0 && res.data) {
        executionStats.value = res.data
      }
    } catch (e) {
      console.error('加载执行统计失败', e)
    }
  }

  // 更新任务状态
  function updateTaskStatus(taskId: number, status: string, result?: any) {
    if (currentPlan.value) {
      const task = currentPlan.value.tasks.find(t => t.id === taskId)
      if (task) {
        task.status = status as any
        if (result) {
          task.result = result
        }
        // 重新计算统计
        const stats = currentPlan.value.task_stats
        stats.pending = currentPlan.value.tasks.filter(t => t.status === 'pending').length
        stats.executing = currentPlan.value.tasks.filter(t => t.status === 'executing').length
        stats.completed = currentPlan.value.tasks.filter(t => t.status === 'completed').length
        stats.failed = currentPlan.value.tasks.filter(t => t.status === 'failed').length
        currentPlan.value.progress_percentage = Math.round(
          stats.completed / stats.total * 100
        )
      }
    }
  }

  // 获取分类名称
  function getCategoryName(category: OpportunityCategory): string {
    return OpportunityCategoryNames[category] || '未知分类'
  }

  // 获取分类Key
  function getCategoryKey(category: OpportunityCategory): string {
    return OpportunityCategoryKeys[category] || 'unknown'
  }

  // 清空数据
  function clearData() {
    dashboard.value = null
    opportunities.value = []
    currentOpportunity.value = null
    simulationResult.value = null
    availableDevices.value = []
    selectedDeviceIds.value = []
    executionPlans.value = []
    currentPlan.value = null
    executionStats.value = null
    lastUpdateTime.value = null
  }

  // 清空当前选择
  function clearCurrentSelection() {
    currentOpportunity.value = null
    simulationResult.value = null
    availableDevices.value = []
    selectedDeviceIds.value = []
    currentPlan.value = null
  }

  return {
    // 状态
    dashboard,
    dashboardLoading,
    opportunities,
    opportunitiesTotal,
    opportunitiesLoading,
    currentOpportunity,
    currentOpportunityLoading,
    simulationResult,
    simulationLoading,
    availableDevices,
    selectedDeviceIds,
    devicesLoading,
    executionPlans,
    plansTotal,
    plansLoading,
    currentPlan,
    currentPlanLoading,
    executionStats,
    lastUpdateTime,

    // 计算属性
    pendingCount,
    executingCount,
    annualPotentialSaving,
    monthlyActualSaving,
    opportunitiesByCategory,
    highPriorityOpportunities,
    totalSelectedPower,
    currentPlanProgress,

    // 方法
    loadDashboard,
    loadOpportunities,
    loadOpportunityDetail,
    loadAvailableDevices,
    setSimulationResult,
    toggleDeviceSelection,
    selectAllDevices,
    loadExecutionPlans,
    loadPlanDetail,
    loadExecutionStats,
    updateTaskStatus,
    getCategoryName,
    getCategoryKey,
    clearData,
    clearCurrentSelection
  }
})
