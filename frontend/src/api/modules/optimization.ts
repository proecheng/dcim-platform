/**
 * 日前调度优化 API
 * 负荷预测、优化计算、调度计划管理
 */
import request from '@/utils/request'
import type { ResponseModel } from './types'

// ==================== 类型定义 ====================

/** 预测数据点 */
export interface ForecastPoint {
  time_slot: number
  time: string
  hour: number
  quarter: number
  predicted_power: number
  lower_bound: number
  upper_bound: number
  period: string
  rigid_load?: number
  shiftable_load?: number
  total_load?: number
}

/** 预测统计信息 */
export interface ForecastStatistics {
  max_power: number
  min_power: number
  avg_power: number
  total_energy: number
}

/** 时段汇总 */
export interface PeriodSummary {
  energy: number
  max_power: number
  hours: number
}

/** 负荷预测结果 */
export interface ForecastResult {
  date: string
  is_weekend: boolean
  seasonal_factor: number
  adjustment_factor: number
  forecasts: ForecastPoint[]
  statistics: ForecastStatistics
  period_summary: Record<string, PeriodSummary>
}

/** 成本分解 */
export interface CostBreakdown {
  energy_cost: number
  demand_cost: number
  total_cost: number
  storage_benefit?: number
  storage_cost?: number
  storage_net?: number
}

/** 储能调度点 */
export interface StorageSchedulePoint {
  time_slot: number
  hour: number
  minute: number
  charge_power: number
  discharge_power: number
  soc: number
  period: string
}

/** 设备调度动作 */
export interface DeviceAction {
  time_slot: number
  hour: number
  minute: number
  action: string
  power?: number
  curtail_ratio?: number
  power_reduction?: number
}

/** 设备调度计划 */
export interface DeviceSchedule {
  device_id: number
  device_name: string
  device_type: string
  actions: DeviceAction[]
}

/** 优化结果 */
export interface OptimizationResult {
  status: string
  solve_status: string
  optimal_value: number
  max_demand: number
  demand_target: number
  schedule: DeviceSchedule[]
  storage_schedule: StorageSchedulePoint[]
  cost_breakdown: CostBreakdown
  baseline_cost: number
  expected_saving: number
  saving_ratio: number
  forecast_date?: string
  base_load_summary?: ForecastStatistics
}

/** 日前调度完整结果 */
export interface DayAheadResult {
  date: string
  forecast: ForecastResult
  optimization: OptimizationResult
  status: 'saved' | 'generated'
}

/** 优化汇总 */
export interface OptimizationSummary {
  month: string
  total_saving: number
  peak_valley_saving: number
  demand_saving: number
  storage_cycles: number
  execution_rate: number
  schedule_count: number
  executed_count: number
  skipped_count: number
}

/** 计划vs实际对比 */
export interface PlanActualComparison {
  date: string
  planned_load: number[]
  actual_load: number[]
  deviation: {
    mean_absolute_error: number
    mean_percentage_error: number
    max_deviation: number
  }
  cost_comparison: {
    planned_cost: number
    actual_cost: number
  }
}

/** 优化请求参数 */
export interface OptimizationParams {
  target_date?: string
  demand_target?: number
  demand_price?: number
  declared_demand?: number
  period_prices?: Record<string, number>
  use_storage?: boolean
  storage_capacity?: number
  storage_charge_power?: number
  storage_discharge_power?: number
  storage_initial_soc?: number
}

// ==================== API 函数 ====================

/** 获取负荷预测 */
export function getLoadForecast(params?: {
  target_date?: string
  meter_point_id?: number
  base_load?: number
  peak_load?: number
}) {
  return request.get<ResponseModel<ForecastResult>>('/v1/optimization/forecast', { params })
}

/** 执行日前优化 */
export function runDayAheadOptimization(data: OptimizationParams) {
  return request.post<ResponseModel<OptimizationResult>>('/v1/optimization/day-ahead', data)
}

/** 获取日前调度计划 */
export function getDayAheadSchedule(date: string) {
  return request.get<ResponseModel<DayAheadResult>>(`/v1/optimization/day-ahead/${date}`)
}

/** 更新调度状态 */
export function updateScheduleStatus(scheduleId: number, data: { status: string; notes?: string }) {
  return request.put<ResponseModel<any>>(`/v1/optimization/schedule/${scheduleId}`, data)
}

/** 获取优化汇总 */
export function getOptimizationSummary(month?: string) {
  return request.get<ResponseModel<OptimizationSummary>>('/v1/optimization/summary', {
    params: month ? { month } : undefined
  })
}

/** 获取计划vs实际对比 */
export function getPlanActualComparison(date: string) {
  return request.get<ResponseModel<PlanActualComparison>>('/v1/optimization/compare', {
    params: { date }
  })
}

// ==================== 学习指标 API ====================

/** 学习指标 */
export interface LearningMetrics {
  period: string
  total_records: number
  mae: number
  mape: number
  rmse: number
  bias: number
  max_deviation: number
  accuracy_rate: number
}

/** 优化效果报告 */
export interface OptimizationReport {
  period: string
  start_date: string
  end_date: string
  cost_analysis: {
    planned_saving: number
    actual_saving: number
    saving_achievement: number
  }
  execution_stats: {
    total_schedules: number
    executed_schedules: number
    success_rate: number
  }
  demand_control: {
    violations: number
    max_reached: number
    target: number
    utilization: number
  }
  forecast_quality: {
    mae: number
    mape: number
    accuracy_rate: number
    bias: number
  }
  recommendations: string[]
}

/** 获取学习指标 */
export function getLearningMetrics(params?: {
  start_date?: string
  end_date?: string
}) {
  return request.get<ResponseModel<LearningMetrics>>('/v1/optimization/learning/metrics', { params })
}

/** 执行参数调整 */
export function runParameterAdjustment() {
  return request.post<ResponseModel<{
    adjusted_params: Record<string, number>
    history_count: number
  }>>('/v1/optimization/learning/adjust')
}

/** 获取优化效果报告 */
export function getOptimizationReport(month?: string) {
  return request.get<ResponseModel<OptimizationReport>>('/v1/optimization/learning/report', {
    params: month ? { month } : undefined
  })
}

/** 提交反馈数据 */
export function submitFeedbackData(params: {
  planned: number
  actual: number
  timestamp?: string
  source?: string
}) {
  return request.post<ResponseModel<any>>('/v1/optimization/learning/feedback', null, { params })
}

// ==================== 辅助函数 ====================

/** 获取时段颜色 */
export function getPeriodColor(period: string): string {
  const colors: Record<string, string> = {
    sharp: '#722ed1',
    peak: '#f5222d',
    flat: '#faad14',
    valley: '#52c41a',
    deep_valley: '#1890ff',
  }
  return colors[period] || '#1890ff'
}

/** 获取时段名称 */
export function getPeriodName(period: string): string {
  const names: Record<string, string> = {
    sharp: '尖峰',
    peak: '峰时',
    flat: '平时',
    valley: '谷时',
    deep_valley: '深谷',
  }
  return names[period] || period
}
