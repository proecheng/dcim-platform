/**
 * 节能机会管理 API
 * V2.5 - 整合节能机会、模拟、设备选择、执行管理
 */
import request from '@/utils/request'
import type { ResponseModel, PageParams } from './types'

// ==================== 类型定义 ====================

/** 机会分类 */
export type OpportunityCategory = 1 | 2 | 3 | 4
export const OpportunityCategoryNames: Record<OpportunityCategory, string> = {
  1: '电费结构优化',
  2: '设备运行优化',
  3: '设备改造升级',
  4: '综合能效提升'
}
export const OpportunityCategoryKeys: Record<OpportunityCategory, string> = {
  1: 'bill_optimization',
  2: 'device_operation',
  3: 'equipment_upgrade',
  4: 'comprehensive'
}

/** 机会优先级 */
export type OpportunityPriority = 'high' | 'medium' | 'low'

/** 机会状态 */
export type OpportunityStatus = 'discovered' | 'simulating' | 'ready' | 'executing' | 'completed' | 'dismissed'

/** 节能机会 */
export interface EnergyOpportunity {
  id: number
  category: OpportunityCategory
  title: string
  description?: string
  priority: OpportunityPriority
  status: OpportunityStatus
  potential_saving: number
  confidence: number
  source_plugin?: string
  analysis_data?: Record<string, any>
  discovered_at?: string
  updated_at?: string
  created_at?: string
}

/** 机会措施 */
export interface OpportunityMeasure {
  id: number
  opportunity_id: number
  measure_type: string
  measure_name?: string
  regulation_object?: string
  current_state?: Record<string, any>
  target_state?: Record<string, any>
  execution_mode: 'auto' | 'manual'
  expected_effect?: number
  selected_devices?: number[]
  sort_order: number
  created_at?: string
}

/** 仪表盘汇总卡片 */
export interface DashboardSummaryCards {
  annual_potential_saving: number
  pending_opportunities: number
  executing_plans: number
  monthly_actual_saving: number
}

/** 机会摘要（用于列表和详情面板） */
export interface OpportunitySummary {
  id: number
  category: OpportunityCategory
  title: string
  description?: string
  priority: OpportunityPriority
  potential_saving: number
  confidence: number
  status: OpportunityStatus
  source_plugin?: string
  analysis_data?: Record<string, any>
}

/** 仪表盘响应 */
export interface DashboardResponse {
  summary_cards: DashboardSummaryCards
  opportunities: OpportunitySummary[]
  by_category: Record<string, OpportunitySummary[]>
  total_count: number
}

/** 模拟类型 */
export type SimulationType =
  | 'demand_adjustment'      // 需量调整
  | 'peak_shift'             // 峰谷转移
  | 'power_factor_adjustment' // 功率因数调整
  | 'temperature_adjustment'  // 温度调节
  | 'lighting_control'       // 照明控制
  | 'device_regulation'      // 设备调控
  | 'equipment_upgrade'      // 设备升级
  | 'comprehensive'          // 综合优化

/** 模拟请求 */
export interface SimulationRequest {
  simulation_type: SimulationType
  parameters: Record<string, any>
}

/** 模拟响应 */
export interface SimulationResponse {
  is_feasible: boolean
  current_state: Record<string, any>
  simulated_state: Record<string, any>
  benefit: {
    daily_saving_kwh: number
    daily_saving_yuan: number
    annual_saving_yuan: number
    payback_months?: number
  }
  confidence: number
  warnings: string[]
  recommendations: string[]
}

/** 设备能力 */
export interface DeviceCapability {
  device_id: number
  device_code: string
  device_name: string
  device_type: string
  rated_power: number
  regulations: Array<{
    config_id: number
    regulation_type: string
    current_value?: number
    min_value: number
    max_value: number
    unit?: string
    power_factor?: number
    is_auto: boolean
  }>
  shift_config?: {
    is_shiftable: boolean
    allowed_hours: number[]
    forbidden_hours: number[]
    shiftable_power: number
  }
  total_adjustable_power: number
  execution_mode: 'auto' | 'manual' | 'mixed'
}

/** 设备选择请求 */
export interface DeviceSelectionRequest {
  selected_device_ids: number[]
  target_power?: number
  target_hours?: number
}

/** 设备选择响应 */
export interface DeviceSelectionResponse {
  selected_count: number
  total_adjustable_power: number
  time_intersection: number[]
  is_feasible: boolean
  warnings: string[]
}

// ==================== 执行管理类型 ====================

/** 执行计划 */
export interface ExecutionPlan {
  id: number
  opportunity_id: number
  plan_name: string
  expected_saving: number
  status: 'pending' | 'executing' | 'completed' | 'failed' | 'cancelled'
  started_at?: string
  completed_at?: string
  created_by?: number
  notes?: string
  created_at?: string
  updated_at?: string
}

/** 执行任务 */
export interface ExecutionTask {
  id: number
  plan_id: number
  task_type: string
  task_name: string
  target_object?: string
  execution_mode: 'auto' | 'manual'
  parameters?: Record<string, any>
  status: 'pending' | 'executing' | 'completed' | 'failed' | 'skipped'
  assigned_to?: string
  scheduled_at?: string
  executed_at?: string
  result?: Record<string, any>
  error_message?: string
  sort_order: number
  created_at?: string
}

/** 执行结果/效果追踪 */
export interface ExecutionResult {
  id: number
  plan_id: number
  tracking_period: number
  tracking_start?: string
  tracking_end?: string
  actual_saving: number
  achievement_rate: number
  energy_before?: Record<string, any>
  energy_after?: Record<string, any>
  power_curve_before?: any[]
  power_curve_after?: any[]
  status: 'tracking' | 'completed'
  analysis_conclusion?: string
  created_at?: string
}

/** 计划详情（含任务和追踪结果） */
export interface PlanDetail {
  plan: ExecutionPlan
  opportunity?: {
    id: number
    title: string
    category: OpportunityCategory
    priority: OpportunityPriority
  }
  tasks: ExecutionTask[]
  task_stats: {
    total: number
    pending: number
    executing: number
    completed: number
    failed: number
  }
  auto_task_count: number
  manual_task_count: number
  results: ExecutionResult[]
  progress_percentage: number
}

/** 执行清单 */
export interface ExecutionChecklist {
  title: string
  expected_saving: number
  created_at: string
  sections: Array<{
    title: string
    description: string
    tasks: Array<Record<string, any>>
  }>
  summary: {
    total_tasks: number
    auto_tasks: number
    manual_tasks: number
    completed: number
    progress: number
  }
}

/** 执行统计汇总 */
export interface ExecutionStats {
  plans: {
    total: number
    by_status: Record<string, { count: number; expected_saving: number }>
    total_expected_saving: number
  }
  results: {
    completed_count: number
    total_actual_saving: number
    overall_achievement_rate: number
  }
}

// ==================== API 函数 - 机会管理 ====================

/** 获取机会仪表盘数据 */
export function getOpportunityDashboard() {
  return request.get<ResponseModel<DashboardResponse>>('/v1/opportunities/dashboard')
}

/** 获取机会列表 */
export function getOpportunities(params?: PageParams & {
  category?: OpportunityCategory
  status?: OpportunityStatus
  priority?: OpportunityPriority
}) {
  return request.get<ResponseModel<{ items: EnergyOpportunity[]; total: number }>>('/v1/opportunities', { params })
}

/** 获取机会详情 */
export function getOpportunityDetail(opportunityId: number) {
  return request.get<ResponseModel<EnergyOpportunity & { measures: OpportunityMeasure[] }>>(`/v1/opportunities/${opportunityId}/detail`)
}

/** 创建机会 */
export function createOpportunity(data: Partial<EnergyOpportunity>) {
  return request.post<ResponseModel<EnergyOpportunity>>('/v1/opportunities', data)
}

/** 更新机会 */
export function updateOpportunity(opportunityId: number, data: Partial<EnergyOpportunity>) {
  return request.put<ResponseModel<EnergyOpportunity>>(`/v1/opportunities/${opportunityId}`, data)
}

/** 删除机会 */
export function deleteOpportunity(opportunityId: number) {
  return request.delete<ResponseModel>(`/v1/opportunities/${opportunityId}`)
}

// ==================== API 函数 - 模拟 ====================

/** 模拟参数调整效果 */
export function simulateOpportunity(opportunityId: number, data: SimulationRequest) {
  return request.post<ResponseModel<SimulationResponse>>(`/v1/opportunities/${opportunityId}/simulate`, data)
}

// ==================== API 函数 - 设备选择 ====================

/** 获取可参与设备列表 */
export function getAvailableDevices(opportunityId: number, params?: {
  regulation_type?: string
  execution_mode?: 'auto' | 'manual'
}) {
  return request.get<ResponseModel<{
    opportunity_id: number
    opportunity_title: string
    available_devices: DeviceCapability[]
    device_count: number
    total_adjustable_power: number
  }>>(`/v1/opportunities/${opportunityId}/devices`, { params })
}

/** 选择参与设备并验证 */
export function selectDevices(opportunityId: number, data: DeviceSelectionRequest) {
  return request.post<ResponseModel<DeviceSelectionResponse>>(`/v1/opportunities/${opportunityId}/select-devices`, data)
}

// ==================== API 函数 - 执行 ====================

/** 确认执行机会 */
export function executeOpportunity(opportunityId: number, selectedDeviceIds?: number[]) {
  return request.post<ResponseModel<{
    message: string
    plan_id: number
    task_count: number
    expected_saving: number
    status: string
  }>>(`/v1/opportunities/${opportunityId}/execute`, {
    selected_device_ids: selectedDeviceIds || []
  })
}

// ==================== API 函数 - 执行计划管理 ====================

/** 获取执行计划列表 */
export function getExecutionPlans(params?: PageParams & {
  status?: string
}) {
  return request.get<ResponseModel<{ items: ExecutionPlan[]; total: number }>>('/v1/execution/plans', { params })
}

/** 获取计划详情 */
export function getExecutionPlanDetail(planId: number) {
  return request.get<ResponseModel<PlanDetail>>(`/v1/execution/plans/${planId}`)
}

/** 更新计划状态 */
export function updatePlanStatus(planId: number, data: { status: string; notes?: string }) {
  return request.put<ResponseModel<{ message: string; plan_id: number; old_status: string; new_status: string }>>(
    `/v1/execution/plans/${planId}/status`,
    data
  )
}

/** 获取执行清单 */
export function getExecutionChecklist(planId: number) {
  return request.get<ResponseModel<ExecutionChecklist>>(`/v1/execution/plans/${planId}/checklist`)
}

// ==================== API 函数 - 任务执行 ====================

/** 执行自动任务 */
export function executeAutoTask(taskId: number, force?: boolean) {
  return request.post<ResponseModel<{
    success: boolean
    task_id: number
    status: string
    control_results: any[]
    executed_at: string
  }>>(`/v1/execution/tasks/${taskId}/execute`, { force: force || false })
}

/** 完成手动任务 */
export function completeManualTask(taskId: number, data?: { completed_by?: string; notes?: string }) {
  return request.post<ResponseModel<{
    success: boolean
    task_id: number
    status: string
    executed_at: string
  }>>(`/v1/execution/tasks/${taskId}/complete`, data || {})
}

/** 获取任务详情 */
export function getTaskDetail(taskId: number) {
  return request.get<ResponseModel<ExecutionTask>>(`/v1/execution/tasks/${taskId}`)
}

// ==================== API 函数 - 效果追踪 ====================

/** 获取效果追踪数据 */
export function getTrackingData(planId: number) {
  return request.get<ResponseModel<{
    plan_id: number
    tracking_period: { days: number; start: string; end: string }
    before_execution: { period: string; total_energy_kwh: number; avg_power_kw: number; max_power_kw: number }
    after_execution: { period: string; total_energy_kwh: number; avg_power_kw: number; max_power_kw: number }
    effect: {
      energy_saved_kwh: number
      cost_saved_yuan: number
      expected_annual_saving: number
      actual_annual_saving: number
      achievement_rate: number
    }
    conclusion: string
    status: string
  }>>(`/v1/execution/plans/${planId}/tracking`)
}

/** 创建追踪任务 */
export function createTracking(planId: number, trackingDays?: number) {
  return request.post<ResponseModel<{ message: string; tracking: any }>>(
    `/v1/execution/plans/${planId}/tracking`,
    { tracking_days: trackingDays || 7 }
  )
}

/** 获取追踪结果列表 */
export function getTrackingResults(params?: PageParams & {
  plan_id?: number
  status?: string
}) {
  return request.get<ResponseModel<{ items: ExecutionResult[]; total: number }>>('/v1/execution/results', { params })
}

/** 获取执行统计汇总 */
export function getExecutionStats() {
  return request.get<ResponseModel<ExecutionStats>>('/v1/execution/stats/summary')
}
